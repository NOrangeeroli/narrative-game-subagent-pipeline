#!/usr/bin/env python3
"""Compile post-design RPG artifacts into one runtime manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_lib import Json, ValidationResult, as_list, ensure_run_layout, load_optional_json, path_for, read_json, write_json


COLLECTION_FILES: dict[str, tuple[str, tuple[str, ...]]] = {
    "actors": ("actors.json", ("actors", "party")),
    "classes": ("classes.json", ("classes",)),
    "items": ("items.json", ("items",)),
    "equipment": ("equipment.json", ("equipment",)),
    "skills": ("skills.json", ("skills",)),
    "enemies": ("enemies.json", ("enemies",)),
    "encounter_tables": ("encounter-tables.json", ("encounter_tables", "encounters")),
    "quests": ("quests.json", ("quests",)),
    "npc_dialogue": ("npc-dialogue.json", ("npc_dialogue", "dialogues", "dialogue")),
    "events": ("events.json", ("events",)),
    "shops": ("shops.json", ("shops",)),
    "rest_points": ("rest-points.json", ("rest_points",)),
    "progression_rules": ("progression-rules.json", ("progression_rules", "rules")),
}

ASSET_PREFIXES = (
    "bg.",
    "cg.",
    "portrait.",
    "ui.",
    "enemy.",
    "prop.",
    "hotspot.",
    "symbol.",
    "effect.",
    "icon.",
    "map.",
    "tileset.",
    "sprite.",
    "battlebg.",
    "itemicon.",
    "skillicon.",
    "equipicon.",
)


def item_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("id")
    return value if isinstance(value, str) and value else None


def coerce_collection(payload: Any, keys: tuple[str, ...]) -> list[Json]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [dict({"id": entry_id}, **entry) for entry_id, entry in value.items() if isinstance(entry, dict)]
    if all(isinstance(value, dict) for value in payload.values()):
        return [dict({"id": entry_id}, **entry) for entry_id, entry in payload.items()]
    return []


def load_collection(run_root: Path, name: str) -> tuple[list[Json], str | None]:
    filename, keys = COLLECTION_FILES[name]
    relative = f"workspace/rpg/{filename}"
    path = run_root / relative
    payload = load_optional_json(path)
    if payload is None:
        return [], None
    return coerce_collection(payload, keys), relative


def normalize_grid(value: Any, width: int, height: int, fill: Any) -> list[list[Any]]:
    rows = value if isinstance(value, list) else []
    normalized: list[list[Any]] = []
    for y in range(height):
        source_row = rows[y] if y < len(rows) and isinstance(rows[y], list) else []
        row = [source_row[x] if x < len(source_row) else fill for x in range(width)]
        normalized.append(row)
    return normalized


def load_maps(run_root: Path, result: ValidationResult) -> list[Json]:
    maps: list[Json] = []
    maps_root = run_root / "workspace" / "rpg" / "maps"
    for path in sorted(maps_root.glob("*.map.json")):
        relative = str(path.relative_to(run_root))
        try:
            payload = read_json(path)
        except Exception as exc:  # noqa: BLE001
            result.add("error", "invalid_json", f"Cannot parse RPG map: {exc}", relative)
            continue
        if not isinstance(payload, dict):
            result.add("error", "schema", "RPG map must be an object.", relative)
            continue
        map_id = payload.get("id")
        if not isinstance(map_id, str) or not map_id:
            map_id = path.name.removesuffix(".map.json")
            payload["id"] = map_id
            result.add("warning", "map_id", "Map id missing; inferred from filename.", f"{relative}.id")
        width = payload.get("width")
        height = payload.get("height")
        if not isinstance(width, int) or width < 4:
            width = 12
            payload["width"] = width
            result.add("warning", "map_width", "Map width missing or too small; normalized to 12.", f"{relative}.width")
        if not isinstance(height, int) or height < 4:
            height = 8
            payload["height"] = height
            result.add("warning", "map_height", "Map height missing or too small; normalized to 8.", f"{relative}.height")
        layers = payload.get("layers") if isinstance(payload.get("layers"), dict) else {}
        ground = normalize_grid(layers.get("ground"), width, height, "grass")
        collision = normalize_grid(layers.get("collision"), width, height, 0)
        payload["layers"] = {**layers, "ground": ground, "collision": collision}
        events = [event for event in as_list(payload.get("events")) if isinstance(event, dict)]
        for index, event in enumerate(events):
            if not isinstance(event.get("id"), str):
                event["id"] = f"{map_id}.event.{index + 1}"
                result.add("warning", "event_id", "Map event id missing; inferred stable id.", f"{relative}.events[{index}].id")
            x = event.get("x")
            y = event.get("y")
            if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0 or x >= width or y >= height:
                result.add("error", "event_position", "Map event position must be inside map bounds.", f"{relative}.events[{index}]")
        payload["events"] = events
        payload["source_path"] = relative
        maps.append(payload)
    return maps


def validate_unique_ids(result: ValidationResult, collection: list[Json], label: str, path: str) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(collection):
        current = item_id(item)
        if current is None:
            result.add("error", "schema", f"{label} entries need id.", f"{path}[{index}].id")
            continue
        if current in ids:
            result.add("error", "duplicate_id", f"Duplicate {label} id: {current}", f"{path}[{index}].id")
        ids.add(current)
    return ids


def collect_asset_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, str):
        if value.startswith(ASSET_PREFIXES):
            refs.add(value)
        return
    if isinstance(value, list):
        for item in value:
            collect_asset_refs(item, refs)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("asset_id") and isinstance(item, str):
                refs.add(item)
            else:
                collect_asset_refs(item, refs)


def actor_stats_valid(actor: Json) -> bool:
    stats = actor.get("stats") if isinstance(actor.get("stats"), dict) else actor
    return all(isinstance(stats.get(key), (int, float)) and stats[key] > 0 for key in ("hp", "attack"))


def compile_rpg_manifest(run_root: Path) -> tuple[Json, Json]:
    ensure_run_layout(run_root)
    result = ValidationResult()
    campaign = load_optional_json(path_for(run_root, "rpg_campaign"))
    world_map = load_optional_json(path_for(run_root, "rpg_world_map"))
    if not isinstance(campaign, dict):
        result.add("error", "missing_artifact", "Missing workspace/rpg/rpg-campaign.json.", "workspace/rpg/rpg-campaign.json")
        campaign = {}
    if not isinstance(world_map, dict):
        result.add("error", "missing_artifact", "Missing workspace/rpg/world-map.json.", "workspace/rpg/world-map.json")
        world_map = {}

    maps = load_maps(run_root, result)
    if not maps:
        result.add("error", "missing_artifact", "Missing RPG map files under workspace/rpg/maps/*.map.json.", "workspace/rpg/maps")
    map_ids = validate_unique_ids(result, maps, "map", "workspace/rpg/maps")

    collections: dict[str, list[Json]] = {}
    source_paths: dict[str, str | None] = {}
    for name in COLLECTION_FILES:
        collection, source_path = load_collection(run_root, name)
        collections[name] = collection
        source_paths[name] = source_path
    actor_ids = validate_unique_ids(result, collections["actors"], "actor", source_paths["actors"] or "workspace/rpg/actors.json")
    enemy_ids = validate_unique_ids(result, collections["enemies"], "enemy", source_paths["enemies"] or "workspace/rpg/enemies.json")
    quest_ids = validate_unique_ids(result, collections["quests"], "quest", source_paths["quests"] or "workspace/rpg/quests.json")
    dialogue_ids = validate_unique_ids(result, collections["npc_dialogue"], "dialogue", source_paths["npc_dialogue"] or "workspace/rpg/npc-dialogue.json")

    if not actor_ids:
        result.add("error", "missing_party", "RPG target needs at least one actor.", "workspace/rpg/actors.json")
    for index, actor in enumerate(collections["actors"]):
        if not actor_stats_valid(actor):
            result.add("error", "actor_stats", "Actor needs positive hp and attack stats.", f"workspace/rpg/actors.json[{index}].stats")
    for index, enemy in enumerate(collections["enemies"]):
        if not actor_stats_valid(enemy):
            result.add("error", "enemy_stats", "Enemy needs positive hp and attack stats.", f"workspace/rpg/enemies.json[{index}].stats")

    start_map_id = campaign.get("start_map_id") or world_map.get("start_map_id") or (maps[0].get("id") if maps else None)
    if start_map_id not in map_ids:
        result.add("error", "start_map", "RPG campaign start_map_id must reference a map.", "workspace/rpg/rpg-campaign.json.start_map_id")
    start_position = campaign.get("start_position") if isinstance(campaign.get("start_position"), dict) else {}
    if not isinstance(start_position.get("x"), int) or not isinstance(start_position.get("y"), int):
        start_position = {"x": 1, "y": 1}
        result.add("warning", "start_position", "Missing start_position; defaulted to {x:1,y:1}.", "workspace/rpg/rpg-campaign.json.start_position")

    battle_events = 0
    for map_index, game_map in enumerate(maps):
        for event_index, event in enumerate(as_list(game_map.get("events"))):
            event_type = str(event.get("type") or "")
            if event_type in ("battle", "encounter"):
                battle_events += 1
                enemy_id = event.get("enemy_id")
                encounter_id = event.get("encounter_id")
                if enemy_id and enemy_id not in enemy_ids:
                    result.add("error", "enemy_reference", f"Battle event references missing enemy: {enemy_id}", f"workspace/rpg/maps[{map_index}].events[{event_index}].enemy_id")
                if not enemy_id and not encounter_id and not enemy_ids:
                    result.add("error", "battle_reference", "Battle event needs enemy_id, encounter_id, or an enemy roster.", f"workspace/rpg/maps[{map_index}].events[{event_index}]")
            dialogue_id = event.get("dialogue_id")
            if isinstance(dialogue_id, str) and dialogue_id not in dialogue_ids:
                result.add("warning", "dialogue_reference", f"Event references missing dialogue: {dialogue_id}", f"workspace/rpg/maps[{map_index}].events[{event_index}].dialogue_id")
            quest_id = event.get("quest_id")
            if isinstance(quest_id, str) and quest_id not in quest_ids:
                result.add("warning", "quest_reference", f"Event references missing quest: {quest_id}", f"workspace/rpg/maps[{map_index}].events[{event_index}].quest_id")
    if battle_events and not enemy_ids:
        result.add("error", "missing_enemies", "Battle events require at least one enemy.", "workspace/rpg/enemies.json")

    asset_refs: set[str] = set()
    collect_asset_refs(campaign, asset_refs)
    collect_asset_refs(world_map, asset_refs)
    collect_asset_refs(maps, asset_refs)
    collect_asset_refs(collections, asset_refs)

    party = as_list(campaign.get("party"))
    if not party and actor_ids:
        party = [sorted(actor_ids)[0]]
    for index, actor_id in enumerate(party):
        if isinstance(actor_id, str) and actor_id not in actor_ids:
            result.add("error", "party_reference", f"Party references missing actor: {actor_id}", f"workspace/rpg/rpg-campaign.json.party[{index}]")

    manifest: Json = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "compile_rpg_manifest.py"},
        "target": "web-rpg",
        "title": campaign.get("title") or world_map.get("title") or "Generated RPG",
        "start_map_id": start_map_id,
        "start_position": start_position,
        "party": party,
        "campaign": campaign,
        "world_map": world_map,
        "maps": maps,
        "asset_refs": sorted(asset_refs),
        **collections,
    }
    coverage = {
        "status": "has_gaps" if result.status == "fail" else "clear",
        "map_count": len(maps),
        "event_count": sum(len(as_list(game_map.get("events"))) for game_map in maps),
        "battle_event_count": battle_events,
        "actor_count": len(collections["actors"]),
        "enemy_count": len(collections["enemies"]),
        "quest_count": len(collections["quests"]),
        "asset_ref_count": len(asset_refs),
        "source_paths": {key: value for key, value in source_paths.items() if value},
    }
    write_json(path_for(run_root, "rpg_manifest"), manifest)
    report = result.to_json()
    write_json(path_for(run_root, "rpg_validation_report"), report)
    write_json(path_for(run_root, "rpg_coverage_report"), coverage)
    return manifest, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    _, report = compile_rpg_manifest(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
