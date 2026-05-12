#!/usr/bin/env python3
"""Export a self-contained browser RPG from compiled RPG artifacts."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import Json, copy_tree, load_optional_json, path_for, skill_root, write_text


def safe_voice_token(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned or "line"


def dialogue_voice_asset_id(dialogue_id: str, line_index: int) -> str:
    return f"voice.{safe_voice_token(dialogue_id)}.{line_index + 1}"


def outcome_voice_asset_id(event_id: str, outcome_id: str, line_index: int) -> str:
    return f"voice.outcome.{safe_voice_token(event_id)}.{safe_voice_token(outcome_id)}.{line_index + 1}"


def attach_dialogue_voice_assets(dialogues: Any, runtime_assets: dict[str, str]) -> list[Json]:
    result: list[Json] = []
    for dialogue in dialogues if isinstance(dialogues, list) else []:
        if not isinstance(dialogue, dict):
            continue
        updated = dict(dialogue)
        dialogue_id = str(updated.get("id") or "")
        lines = []
        for index, line in enumerate(updated.get("lines") if isinstance(updated.get("lines"), list) else []):
            if isinstance(line, dict):
                line_payload = dict(line)
            else:
                line_payload = {"text": str(line)}
            voice_asset_id = dialogue_voice_asset_id(dialogue_id, index)
            if voice_asset_id in runtime_assets:
                line_payload.setdefault("voice_asset_id", voice_asset_id)
            lines.append(line_payload)
        if lines:
            updated["lines"] = lines
        result.append(updated)
    return result


def attach_map_outcome_voice_assets(maps: Any, runtime_assets: dict[str, str]) -> list[Json]:
    result: list[Json] = []
    for game_map in maps if isinstance(maps, list) else []:
        if not isinstance(game_map, dict):
            continue
        updated_map = dict(game_map)
        events = []
        for event in game_map.get("events", []) if isinstance(game_map.get("events"), list) else []:
            if not isinstance(event, dict):
                continue
            updated_event = dict(event)
            event_id = str(updated_event.get("id") or "event")
            for outcome_key in ("outcomes", "win_outcomes"):
                outcomes = []
                for outcome in updated_event.get(outcome_key, []) if isinstance(updated_event.get(outcome_key), list) else []:
                    if not isinstance(outcome, dict):
                        continue
                    updated_outcome = dict(outcome)
                    outcome_id = str(updated_outcome.get("id") or "outcome")
                    lines = []
                    for index, line in enumerate(updated_outcome.get("lines", []) if isinstance(updated_outcome.get("lines"), list) else []):
                        if isinstance(line, dict):
                            line_payload = dict(line)
                        else:
                            line_payload = {"speaker": str(updated_event.get("name") or ""), "text": str(line)}
                        voice_asset_id = outcome_voice_asset_id(event_id, outcome_id, index)
                        if voice_asset_id in runtime_assets:
                            line_payload.setdefault("voice_asset_id", voice_asset_id)
                        lines.append(line_payload)
                    if lines:
                        updated_outcome["lines"] = lines
                    outcomes.append(updated_outcome)
                if outcomes:
                    updated_event[outcome_key] = outcomes
            events.append(updated_event)
        if events:
            updated_map["events"] = events
        result.append(updated_map)
    return result


def copy_manifest_assets(run_root: Path, output_root: Path) -> dict[str, str]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    destination_root = output_root / "assets"
    destination_root.mkdir(parents=True, exist_ok=True)
    runtime_paths: dict[str, str] = {}

    def copy_asset(asset_id: Any, file_ref: Any) -> None:
        if not isinstance(asset_id, str) or not isinstance(file_ref, str):
            return
        source = generated_root / file_ref
        if not source.exists():
            return
        destination = destination_root / file_ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{file_ref}"

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            copy_asset(value.get("asset_id"), value.get("file_ref"))
            copy_asset(value.get("canon_ref_asset_id"), value.get("canon_ref_file_ref"))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(manifest)

    dynamic_root = generated_root / "generated"
    for folder in ("videos", "rpg-motion", "rpg/map_boundaries_qa", "rpg/map_boundaries"):
        source_folder = dynamic_root / folder
        if not source_folder.exists():
            continue
        for source in sorted(source_folder.rglob("*")):
            if not source.is_file():
                continue
            if source.suffix.lower() == ".mp4" and source.with_suffix(".gif").exists():
                continue
            relative = source.relative_to(dynamic_root)
            destination = destination_root / "generated" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            runtime_paths[source.stem] = f"assets/generated/{relative.as_posix()}"

    return runtime_paths


def build_rpg_payload(run_root: Path, runtime_assets: dict[str, str]) -> Json:
    manifest = load_optional_json(path_for(run_root, "rpg_manifest"))
    if not manifest:
        raise SystemExit("Missing workspace/rpg/rpg-manifest.json. Run compile_rpg_manifest.py first.")
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_rpg.py"},
        "title": manifest.get("title") or "Generated RPG",
        "start_map_id": manifest.get("start_map_id"),
        "start_position": manifest.get("start_position") or {"x": 1, "y": 1},
        "entry_points": manifest.get("entry_points") or [],
        "party": manifest.get("party") or [],
        "campaign": manifest.get("campaign") or {},
        "maps": attach_map_outcome_voice_assets(manifest.get("maps") or [], runtime_assets),
        "actors": manifest.get("actors") or [],
        "classes": manifest.get("classes") or [],
        "items": manifest.get("items") or [],
        "equipment": manifest.get("equipment") or [],
        "skills": manifest.get("skills") or [],
        "enemies": manifest.get("enemies") or [],
        "encounter_tables": manifest.get("encounter_tables") or [],
        "quests": manifest.get("quests") or [],
        "npc_dialogue": attach_dialogue_voice_assets(manifest.get("npc_dialogue") or [], runtime_assets),
        "events": manifest.get("events") or [],
        "shops": manifest.get("shops") or [],
        "rest_points": manifest.get("rest_points") or [],
        "progression_rules": manifest.get("progression_rules") or [],
        "asset_refs": manifest.get("asset_refs") or [],
        "assets": runtime_assets,
    }


def export_web_rpg(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-rpg"
    copy_tree(skill_root() / "assets" / "web-rpg-template", output_root)
    runtime_assets = copy_manifest_assets(run_root, output_root)
    payload = build_rpg_payload(run_root, runtime_assets)
    write_text(output_root / "game-data.js", "window.RPG_GAME_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_rpg(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
