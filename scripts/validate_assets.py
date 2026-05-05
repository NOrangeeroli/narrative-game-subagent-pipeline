#!/usr/bin/env python3
"""Validate generated assets against asset-manifest.json."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import wave
from pathlib import Path

from pipeline_lib import Json, as_list, load_optional_json, load_yarn_fragments, path_for, write_json


MAX_SFX_DURATION_SECONDS = 2.35
VALID_ASSET_PREFIXES = {
    "bg",
    "cg",
    "portrait",
    "bgm",
    "sfx",
    "voice",
    "ui",
    "enemy",
    "prop",
    "hotspot",
    "symbol",
    "effect",
    "icon",
    "map",
}


def looks_like_asset_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if not re.match(r"^[a-z][a-z0-9_-]*\.", value.strip()):
        return False
    return value.split(".", 1)[0] in VALID_ASSET_PREFIXES


def command_args_from_yarn_line(line: str) -> Json | None:
    stripped = line.strip()
    if not (stripped.startswith("<<") and stripped.endswith(">>")):
        return None
    body = stripped[2:-2].strip()
    if not body:
        return None
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    if not tokens:
        return None
    command = tokens[0]
    args: Json = {}
    positional: list[str] = []
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            args[key] = value.strip().strip('"').strip("'")
        else:
            positional.append(token.strip().strip('"').strip("'"))
    if positional:
        if command in {"show_bg", "show_cg", "play_bgm", "play_sfx"}:
            args.setdefault("asset_id", positional[0])
        elif command == "show_char":
            args.setdefault("character_id", positional[0])
            if len(positional) > 1:
                args.setdefault("asset_id", positional[1])
        elif command == "set_expression":
            args.setdefault("character_id", positional[0])
            if len(positional) > 1:
                args.setdefault("expression_asset_id", positional[1])
    return {"command": command, "args": args}


def command_refs_from_yarn_text(text: str) -> list[Json]:
    refs: list[Json] = []
    for line in text.splitlines():
        parsed = command_args_from_yarn_line(line)
        if parsed:
            refs.append(parsed)
    return refs


def scheduled_asset_refs(run_root: Path) -> tuple[list[Json], list[str]]:
    refs: list[Json] = []
    warnings: list[str] = []
    expected_by_command = {
        "show_bg": "background",
        "show_cg": "cg",
        "show_char": "portrait",
        "set_expression": "portrait",
        "play_bgm": "bgm",
        "play_sfx": "sfx",
    }
    for fragment in load_yarn_fragments(run_root):
        node_id = str(fragment.get("node_id") or "")
        manifest = fragment.get("manifest") if isinstance(fragment.get("manifest"), dict) else {}
        command_refs = [ref for ref in as_list(manifest.get("command_refs")) if isinstance(ref, dict)]
        command_refs.extend(command_refs_from_yarn_text(str(fragment.get("yarn_text") or "")))
        has_background = False
        has_music = False
        has_character_staging = False
        for command_ref in command_refs:
            command = str(command_ref.get("command") or "")
            args = command_ref.get("args") if isinstance(command_ref.get("args"), dict) else {}
            asset_id = ""
            if command in {"show_bg", "show_cg", "play_bgm", "play_sfx"}:
                asset_id = str(args.get("asset_id") or "")
            elif command == "show_char":
                asset_id = str(args.get("asset_id") or "")
            elif command == "set_expression":
                asset_id = str(args.get("expression_asset_id") or args.get("asset_id") or "")
            if command == "show_bg":
                has_background = True
            if command == "play_bgm":
                has_music = True
            if command in {"show_char", "set_expression", "hide_char"}:
                has_character_staging = True
            if asset_id:
                refs.append({
                    "source_node_id": node_id,
                    "asset_id": asset_id,
                    "command": command,
                    "expected_kind": expected_by_command.get(command),
                })
        for asset_id in as_list(manifest.get("local_asset_refs")):
            if isinstance(asset_id, str) and asset_id:
                refs.append({
                    "source_node_id": node_id,
                    "asset_id": asset_id,
                    "command": "local_asset_refs",
                    "expected_kind": None,
                })
        if not has_background:
            warnings.append(f"VN fragment {node_id} has no show_bg cue.")
        if not has_music:
            warnings.append(f"VN fragment {node_id} has no play_bgm cue.")
        if not has_character_staging:
            warnings.append(f"VN fragment {node_id} has no character staging cue.")
    return refs, warnings


def manifest_asset_kinds(manifest: Json) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str):
            kinds[background["asset_id"]] = "background"
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str):
            kinds[cg["asset_id"]] = "cg"
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str):
            kinds[ui_asset["asset_id"]] = str(ui_asset.get("kind") or "ui")
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict) and isinstance(portrait.get("asset_id"), str):
                kinds[portrait["asset_id"]] = "portrait"
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict) and isinstance(audio.get("asset_id"), str):
            kinds[audio["asset_id"]] = str(audio.get("kind") or "audio")
    return kinds


def identify(path: Path) -> dict[str, str] | None:
    try:
        output = subprocess.check_output(
            ["magick", "identify", "-format", "%w %h %[channels]", str(path)],
            text=True,
        )
    except Exception:
        return None
    width, height, channels = output.strip().split(" ", 2)
    return {"width": width, "height": height, "channels": channels}


def has_transparency(path: Path) -> bool:
    metadata = identify(path)
    if not metadata or "a" not in metadata["channels"].lower():
        return False
    try:
        minimum = subprocess.check_output(
            ["magick", str(path), "-channel", "A", "-separate", "-format", "%[min]", "info:"],
            text=True,
        ).strip()
        return int(float(minimum)) < 65535
    except Exception:
        return False


def wav_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / float(audio.getframerate())
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return None


def validate_assets(run_root: Path) -> Json:
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not manifest:
        report = {"status": "skipped", "issues": [], "warnings": ["Missing workspace/asset-manifest.json."]}
        write_json(path_for(run_root, "asset_validation_report"), report)
        return report
    output_root = run_root / "workspace" / "generated-assets"
    issues: list[Json] = []
    warnings: list[str] = []

    def check_file(asset_id: str, file_ref: str, role: str, require_transparency: bool = False) -> None:
        path = output_root / file_ref
        if not path.exists():
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "missing_file", "message": "Manifest file_ref was not generated."})
            return
        info = identify(path)
        if not info:
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "not_inspectable", "message": "ImageMagick could not inspect generated image."})
            return
        if require_transparency and not has_transparency(path):
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "portrait_missing_transparency", "message": "Portrait output is not transparent."})
        if role == "background" and (int(info["width"]) < 640 or int(info["height"]) < 360):
            warnings.append(f"Background {asset_id} is small: {info['width']}x{info['height']}.")

    def check_audio_file(asset_id: str, file_ref: str, audio: Json | None = None) -> None:
        kind = str((audio or {}).get("kind") or "").lower()
        spec = (audio or {}).get("spec") if isinstance((audio or {}).get("spec"), dict) else {}
        if kind == "voice" or asset_id.startswith("voice."):
            text = str(spec.get("text") or spec.get("line_text") or (audio or {}).get("text") or "").strip()
            speaker = str(spec.get("speaker") or (audio or {}).get("speaker") or "").strip()
            trace = spec.get("source_trace") if isinstance(spec.get("source_trace"), dict) else {}
            node_ids = [node_id for node_id in as_list(trace.get("node_ids")) if isinstance(node_id, str) and node_id]
            if not text:
                issues.append({
                    "asset_id": asset_id,
                    "file_ref": file_ref,
                    "code": "voice_missing_line_text",
                    "message": "Voice assets must be tied to dialogue or monologue and include exact text in spec.text or spec.line_text.",
                })
            if not speaker:
                issues.append({
                    "asset_id": asset_id,
                    "file_ref": file_ref,
                    "code": "voice_missing_speaker",
                    "message": "Voice assets must include speaker for deterministic line attachment and casting.",
                })
            if not node_ids:
                issues.append({
                    "asset_id": asset_id,
                    "file_ref": file_ref,
                    "code": "voice_missing_node_trace",
                    "message": "Voice assets must include spec.source_trace.node_ids for deterministic line attachment.",
                })
        path = output_root / file_ref
        if not path.exists():
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "missing_file", "message": "Manifest audio file_ref was not generated."})
            return
        if not path.is_file():
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "not_file", "message": "Manifest audio file_ref is not a file."})
            return
        if path.stat().st_size <= 0:
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "empty_file", "message": "Generated audio file is empty."})
            return
        if kind == "sfx" or asset_id.startswith("sfx."):
            duration = wav_duration_seconds(path)
            if duration is None:
                warnings.append(f"SFX {asset_id} duration could not be inspected.")
            elif duration > MAX_SFX_DURATION_SECONDS:
                issues.append({
                    "asset_id": asset_id,
                    "file_ref": file_ref,
                    "code": "sfx_too_long",
                    "message": f"SFX should be a short one-shot cue; duration is {duration:.2f}s, max is {MAX_SFX_DURATION_SECONDS:.2f}s.",
                })

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict):
            check_file(str(background.get("asset_id")), str(background.get("file_ref")), "background")
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict):
            check_file(str(cg.get("asset_id")), str(cg.get("file_ref")), "cg")
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict):
            check_file(str(ui_asset.get("asset_id")), str(ui_asset.get("file_ref")), "ui")
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict):
                check_file(str(portrait.get("asset_id")), str(portrait.get("file_ref")), "portrait", require_transparency=True)
        canon_ref = character.get("canon_ref_file_ref")
        if isinstance(canon_ref, str):
            check_file(str(character.get("canon_ref_asset_id")), canon_ref, "canon", require_transparency=True)
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict):
            check_audio_file(str(audio.get("asset_id")), str(audio.get("file_ref")), audio)

    manifest_kinds = manifest_asset_kinds(manifest)
    scheduled_refs, staging_warnings = scheduled_asset_refs(run_root)
    warnings.extend(staging_warnings)
    seen_scheduled: set[tuple[str, str, str]] = set()
    for ref in scheduled_refs:
        asset_id = str(ref.get("asset_id") or "")
        command = str(ref.get("command") or "")
        source_node_id = str(ref.get("source_node_id") or "")
        key = (source_node_id, command, asset_id)
        if key in seen_scheduled:
            continue
        seen_scheduled.add(key)
        if not looks_like_asset_id(asset_id):
            issues.append({
                "asset_id": asset_id,
                "source_node_id": source_node_id,
                "command": command,
                "code": "invalid_scheduled_asset_id",
                "message": "Yarn and fragment manifests must reference stable prefixed asset ids.",
            })
            continue
        actual_kind = manifest_kinds.get(asset_id)
        if not actual_kind:
            issues.append({
                "asset_id": asset_id,
                "source_node_id": source_node_id,
                "command": command,
                "code": "scheduled_asset_missing_from_manifest",
                "message": "Yarn or fragment manifest references an asset that was not planned into asset-manifest.json.",
            })
            continue
        expected_kind = ref.get("expected_kind")
        if expected_kind and actual_kind != expected_kind:
            issues.append({
                "asset_id": asset_id,
                "source_node_id": source_node_id,
                "command": command,
                "code": "scheduled_asset_kind_mismatch",
                "message": f"Command {command} expects {expected_kind}, but asset-manifest.json planned {actual_kind}.",
            })

    report = {
        "status": "pass" if not issues else "fail",
        "output_root": str(output_root),
        "issues": issues,
        "warnings": warnings,
    }
    write_json(path_for(run_root, "asset_validation_report"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = validate_assets(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
