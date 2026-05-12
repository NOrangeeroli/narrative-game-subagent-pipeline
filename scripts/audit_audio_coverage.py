#!/usr/bin/env python3
"""Audit Web RPG dialogue and outcome voice coverage."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


def load_exported_game_data(run_root: Path) -> Json | None:
    path = run_root / "build" / "web-rpg" / "game-data.js"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\s*window\.RPG_GAME_DATA\s*=\s*(.*);\s*\Z", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}; expected window.RPG_GAME_DATA assignment.")
    return json.loads(match.group(1))


def line_text(line: Any) -> str:
    if isinstance(line, dict):
        return str(line.get("text") or "")
    return str(line or "")


def line_speaker(line: Any, fallback: str = "") -> str:
    if isinstance(line, dict):
        return str(line.get("speaker") or fallback)
    return fallback


def line_voice(line: Any) -> str:
    return str(line.get("voice_asset_id") or "") if isinstance(line, dict) else ""


def collect_lines(data: Json) -> list[Json]:
    records: list[Json] = []
    for dialogue in as_list(data.get("npc_dialogue")):
        if not isinstance(dialogue, dict):
            continue
        dialogue_id = str(dialogue.get("id") or "")
        for index, line in enumerate(as_list(dialogue.get("lines"))):
            records.append({
                "scope": "npc_dialogue",
                "owner_id": dialogue_id,
                "line_index": index,
                "speaker": line_speaker(line),
                "text": line_text(line),
                "voice_asset_id": line_voice(line),
            })
    for game_map in as_list(data.get("maps")):
        if not isinstance(game_map, dict):
            continue
        map_id = str(game_map.get("id") or "")
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            event_name = str(event.get("name") or "")
            for outcome_key in ("outcomes", "win_outcomes"):
                for outcome in as_list(event.get(outcome_key)):
                    if not isinstance(outcome, dict):
                        continue
                    outcome_id = str(outcome.get("id") or "")
                    for index, line in enumerate(as_list(outcome.get("lines"))):
                        records.append({
                            "scope": outcome_key,
                            "map_id": map_id,
                            "owner_id": f"{event_id}.{outcome_id}",
                            "line_index": index,
                            "speaker": line_speaker(line, event_name),
                            "text": line_text(line),
                            "voice_asset_id": line_voice(line),
                        })
    return records


def audit(run_root: Path) -> Json:
    data = load_exported_game_data(run_root)
    source = "build/web-rpg/game-data.js"
    if data is None:
        data = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
        source = "workspace/rpg/rpg-manifest.json"
    assets = data.get("assets") if isinstance(data.get("assets"), dict) else {}
    records = collect_lines(data)
    issues: list[Json] = []
    warnings: list[str] = []
    speaker_voices: dict[str, set[str]] = defaultdict(set)
    for record in records:
        voice_id = str(record.get("voice_asset_id") or "")
        speaker = str(record.get("speaker") or "").strip() or "(unknown)"
        if not str(record.get("text") or "").strip():
            continue
        if not voice_id:
            issues.append({**record, "code": "missing_voice_asset_id", "message": "Dialogue line has no voice_asset_id."})
            continue
        if voice_id not in assets:
            issues.append({**record, "code": "missing_runtime_asset", "message": "voice_asset_id is not present in runtime assets."})
            continue
        speaker_voices[speaker].add(voice_id)
    voice_signature: dict[str, str] = {}
    for speaker, voice_ids in sorted(speaker_voices.items()):
        signature = ";".join(sorted(voice_ids))
        if signature in voice_signature:
            warnings.append(f"Speakers {voice_signature[signature]!r} and {speaker!r} share the same voice asset set.")
        else:
            voice_signature[signature] = speaker
    report = {
        "status": "pass" if not issues else "fail",
        "source": source,
        "line_count": len(records),
        "voiced_line_count": sum(1 for record in records if record.get("voice_asset_id")),
        "speaker_count": len(speaker_voices),
        "speaker_voice_counts": {speaker: len(voices) for speaker, voices in sorted(speaker_voices.items())},
        "issues": issues,
        "warnings": warnings,
    }
    write_json(run_root / "reports" / "audio-coverage-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = audit(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
