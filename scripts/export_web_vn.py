#!/usr/bin/env python3
"""Export a self-contained browser VN from accepted artifacts."""

from __future__ import annotations

import argparse
import collections
import json
import shlex
import re
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Json,
    as_list,
    copy_tree,
    load_gameplay_units,
    load_optional_json,
    load_yarn_fragments,
    path_for,
    skill_root,
    write_text,
)


def node_text(node: Json) -> str:
    return str(node.get("body") or node.get("summary") or node.get("title") or "The scene continues.")


def runtime_asset_name(asset_id: str, suffix: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", asset_id).strip("_") or "asset"
    return f"{safe_id}{suffix}"


def normalize_command_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip('"').strip("'")
    return value or None


def character_id_for_portrait(asset_id: str) -> str:
    parts = asset_id.split(".")
    if len(parts) >= 2:
        return f"char.{parts[1]}"
    return "char.unknown"


def safe_voice_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_").lower()


def is_narration_speaker(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"", "旁白", "narrator"}


def parse_yarn_command(line: str) -> Json | None:
    if not (line.startswith("<<") and line.endswith(">>")):
        return None
    body = line[2:-2].strip()
    if not body:
        return None
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    if not tokens:
        return None
    command = tokens[0]
    named: dict[str, str] = {}
    positional: list[str] = []
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            if key:
                named[key] = value
        else:
            positional.append(token)

    def first(*keys: str) -> str | None:
        for key in keys:
            value = normalize_command_token(named.get(key))
            if value:
                return value
        while positional and not normalize_command_token(positional[0]):
            positional.pop(0)
        return normalize_command_token(positional.pop(0)) if positional else None

    args: Json = {}
    if command in ("show_bg", "show_cg", "play_bgm", "play_sfx"):
        asset_id = first("asset_id", "bg", "cg", "track", "location")
        if asset_id:
            args["asset_id"] = asset_id
    elif command == "show_char":
        character_id = first("character_id", "character", "name")
        asset_id = first("asset_id", "portrait", "expression_asset_id")
        if character_id:
            args["character_id"] = character_id
        if asset_id:
            args["asset_id"] = asset_id
    elif command == "set_expression":
        character_id = first("character_id", "character", "name")
        expression = first("expression_asset_id", "asset_id", "expression", "expr", "emotion")
        if character_id:
            args["character_id"] = character_id
        if expression:
            args["expression_asset_id"] = expression
    elif command == "hide_char":
        character_id = first("character_id", "character", "name")
        if character_id:
            args["character_id"] = character_id
    elif command == "stop_bgm":
        pass
    else:
        return None
    return {"type": "command", "command": command, "args": args}


def vn_beats_from_yarn(text: str) -> list[Json]:
    beats: list[Json] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line in ("---", "===") or line.startswith("title:") or line.startswith("->") or line.startswith("[["):
            continue
        command = parse_yarn_command(line)
        if command:
            beats.append(command)
            continue
        if line.startswith("<<") and line.endswith(">>"):
            continue
        match = re.match(r"^([^:]{1,32}):\s*(.+)$", line)
        if match:
            beats.append({"type": "line", "speaker": match.group(1).strip(), "text": match.group(2).strip()})
        else:
            beats.append({"type": "line", "speaker": "Narrator", "text": line})
    return beats or [{"type": "line", "speaker": "Narrator", "text": "The scene continues."}]


def voice_asset_lookup(manifest: Json) -> tuple[set[str], dict[str, Json]]:
    voice_ids: set[str] = set()
    voice_specs: dict[str, Json] = {}
    for audio in as_list(manifest.get("audio")):
        if not isinstance(audio, dict) or not isinstance(audio.get("asset_id"), str):
            continue
        kind = str(audio.get("kind") or "").lower()
        asset_id = audio["asset_id"]
        if kind == "voice" or asset_id.startswith("voice."):
            voice_ids.add(asset_id)
            voice_specs[asset_id] = audio
    return voice_ids, voice_specs


def attach_voice_assets(beats: list[Json], node_id: str, manifest: Json) -> None:
    voice_ids, voice_specs = voice_asset_lookup(manifest)
    if not voice_ids:
        return
    node_token = safe_voice_token(node_id)
    node_short_token = safe_voice_token(str(node_id).removeprefix("node."))
    line_index = 0
    for beat in beats:
        if not isinstance(beat, dict) or beat.get("type") != "line":
            continue
        line_index += 1
        if is_narration_speaker(beat.get("speaker")):
            continue
        speaker_token = safe_voice_token(beat.get("speaker"))
        beat_text = str(beat.get("text") or "").strip()
        beat_speaker = str(beat.get("speaker") or "").strip()
        for asset_id, audio in voice_specs.items():
            spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
            trace = spec.get("source_trace") if isinstance(spec.get("source_trace"), dict) else {}
            source_nodes = as_list(trace.get("node_ids"))
            if node_id not in source_nodes:
                continue
            spec_text = str(spec.get("line_text") or spec.get("text") or "").strip()
            spec_speaker = str(spec.get("speaker") or "").strip()
            if spec_text and spec_text == beat_text and (not spec_speaker or not beat_speaker or spec_speaker == beat_speaker):
                beat["voice_asset_id"] = asset_id
                break
        if beat.get("voice_asset_id"):
            continue
        candidates = [
            f"voice.{node_id}.{line_index}",
            f"voice.{node_id}.{line_index - 1}",
            f"voice.{node_token}.{line_index}",
            f"voice.{node_token}.{line_index - 1}",
            f"voice.{node_short_token}.{line_index}",
            f"voice.{node_short_token}.{line_index - 1}",
        ]
        if speaker_token:
            candidates.extend([
                f"voice.{node_token}.{speaker_token}.{line_index}",
                f"voice.{node_token}.{speaker_token}.{line_index - 1}",
                f"voice.{node_short_token}.{speaker_token}.{line_index}",
                f"voice.{node_short_token}.{speaker_token}.{line_index - 1}",
            ])
        for asset_id in candidates:
            if asset_id in voice_ids:
                beat["voice_asset_id"] = asset_id
                break


def collect_runtime_assets(run_root: Path, output_root: Path, asset_directions: list[Any]) -> dict[str, str]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    source_root = run_root / "workspace" / "assets" / "web-vn"
    destination_root = output_root / "assets"
    destination_root.mkdir(parents=True, exist_ok=True)
    runtime_paths: dict[str, str] = {}

    def copy_manifest_asset(asset_id: str, file_ref: str) -> None:
        source = generated_root / file_ref
        if not source.exists():
            return
        destination = destination_root / file_ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{file_ref}"

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str) and isinstance(background.get("file_ref"), str):
            copy_manifest_asset(background["asset_id"], background["file_ref"])
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str) and isinstance(cg.get("file_ref"), str):
            copy_manifest_asset(cg["asset_id"], cg["file_ref"])
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str) and isinstance(ui_asset.get("file_ref"), str):
            copy_manifest_asset(ui_asset["asset_id"], ui_asset["file_ref"])
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict) and isinstance(audio.get("asset_id"), str) and isinstance(audio.get("file_ref"), str):
            copy_manifest_asset(audio["asset_id"], audio["file_ref"])
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        if isinstance(character.get("canon_ref_asset_id"), str) and isinstance(character.get("canon_ref_file_ref"), str):
            copy_manifest_asset(character["canon_ref_asset_id"], character["canon_ref_file_ref"])
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict) and isinstance(portrait.get("asset_id"), str) and isinstance(portrait.get("file_ref"), str):
                copy_manifest_asset(portrait["asset_id"], portrait["file_ref"])

    if not source_root.exists():
        return runtime_paths

    for asset in asset_directions:
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str):
            continue
        asset_id = asset["asset_id"]
        if asset_id in runtime_paths:
            continue
        source = None
        for suffix in (".png", ".svg", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac"):
            candidate = source_root / runtime_asset_name(asset_id, suffix)
            if candidate.exists():
                source = candidate
                break
        if source is None:
            continue
        destination = destination_root / source.name
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{destination.name}"
    return runtime_paths


def manifest_asset_entries(manifest: Json, runtime_assets: dict[str, str]) -> list[Json]:
    entries: list[Json] = []

    def add_entry(asset_id: str, kind: str, source: Json) -> None:
        entry = {"asset_id": asset_id, "kind": kind}
        for key in ("scene_id", "story_beat_id", "location_tag", "time_of_day", "emotion", "character_id", "display_name"):
            if key in source:
                entry[key] = source[key]
        spec = source.get("spec")
        if isinstance(spec, dict):
            entry["spec"] = spec
        if asset_id in runtime_assets:
            entry["runtime_path"] = runtime_assets[asset_id]
        entries.append(entry)

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str):
            add_entry(background["asset_id"], "background", background)
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str):
            add_entry(cg["asset_id"], "cg", cg)
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str):
            add_entry(ui_asset["asset_id"], str(ui_asset.get("kind") or "ui"), ui_asset)
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict) and isinstance(audio.get("asset_id"), str):
            add_entry(audio["asset_id"], str(audio.get("kind") or "audio"), audio)
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        character_id = character.get("id")
        if isinstance(character.get("canon_ref_asset_id"), str):
            add_entry(character["canon_ref_asset_id"], "charref", {
                "character_id": character_id,
                "display_name": character.get("display_name"),
            })
        for portrait in as_list(character.get("portrait_assets")):
            if not isinstance(portrait, dict) or not isinstance(portrait.get("asset_id"), str):
                continue
            add_entry(portrait["asset_id"], "portrait", {
                **portrait,
                "character_id": character_id or character_id_for_portrait(portrait["asset_id"]),
                "display_name": character.get("display_name"),
            })
    return entries


def manifest_character_entries(manifest: Json) -> list[Json]:
    characters = []
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict) or not isinstance(character.get("id"), str):
            continue
        characters.append({
            "id": character["id"],
            "display_name": character.get("display_name") or character["id"],
            "base_portrait_asset_id": character.get("base_portrait_asset_id"),
            "expression_asset_ids": as_list(character.get("expression_asset_ids")),
            "portrait_assets": as_list(character.get("portrait_assets")),
        })
    return characters


def build_story_payload(run_root: Path, runtime_assets: dict[str, str] | None = None) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    shared_state = load_optional_json(path_for(run_root, "shared_state")) or {"variables": []}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    asset_directions = as_list(asset_direction.get("asset_directions"))
    runtime_assets = runtime_assets or {}
    fragments = load_yarn_fragments(run_root)
    gameplay_units = load_gameplay_units(run_root)

    fragments_by_node = {fragment["node_id"]: fragment for fragment in fragments}
    plan_by_node = {
        plan.get("source_node_id"): plan
        for plan in as_list(plans.get("plans"))
        if isinstance(plan, dict)
    }
    edges_by_from: dict[str, list[Json]] = {}
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            edges_by_from.setdefault(edge["from"], []).append(edge)

    initial_state = {
        variable.get("id"): variable.get("initial_value")
        for variable in as_list(shared_state.get("variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }

    story_nodes = []
    for node in as_list(branch_graph.get("nodes")):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        node_id = node["id"]
        plan = plan_by_node.get(node_id, {})
        fragment = fragments_by_node.get(node_id)
        gameplay_unit = gameplay_units.get(node_id)
        entry_text = str(gameplay_unit.get("entry_text") or node_text(node)) if gameplay_unit else node_text(node)
        beats = vn_beats_from_yarn(fragment["yarn_text"]) if fragment else [{"type": "line", "speaker": "Narrator", "text": entry_text}]
        attach_voice_assets(beats, node_id, asset_manifest)
        exit_bindings = {
            binding.get("edge_id"): binding
            for binding in as_list((gameplay_unit or plan).get("exit_bindings") if isinstance((gameplay_unit or plan), dict) else [])
            if isinstance(binding, dict)
        }
        choices = []
        for edge in edges_by_from.get(node_id, []):
            edge_id = edge.get("id")
            binding = exit_bindings.get(edge_id, {})
            choices.append({
                "label": binding.get("label") or edge.get("label") or edge.get("condition_label") or edge.get("outcome_label") or "Continue",
                "target": edge.get("to"),
                "edge_id": edge_id,
                "outcome_id": binding.get("outcome_id") or edge_id,
                "condition_type": edge.get("condition_type", "player_choice"),
                "state_writes": binding.get("state_writes") or (plan.get("state_writes", []) if isinstance(plan, dict) else []),
                "conditions": edge.get("conditions", []),
            })
        required_assets = as_list(plan.get("required_assets") if isinstance(plan, dict) else [])
        if isinstance(gameplay_unit, dict):
            required_assets = [*required_assets, *as_list(gameplay_unit.get("required_assets"))]
        background_id = next((asset for asset in required_assets if isinstance(asset, str) and asset.startswith("bg.")), None)
        portrait_ids = [asset for asset in required_assets if isinstance(asset, str) and asset.startswith("portrait.")]
        story_node = {
            "id": node_id,
            "title": node.get("title") or node_id,
            "background_id": background_id or node.get("asset_id") or "bg.default",
            "portrait_ids": portrait_ids,
            "beats": beats,
            "choices": choices,
            "is_terminal": bool(node.get("is_terminal") or node.get("node_type") == "terminal" or not choices),
            "realization_kind": plan.get("realization_kind") if isinstance(plan, dict) else "vn_yarn",
        }
        if isinstance(gameplay_unit, dict):
            story_node["gameplay_unit_id"] = gameplay_unit.get("realization_unit_id")
            story_node["gameplay"] = {
                "adapter_id": gameplay_unit.get("adapter_id"),
                "entry_text": gameplay_unit.get("entry_text", ""),
                "runtime_spec": gameplay_unit.get("runtime_spec", {}),
                "exit_bindings": gameplay_unit.get("exit_bindings", []),
                "fail_forward": gameplay_unit.get("fail_forward", {}),
            }
        story_nodes.append(story_node)

    assets = manifest_asset_entries(asset_manifest, runtime_assets)
    seen_asset_ids = {asset.get("asset_id") for asset in assets if isinstance(asset, dict)}
    for asset in asset_directions:
        if not isinstance(asset, dict):
            continue
        enriched = dict(asset)
        asset_id = enriched.get("asset_id")
        if asset_id in seen_asset_ids:
            continue
        if isinstance(asset_id, str) and asset_id in runtime_assets:
            enriched["runtime_path"] = runtime_assets[asset_id]
        assets.append(enriched)

    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_vn.py"},
        "title": branch_graph.get("title") or "Generated Narrative Game",
        "start_node_id": branch_graph.get("start_node_id") or (story_nodes[0]["id"] if story_nodes else ""),
        "initial_state": initial_state,
        "nodes": story_nodes,
        "characters": manifest_character_entries(asset_manifest),
        "assets": assets,
        "gameplay_units": gameplay_units,
    }


def web_export_audio_report(story: Json) -> Json:
    non_narration_lines = 0
    voiced_lines = 0
    voice_ids: list[str] = []
    unvoiced_lines: list[Json] = []
    for node in as_list(story.get("nodes")):
        if not isinstance(node, dict):
            continue
        for index, beat in enumerate(as_list(node.get("beats"))):
            if not isinstance(beat, dict) or beat.get("type") != "line" or is_narration_speaker(beat.get("speaker")):
                continue
            non_narration_lines += 1
            voice_asset_id = beat.get("voice_asset_id")
            if isinstance(voice_asset_id, str) and voice_asset_id:
                voiced_lines += 1
                voice_ids.append(voice_asset_id)
            else:
                unvoiced_lines.append({
                    "node_id": node.get("id"),
                    "beat_index": index,
                    "speaker": beat.get("speaker"),
                    "text": beat.get("text"),
                })
    duplicate_voice_asset_ids = [
        {"asset_id": asset_id, "count": count}
        for asset_id, count in collections.Counter(voice_ids).items()
        if count > 1
    ]
    return {
        "status": "pass" if not unvoiced_lines and not duplicate_voice_asset_ids else "fail",
        "non_narration_lines": non_narration_lines,
        "voiced_lines": voiced_lines,
        "unique_voice_asset_ids": len(set(voice_ids)),
        "unvoiced_lines": unvoiced_lines,
        "duplicate_voice_asset_ids": duplicate_voice_asset_ids,
    }


def export_web_vn(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-vn"
    copy_tree(skill_root() / "assets" / "web-vn-template", output_root)
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    runtime_assets = collect_runtime_assets(run_root, output_root, as_list(asset_direction.get("asset_directions")))
    story = build_story_payload(run_root, runtime_assets)
    write_text(output_root / "story-data.js", "window.NARRATIVE_GAME_STORY = " + json.dumps(story, ensure_ascii=False, indent=2) + ";\n")
    write_text(run_root / "reports" / "web-vn-export-report.json", json.dumps(web_export_audio_report(story), ensure_ascii=False, indent=2) + "\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_vn(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
