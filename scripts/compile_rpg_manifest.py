#!/usr/bin/env python3
"""Compile post-design RPG artifacts into one runtime manifest."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
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
    "tile.",
    "sceneprop.",
    "sprite.",
    "battlebg.",
    "itemicon.",
    "skillicon.",
    "equipicon.",
    "mapprop.",
)

MAP_PROP_KINDS = {
    "fence": {"blocked": True, "asset": "mapprop.fence"},
    "barrel": {"blocked": True, "asset": "mapprop.barrel"},
    "crate": {"blocked": True, "asset": "mapprop.crate"},
    "chest": {"blocked": True, "asset": "mapprop.chest"},
    "flower": {"blocked": False, "asset": "mapprop.flower"},
    "rock": {"blocked": True, "asset": "mapprop.rock"},
    "tree": {"blocked": True, "asset": "mapprop.tree"},
    "tree_canopy": {"blocked": False, "asset": "mapprop.tree_canopy"},
    "house_small": {"blocked": True, "asset": "mapprop.house_small"},
    "house_big": {"blocked": True, "asset": "mapprop.house_big"},
    "roof": {"blocked": False, "asset": "mapprop.roof"},
    "bridge": {"blocked": False, "asset": "mapprop.bridge"},
}

HOUSE_KINDS = {"house_small", "house_big"}
NPC_KINDS = {"npc1", "npc2"}


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


def stable_slug(value: Any, fallback: str = "map") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("_")
    return cleaned or fallback


def rect_bounds(item: Json, result: ValidationResult, path: str) -> tuple[int, int, int, int] | None:
    values = [item.get(key) for key in ("x0", "y0", "x1", "y1")]
    if not all(isinstance(value, int) for value in values):
        result.add("error", "map_design_rect", "Map design rectangle needs integer x0, y0, x1, and y1.", path)
        return None
    x0, y0, x1, y1 = values
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def in_bounds(width: int, height: int, x: int, y: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def mark_rect(grid: list[list[Any]], width: int, height: int, item: Json, value: Any, result: ValidationResult, path: str) -> bool:
    bounds = rect_bounds(item, result, path)
    if bounds is None:
        return False
    x0, y0, x1, y1 = bounds
    if not in_bounds(width, height, x0, y0) or not in_bounds(width, height, x1, y1):
        result.add("error", "map_design_bounds", "Map design rectangle must be inside map bounds.", path)
        return False
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = value
    return True


def apply_path_design(ground: list[list[Any]], width: int, height: int, path_item: Json, result: ValidationResult, path: str) -> None:
    path_type = path_item.get("type", "rect")
    if path_type == "rect":
        mark_rect(ground, width, height, path_item, "path", result, path)
        return
    if path_type != "line":
        result.add("error", "map_design_path", f"Unsupported path type: {path_type!r}.", path)
        return
    x0 = path_item.get("x0")
    y0 = path_item.get("y0")
    x1 = path_item.get("x1")
    y1 = path_item.get("y1")
    if not all(isinstance(value, int) for value in (x0, y0, x1, y1)):
        result.add("error", "map_design_path", "Line path needs integer x0, y0, x1, and y1.", path)
        return
    if not in_bounds(width, height, x0, y0) or not in_bounds(width, height, x1, y1):
        result.add("error", "map_design_bounds", "Path endpoints must be inside map bounds.", path)
        return
    if x0 != x1 and y0 != y1:
        result.add("error", "map_design_path", "Line path supports horizontal or vertical lines only.", path)
        return
    radius = max(0, int(path_item.get("width", 1)) - 1)
    if x0 == x1:
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for dx in range(-radius, radius + 1):
                x = x0 + dx
                if in_bounds(width, height, x, y) and ground[y][x] not in ("water", "bridge"):
                    ground[y][x] = "path"
    else:
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for dy in range(-radius, radius + 1):
                y = y0 + dy
                if in_bounds(width, height, x, y) and ground[y][x] not in ("water", "bridge"):
                    ground[y][x] = "path"


def append_unique_event(events: list[Json], event: Json) -> None:
    event_id = event.get("id")
    if isinstance(event_id, str) and any(existing.get("id") == event_id for existing in events):
        return
    events.append(event)


def add_required_asset(payload: Json, asset_id: str) -> None:
    assets = payload.setdefault("required_assets", [])
    if isinstance(assets, list) and asset_id not in assets:
        assets.append(asset_id)


def ground_tokens(ground: list[list[Any]]) -> list[str]:
    tokens: set[str] = set()
    for row in ground:
        for cell in row:
            token = str(cell or "").strip()
            if token and token not in (".", "0", "void"):
                tokens.add(token)
    return sorted(tokens)


def terrain_tile_asset_id(map_id: str, terrain: str) -> str:
    map_slug = stable_slug(map_id.removeprefix("map."), "scene")
    terrain_slug = stable_slug(terrain, "terrain")
    return f"tile.{map_slug}.{terrain_slug}"


def attach_terrain_tile_assets(payload: Json, map_id: str) -> None:
    layers = payload.get("layers") if isinstance(payload.get("layers"), dict) else {}
    ground = layers.get("ground")
    if not isinstance(ground, list):
        return
    terrain_asset_ids = {
        terrain: terrain_tile_asset_id(map_id, terrain)
        for terrain in ground_tokens(ground)
    }
    if not terrain_asset_ids:
        return
    payload["terrain_asset_ids"] = terrain_asset_ids
    scene = payload.get("scene")
    if isinstance(scene, dict):
        scene["terrain_asset_ids"] = terrain_asset_ids
    for asset_id in terrain_asset_ids.values():
        add_required_asset(payload, asset_id)


def scene_prop_asset_id(map_id: str, asset: Any) -> str:
    map_slug = stable_slug(map_id.removeprefix("map."), "scene")
    asset_slug = stable_slug(str(asset or "prop").removeprefix("mapprop.").removeprefix("sceneprop."), "prop")
    return f"sceneprop.{map_slug}.{asset_slug}"


def localize_scene_prop_assets(payload: Json, scene: Json, map_id: str) -> None:
    props = scene.get("props")
    if not isinstance(props, list):
        return
    for prop in props:
        if not isinstance(prop, dict):
            continue
        asset_name = prop.get("asset") or str(prop.get("asset_id") or "").split(".")[-1]
        localized_id = scene_prop_asset_id(map_id, asset_name)
        original_id = prop.get("asset_id")
        if isinstance(original_id, str) and original_id != localized_id:
            prop.setdefault("base_asset_id", original_id)
        prop["asset_id"] = localized_id
        add_required_asset(payload, localized_id)


def scene_terrain_asset_name(game_map: Json, terrain: Any) -> str:
    terrain_name = str(terrain or "grass")
    terrain_asset_ids = game_map.get("terrain_asset_ids")
    if not isinstance(terrain_asset_ids, dict):
        scene = game_map.get("scene") if isinstance(game_map.get("scene"), dict) else {}
        terrain_asset_ids = scene.get("terrain_asset_ids")
    if isinstance(terrain_asset_ids, dict) and isinstance(terrain_asset_ids.get(terrain_name), str):
        return terrain_asset_ids[terrain_name]
    return terrain_name


def path_design_region(item: Json, index: int, width: int | None = None, height: int | None = None) -> Json | None:
    path_type = item.get("type", "rect")
    if path_type == "rect":
        values = [item.get(key) for key in ("x0", "y0", "x1", "y1")]
        if not all(isinstance(value, int) for value in values):
            return None
        x0, y0, x1, y1 = min(values[0], values[2]), min(values[1], values[3]), max(values[0], values[2]), max(values[1], values[3])
    elif path_type == "line":
        values = [item.get(key) for key in ("x0", "y0", "x1", "y1")]
        if not all(isinstance(value, int) for value in values):
            return None
        path_width = max(1, int(item.get("width", 1)))
        radius = path_width - 1
        x0, y0, x1, y1 = min(values[0], values[2]), min(values[1], values[3]), max(values[0], values[2]), max(values[1], values[3])
        if values[0] == values[2]:
            x0 -= radius
            x1 += radius
        elif values[1] == values[3]:
            y0 -= radius
            y1 += radius
        else:
            return None
    else:
        return None
    if width is not None:
        x0 = max(0, x0)
        x1 = min(width - 1, x1)
    if height is not None:
        y0 = max(0, y0)
        y1 = min(height - 1, y1)
    if x0 > x1 or y0 > y1:
        return None
    return {
        "id": f"path_{index + 1}",
        "name": item.get("name") or f"Path {index + 1}",
        "x": x0,
        "y": y0,
        "w": x1 - x0 + 1,
        "h": y1 - y0 + 1,
        "floor": item.get("floor") or "path",
    }


def rect_item_to_scene_rect(item: Json, index: int, *, kind: str, key: str) -> Json | None:
    values = [item.get(name) for name in ("x0", "y0", "x1", "y1")]
    if not all(isinstance(value, int) for value in values):
        return None
    x0, y0, x1, y1 = min(values[0], values[2]), min(values[1], values[3]), max(values[0], values[2]), max(values[1], values[3])
    return {
        "id": f"{kind}_{index + 1}",
        "x": x0,
        "y": y0,
        "w": x1 - x0 + 1,
        "h": y1 - y0 + 1,
        key: item.get(key) or kind,
    }


def scene_spec_for_map(game_map: Json) -> Json:
    map_id = str(game_map.get("id") or "map")
    design = game_map.get("map_design") if isinstance(game_map.get("map_design"), dict) else game_map.get("layout_spec")
    design = design if isinstance(design, dict) else {}
    width = int(game_map.get("width") or 40)
    height = int(game_map.get("height") or 30)
    spawn = game_map.get("player_spawn") if isinstance(game_map.get("player_spawn"), dict) else design.get("player_spawn")
    if not isinstance(spawn, dict):
        spawn = {"x": 1, "y": 1}
    regions: list[Json] = []
    for index, region in enumerate(as_list(design.get("regions"))):
        if isinstance(region, dict):
            normalized = dict(region)
            normalized.setdefault("id", f"region_{index + 1}")
            normalized["floor"] = scene_terrain_asset_name(game_map, normalized.get("floor") or "grass")
            regions.append(normalized)
    for index, item in enumerate(as_list(design.get("paths"))):
        if isinstance(item, dict):
            region = path_design_region(item, index, width, height)
            if region:
                region["floor"] = scene_terrain_asset_name(game_map, region.get("floor") or "path")
                regions.append(region)

    barriers: list[Json] = []
    openings: list[Json] = []
    for index, item in enumerate(as_list(design.get("terrain"))):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        if kind == "water":
            barrier = rect_item_to_scene_rect(item, index, kind="water", key="asset")
            if barrier:
                barrier["name"] = item.get("name") or "Water"
                barrier["asset"] = scene_terrain_asset_name(game_map, item.get("asset") or "water")
                barriers.append(barrier)
        elif kind == "bridge":
            opening = rect_item_to_scene_rect(item, index, kind="bridge", key="floor")
            if opening:
                opening["floor"] = scene_terrain_asset_name(game_map, item.get("floor") or "bridge")
                openings.append(opening)

    props = []
    scene = game_map.get("scene") if isinstance(game_map.get("scene"), dict) else {}
    for prop in as_list(scene.get("props")):
        if not isinstance(prop, dict):
            continue
        scene_prop = {
            key: value
            for key, value in prop.items()
            if key in {
                "id",
                "asset",
                "asset_id",
                "base_asset_id",
                "region",
                "name",
                "x",
                "y",
                "w",
                "h",
                "blocking",
                "layer",
                "interaction",
                "lines",
                "render_scale",
                "item_id",
                "event_id",
            }
        }
        if isinstance(scene_prop.get("asset_id"), str):
            scene_prop.setdefault("base_asset", scene_prop.get("asset"))
            scene_prop["asset"] = scene_prop["asset_id"]
        props.append(scene_prop)

    return {
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "compile_rpg_manifest.py",
            "source_map_id": map_id,
            "source_path": game_map.get("source_path"),
            "compatible_with": "rpg-map-designer scene_spec_schema.md",
        },
        "map": {
            "w": width,
            "h": height,
            "tile": int(scene.get("tile") or 48),
            "title": game_map.get("title") or map_id,
            "base_floor": scene_terrain_asset_name(game_map, "grass"),
        },
        "player_spawn": {"x": int(spawn.get("x", 1)), "y": int(spawn.get("y", 1))},
        "regions": regions,
        "barriers": barriers,
        "openings": openings,
        "props": props,
        "validation": {"require_interaction_per_region": False},
    }


def scene_asset_prompt(game_map: Json, asset_id: str, role: str, label: str) -> str:
    title = str(game_map.get("title") or game_map.get("id") or "RPG scene")
    design = game_map.get("map_design") if isinstance(game_map.get("map_design"), dict) else {}
    role_text = str(game_map.get("role") or design.get("role") or "playable top-down scene")
    if role == "terrain_tile":
        terrain = label.replace("_", " ")
        return (
            f"Top-down 2D RPG seamless terrain tile for {title}. Material: {terrain}. "
            f"Scene role: {role_text}. The whole square is one repeatable ground material, "
            "clean 48px-grid readability, no props, no characters, no labels, no border."
        )
    if role == "scene_prop":
        return (
            f"Top-down / slight three-quarter RPG object sprite for {title}. Object: {label.replace('_', ' ')}. "
            f"Scene role: {role_text}. Centered game prop, clear silhouette, transparent or flat chroma-key background, "
            "no labels, no UI, no border."
        )
    if role == "sprite":
        return (
            f"2x2 RPG spritesheet for {label.replace('_', ' ')} in {title}. "
            "Same character in four directions, consistent outfit and proportions, transparent or flat chroma-key background."
        )
    return f"Top-down RPG asset {asset_id} for {title}."


def assets_request_for_map(game_map: Json, scene_spec_ref: str) -> Json:
    assets: list[Json] = []
    for terrain, asset_id in sorted((game_map.get("terrain_asset_ids") or {}).items()):
        if isinstance(terrain, str) and isinstance(asset_id, str):
            assets.append({
                "name": stable_slug(asset_id),
                "asset_id": asset_id,
                "kind": "terrain_tile",
                "prompt": scene_asset_prompt(game_map, asset_id, "terrain_tile", terrain),
            })
    scene = game_map.get("scene") if isinstance(game_map.get("scene"), dict) else {}
    seen_prop_assets: set[str] = set()
    for prop in as_list(scene.get("props")):
        if not isinstance(prop, dict):
            continue
        asset_id = prop.get("asset_id")
        if not isinstance(asset_id, str) or asset_id in seen_prop_assets:
            continue
        seen_prop_assets.add(asset_id)
        label = str(prop.get("name") or prop.get("asset") or asset_id.split(".")[-1])
        assets.append({
            "name": stable_slug(asset_id),
            "asset_id": asset_id,
            "kind": "scene_prop",
            "prompt": scene_asset_prompt(game_map, asset_id, "scene_prop", label),
            "transparent": True,
        })
    seen_sprites: set[str] = set()
    for event in as_list(game_map.get("events")):
        if not isinstance(event, dict):
            continue
        sprite_id = event.get("sprite_asset_id")
        if not isinstance(sprite_id, str) or sprite_id in seen_sprites:
            continue
        seen_sprites.add(sprite_id)
        assets.append({
            "name": stable_slug(sprite_id),
            "asset_id": sprite_id,
            "kind": "sprite",
            "prompt": scene_asset_prompt(game_map, sprite_id, "sprite", str(event.get("name") or sprite_id)),
            "transparent": True,
        })
    return {
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "compile_rpg_manifest.py",
            "source_map_id": game_map.get("id"),
            "scene_spec_ref": scene_spec_ref,
            "mode": "per-map rpg-map-designer compatible asset request",
        },
        "assets": assets,
    }


def make_scene_grid(width: int, height: int, fill: Any) -> list[list[Any]]:
    return [[fill for _ in range(width)] for _ in range(height)]


def scene_rect_values(rect: Json, issues: list[Json], label: str) -> tuple[int, int, int, int] | None:
    values = [rect.get(key) for key in ("x", "y", "w", "h")]
    if not all(isinstance(value, int) for value in values):
        issues.append({"level": "error", "code": "scene_rect", "message": f"{label} needs integer x, y, w, and h."})
        return None
    x, y, width, height = values
    if width <= 0 or height <= 0:
        issues.append({"level": "error", "code": "scene_rect", "message": f"{label} must have positive w and h."})
        return None
    return x, y, width, height


def scene_rect_cells(rect: Json, issues: list[Json], label: str) -> list[tuple[int, int]]:
    values = scene_rect_values(rect, issues, label)
    if values is None:
        return []
    x0, y0, width, height = values
    return [(x, y) for y in range(y0, y0 + height) for x in range(x0, x0 + width)]


def check_scene_cell(width: int, height: int, x: int, y: int, issues: list[Json], label: str) -> bool:
    if in_bounds(width, height, x, y):
        return True
    issues.append({"level": "error", "code": "scene_bounds", "message": f"{label} ({x},{y}) is outside {width}x{height}."})
    return False


def build_scene_layers_from_spec(spec: Json) -> tuple[list[list[str]], list[list[str]], list[list[str]], list[list[str]], list[Json]]:
    issues: list[Json] = []
    meta = spec.get("map") if isinstance(spec.get("map"), dict) else {}
    width = int(meta.get("w") or 40)
    height = int(meta.get("h") or 30)
    floor = make_scene_grid(width, height, "void")
    barrier = make_scene_grid(width, height, "")
    collide = make_scene_grid(width, height, "x")
    interaction = make_scene_grid(width, height, ".")

    base_floor = meta.get("base_floor")
    if isinstance(base_floor, str) and base_floor:
        for y in range(height):
            for x in range(width):
                floor[y][x] = base_floor
                collide[y][x] = "o"

    for region in as_list(spec.get("regions")):
        if not isinstance(region, dict):
            continue
        label = f"region {region.get('id') or region.get('name') or ''}".strip()
        for x, y in scene_rect_cells(region, issues, label):
            if check_scene_cell(width, height, x, y, issues, label):
                floor[y][x] = str(region.get("floor") or base_floor or "grass")
                collide[y][x] = "o"

    for item in as_list(spec.get("barriers")):
        if not isinstance(item, dict):
            continue
        label = f"barrier {item.get('id') or item.get('asset') or ''}".strip()
        for x, y in scene_rect_cells(item, issues, label):
            if check_scene_cell(width, height, x, y, issues, label):
                barrier[y][x] = str(item.get("asset") or "")
                collide[y][x] = "x"

    for opening in as_list(spec.get("openings")):
        if not isinstance(opening, dict):
            continue
        label = f"opening {opening.get('id') or ''}".strip()
        for x, y in scene_rect_cells(opening, issues, label):
            if check_scene_cell(width, height, x, y, issues, label):
                barrier[y][x] = ""
                collide[y][x] = "o"
                if opening.get("floor"):
                    floor[y][x] = str(opening["floor"])

    for prop in as_list(spec.get("props")):
        if not isinstance(prop, dict):
            continue
        label = f"prop {prop.get('id') or prop.get('asset') or ''}".strip()
        cells = scene_rect_cells(prop, issues, label)
        if prop.get("blocking", True):
            for x, y in cells:
                if check_scene_cell(width, height, x, y, issues, label):
                    collide[y][x] = "x"
        can_interact = prop.get("interaction") or prop.get("lines") or prop.get("item_id") or prop.get("event_id")
        if can_interact:
            for x, y in cells:
                if in_bounds(width, height, x, y):
                    interaction[y][x] = "I"

    spawn = spec.get("player_spawn") if isinstance(spec.get("player_spawn"), dict) else {}
    sx = spawn.get("x")
    sy = spawn.get("y")
    if not isinstance(sx, int) or not isinstance(sy, int):
        issues.append({"level": "error", "code": "scene_spawn", "message": "player_spawn needs integer x and y."})
    elif not check_scene_cell(width, height, sx, sy, issues, "player_spawn"):
        pass
    elif collide[sy][sx] != "o":
        issues.append({"level": "error", "code": "scene_spawn", "message": "player_spawn must be on a passable tile."})
    return floor, barrier, collide, interaction, issues


def scene_reachable(collide: list[list[str]], start: tuple[int, int]) -> set[tuple[int, int]]:
    height = len(collide)
    width = len(collide[0]) if height else 0
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = x + dx
            ny = y + dy
            if in_bounds(width, height, nx, ny) and (nx, ny) not in seen and collide[ny][nx] == "o":
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def scene_rect_reaches(rect: Json, seen: set[tuple[int, int]]) -> bool:
    scratch: list[Json] = []
    for x, y in scene_rect_cells(rect, scratch, "rect"):
        if (x, y) in seen or adjacent_to_seen((x, y), seen):
            return True
    return False


def validate_scene_spec(spec: Json, collide: list[list[str]], issues: list[Json]) -> None:
    if any(issue.get("level") == "error" for issue in issues):
        return
    spawn = spec.get("player_spawn") if isinstance(spec.get("player_spawn"), dict) else {}
    sx = spawn.get("x")
    sy = spawn.get("y")
    if not isinstance(sx, int) or not isinstance(sy, int):
        return
    seen = scene_reachable(collide, (sx, sy))

    unreachable_regions = []
    for region in as_list(spec.get("regions")):
        if isinstance(region, dict) and not scene_rect_reaches(region, seen):
            unreachable_regions.append(region.get("id") or region.get("name") or "<unnamed>")
    if unreachable_regions:
        issues.append({
            "level": "error",
            "code": "scene_reachability",
            "message": "Unreachable regions: " + ", ".join(str(region) for region in unreachable_regions),
        })

    region_has_interaction: dict[str, bool] = {
        str(region.get("id") or region.get("name") or ""): False
        for region in as_list(spec.get("regions"))
        if isinstance(region, dict)
    }
    for prop in as_list(spec.get("props")):
        if not isinstance(prop, dict):
            continue
        can_interact = prop.get("interaction") or prop.get("lines") or prop.get("item_id") or prop.get("event_id")
        if not can_interact:
            continue
        if not scene_rect_reaches(prop, seen):
            issues.append({
                "level": "error",
                "code": "scene_reachability",
                "message": f"Interactive prop is unreachable: {prop.get('id') or prop.get('asset')}",
            })
        region_id = prop.get("region")
        if isinstance(region_id, str) and region_id in region_has_interaction:
            region_has_interaction[region_id] = True

    validation = spec.get("validation") if isinstance(spec.get("validation"), dict) else {}
    if validation.get("require_interaction_per_region", False):
        missing = [region for region, ok in region_has_interaction.items() if region and not ok]
        if missing:
            issues.append({
                "level": "error",
                "code": "scene_interactions",
                "message": "Regions missing interactive props: " + ", ".join(missing),
            })


def write_scene_grid(path: Path, rows: list[list[Any]], *, collision: bool = False) -> None:
    lines = []
    for row in rows:
        if collision:
            lines.append("".join("x" if not is_passable_value(cell) else "o" for cell in row))
        else:
            lines.append(",".join(str(cell or ".") for cell in row))
    write_json(path.with_suffix(".json"), rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scene_interaction_grid(game_map: Json, width: int, height: int) -> list[list[str]]:
    grid = [["." for _ in range(width)] for _ in range(height)]
    for prop in as_list((game_map.get("scene") or {}).get("props") if isinstance(game_map.get("scene"), dict) else []):
        if not isinstance(prop, dict):
            continue
        can_interact = prop.get("interaction") or prop.get("lines") or prop.get("item_id") or prop.get("event_id")
        if not can_interact:
            continue
        x0 = int(prop.get("x", 0))
        y0 = int(prop.get("y", 0))
        w = max(1, int(prop.get("w", 1)))
        h = max(1, int(prop.get("h", 1)))
        for y in range(y0, min(height, y0 + h)):
            for x in range(x0, min(width, x0 + w)):
                if in_bounds(width, height, x, y):
                    grid[y][x] = "I"
    for event in as_list(game_map.get("events")):
        if not isinstance(event, dict):
            continue
        x = event.get("x")
        y = event.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not in_bounds(width, height, x, y):
            continue
        event_type = str(event.get("type") or "")
        grid[y][x] = {
            "transfer": "T",
            "battle": "B",
            "encounter": "B",
            "rest": "R",
            "shop": "S",
            "pickup": "I",
            "item": "I",
            "quest": "I",
            "npc": "I",
        }.get(event_type, "I")
    return grid


def write_rpg_scene_packages(run_root: Path, maps: list[Json]) -> Json:
    packages = []
    all_issues: list[Json] = []
    scenes_root = run_root / "workspace" / "rpg" / "scenes"
    scenes_root.mkdir(parents=True, exist_ok=True)
    for game_map in maps:
        map_id = str(game_map.get("id") or "map")
        slug = stable_slug(map_id.removeprefix("map."), "scene")
        scene_dir = scenes_root / slug
        grids_dir = scene_dir / "grids"
        grids_dir.mkdir(parents=True, exist_ok=True)
        scene_spec = scene_spec_for_map(game_map)
        floor, barrier, collision, interaction, scene_issues = build_scene_layers_from_spec(scene_spec)
        validate_scene_spec(scene_spec, collision, scene_issues)
        for issue in scene_issues:
            issue.setdefault("map_id", map_id)
            all_issues.append(issue)
        scene_spec_path = scene_dir / "scene-spec.json"
        assets_request_path = scene_dir / "assets-request.json"
        write_json(scene_spec_path, scene_spec)
        write_json(assets_request_path, assets_request_for_map(game_map, str(scene_spec_path.relative_to(run_root))))
        write_scene_grid(grids_dir / "floor_layer.txt", floor)
        write_scene_grid(grids_dir / "barrier_layer.txt", barrier)
        write_scene_grid(grids_dir / "collision_layer.txt", collision, collision=True)
        write_scene_grid(grids_dir / "interaction_layer.txt", interaction)
        packages.append({
            "map_id": map_id,
            "title": game_map.get("title") or map_id,
            "scene_dir": str(scene_dir.relative_to(run_root)),
            "scene_spec": str(scene_spec_path.relative_to(run_root)),
            "assets_request": str(assets_request_path.relative_to(run_root)),
            "grid_files": [
                str((grids_dir / name).relative_to(run_root))
                for name in ("floor_layer.txt", "barrier_layer.txt", "collision_layer.txt", "interaction_layer.txt")
            ],
            "terrain_asset_count": len(game_map.get("terrain_asset_ids") or {}),
            "scene_prop_count": len(as_list((game_map.get("scene") or {}).get("props") if isinstance(game_map.get("scene"), dict) else [])),
            "event_count": len(as_list(game_map.get("events"))),
            "validation_status": "fail" if scene_issues else "pass",
            "validation_issue_count": len(scene_issues),
        })
    report = {
        "status": "fail" if all_issues else "pass",
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "compile_rpg_manifest.py",
            "reference": "rpg_map_designer/skills/rpg-map-designer",
        },
        "package_count": len(packages),
        "packages": packages,
        "issues": all_issues,
    }
    write_json(path_for(run_root, "rpg_scene_report"), report)
    return report


def scene_lines(value: Any, fallback: str) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    if isinstance(value, str) and value.strip():
        return [value]
    return [fallback]


def append_scene_prop(scene: Json, prop: Json) -> None:
    props = scene.setdefault("props", [])
    if isinstance(props, list):
        props.append({key: value for key, value in prop.items() if value is not None})


def apply_house_design(
    payload: Json,
    scene: Json,
    objects: list[list[Any]],
    overlay: list[list[Any]],
    collision: list[list[Any]],
    events: list[Json],
    width: int,
    height: int,
    house: Json,
    result: ValidationResult,
    path: str,
) -> None:
    kind = str(house.get("kind") or "house_small")
    if kind not in HOUSE_KINDS:
        result.add("error", "map_design_house", f"Unsupported house kind: {kind!r}.", f"{path}.kind")
        return
    x0 = house.get("x")
    y0 = house.get("y")
    house_w = house.get("w")
    house_h = house.get("h")
    if not all(isinstance(value, int) for value in (x0, y0, house_w, house_h)):
        result.add("error", "map_design_house", "House needs integer x, y, w, and h.", path)
        return
    x1 = x0 + house_w - 1
    y1 = y0 + house_h - 1
    if house_w <= 0 or house_h <= 0 or not in_bounds(width, height, x0, y0) or not in_bounds(width, height, x1, y1):
        result.add("error", "map_design_house", "House footprint must be positive and inside map bounds.", path)
        return
    door = house.get("door") if isinstance(house.get("door"), dict) else {}
    dx = door.get("x")
    dy = door.get("y")
    if not isinstance(dx, int) or not isinstance(dy, int) or not (x0 <= dx <= x1 and y0 <= dy <= y1):
        result.add("error", "map_design_house", "House door must be an x/y coordinate inside the footprint.", f"{path}.door")
        return

    roof_rows = max(1, house_h - 2)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            collision[y][x] = 1
            objects[y][x] = kind
            if y < y0 + roof_rows:
                overlay[y][x] = "roof"
    append_scene_prop(scene, {
        "id": f"sceneprop.house.{stable_slug(house.get('name') or f'{x0}_{y0}', 'house')}",
        "asset_id": f"mapprop.{kind}",
        "asset": kind,
        "name": house.get("name") or kind.replace("_", " ").title(),
        "x": x0,
        "y": y0,
        "w": house_w,
        "h": house_h,
        "blocking": True,
        "layer": "object",
    })
    append_scene_prop(scene, {
        "id": f"sceneprop.roof.{stable_slug(house.get('name') or f'{x0}_{y0}', 'house')}",
        "asset_id": "mapprop.roof",
        "asset": "roof",
        "x": x0,
        "y": y0,
        "w": house_w,
        "h": roof_rows,
        "blocking": False,
        "layer": "overlay",
        "render_scale": house.get("roof_render_scale"),
    })
    collision[dy][dx] = 0
    objects[dy][dx] = "door"
    event_id = house.get("event_id") if isinstance(house.get("event_id"), str) else f"door.{stable_slug(house.get('name') or f'{x0}_{y0}', 'house')}"
    door_lines = as_list(house.get("lines")) or ["The door is closed."]
    append_scene_prop(scene, {
        "id": f"sceneprop.{event_id}",
        "asset_id": "mapprop.door",
        "asset": "door",
        "event_id": event_id,
        "name": house.get("name") or "Door",
        "x": dx,
        "y": dy,
        "w": 1,
        "h": 1,
        "blocking": False,
        "layer": "object",
        "lines": None if house.get("target_map_id") else door_lines,
        "interaction": None if house.get("target_map_id") else door_lines[0],
    })
    if house.get("target_map_id"):
        append_unique_event(events, {
            "id": event_id,
            "type": "transfer",
            "x": dx,
            "y": dy,
            "name": house.get("name") or "Door",
            "target_map_id": house.get("target_map_id"),
            "target_x": house.get("target_x", 1),
            "target_y": house.get("target_y", 1),
        })
    elif house.get("interactive", True):
        append_unique_event(events, {
            "id": event_id,
            "type": "npc",
            "x": dx,
            "y": dy,
            "name": house.get("name") or "Door",
            "lines": as_list(house.get("lines")) or ["The door is closed."],
        })
    add_required_asset(payload, f"mapprop.{kind}")
    add_required_asset(payload, "mapprop.roof")


def apply_tree_design(
    payload: Json,
    scene: Json,
    objects: list[list[Any]],
    overlay: list[list[Any]],
    collision: list[list[Any]],
    width: int,
    height: int,
    tree: Json,
    result: ValidationResult,
    path: str,
) -> None:
    x = tree.get("x")
    y = tree.get("y")
    if not isinstance(x, int) or not isinstance(y, int) or not in_bounds(width, height, x, y):
        result.add("error", "map_design_tree", "Tree needs an in-bounds integer x/y anchor.", path)
        return
    objects[y][x] = "tree"
    collision[y][x] = 1
    append_scene_prop(scene, {
        "id": f"sceneprop.tree.{x}.{y}",
        "asset_id": "mapprop.tree",
        "asset": "tree",
        "x": x,
        "y": y,
        "w": 1,
        "h": 1,
        "blocking": True,
        "layer": "object",
    })
    canopy_cells: list[tuple[int, int]] = []
    for oy in (y - 2, y - 1):
        for ox in (x - 1, x, x + 1):
            if in_bounds(width, height, ox, oy):
                overlay[oy][ox] = "tree_canopy"
                canopy_cells.append((ox, oy))
    if canopy_cells:
        xs = [cell[0] for cell in canopy_cells]
        ys = [cell[1] for cell in canopy_cells]
        append_scene_prop(scene, {
            "id": f"sceneprop.tree_canopy.{x}.{y}",
            "asset_id": "mapprop.tree_canopy",
            "asset": "tree_canopy",
            "x": min(xs),
            "y": min(ys),
            "w": max(xs) - min(xs) + 1,
            "h": max(ys) - min(ys) + 1,
            "blocking": False,
            "layer": "overlay",
        })
    add_required_asset(payload, "mapprop.tree")
    add_required_asset(payload, "mapprop.tree_canopy")


def apply_garden_design(
    payload: Json,
    scene: Json,
    objects: list[list[Any]],
    collision: list[list[Any]],
    width: int,
    height: int,
    garden: Json,
    result: ValidationResult,
    path: str,
) -> None:
    bounds = rect_bounds(garden, result, path)
    if bounds is None:
        return
    x0, y0, x1, y1 = bounds
    if not in_bounds(width, height, x0, y0) or not in_bounds(width, height, x1, y1):
        result.add("error", "map_design_garden", "Garden must be inside map bounds.", path)
        return
    if garden.get("fenced", True):
        for x in range(x0, x1 + 1):
            for y in (y0, y1):
                objects[y][x] = "fence"
                collision[y][x] = 1
                append_scene_prop(scene, {
                    "id": f"sceneprop.fence.{x}.{y}",
                    "asset_id": "mapprop.fence",
                    "asset": "fence",
                    "x": x,
                    "y": y,
                    "w": 1,
                    "h": 1,
                    "blocking": True,
                    "layer": "object",
                })
        for y in range(y0 + 1, y1):
            for x in (x0, x1):
                objects[y][x] = "fence"
                collision[y][x] = 1
                append_scene_prop(scene, {
                    "id": f"sceneprop.fence.{x}.{y}",
                    "asset_id": "mapprop.fence",
                    "asset": "fence",
                    "x": x,
                    "y": y,
                    "w": 1,
                    "h": 1,
                    "blocking": True,
                    "layer": "object",
                })
        add_required_asset(payload, "mapprop.fence")
    for index, flower in enumerate(as_list(garden.get("flowers"))):
        x = flower.get("x") if isinstance(flower, dict) else None
        y = flower.get("y") if isinstance(flower, dict) else None
        if isinstance(x, int) and isinstance(y, int) and in_bounds(width, height, x, y):
            objects[y][x] = "flower"
            append_scene_prop(scene, {
                "id": f"sceneprop.flower.{x}.{y}",
                "asset_id": "mapprop.flower",
                "asset": "flower",
                "x": x,
                "y": y,
                "w": 1,
                "h": 1,
                "blocking": False,
                "layer": "floor_decor",
            })
            add_required_asset(payload, "mapprop.flower")
        else:
            result.add("warning", "map_design_garden", "Garden flower outside bounds was skipped.", f"{path}.flowers[{index}]")


def apply_prop_design(
    payload: Json,
    scene: Json,
    objects: list[list[Any]],
    collision: list[list[Any]],
    events: list[Json],
    width: int,
    height: int,
    prop: Json,
    result: ValidationResult,
    path: str,
) -> None:
    kind = str(prop.get("kind") or "")
    if kind not in MAP_PROP_KINDS:
        result.add("error", "map_design_prop", f"Unsupported prop kind: {kind!r}.", f"{path}.kind")
        return
    x = prop.get("x")
    y = prop.get("y")
    if not isinstance(x, int) or not isinstance(y, int) or not in_bounds(width, height, x, y):
        result.add("error", "map_design_prop", "Prop needs an in-bounds integer x/y coordinate.", path)
        return
    objects[y][x] = kind
    blocked = bool(prop.get("blocked", MAP_PROP_KINDS[kind]["blocked"]))
    if blocked:
        collision[y][x] = 1
    add_required_asset(payload, str(MAP_PROP_KINDS[kind]["asset"]))
    scene_prop: Json = {
        "id": prop.get("id") if isinstance(prop.get("id"), str) else f"sceneprop.{stable_slug(prop.get('name') or f'{kind}_{x}_{y}', kind)}",
        "asset_id": str(MAP_PROP_KINDS[kind]["asset"]),
        "asset": kind,
        "name": prop.get("name") or kind.replace("_", " ").title(),
        "x": x,
        "y": y,
        "w": prop.get("w") if isinstance(prop.get("w"), int) and prop["w"] > 0 else 1,
        "h": prop.get("h") if isinstance(prop.get("h"), int) and prop["h"] > 0 else 1,
        "blocking": blocked,
        "layer": prop.get("layer") if isinstance(prop.get("layer"), str) else ("object" if blocked else "floor_decor"),
        "render_scale": prop.get("render_scale") if isinstance(prop.get("render_scale"), (int, float)) else None,
    }
    if prop.get("event") == "chest" or prop.get("interaction"):
        event_type = "pickup" if kind == "chest" else "npc"
        event_id = prop.get("event_id") if isinstance(prop.get("event_id"), str) else f"{event_type}.{stable_slug(prop.get('name') or f'{kind}_{x}_{y}', kind)}"
        event: Json = {
            "id": event_id,
            "type": event_type,
            "x": x,
            "y": y,
            "name": prop.get("name") or kind.replace("_", " ").title(),
        }
        if event_type == "pickup":
            event["item_id"] = prop.get("item_id") if isinstance(prop.get("item_id"), str) else "item.gold"
            scene_prop["item_id"] = event["item_id"]
            scene_prop["event_id"] = event_id
        else:
            event["lines"] = as_list(prop.get("lines")) or [str(prop.get("interaction") or "Nothing unusual.")]
            scene_prop["lines"] = event["lines"]
            scene_prop["interaction"] = event["lines"][0]
            scene_prop["event_id"] = event_id
        append_unique_event(events, event)
    elif isinstance(prop.get("interaction"), str):
        scene_prop["interaction"] = prop["interaction"]
        scene_prop["lines"] = scene_lines(prop.get("lines"), prop["interaction"])
    append_scene_prop(scene, scene_prop)


def apply_npc_design(payload: Json, events: list[Json], collision: list[list[Any]], width: int, height: int, npc: Json, result: ValidationResult, path: str) -> None:
    kind = str(npc.get("kind") or "npc1")
    if kind not in NPC_KINDS:
        result.add("warning", "map_design_npc", f"Unknown NPC kind {kind!r}; using npc1 sprite fallback.", f"{path}.kind")
        kind = "npc1"
    x = npc.get("x")
    y = npc.get("y")
    if not isinstance(x, int) or not isinstance(y, int) or not in_bounds(width, height, x, y):
        result.add("error", "map_design_npc", "NPC needs an in-bounds integer x/y coordinate.", path)
        return
    collision[y][x] = 1
    event_id = npc.get("id") if isinstance(npc.get("id"), str) else f"npc.{stable_slug(npc.get('name') or f'{x}_{y}', 'npc')}"
    sprite_asset_id = npc.get("sprite_asset_id") if isinstance(npc.get("sprite_asset_id"), str) else f"sprite.{kind}"
    append_unique_event(events, {
        "id": event_id,
        "type": "npc",
        "x": x,
        "y": y,
        "name": npc.get("name") or "Villager",
        "lines": as_list(npc.get("lines")) or ["Hello, traveler."],
        "sprite_asset_id": sprite_asset_id,
    })
    add_required_asset(payload, sprite_asset_id)


def compile_map_design(payload: Json, width: int, height: int, result: ValidationResult, relative: str) -> None:
    design = payload.get("map_design") or payload.get("layout_spec")
    if not isinstance(design, dict):
        return
    scene: Json = {
        "renderer": "canvas-scene",
        "tile": 48,
        "width": width,
        "height": height,
        "title": payload.get("title") or payload.get("id") or "RPG Map",
        "regions": as_list(design.get("regions")),
        "props": [],
    }
    layers = payload.get("layers") if isinstance(payload.get("layers"), dict) else {}
    ground = normalize_grid(layers.get("ground"), width, height, "grass")
    collision = normalize_grid(layers.get("collision"), width, height, 0)
    objects = normalize_grid(layers.get("objects") or layers.get("object"), width, height, "")
    overlay = normalize_grid(layers.get("overlay"), width, height, "")
    events = [event for event in as_list(payload.get("events")) if isinstance(event, dict)]

    for index, item in enumerate(as_list(design.get("terrain"))):
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind == "water":
            if mark_rect(ground, width, height, item, "water", result, f"{relative}.map_design.terrain[{index}]"):
                bounds = rect_bounds(item, result, f"{relative}.map_design.terrain[{index}]")
                if bounds:
                    x0, y0, x1, y1 = bounds
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            collision[y][x] = 1
        elif kind == "bridge":
            if mark_rect(ground, width, height, item, "bridge", result, f"{relative}.map_design.terrain[{index}]"):
                bounds = rect_bounds(item, result, f"{relative}.map_design.terrain[{index}]")
                if bounds:
                    x0, y0, x1, y1 = bounds
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            collision[y][x] = 0
                add_required_asset(payload, "mapprop.bridge")
        else:
            result.add("error", "map_design_terrain", f"Unsupported terrain kind: {kind!r}.", f"{relative}.map_design.terrain[{index}].kind")

    for index, item in enumerate(as_list(design.get("paths"))):
        if isinstance(item, dict):
            apply_path_design(ground, width, height, item, result, f"{relative}.map_design.paths[{index}]")
    for index, house in enumerate(as_list(design.get("houses"))):
        if isinstance(house, dict):
            apply_house_design(payload, scene, objects, overlay, collision, events, width, height, house, result, f"{relative}.map_design.houses[{index}]")
    for index, tree in enumerate(as_list(design.get("trees"))):
        if isinstance(tree, dict):
            apply_tree_design(payload, scene, objects, overlay, collision, width, height, tree, result, f"{relative}.map_design.trees[{index}]")
    for index, garden in enumerate(as_list(design.get("gardens"))):
        if isinstance(garden, dict):
            apply_garden_design(payload, scene, objects, collision, width, height, garden, result, f"{relative}.map_design.gardens[{index}]")
    for index, prop in enumerate(as_list(design.get("props"))):
        if isinstance(prop, dict):
            apply_prop_design(payload, scene, objects, collision, events, width, height, prop, result, f"{relative}.map_design.props[{index}]")
    for index, npc in enumerate(as_list(design.get("npcs"))):
        if isinstance(npc, dict):
            apply_npc_design(payload, events, collision, width, height, npc, result, f"{relative}.map_design.npcs[{index}]")

    spawn = design.get("player_spawn")
    if isinstance(spawn, dict) and isinstance(spawn.get("x"), int) and isinstance(spawn.get("y"), int):
        sx = spawn["x"]
        sy = spawn["y"]
        if in_bounds(width, height, sx, sy):
            payload["player_spawn"] = {"x": sx, "y": sy}
            scene["player_spawn"] = {"x": sx, "y": sy}
            if not is_passable_value(collision[sy][sx]):
                result.add("error", "map_design_spawn", f"player_spawn ({sx},{sy}) must be passable.", f"{relative}.map_design.player_spawn")
        else:
            result.add("error", "map_design_spawn", "player_spawn must be inside map bounds.", f"{relative}.map_design.player_spawn")

    map_id = str(payload.get("id") or "map")
    if not isinstance(payload.get("map_asset_id"), str) and not isinstance(payload.get("asset_id"), str):
        payload["map_asset_id"] = f"map.{stable_slug(map_id.removeprefix('map.'), 'scene')}"
    if not isinstance(payload.get("tileset_asset_id"), str):
        payload["tileset_asset_id"] = f"tileset.{stable_slug(map_id.removeprefix('map.'), 'scene')}"
    map_asset_id = payload.get("map_asset_id") or payload.get("asset_id")
    if isinstance(map_asset_id, str):
        add_required_asset(payload, map_asset_id)
        scene["map_asset_id"] = map_asset_id
    add_required_asset(payload, payload["tileset_asset_id"])
    scene["tileset_asset_id"] = payload["tileset_asset_id"]
    localize_scene_prop_assets(payload, scene, map_id)

    payload["layers"] = {**layers, "ground": ground, "collision": collision, "objects": objects, "overlay": overlay}
    payload["events"] = events
    payload["scene"] = scene


def is_passable_value(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value <= 0
    if isinstance(value, str):
        return value.strip().lower() in ("", "0", "o", "open", "passable", "false")
    return not bool(value)


def reachable_tiles(collision: list[list[Any]], start: tuple[int, int]) -> set[tuple[int, int]]:
    height = len(collision)
    width = len(collision[0]) if height else 0
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = x + dx
            ny = y + dy
            if in_bounds(width, height, nx, ny) and (nx, ny) not in seen and is_passable_value(collision[ny][nx]):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def adjacent_to_seen(tile: tuple[int, int], seen: set[tuple[int, int]]) -> bool:
    x, y = tile
    return any((x + dx, y + dy) in seen for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def validate_map_reachability(game_map: Json, start_position: Json | None, result: ValidationResult, relative: str) -> None:
    width = game_map.get("width")
    height = game_map.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return
    layers = game_map.get("layers") if isinstance(game_map.get("layers"), dict) else {}
    collision = normalize_grid(layers.get("collision"), width, height, 0)
    spawn = game_map.get("player_spawn") if isinstance(game_map.get("player_spawn"), dict) else start_position
    if not isinstance(spawn, dict) or not isinstance(spawn.get("x"), int) or not isinstance(spawn.get("y"), int):
        return
    sx = spawn["x"]
    sy = spawn["y"]
    if not in_bounds(width, height, sx, sy):
        result.add("error", "map_spawn", "Map spawn/start position must be inside map bounds.", relative)
        return
    if not is_passable_value(collision[sy][sx]):
        result.add("error", "map_spawn", "Map spawn/start position must be passable.", relative)
        return
    seen = reachable_tiles(collision, (sx, sy))
    for index, event in enumerate(as_list(game_map.get("events"))):
        if not isinstance(event, dict):
            continue
        x = event.get("x")
        y = event.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not in_bounds(width, height, x, y):
            continue
        event_type = str(event.get("type") or "")
        tile = (x, y)
        if event.get("trigger") == "touch" or event_type == "transfer":
            if tile not in seen:
                result.add("warning", "map_reachability", f"Touch/transfer event is not reachable from spawn: {event.get('id')}", f"{relative}.events[{index}]")
        elif tile not in seen and not adjacent_to_seen(tile, seen):
            result.add("warning", "map_reachability", f"Event is not reachable or adjacent to a reachable tile: {event.get('id')}", f"{relative}.events[{index}]")


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
        design_payload = payload.get("map_design") if isinstance(payload.get("map_design"), dict) else payload.get("layout_spec")
        has_map_design = isinstance(design_payload, dict)
        design_meta = design_payload.get("map") if isinstance(design_payload, dict) and isinstance(design_payload.get("map"), dict) else {}
        if not isinstance(payload.get("title"), str) and isinstance(design_meta.get("title"), str):
            payload["title"] = design_meta["title"]
        if not isinstance(width, int) or width < 4:
            width = design_meta.get("w") if isinstance(design_meta.get("w"), int) and design_meta["w"] >= 4 else (40 if has_map_design else 12)
            payload["width"] = width
            result.add("warning", "map_width", f"Map width missing or too small; normalized to {width}.", f"{relative}.width")
        if not isinstance(height, int) or height < 4:
            height = design_meta.get("h") if isinstance(design_meta.get("h"), int) and design_meta["h"] >= 4 else (30 if has_map_design else 8)
            payload["height"] = height
            result.add("warning", "map_height", f"Map height missing or too small; normalized to {height}.", f"{relative}.height")
        layers = payload.get("layers") if isinstance(payload.get("layers"), dict) else {}
        ground = normalize_grid(layers.get("ground"), width, height, "grass")
        collision = normalize_grid(layers.get("collision"), width, height, 0)
        payload["layers"] = {**layers, "ground": ground, "collision": collision}
        compile_map_design(payload, width, height, result, relative)
        attach_terrain_tile_assets(payload, str(map_id))
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


def quest_id_list(quests: list[Json]) -> list[str]:
    return [quest["id"] for quest in quests if isinstance(quest.get("id"), str) and quest["id"]]


def valid_final_quest_id(campaign: Json, quests: list[Json], result: ValidationResult) -> str | None:
    ids = quest_id_list(quests)
    quest_ids = set(ids)
    if not ids:
        return None

    configured = campaign.get("final_quest_id")
    if isinstance(configured, str):
        if configured in quest_ids:
            return configured
        result.add(
            "warning",
            "final_quest_reference",
            f"Campaign final_quest_id does not exist in quests.json: {configured}.",
            "workspace/rpg/rpg-campaign.json.final_quest_id",
        )

    major_ids = [item for item in as_list(campaign.get("major_quest_ids")) if isinstance(item, str)]
    for quest_id in reversed(major_ids):
        if quest_id in quest_ids:
            return quest_id
    if major_ids:
        result.add(
            "warning",
            "final_quest_inferred",
            "Campaign major_quest_ids do not match runtime quests; using the last runtime quest as final_quest_id.",
            "workspace/rpg/rpg-campaign.json.major_quest_ids",
        )
    else:
        result.add(
            "warning",
            "final_quest_inferred",
            "Campaign final_quest_id missing; using the last runtime quest as final_quest_id.",
            "workspace/rpg/quests.json",
        )
    return ids[-1]


def quest_event_completion_id(event: Json) -> str | None:
    complete_quest_id = event.get("complete_quest_id")
    if isinstance(complete_quest_id, str) and complete_quest_id:
        return complete_quest_id
    quest_id = event.get("quest_id")
    if not isinstance(quest_id, str) or not quest_id:
        return None
    event_type = str(event.get("type") or "")
    if event.get("complete") is True or event_type in ("battle", "encounter"):
        return quest_id
    return None


def quest_completion_sources(maps: list[Json]) -> dict[str, list[str]]:
    sources: dict[str, list[str]] = {}
    for game_map in maps:
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            quest_id = quest_event_completion_id(event)
            if quest_id:
                sources.setdefault(quest_id, []).append(str(event.get("id") or "<event>"))
    return sources


def stem_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ers"):
        return token[:-1]
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def text_tokens(*values: Any) -> set[str]:
    text = " ".join(str(value or "") for value in values)
    tokens = set()
    for token in re.findall(r"[A-Za-z0-9]+", text.lower()):
        normalized = stem_token(token)
        if len(normalized) >= 3 and normalized not in {"quest", "event", "map", "the", "and", "with", "for"}:
            tokens.add(normalized)
    return tokens


def quest_text(quest: Json) -> str:
    fields: list[Any] = [quest.get("id"), quest.get("title"), quest.get("description"), quest.get("summary"), quest.get("stage_id")]
    fields.extend(as_list(quest.get("objectives")))
    fields.extend(as_list(quest.get("required_item_ids")))
    if quest.get("reward_item_id"):
        fields.append(quest.get("reward_item_id"))
    return " ".join(str(field or "") for field in fields)


def event_text(game_map: Json, event: Json) -> str:
    fields: list[Any] = [
        game_map.get("id"),
        game_map.get("title"),
        event.get("id"),
        event.get("name"),
        event.get("type"),
        event.get("dialogue_id"),
        event.get("item_id"),
        event.get("target_map_id"),
    ]
    fields.extend(as_list(event.get("lines")))
    return " ".join(str(field or "") for field in fields)


def score_quest_completion_candidate(quest: Json, game_map: Json, event: Json, *, final: bool = False) -> int:
    event_type = str(event.get("type") or "")
    if event_type in {"battle", "encounter"} and not final:
        return 0
    if event_type in {"transfer"} and not final:
        return 0
    if event_type in {"rest"}:
        return 0
    if event.get("complete_quest_id") or event.get("complete") is True:
        return 0

    q_tokens = text_tokens(quest_text(quest))
    e_tokens = text_tokens(event_text(game_map, event))
    overlap = q_tokens & e_tokens
    score = len(overlap) * 3
    if event_type == "npc":
        score += 4
    if event_type == "quest":
        score += 3
    if event_type == "pickup" and event.get("item_id") == quest.get("reward_item_id"):
        score += 6
    if isinstance(event.get("dialogue_id"), str) or as_list(event.get("lines")):
        score += 2
    if str(event.get("id") or "").startswith("event."):
        score += 2
    if final and event_type == "transfer":
        final_tokens = {"final", "end", "ending", "home", "homeward", "waking", "wake", "door", "exit"}
        score += 6 + len(e_tokens & final_tokens) * 4
    return score


def best_quest_completion_event(maps: list[Json], quest: Json, *, final: bool = False) -> Json | None:
    best: tuple[int, Json] | None = None
    for game_map in maps:
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            score = score_quest_completion_candidate(quest, game_map, event, final=final)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, event)
    return best[1] if best else None


def attach_completion_to_event_stack(maps: list[Json], anchor: Json, quest_id: str) -> list[str]:
    anchor_x = anchor.get("x")
    anchor_y = anchor.get("y")
    if not isinstance(anchor_x, int) or not isinstance(anchor_y, int):
        anchor["complete_quest_id"] = quest_id
        return [str(anchor.get("id") or "<event>")]
    attached: list[str] = []
    for game_map in maps:
        events = as_list(game_map.get("events"))
        if not any(event is anchor for event in events):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("x") != anchor_x or event.get("y") != anchor_y:
                continue
            event_type = str(event.get("type") or "")
            if event_type in {"battle", "encounter", "rest"}:
                continue
            if event.get("complete_quest_id") or event.get("complete") is True:
                continue
            event["complete_quest_id"] = quest_id
            event.setdefault("once", False)
            attached.append(str(event.get("id") or "<event>"))
        return attached or [str(anchor.get("id") or "<event>")]
    anchor["complete_quest_id"] = quest_id
    return [str(anchor.get("id") or "<event>")]


def normalize_quest_progression(campaign: Json, maps: list[Json], quests: list[Json], result: ValidationResult) -> Json:
    ids = quest_id_list(quests)
    quest_ids = set(ids)
    final_quest_id = valid_final_quest_id(campaign, quests, result)
    if final_quest_id:
        campaign["final_quest_id"] = final_quest_id

    inferred: list[Json] = []
    for game_map in maps:
        for index, event in enumerate(as_list(game_map.get("events"))):
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type") or "")
            quest_id = event.get("quest_id")
            if event_type != "quest" or not isinstance(quest_id, str) or quest_id not in quest_ids:
                continue
            if event.get("complete") is True or event.get("complete_quest_id"):
                continue
            if quest_id == final_quest_id:
                event.setdefault("once", False)
                continue
            event["complete"] = True
            event.setdefault("once", True)
            inferred.append({"quest_id": quest_id, "event_id": event.get("id"), "mode": "quest_event_complete"})
            result.add(
                "warning",
                "quest_completion_inferred",
                f"Inferred quest event completion for {quest_id}.",
                f"{game_map.get('source_path') or 'workspace/rpg/maps'}.events[{index}]",
            )

    by_id = {quest["id"]: quest for quest in quests if isinstance(quest.get("id"), str)}
    sources = quest_completion_sources(maps)
    for quest_id in ids:
        if sources.get(quest_id):
            continue
        quest = by_id[quest_id]
        candidate = best_quest_completion_event(maps, quest, final=quest_id == final_quest_id)
        if candidate:
            event_ids = attach_completion_to_event_stack(maps, candidate, quest_id)
            inferred.append({"quest_id": quest_id, "event_id": candidate.get("id"), "event_ids": event_ids, "mode": "interaction_complete"})
            result.add(
                "warning",
                "quest_completion_inferred",
                f"Inferred completion anchor for {quest_id} at event {candidate.get('id')}.",
                "workspace/rpg/maps",
            )
            sources = quest_completion_sources(maps)
        else:
            severity = "error" if quest_id == final_quest_id else "warning"
            result.add(
                severity,
                "quest_completion_missing",
                f"Quest has no runtime completion source: {quest_id}.",
                "workspace/rpg/quests.json",
            )

    final_sources = quest_completion_sources(maps).get(final_quest_id or "", [])
    if final_quest_id and not final_sources:
        result.add(
            "error",
            "final_quest_completion_missing",
            f"Final quest has no runtime completion source: {final_quest_id}.",
            "workspace/rpg/quests.json",
        )
    return {
        "final_quest_id": final_quest_id,
        "inferred": inferred,
        "completion_sources": quest_completion_sources(maps),
    }


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
        start_map = next((game_map for game_map in maps if game_map.get("id") == start_map_id), None)
        start_spawn = start_map.get("player_spawn") if isinstance(start_map, dict) and isinstance(start_map.get("player_spawn"), dict) else {}
        if isinstance(start_spawn.get("x"), int) and isinstance(start_spawn.get("y"), int):
            start_position = {"x": start_spawn["x"], "y": start_spawn["y"]}
            result.add("warning", "start_position", "Missing start_position; defaulted to start map player_spawn.", "workspace/rpg/rpg-campaign.json.start_position")
        else:
            start_position = {"x": 1, "y": 1}
            result.add("warning", "start_position", "Missing start_position; defaulted to {x:1,y:1}.", "workspace/rpg/rpg-campaign.json.start_position")

    quest_progression = normalize_quest_progression(campaign, maps, collections["quests"], result)

    battle_events = 0
    for map_index, game_map in enumerate(maps):
        map_start = start_position if game_map.get("id") == start_map_id else None
        validate_map_reachability(game_map, map_start, result, str(game_map.get("source_path") or f"workspace/rpg/maps[{map_index}]"))
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
        "final_quest_id": quest_progression.get("final_quest_id"),
        "campaign": campaign,
        "world_map": world_map,
        "maps": maps,
        "quest_progression": quest_progression,
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
        "final_quest_id": quest_progression.get("final_quest_id"),
        "quest_completion_source_count": sum(len(value) for value in quest_progression.get("completion_sources", {}).values()),
        "inferred_quest_completion_count": len(quest_progression.get("inferred", [])),
        "asset_ref_count": len(asset_refs),
        "source_paths": {key: value for key, value in source_paths.items() if value},
    }
    scene_report = write_rpg_scene_packages(run_root, maps)
    coverage["scene_package_count"] = scene_report.get("package_count", 0)
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
