#!/usr/bin/env python3
"""Export a self-contained browser RPG from compiled RPG artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import Json, copy_tree, load_optional_json, path_for, skill_root, write_text


def inspect_image_bounds(path: Path) -> Json | None:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        with Image.open(path) as image:
            width, height = image.size
            if "A" not in image.getbands():
                return {"sx": 0, "sy": 0, "sw": width, "sh": height, "w": width, "h": height}
            alpha = image.convert("RGBA").getchannel("A")
            bbox = alpha.getbbox()
            if bbox is None:
                return {"sx": 0, "sy": 0, "sw": width, "sh": height, "w": width, "h": height}
            x0, y0, x1, y1 = bbox
            return {"sx": x0, "sy": y0, "sw": x1 - x0, "sh": y1 - y0, "w": width, "h": height}
    except Exception:
        return None


def copy_manifest_assets(run_root: Path, output_root: Path) -> tuple[dict[str, str], dict[str, Json]]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    destination_root = output_root / "assets"
    destination_root.mkdir(parents=True, exist_ok=True)
    runtime_paths: dict[str, str] = {}
    runtime_bounds: dict[str, Json] = {}

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
        bounds = inspect_image_bounds(source)
        if bounds:
            runtime_bounds[asset_id] = bounds

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
    return runtime_paths, runtime_bounds


def build_rpg_payload(run_root: Path, runtime_assets: dict[str, str], runtime_bounds: dict[str, Json]) -> Json:
    manifest = load_optional_json(path_for(run_root, "rpg_manifest"))
    if not manifest:
        raise SystemExit("Missing workspace/rpg/rpg-manifest.json. Run compile_rpg_manifest.py first.")
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_rpg.py"},
        "title": manifest.get("title") or "Generated RPG",
        "start_map_id": manifest.get("start_map_id"),
        "start_position": manifest.get("start_position") or {"x": 1, "y": 1},
        "party": manifest.get("party") or [],
        "final_quest_id": manifest.get("final_quest_id"),
        "campaign": manifest.get("campaign") or {},
        "quest_progression": manifest.get("quest_progression") or {},
        "maps": manifest.get("maps") or [],
        "actors": manifest.get("actors") or [],
        "classes": manifest.get("classes") or [],
        "items": manifest.get("items") or [],
        "equipment": manifest.get("equipment") or [],
        "skills": manifest.get("skills") or [],
        "enemies": manifest.get("enemies") or [],
        "encounter_tables": manifest.get("encounter_tables") or [],
        "quests": manifest.get("quests") or [],
        "npc_dialogue": manifest.get("npc_dialogue") or [],
        "events": manifest.get("events") or [],
        "shops": manifest.get("shops") or [],
        "rest_points": manifest.get("rest_points") or [],
        "progression_rules": manifest.get("progression_rules") or [],
        "asset_refs": manifest.get("asset_refs") or [],
        "assets": runtime_assets,
        "asset_bounds": runtime_bounds,
    }


def export_web_rpg(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-rpg"
    copy_tree(skill_root() / "assets" / "web-rpg-template", output_root)
    runtime_assets, runtime_bounds = copy_manifest_assets(run_root, output_root)
    payload = build_rpg_payload(run_root, runtime_assets, runtime_bounds)
    write_text(output_root / "game-data.js", "window.RPG_GAME_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_rpg(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
