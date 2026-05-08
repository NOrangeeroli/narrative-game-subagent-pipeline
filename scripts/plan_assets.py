#!/usr/bin/env python3
"""Plan runtime assets from asset direction, following unity-vn-studio's manifest split."""

from __future__ import annotations

import argparse
from collections import Counter
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
    if asset_id.startswith("icon.item."):
        return "item_icon"
    if asset_id.startswith("icon.skill."):
        return "skill_icon"
    if asset_id.startswith("icon.equip.") or asset_id.startswith("icon.equipment."):
        return "equipment_icon"
    return {
        "bg": "background",
        "cg": "cg",
        "portrait": "portrait",
        "bgm": "bgm",
        "sfx": "sfx",
        "enemy": "enemy_sprite",
        "prop": "prop",
        "hotspot": "hotspot",
        "symbol": "symbol",
        "effect": "effect",
        "icon": "icon",
        "map": "map_asset",
        "tileset": "tileset",
        "tile": "terrain_tile",
        "sceneprop": "map_prop",
        "sprite": "sprite",
        "mapprop": "map_prop",
        "battlebg": "battle_background",
        "itemicon": "item_icon",
        "skillicon": "skill_icon",
        "equipicon": "equipment_icon",
        "ui": "ui",
    }.get(prefix, "ui")


def add_required(required: dict[str, Json], asset_id: str, kind: str | None, description: str, source_path: str) -> None:
    if not asset_id:
        return
    required.setdefault(asset_id, {
        "asset_id": asset_id,
        "kind": kind or kind_for_asset_id(asset_id),
        "description": description,
        "source_trace": {"node_ids": [], "artifact_paths": [source_path] if source_path else []},
        "provider_hints": [],
    })


def summarize_map_layout(game_map: Json) -> str:
    title = str(game_map.get("title") or game_map.get("id") or "RPG map")
    width = game_map.get("width")
    height = game_map.get("height")
    layers = game_map.get("layers") if isinstance(game_map.get("layers"), dict) else {}
    ground_counts: Counter[str] = Counter()
    for row in as_list(layers.get("ground")):
        if isinstance(row, list):
            ground_counts.update(str(cell) for cell in row if cell not in ("", None))
    terrain = ", ".join(f"{name} x{count}" for name, count in ground_counts.most_common(5))
    design = game_map.get("map_design") if isinstance(game_map.get("map_design"), dict) else {}
    counts = []
    for key in ("houses", "trees", "gardens", "props", "npcs", "terrain", "paths"):
        value = as_list(design.get(key))
        if value:
            counts.append(f"{len(value)} {key}")
    event_count = len(as_list(game_map.get("events")))
    size = f"{width}x{height}" if isinstance(width, int) and isinstance(height, int) else "fixed-grid"
    detail = "; ".join(counts) if counts else f"{event_count} events"
    return f"{title}, {size}. Layout: {detail}. Ground mix: {terrain or 'grass/path/floor'}."


def collect_layer_map_props(game_map: Json) -> set[str]:
    layers = game_map.get("layers") if isinstance(game_map.get("layers"), dict) else {}
    props: set[str] = set()
    for layer_name in ("objects", "overlay"):
        for row in as_list(layers.get(layer_name)):
            if not isinstance(row, list):
                continue
            for cell in row:
                token = str(cell or "")
                if token and token not in (".", "0"):
                    props.add(token if token.startswith("mapprop.") else f"mapprop.{token}")
    return props


def collect_scene_map_props(game_map: Json) -> list[Json]:
    scene = game_map.get("scene") if isinstance(game_map.get("scene"), dict) else {}
    props = []
    for prop in as_list(scene.get("props")):
        if isinstance(prop, dict) and isinstance(prop.get("asset_id"), str):
            props.append(prop)
    return props


def collect_rpg_required_assets(rpg_manifest: Json) -> list[Json]:
    required: dict[str, Json] = {}
    for game_map in as_list(rpg_manifest.get("maps")):
        if not isinstance(game_map, dict):
            continue
        source_path = str(game_map.get("source_path") or "workspace/rpg/maps")
        summary = summarize_map_layout(game_map)
        for key in ("map_asset_id", "asset_id"):
            asset_id = game_map.get(key)
            if isinstance(asset_id, str) and asset_id.startswith("map."):
                add_required(required, asset_id, "map_asset", f"Top-down playable RPG map background for {summary}", source_path)
        tileset_id = game_map.get("tileset_asset_id")
        if isinstance(tileset_id, str):
            add_required(required, tileset_id, "tileset", f"Tile atlas matching {summary}", source_path)
        terrain_asset_ids = game_map.get("terrain_asset_ids")
        if not isinstance(terrain_asset_ids, dict):
            scene = game_map.get("scene") if isinstance(game_map.get("scene"), dict) else {}
            terrain_asset_ids = scene.get("terrain_asset_ids") if isinstance(scene.get("terrain_asset_ids"), dict) else {}
        for terrain, asset_id in sorted(terrain_asset_ids.items()):
            if isinstance(terrain, str) and isinstance(asset_id, str):
                add_required(
                    required,
                    asset_id,
                    "terrain_tile",
                    f"Single seamless top-down terrain tile for {terrain}; repeat it across {summary}. This is not an atlas or full-map background.",
                    source_path,
                )
        for prop_id in sorted(collect_layer_map_props(game_map)):
            label = prop_id.removeprefix("mapprop.").replace("_", " ")
            add_required(required, prop_id, "map_prop", f"Top-down map prop for {label}; match the scale and palette of {summary}", source_path)
        for prop in collect_scene_map_props(game_map):
            prop_id = prop["asset_id"]
            label = str(prop.get("name") or prop.get("asset") or prop_id.split(".")[-1]).replace("_", " ")
            add_required(
                required,
                prop_id,
                "map_prop",
                f"Scene-specific top-down RPG map prop for {label}; generated for this map only and scaled by scene.props in {summary}.",
                source_path,
            )
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            sprite_id = event.get("sprite_asset_id") or event.get("asset_id")
            if isinstance(sprite_id, str) and sprite_id.startswith("sprite."):
                add_required(required, sprite_id, "sprite", f"RPG map sprite for {event.get('name') or event.get('id') or 'event'} in {summary}", source_path)

    for actor in as_list(rpg_manifest.get("actors")):
        if isinstance(actor, dict):
            sprite_id = actor.get("sprite_asset_id") or actor.get("asset_id")
            if isinstance(sprite_id, str):
                add_required(required, sprite_id, kind_for_asset_id(sprite_id), f"Playable party sprite for {actor.get('name') or actor.get('id')}.", "workspace/rpg/actors.json")
    for enemy in as_list(rpg_manifest.get("enemies")):
        if isinstance(enemy, dict):
            sprite_id = enemy.get("sprite_asset_id") or enemy.get("asset_id")
            if isinstance(sprite_id, str):
                add_required(required, sprite_id, kind_for_asset_id(sprite_id), f"Enemy battle/map sprite for {enemy.get('name') or enemy.get('id')}.", "workspace/rpg/enemies.json")
    for item in as_list(rpg_manifest.get("items")):
        if isinstance(item, dict):
            icon_id = item.get("icon_asset_id") or item.get("asset_id")
            if isinstance(icon_id, str):
                add_required(required, icon_id, kind_for_asset_id(icon_id), f"Readable RPG inventory icon for {item.get('name') or item.get('id')}.", "workspace/rpg/items.json")
    for asset_id in as_list(rpg_manifest.get("asset_refs")):
        if isinstance(asset_id, str):
            add_required(required, asset_id, kind_for_asset_id(asset_id), "Runtime RPG asset required by rpg-manifest.json.", "workspace/rpg/rpg-manifest.json")
    return list(required.values())


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
    rpg_manifest = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
    for rpg_asset in collect_rpg_required_assets(rpg_manifest):
        if isinstance(rpg_asset.get("asset_id"), str):
            required.setdefault(rpg_asset["asset_id"], rpg_asset)
    return list(required.values())


RPG_SECTION_BY_KIND = {
    "terrain_tile": "terrain_tiles",
    "tileset": "tilesets",
    "sprite": "sprites",
    "enemy_sprite": "enemy_sprites",
    "map_prop": "map_props",
    "item_icon": "item_icons",
    "skill_icon": "skill_icons",
    "equipment_icon": "equipment_icons",
    "battle_background": "battle_backgrounds",
    "map_asset": "map_assets",
    "rpg_ui": "rpg_ui",
}


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
    rpg_sections: dict[str, list[Json]] = {section: [] for section in RPG_SECTION_BY_KIND.values()}
    portrait_ids_by_character: dict[str, list[str]] = {}
    portrait_specs: dict[str, Json] = {}

    for asset in directions:
        asset_id = asset["asset_id"]
        kind = asset.get("kind") or kind_for_asset_id(asset_id)
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
        section = RPG_SECTION_BY_KIND.get(str(kind))
        if section:
            rpg_sections[section].append({
                "asset_id": asset_id,
                "kind": str(kind),
                "spec": spec,
                "file_ref": f"generated/rpg/{section}/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind in ("ui", "enemy", "prop", "hotspot", "symbol", "effect", "icon", "map") or asset_id.startswith(("ui.", "prop.", "hotspot.", "symbol.", "effect.", "icon.")):
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
            continue

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
        **rpg_sections,
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
