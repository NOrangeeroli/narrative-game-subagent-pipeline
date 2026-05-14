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
    "scene_scripts": ("scene-scripts.json", ("scene_scripts", "scenes", "scripts")),
}

ASSET_PREFIXES = (
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
    "bgm.",
    "sfx.",
    "voice.",
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


def valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_collision_shapes(value: Any, width: int, height: int, result: ValidationResult, path: str) -> list[Json]:
    shapes: list[Json] = []
    for index, shape in enumerate(as_list(value)):
        if not isinstance(shape, dict):
            result.add("warning", "collision_shape", "Collision shape must be an object; skipped.", f"{path}[{index}]")
            continue
        shape_type = shape.get("type")
        if shape_type == "polygon":
            points = shape.get("points")
            if not isinstance(points, list) or len(points) < 3:
                result.add("warning", "collision_shape", "Polygon collision shape needs at least three points; skipped.", f"{path}[{index}].points")
                continue
            normalized_points = []
            valid = True
            for point_index, point in enumerate(points):
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or not isinstance(point[0], (int, float))
                    or not isinstance(point[1], (int, float))
                ):
                    result.add("warning", "collision_shape", "Polygon point must be [x, y]; skipped shape.", f"{path}[{index}].points[{point_index}]")
                    valid = False
                    break
                normalized_points.append([max(0, min(width, float(point[0]))), max(0, min(height, float(point[1])))])
            if valid:
                shapes.append({**shape, "points": normalized_points})
            continue
        if shape_type == "rect":
            if all(isinstance(shape.get(key), (int, float)) for key in ("x", "y", "w", "h")):
                shapes.append({
                    **shape,
                    "x": max(0, min(width, float(shape["x"]))),
                    "y": max(0, min(height, float(shape["y"]))),
                    "w": max(0, min(width, float(shape["w"]))),
                    "h": max(0, min(height, float(shape["h"]))),
                })
            else:
                result.add("warning", "collision_shape", "Rect collision shape needs x, y, w, h; skipped.", f"{path}[{index}]")
            continue
        result.add("warning", "collision_shape", f"Unsupported collision shape type: {shape_type}", f"{path}[{index}].type")
    return shapes


def load_boundary_payload(run_root: Path, map_payload: Json, map_path: Path) -> tuple[Any, str | None]:
    candidates: list[Path] = []
    boundary_file = map_payload.get("boundary_file") or map_payload.get("boundaries_file")
    if isinstance(boundary_file, str) and boundary_file:
        candidates.append((map_path.parent / boundary_file).resolve())
        candidates.append((run_root / boundary_file).resolve())
    map_id = map_payload.get("id")
    stem = map_path.name.removesuffix(".map.json")
    candidates.append(run_root / "workspace" / "rpg" / "boundaries" / f"{stem}.boundaries.json")
    if isinstance(map_id, str):
        candidates.append(run_root / "workspace" / "rpg" / "boundaries" / f"{map_id}.boundaries.json")
        if map_id.startswith("map."):
            candidates.append(run_root / "workspace" / "rpg" / "boundaries" / f"{map_id.removeprefix('map.')}.boundaries.json")
    for candidate in candidates:
        if candidate.exists():
            return load_optional_json(candidate), str(candidate.relative_to(run_root))
    return None, None


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
        payload["coordinate_system"] = "pixels"
        width = payload.get("width")
        height = payload.get("height")
        default_width = 1280
        default_height = 720
        if not isinstance(width, int):
            width = default_width
            payload["width"] = width
            result.add("warning", "map_width", f"Map width missing; normalized to {default_width}.", f"{relative}.width")
        elif width < 64:
            result.add("error", "map_width", "Pixel-native map width must be at least 64 pixels; tile-sized maps are not supported.", f"{relative}.width")
        if not isinstance(height, int):
            height = default_height
            payload["height"] = height
            result.add("warning", "map_height", f"Map height missing; normalized to {default_height}.", f"{relative}.height")
        elif height < 64:
            result.add("error", "map_height", "Pixel-native map height must be at least 64 pixels; tile-sized maps are not supported.", f"{relative}.height")
        layers = payload.get("layers") if isinstance(payload.get("layers"), dict) else {}
        ground = layers.get("ground") if isinstance(layers.get("ground"), list) else []
        collision = layers.get("collision") if isinstance(layers.get("collision"), list) else []
        payload["layers"] = {**layers, "ground": ground, "collision": collision}
        shape_source = payload.get("collision_shapes")
        boundary_payload, boundary_source = load_boundary_payload(run_root, payload, path)
        if isinstance(boundary_payload, dict):
            shape_source = boundary_payload.get("collision_shapes") or boundary_payload.get("shapes") or shape_source
            payload["boundary_source_path"] = boundary_source
            if isinstance(boundary_payload.get("walkable_mask_ref"), str):
                payload["walkable_mask_ref"] = boundary_payload["walkable_mask_ref"]
            if isinstance(boundary_payload.get("boundary_source"), dict):
                payload["boundary_source"] = boundary_payload["boundary_source"]
            if isinstance(boundary_payload.get("walkable_hint"), dict):
                payload["walkable_hint"] = boundary_payload["walkable_hint"]
        elif boundary_payload is not None:
            result.add("warning", "boundary_json", "Boundary payload must be an object; ignored.", boundary_source or relative)
        payload["collision_shapes"] = normalize_collision_shapes(shape_source, width, height, result, f"{relative}.collision_shapes")
        events = [event for event in as_list(payload.get("events")) if isinstance(event, dict)]
        for index, event in enumerate(events):
            if not isinstance(event.get("id"), str):
                event["id"] = f"{map_id}.event.{index + 1}"
                result.add("warning", "event_id", "Map event id missing; inferred stable id.", f"{relative}.events[{index}].id")
            x = event.get("x")
            y = event.get("y")
            if not valid_number(x) or not valid_number(y) or x < 0 or y < 0 or x >= width or y >= height:
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


def collect_item_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            collect_item_refs(item, refs)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        if key in {"item_id", "reward_item_id"} and isinstance(item, str):
            refs.add(item)
        elif key in {"required_items", "item_ids"}:
            refs.update(entry for entry in as_list(item) if isinstance(entry, str) and entry)
        elif key in {"inventory", "inventory_delta", "initial_inventory"} and isinstance(item, dict):
            refs.update(entry for entry in item if isinstance(entry, str) and entry)
        collect_item_refs(item, refs)


def collect_item_consumers(value: Any, refs: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            collect_item_consumers(item, refs)
        return
    if not isinstance(value, dict):
        return
    conditions = value.get("conditions")
    if isinstance(conditions, dict) and isinstance(conditions.get("inventory"), dict):
        refs.update(item_id for item_id in conditions["inventory"] if isinstance(item_id, str) and item_id)
    if isinstance(value.get("required_items"), list):
        refs.update(item_id for item_id in value["required_items"] if isinstance(item_id, str) and item_id)
    beat_kind = value.get("kind") or value.get("type")
    if beat_kind in {"take_item", "consume_item", "use_item"} and isinstance(value.get("item_id"), str):
        refs.add(value["item_id"])
    inventory_delta = value.get("inventory_delta")
    if isinstance(inventory_delta, dict):
        refs.update(item_id for item_id, delta in inventory_delta.items() if isinstance(item_id, str) and number_like(delta) < 0)
    for item in value.values():
        collect_item_consumers(item, refs)


def number_like(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def has_story_lines(value: Any) -> bool:
    return isinstance(value, list) and any(
        (isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text").strip())
        or (isinstance(item, str) and item.strip())
        for item in value
    )


def is_story_item(item: Json) -> bool:
    if isinstance(item.get("story_role"), str) and item["story_role"].strip():
        return True
    if isinstance(item.get("quest_id"), str) and item["quest_id"].strip():
        return True
    for key in ("state_change_ids", "story_unit_ids", "public_node_ids", "public_edge_ids"):
        if any(isinstance(entry, str) and entry.strip() for entry in as_list(item.get(key))):
            return True
    return isinstance(item.get("on_pickup"), dict) or isinstance(item.get("on_inspect"), dict)


def validate_story_items(result: ValidationResult, items: list[Json], consumed_items: set[str], source_path: str) -> None:
    for index, item in enumerate(items):
        item_id_value = item_id(item) or f"items[{index}]"
        item_path = f"{source_path}[{index}]"
        if not is_story_item(item):
            continue
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            result.add("warning", "story_item_description", "Story item should include a readable description.", f"{item_path}.description")
        if not has_story_lines(item.get("inspect_lines")) and not isinstance(item.get("on_inspect"), dict):
            result.add("warning", "story_item_inspect", "Story item should include inspect_lines or on_inspect so it can be read from inventory.", item_path)
        if not isinstance(item.get("on_pickup"), dict) and not isinstance(item.get("on_inspect"), dict):
            result.add("warning", "story_item_outcome", "Story item should define on_pickup or on_inspect when it changes quests, flags, or route state.", item_path)
        if item_id_value not in consumed_items:
            result.add("warning", "story_item_unused", "Story item is not consumed by a quest requirement, inventory gate, scene beat, or inventory outcome.", item_path)


def actor_stats_valid(actor: Json) -> bool:
    stats = actor.get("stats") if isinstance(actor.get("stats"), dict) else actor
    return all(isinstance(stats.get(key), (int, float)) and stats[key] > 0 for key in ("hp", "attack"))


def validate_position(result: ValidationResult, value: Any, path: str) -> Json | None:
    if not isinstance(value, dict):
        result.add("error", "position", "Position must be an object with numeric x and y.", path)
        return None
    if not valid_number(value.get("x")) or not valid_number(value.get("y")):
        result.add("error", "position", "Position must include numeric x and y.", path)
        return None
    return value


def build_map_event_ids(maps: list[Json]) -> tuple[set[str], dict[str, set[str]], dict[str, Json]]:
    all_event_ids: set[str] = set()
    event_ids_by_map: dict[str, set[str]] = {}
    maps_by_id: dict[str, Json] = {}
    for game_map in maps:
        map_id = item_id(game_map)
        if not map_id:
            continue
        maps_by_id[map_id] = game_map
        event_ids: set[str] = set()
        for event in as_list(game_map.get("events")):
            event_id = item_id(event)
            if event_id:
                all_event_ids.add(event_id)
                event_ids.add(event_id)
        event_ids_by_map[map_id] = event_ids
    return all_event_ids, event_ids_by_map, maps_by_id


def validate_scene_position(result: ValidationResult, value: Any, game_map: Json | None, path: str) -> None:
    position = validate_position(result, value, path)
    if not position or not game_map:
        return
    width = game_map.get("width")
    height = game_map.get("height")
    x = position.get("x")
    y = position.get("y")
    if valid_number(width) and valid_number(height) and valid_number(x) and valid_number(y):
        if x < 0 or y < 0 or x >= width or y >= height:
            result.add("warning", "scene_position", "Scene position falls outside the referenced map bounds.", path)


def validate_scene_scripts(
    result: ValidationResult,
    scenes: list[Json],
    map_ids: set[str],
    maps_by_id: dict[str, Json],
    all_event_ids: set[str],
    event_ids_by_map: dict[str, set[str]],
    source_path: str,
) -> None:
    allowed_triggers = {"on_entry", "interact", "touch", "manual", "after_event"}
    allowed_beats = {
        "dialogue",
        "line",
        "move_actor",
        "set_actor_position",
        "teleport_actor",
        "place_actor",
        "face_actor",
        "face_direction",
        "wait",
        "set_flag",
        "activate_quest",
        "complete_quest",
        "set_quest_state",
        "give_item",
        "take_item",
        "inventory_delta",
        "show_actor",
        "hide_actor",
        "show_event",
        "hide_event",
        "transfer",
        "transfer_map",
        "play_sfx",
        "log",
        "end_scene",
    }
    for index, scene in enumerate(scenes):
        scene_path = f"{source_path}[{index}]"
        scene_id = item_id(scene)
        trigger = scene.get("trigger")
        if not isinstance(trigger, dict):
            result.add("error", "scene_trigger", "Scene script needs a trigger object.", f"{scene_path}.trigger")
            trigger = {}
        trigger_kind = trigger.get("kind") or trigger.get("type")
        if trigger_kind not in allowed_triggers:
            result.add("error", "scene_trigger", f"Scene trigger kind must be one of {sorted(allowed_triggers)}.", f"{scene_path}.trigger.kind")
        scene_map_id = scene.get("map_id") or trigger.get("map_id")
        if isinstance(scene_map_id, str) and scene_map_id not in map_ids:
            result.add("error", "scene_map_reference", f"Scene script references missing map: {scene_map_id}", f"{scene_path}.trigger.map_id")
        if trigger_kind in {"on_entry", "touch", "interact"} and not isinstance(scene_map_id, str):
            result.add("warning", "scene_map_reference", "Map-triggered scene should specify trigger.map_id or map_id.", f"{scene_path}.trigger.map_id")
        trigger_event_id = trigger.get("event_id")
        if isinstance(trigger_event_id, str):
            if trigger_event_id not in all_event_ids:
                result.add("warning", "scene_event_reference", f"Scene trigger references missing event: {trigger_event_id}", f"{scene_path}.trigger.event_id")
            elif isinstance(scene_map_id, str) and trigger_event_id not in event_ids_by_map.get(scene_map_id, set()):
                result.add("warning", "scene_event_reference", "Scene trigger event is not on the referenced map.", f"{scene_path}.trigger.event_id")

        actor_ids: set[str] = {"player", "hero"}
        for actor_index, actor in enumerate(as_list(scene.get("actors"))):
            if not isinstance(actor, dict):
                result.add("warning", "scene_actor", "Scene actor binding must be an object; skipped.", f"{scene_path}.actors[{actor_index}]")
                continue
            actor_id = actor.get("actor_id")
            if isinstance(actor_id, str) and actor_id:
                actor_ids.add(actor_id)
            else:
                result.add("warning", "scene_actor", "Scene actor binding should include actor_id.", f"{scene_path}.actors[{actor_index}].actor_id")
            event_id = actor.get("event_id")
            if isinstance(event_id, str) and event_id not in all_event_ids:
                result.add("warning", "scene_actor_event", f"Scene actor references missing map event: {event_id}", f"{scene_path}.actors[{actor_index}].event_id")
            actor_map_id = actor.get("map_id") or scene_map_id
            if isinstance(event_id, str) and isinstance(actor_map_id, str) and event_id not in event_ids_by_map.get(actor_map_id, set()):
                result.add("warning", "scene_actor_event", "Scene actor event is not on the referenced map.", f"{scene_path}.actors[{actor_index}].event_id")
            if "x" in actor or "y" in actor:
                validate_scene_position(result, {"x": actor.get("x"), "y": actor.get("y")}, maps_by_id.get(actor_map_id), f"{scene_path}.actors[{actor_index}]")

        beats = as_list(scene.get("beats"))
        if not beats:
            result.add("warning", "scene_beats", "Scene script has no beats.", f"{scene_path}.beats")
            continue
        for beat_index, beat in enumerate(beats):
            beat_path = f"{scene_path}.beats[{beat_index}]"
            if not isinstance(beat, dict):
                result.add("error", "scene_beat", "Scene beat must be an object.", beat_path)
                continue
            beat_kind = beat.get("kind") or beat.get("type")
            if beat_kind not in allowed_beats:
                result.add("warning", "scene_beat_kind", f"Unsupported scene beat kind for current Web RPG runtime: {beat_kind}", f"{beat_path}.kind")
            if beat_kind in {"dialogue", "line"}:
                if not isinstance(beat.get("text"), str) or not beat.get("text"):
                    result.add("error", "scene_dialogue", "Dialogue scene beat needs text.", f"{beat_path}.text")
            actor_id = beat.get("actor_id") or beat.get("speaker_actor_id")
            if isinstance(actor_id, str) and actor_id not in actor_ids:
                result.add("warning", "scene_actor_reference", f"Beat references actor without an explicit scene binding: {actor_id}", f"{beat_path}.actor_id")
            if beat_kind in {"move_actor", "set_actor_position", "teleport_actor", "place_actor"}:
                target = beat.get("to") if isinstance(beat.get("to"), dict) else beat
                validate_scene_position(result, target, maps_by_id.get(scene_map_id), f"{beat_path}.to")


def campaign_entry_points(campaign: Json, start_map_id: Any, start_position: Json, party: list[Any]) -> list[Json]:
    entries = as_list(campaign.get("entry_points"))
    if entries:
        return [entry for entry in entries if isinstance(entry, dict)]
    return [{
        "id": "entry.default",
        "title": "Start",
        "description": "Begin from the campaign default start.",
        "start_map_id": start_map_id,
        "start_position": start_position,
        "party": party,
    }]


def sanitize_asset_token(value: Any) -> str:
    text = str(value or "").strip().removeprefix("map.")
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._-")
    return cleaned or "default"


def ensure_map_bgm_assets(maps: list[Json]) -> None:
    for game_map in maps:
        if not isinstance(game_map.get("bgm_asset_id"), str):
            game_map["bgm_asset_id"] = f"bgm.{sanitize_asset_token(game_map.get('id'))}"


def collect_trace_tokens(value: Any, keys: set[str]) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                if isinstance(item, str) and item:
                    tokens.add(item)
                elif isinstance(item, list):
                    tokens.update(str(entry) for entry in item if isinstance(entry, str) and entry)
                elif isinstance(item, dict):
                    tokens.update(str(entry) for entry in item.values() if isinstance(entry, str) and entry)
            tokens.update(collect_trace_tokens(item, keys))
    elif isinstance(value, list):
        for item in value:
            tokens.update(collect_trace_tokens(item, keys))
    return tokens


def check_rpg_overlay_trace(run_root: Path, manifest: Json, result: ValidationResult) -> Json:
    overlay_plan = load_optional_json(path_for(run_root, "rpg_overlay_plan"))
    postdesign_slices = load_optional_json(path_for(run_root, "rpg_postdesign_slices"))
    freeze = load_optional_json(path_for(run_root, "rpg_narrative_freeze"))
    if not isinstance(overlay_plan, dict) and not isinstance(postdesign_slices, dict) and not isinstance(freeze, dict):
        return {"status": "not_applicable"}

    trace_summary: Json = {"status": "warning_only"}
    if isinstance(overlay_plan, dict) and not isinstance(postdesign_slices, dict):
        result.add(
            "warning",
            "missing_rpg_postdesign_slices",
            "RPG overlay plan exists, but rpg-postdesign-slices.json is missing.",
            "workspace/design_layer_rpg/rpg-postdesign-slices.json",
        )
        trace_summary["postdesign_slices"] = "missing"

    if isinstance(freeze, dict):
        try:
            from freeze_narrative import verify_narrative_freeze

            freeze_status = verify_narrative_freeze(run_root)
        except Exception as exc:  # noqa: BLE001
            freeze_status = {"status": "fail", "findings": [{"kind": "narrative_freeze_check_error", "message": str(exc)}]}
        trace_summary["narrative_freeze_status"] = freeze_status.get("status")
        for finding in as_list(freeze_status.get("findings")):
            if isinstance(finding, dict):
                result.add(
                    "warning",
                    str(finding.get("kind") or "narrative_freeze"),
                    str(finding.get("message") or "Narrative freeze check failed."),
                    str(finding.get("path") or "workspace/design_layer_rpg/narrative-freeze.json"),
                )
    elif isinstance(overlay_plan, dict):
        result.add(
            "warning",
            "missing_narrative_freeze",
            "RPG overlay plan exists, but narrative-freeze.json is missing.",
            "workspace/design_layer_rpg/narrative-freeze.json",
        )

    if not isinstance(postdesign_slices, dict):
        return trace_summary

    slices = [item for item in as_list(postdesign_slices.get("slices")) if isinstance(item, dict)]
    expected_slice_ids = {item.get("slice_id") for item in slices if isinstance(item.get("slice_id"), str)}
    expected_public_node_ids = {
        node_id
        for item in slices
        for node_id in as_list(item.get("public_node_ids"))
        if isinstance(node_id, str)
    }
    expected_story_unit_ids = {
        story_id
        for item in slices
        for story_id in as_list(item.get("source_story_unit_ids"))
        if isinstance(story_id, str)
    }
    slice_trace = collect_trace_tokens(manifest, {"slice_id", "slice_ids", "source_slice_id", "source_slice_ids", "rpg_slice_id", "rpg_slice_ids"})
    public_node_trace = collect_trace_tokens(manifest, {"public_node_id", "public_node_ids", "source_node_id", "source_node_ids"})
    story_unit_trace = collect_trace_tokens(manifest, {"story_unit_id", "story_unit_ids", "source_story_unit_id", "source_story_unit_ids"})

    if expected_slice_ids and not (slice_trace & expected_slice_ids):
        result.add(
            "warning",
            "missing_rpg_slice_trace",
            "RPG postdesign slices exist, but compiled RPG artifacts do not trace back to slice ids.",
            "workspace/rpg",
        )
    if expected_public_node_ids and not (public_node_trace & expected_public_node_ids):
        result.add(
            "warning",
            "missing_public_node_trace",
            "RPG postdesign slices include public node ids, but compiled RPG artifacts do not trace back to public nodes.",
            "workspace/rpg",
        )
    if expected_story_unit_ids and not (story_unit_trace & expected_story_unit_ids):
        result.add(
            "warning",
            "missing_story_unit_trace",
            "RPG postdesign slices include story unit ids, but compiled RPG artifacts do not trace back to story units.",
            "workspace/rpg",
        )

    trace_summary.update({
        "slice_count": len(slices),
        "expected_slice_trace_count": len(expected_slice_ids),
        "found_slice_trace_count": len(slice_trace & expected_slice_ids),
        "expected_public_node_trace_count": len(expected_public_node_ids),
        "found_public_node_trace_count": len(public_node_trace & expected_public_node_ids),
        "expected_story_unit_trace_count": len(expected_story_unit_ids),
        "found_story_unit_trace_count": len(story_unit_trace & expected_story_unit_ids),
    })
    return trace_summary


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
    ensure_map_bgm_assets(maps)
    map_ids = validate_unique_ids(result, maps, "map", "workspace/rpg/maps")
    all_event_ids, event_ids_by_map, maps_by_id = build_map_event_ids(maps)

    collections: dict[str, list[Json]] = {}
    source_paths: dict[str, str | None] = {}
    for name in COLLECTION_FILES:
        collection, source_path = load_collection(run_root, name)
        collections[name] = collection
        source_paths[name] = source_path
    actor_ids = validate_unique_ids(result, collections["actors"], "actor", source_paths["actors"] or "workspace/rpg/actors.json")
    item_ids = validate_unique_ids(result, collections["items"], "item", source_paths["items"] or "workspace/rpg/items.json")
    enemy_ids = validate_unique_ids(result, collections["enemies"], "enemy", source_paths["enemies"] or "workspace/rpg/enemies.json")
    quest_ids = validate_unique_ids(result, collections["quests"], "quest", source_paths["quests"] or "workspace/rpg/quests.json")
    dialogue_ids = validate_unique_ids(result, collections["npc_dialogue"], "dialogue", source_paths["npc_dialogue"] or "workspace/rpg/npc-dialogue.json")
    validate_unique_ids(result, collections["scene_scripts"], "scene script", source_paths["scene_scripts"] or "workspace/rpg/scene-scripts.json")
    validate_scene_scripts(
        result,
        collections["scene_scripts"],
        map_ids,
        maps_by_id,
        all_event_ids,
        event_ids_by_map,
        source_paths["scene_scripts"] or "workspace/rpg/scene-scripts.json",
    )

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
    if not valid_number(start_position.get("x")) or not valid_number(start_position.get("y")):
        start_position = {"x": 180, "y": 520}
        result.add("warning", "start_position", "Missing start_position; defaulted to pixel position {x:180,y:520}.", "workspace/rpg/rpg-campaign.json.start_position")

    battle_events = 0
    for map_index, game_map in enumerate(maps):
        for event_index, event in enumerate(as_list(game_map.get("events"))):
            event_type = str(event.get("type") or "")
            event_path = f"workspace/rpg/maps[{map_index}].events[{event_index}]"
            if event_type in ("battle", "encounter"):
                battle_events += 1
                enemy_id = event.get("enemy_id")
                encounter_id = event.get("encounter_id")
                if enemy_id and enemy_id not in enemy_ids:
                    result.add("error", "enemy_reference", f"Battle event references missing enemy: {enemy_id}", f"{event_path}.enemy_id")
                if not enemy_id and not encounter_id and not enemy_ids:
                    result.add("error", "battle_reference", "Battle event needs enemy_id, encounter_id, or an enemy roster.", event_path)
            if event_type in ("pickup", "item"):
                event_item_id = event.get("item_id")
                if not isinstance(event_item_id, str) or not event_item_id:
                    result.add("warning", "item_reference", "Pickup event should reference item_id.", f"{event_path}.item_id")
                elif event_item_id not in item_ids:
                    result.add("warning", "item_reference", f"Pickup event references missing item: {event_item_id}", f"{event_path}.item_id")
            dialogue_id = event.get("dialogue_id")
            if isinstance(dialogue_id, str) and dialogue_id not in dialogue_ids:
                result.add("warning", "dialogue_reference", f"Event references missing dialogue: {dialogue_id}", f"{event_path}.dialogue_id")
            quest_id = event.get("quest_id")
            if isinstance(quest_id, str) and quest_id not in quest_ids:
                result.add("warning", "quest_reference", f"Event references missing quest: {quest_id}", f"{event_path}.quest_id")
    if battle_events and not enemy_ids:
        result.add("error", "missing_enemies", "Battle events require at least one enemy.", "workspace/rpg/enemies.json")

    referenced_items: set[str] = set()
    consumed_items: set[str] = set()
    for value in (
        campaign,
        world_map,
        maps,
        collections["quests"],
        collections["npc_dialogue"],
        collections["events"],
        collections["shops"],
        collections["rest_points"],
        collections["progression_rules"],
        collections["scene_scripts"],
    ):
        collect_item_refs(value, referenced_items)
        collect_item_consumers(value, consumed_items)
    for missing_item_id in sorted(referenced_items - item_ids):
        result.add("warning", "item_reference", f"Referenced item is not in items.json: {missing_item_id}", "workspace/rpg/items.json")
    validate_story_items(result, collections["items"], consumed_items, source_paths["items"] or "workspace/rpg/items.json")

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

    entry_points = campaign_entry_points(campaign, start_map_id, start_position, party)
    entry_ids: set[str] = set()
    for index, entry in enumerate(entry_points):
        entry_path = f"workspace/rpg/rpg-campaign.json.entry_points[{index}]"
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            result.add("error", "entry_point", "Entry point needs id.", f"{entry_path}.id")
        elif entry_id in entry_ids:
            result.add("error", "duplicate_id", f"Duplicate entry point id: {entry_id}", f"{entry_path}.id")
        else:
            entry_ids.add(entry_id)
        entry_map_id = entry.get("start_map_id", start_map_id)
        if entry_map_id not in map_ids:
            result.add("error", "entry_point_map", f"Entry point references missing map: {entry_map_id}", f"{entry_path}.start_map_id")
        validate_position(result, entry.get("start_position", start_position), f"{entry_path}.start_position")
        entry_party = as_list(entry.get("party")) or party
        for party_index, actor_id in enumerate(entry_party):
            if isinstance(actor_id, str) and actor_id not in actor_ids:
                result.add("error", "entry_point_party", f"Entry point party references missing actor: {actor_id}", f"{entry_path}.party[{party_index}]")
        for quest_index, quest_id in enumerate(as_list(entry.get("initial_quests"))):
            if isinstance(quest_id, str) and quest_id not in quest_ids:
                result.add("warning", "entry_point_quest", f"Entry point initial quest is not in quests: {quest_id}", f"{entry_path}.initial_quests[{quest_index}]")

    manifest: Json = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "compile_rpg_manifest.py"},
        "target": "web-rpg",
        "title": campaign.get("title") or world_map.get("title") or "Generated RPG",
        "start_map_id": start_map_id,
        "start_position": start_position,
        "entry_points": entry_points,
        "party": party,
        "campaign": campaign,
        "world_map": world_map,
        "maps": maps,
        "asset_refs": sorted(asset_refs),
        **collections,
    }
    overlay_trace = check_rpg_overlay_trace(run_root, manifest, result)
    coverage = {
        "status": "has_gaps" if result.status == "fail" else "clear",
        "map_count": len(maps),
        "event_count": sum(len(as_list(game_map.get("events"))) for game_map in maps),
        "battle_event_count": battle_events,
        "entry_point_count": len(entry_points),
        "actor_count": len(collections["actors"]),
        "item_count": len(collections["items"]),
        "enemy_count": len(collections["enemies"]),
        "quest_count": len(collections["quests"]),
        "scene_script_count": len(collections["scene_scripts"]),
        "asset_ref_count": len(asset_refs),
        "source_paths": {key: value for key, value in source_paths.items() if value},
        "rpg_overlay_trace": overlay_trace,
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
