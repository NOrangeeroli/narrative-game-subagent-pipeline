#!/usr/bin/env python3
"""Validate generated assets against asset-manifest.json."""

from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


MAX_SFX_DURATION_SECONDS = 2.35


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
            if not text:
                issues.append({
                    "asset_id": asset_id,
                    "file_ref": file_ref,
                    "code": "voice_missing_line_text",
                    "message": "Voice assets must be tied to dialogue or monologue and include exact text in spec.text or spec.line_text.",
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
