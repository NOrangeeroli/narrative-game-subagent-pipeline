#!/usr/bin/env python3
"""Probe asset-manifest.json and plan asset subagent dispatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


BACKGROUND_SECTIONS = {
    "map_assets": ("rpg_background", "rpg"),
    "battle_backgrounds": ("rpg_background", "rpg"),
}

MANIFEST_SECTION_GROUPS = {
    "map_assets": "rpg_backgrounds",
    "battle_backgrounds": "rpg_backgrounds",
    "tilesets": "tilesets",
    "sprites": "sprites",
    "enemy_sprites": "enemy_sprites",
    "item_icons": "item_icons",
    "skill_icons": "skill_icons",
    "equipment_icons": "equipment_icons",
    "rpg_ui": "rpg_ui",
    "ui": "ui",
}

SUBAGENT_ROLE_CARDS = {
    "rpg_backgrounds": "references/subagents/background/RPGBackgroundGenerator.md",
    "bgm": "references/subagents/audio/BGMAudioGenerator.md",
    "sfx": "references/subagents/audio/SFXAudioGenerator.md",
    "voice": "references/subagents/audio/VoiceAudioGenerator.md",
}


def asset_output_path(run_root: Path, file_ref: Any) -> Path | None:
    if not isinstance(file_ref, str) or not file_ref.strip():
        return None
    return run_root / "workspace" / "generated-assets" / file_ref


def asset_exists(run_root: Path, file_ref: Any) -> bool:
    output_path = asset_output_path(run_root, file_ref)
    return bool(output_path and output_path.exists() and output_path.stat().st_size > 0)


def background_entry(run_root: Path, section: str, asset: Json) -> Json:
    background_type, scope = BACKGROUND_SECTIONS[section]
    file_ref = asset.get("file_ref")
    return {
        "asset_id": str(asset.get("asset_id") or ""),
        "section": section,
        "dispatch_group": MANIFEST_SECTION_GROUPS[section],
        "background_type": background_type,
        "scope": scope,
        "kind": str(asset.get("kind") or background_type),
        "file_ref": file_ref,
        "output_file": str(asset_output_path(run_root, file_ref)) if asset_output_path(run_root, file_ref) else None,
        "exists": asset_exists(run_root, file_ref),
        "spec": asset.get("spec") if isinstance(asset.get("spec"), dict) else {},
    }


def manifest_asset_entry(
    run_root: Path,
    section: str,
    group: str,
    asset: Json,
    *,
    asset_id_key: str = "asset_id",
    file_ref_key: str = "file_ref",
    kind: str | None = None,
) -> Json | None:
    asset_id = asset.get(asset_id_key)
    file_ref = asset.get(file_ref_key)
    if not isinstance(asset_id, str) or not asset_id:
        return None
    output_path = asset_output_path(run_root, file_ref)
    return {
        "asset_id": asset_id,
        "section": section,
        "dispatch_group": group,
        "kind": str(kind or asset.get("kind") or group),
        "file_ref": file_ref,
        "output_file": str(output_path) if output_path else None,
        "exists": bool(output_path and output_path.exists() and output_path.stat().st_size > 0),
        "spec": asset.get("spec") if isinstance(asset.get("spec"), dict) else {},
    }


def collect_manifest_assets(run_root: Path, manifest: Json) -> list[Json]:
    assets: list[Json] = []
    seen: set[tuple[str, str]] = set()

    def add(entry: Json | None) -> None:
        if not entry:
            return
        key = (str(entry.get("asset_id") or ""), str(entry.get("file_ref") or ""))
        if key in seen:
            return
        seen.add(key)
        assets.append(entry)

    for section, group in MANIFEST_SECTION_GROUPS.items():
        for asset in as_list(manifest.get(section)):
            if not isinstance(asset, dict):
                continue
            if section in BACKGROUND_SECTIONS:
                add(background_entry(run_root, section, asset))
            else:
                add(manifest_asset_entry(run_root, section, group, asset))

    for audio in as_list(manifest.get("audio")):
        if not isinstance(audio, dict):
            continue
        audio_kind = str(audio.get("kind") or "bgm").lower()
        group = audio_kind if audio_kind in {"bgm", "sfx", "voice"} else "audio"
        add(manifest_asset_entry(run_root, "audio", group, audio, kind=audio_kind))

    return assets


def group_assets(assets: list[Json]) -> dict[str, Json]:
    groups: dict[str, Json] = {}
    for asset in assets:
        group = str(asset.get("dispatch_group") or "assets")
        payload = groups.setdefault(group, {
            "dispatch_group": group,
            "status": "ready",
            "asset_count": 0,
            "existing_count": 0,
            "missing_count": 0,
            "sections": [],
            "role_card": SUBAGENT_ROLE_CARDS.get(group),
            "assets": [],
            "missing_assets": [],
        })
        payload["asset_count"] += 1
        section = str(asset.get("section") or "")
        if section and section not in payload["sections"]:
            payload["sections"].append(section)
        payload["assets"].append(asset)
        if asset.get("exists"):
            payload["existing_count"] += 1
        else:
            payload["missing_count"] += 1
            payload["missing_assets"].append(asset)
            payload["status"] = "needs_generation"
    return groups


def probe_asset_manifest(run_root: Path) -> Json:
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not isinstance(manifest, dict):
        return {
            "status": "fail",
            "issues": [{"code": "missing_manifest", "message": "Missing workspace/asset-manifest.json."}],
            "background": False,
            "rpg_background": False,
            "background_count": 0,
            "rpg_background_count": 0,
            "background_assets": [],
            "asset_count": 0,
            "existing_asset_count": 0,
            "missing_asset_count": 0,
            "asset_groups": {},
            "subagent_dispatch": [],
            "missing_assets": [],
        }

    assets = collect_manifest_assets(run_root, manifest)
    groups = group_assets(assets)
    missing_assets = [asset for asset in assets if not asset.get("exists")]
    background_assets = [asset for asset in assets if asset.get("section") in BACKGROUND_SECTIONS]
    rpg_assets = [asset for asset in background_assets if asset.get("scope") == "rpg"]
    dispatch = [
        {
            "dispatch_group": group_name,
            "status": group["status"],
            "sections": group["sections"],
            "role_card": group.get("role_card"),
            "missing_count": group["missing_count"],
            "missing_assets": group["missing_assets"],
        }
        for group_name, group in sorted(groups.items())
        if group["missing_count"] > 0
    ]
    return {
        "status": "needs_generation" if missing_assets else "pass",
        "issues": [],
        "background": bool(background_assets),
        "rpg_background": bool(rpg_assets),
        "background_count": len(background_assets),
        "rpg_background_count": len(rpg_assets),
        "background_assets": background_assets,
        "asset_count": len(assets),
        "existing_asset_count": len(assets) - len(missing_assets),
        "missing_asset_count": len(missing_assets),
        "asset_groups": groups,
        "subagent_dispatch": dispatch,
        "missing_assets": missing_assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    report = probe_asset_manifest(run_root)
    if args.write_report:
        write_json(run_root / "reports" / "asset-manifest-probe.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
