#!/usr/bin/env python3
"""Plan runtime assets from asset direction, following unity-vn-studio's manifest split."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_gameplay_units, load_optional_json, path_for, write_json


def sanitize_file_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "asset"


def asset_slug(asset_id: str) -> str:
    parts = asset_id.split(".")
    if len(parts) >= 2:
        return parts[1]
    return sanitize_file_stem(asset_id)


def portrait_emotion(asset_id: str) -> str:
    parts = asset_id.split(".")
    return parts[2] if len(parts) >= 3 else "neutral"


def character_id_for_portrait(asset_id: str) -> str:
    return f"char.{asset_slug(asset_id)}"


def collect_character_names(game_ir: Json) -> dict[str, str]:
    names: dict[str, str] = {}
    for entity in as_list(game_ir.get("entities")):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("id")
        if not isinstance(entity_id, str):
            continue
        if entity.get("kind") != "character" and not entity_id.startswith("char."):
            continue
        names[entity_id] = str(entity.get("name") or entity_id)
    bible = game_ir.get("design_brief", {}).get("narrative_bible", {}) if isinstance(game_ir.get("design_brief"), dict) else {}
    for character in as_list(bible.get("cast") if isinstance(bible, dict) else []):
        if not isinstance(character, dict) or not isinstance(character.get("id"), str):
            continue
        names.setdefault(character["id"], str(character.get("name") or character["id"]))
    return names


def source_node_for_asset(asset: Json, branch_graph: Json) -> str:
    trace = asset.get("source_trace") if isinstance(asset.get("source_trace"), dict) else {}
    node_ids = as_list(trace.get("node_ids") if isinstance(trace, dict) else [])
    for node_id in node_ids:
        if isinstance(node_id, str) and node_id:
            return node_id
    start = branch_graph.get("start_node_id")
    return start if isinstance(start, str) and start else "node.start"


def make_style_bible(asset_direction: Json) -> Json:
    style = asset_direction.get("style_pack") if isinstance(asset_direction.get("style_pack"), dict) else {}
    return {
        "palette": as_list(style.get("palette") if isinstance(style, dict) else []),
        "rendering_mode": style.get("rendering") or style.get("summary") or "visual novel illustration",
        "lighting_mood": style.get("lighting", "") if isinstance(style, dict) else "",
        "summary": style.get("summary", "") if isinstance(style, dict) else "",
    }


def kind_for_asset_id(asset_id: str) -> str:
    prefix = asset_id.split(".", 1)[0]
    return {
        "bg": "background",
        "cg": "cg",
        "portrait": "portrait",
        "bgm": "bgm",
        "sfx": "sfx",
        "enemy": "enemy",
        "prop": "prop",
        "hotspot": "hotspot",
        "symbol": "symbol",
        "effect": "effect",
        "icon": "icon",
        "map": "map",
        "ui": "ui",
    }.get(prefix, "ui")


def collect_required_assets(run_root: Path) -> list[Json]:
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    gameplay_units = load_gameplay_units(run_root)
    required: dict[str, Json] = {}
    for plan in as_list(plans.get("plans")):
        if not isinstance(plan, dict):
            continue
        node_id = plan.get("source_node_id")
        for asset_id in as_list(plan.get("required_assets")):
            if isinstance(asset_id, str):
                required.setdefault(asset_id, {
                    "asset_id": asset_id,
                    "kind": kind_for_asset_id(asset_id),
                    "description": f"Runtime asset required by {node_id}.",
                    "source_trace": {"node_ids": [node_id] if isinstance(node_id, str) else []},
                    "provider_hints": [],
                })
    for unit in gameplay_units.values():
        node_id = unit.get("source_node_id")
        for asset_id in as_list(unit.get("required_assets")):
            if isinstance(asset_id, str):
                required.setdefault(asset_id, {
                    "asset_id": asset_id,
                    "kind": kind_for_asset_id(asset_id),
                    "description": f"Gameplay asset required by {node_id}.",
                    "source_trace": {"node_ids": [node_id] if isinstance(node_id, str) else []},
                    "provider_hints": [],
                })
    return list(required.values())


def plan_asset_manifest(run_root: Path) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    game_ir = load_optional_json(path_for(run_root, "game_ir")) or {}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    project_id = sanitize_file_stem(str(branch_graph.get("title") or "generated-narrative-game")).lower()
    directions = [asset for asset in as_list(asset_direction.get("asset_directions")) if isinstance(asset, dict) and isinstance(asset.get("asset_id"), str)]
    seen_direction_ids = {asset["asset_id"] for asset in directions}
    for required_asset in collect_required_assets(run_root):
        if required_asset["asset_id"] not in seen_direction_ids:
            directions.append(required_asset)
            seen_direction_ids.add(required_asset["asset_id"])
    character_names = collect_character_names(game_ir)

    backgrounds = []
    cgs = []
    ui = []
    audio = []
    portrait_ids_by_character: dict[str, list[str]] = {}
    portrait_specs: dict[str, Json] = {}

    for asset in directions:
        asset_id = asset["asset_id"]
        kind = asset.get("kind")
        trace_node = source_node_for_asset(asset, branch_graph)
        spec = {
            "description": asset.get("description", ""),
            "provider_hints": as_list(asset.get("provider_hints")),
            "source_trace": asset.get("source_trace", {}),
        }
        if kind == "background" or asset_id.startswith("bg."):
            backgrounds.append({
                "asset_id": asset_id,
                "scene_id": trace_node,
                "location_tag": asset_slug(asset_id),
                "time_of_day": asset_id.split(".")[2] if len(asset_id.split(".")) >= 3 else "default",
                "spec": spec,
                "file_ref": f"generated/backgrounds/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind == "cg" or asset_id.startswith("cg."):
            cgs.append({
                "asset_id": asset_id,
                "story_beat_id": trace_node,
                "participating_characters": [],
                "spec": spec,
                "file_ref": f"generated/cgs/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind == "portrait" or asset_id.startswith("portrait."):
            character_id = character_id_for_portrait(asset_id)
            portrait_ids_by_character.setdefault(character_id, []).append(asset_id)
            portrait_specs[asset_id] = spec
            continue
        if kind in ("ui", "enemy", "prop", "hotspot", "symbol", "effect", "icon", "map") or asset_id.startswith(("ui.", "enemy.", "prop.", "hotspot.", "symbol.", "effect.", "icon.", "map.")):
            ui.append({
                "asset_id": asset_id,
                "kind": str(kind or asset_slug(asset_id)),
                "spec": spec,
                "file_ref": f"generated/ui/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind in ("bgm", "sfx") or asset_id.startswith(("bgm.", "sfx.")):
            audio.append({
                "asset_id": asset_id,
                "kind": "bgm" if asset_id.startswith("bgm.") else "sfx",
                "mood": make_style_bible(asset_direction).get("lighting_mood", ""),
                "file_ref": f"audio/{sanitize_file_stem(asset_id)}.ogg",
            })

    characters = []
    for character_id, portrait_ids in sorted(portrait_ids_by_character.items()):
        slug = character_id.removeprefix("char.")
        portrait_ids = sorted(dict.fromkeys(portrait_ids))
        portrait_assets = [
            {
                "asset_id": portrait_id,
                "emotion": portrait_emotion(portrait_id),
                "file_ref": f"generated/portraits/{sanitize_file_stem(portrait_id)}.png",
                "source_file_ref": f"generated/portraits/source/{sanitize_file_stem(portrait_id)}.png",
                "spec": portrait_specs.get(portrait_id, {}),
            }
            for portrait_id in portrait_ids
        ]
        characters.append({
            "id": character_id,
            "display_name": character_names.get(character_id, slug.replace("_", " ")),
            "canon_ref_asset_id": f"charref.{slug}.core",
            "canon_ref_file_ref": f"generated/charrefs/charref.{sanitize_file_stem(slug)}.core.png",
            "base_portrait_asset_id": portrait_ids[0],
            "expression_asset_ids": portrait_ids,
            "portrait_assets": portrait_assets,
            "costume_rules": "",
            "color_anchors": [],
        })

    manifest: Json = {
        "project_id": project_id,
        "style_bible": make_style_bible(asset_direction),
        "characters": characters,
        "backgrounds": backgrounds,
        "cgs": cgs,
        "ui": ui,
        "audio": audio,
        "version": "v1",
        "source_asset_direction": "workspace/asset-direction.json",
    }
    write_json(path_for(run_root, "asset_manifest"), manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    plan_asset_manifest(run_root)
    print(str(path_for(run_root, "asset_manifest")))


if __name__ == "__main__":
    main()
