#!/usr/bin/env python3
"""Validate Web RPG collision boundaries and key point reachability."""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json

PLAYER_RADIUS = 22.0
SAMPLE_STEP = 32


def point_in_polygon(points: list[list[float]], x: float, y: float) -> bool:
    inside = False
    count = len(points)
    for index in range(count):
        xi, yi = points[index]
        xj, yj = points[(index - 1) % count]
        hit = (yi > y) != (yj > y) and x < ((xj - xi) * (y - yi)) / ((yj - yi) or 1e-9) + xi
        if hit:
            inside = not inside
    return inside


def shape_contains(shape: Json, x: float, y: float) -> bool:
    if shape.get("type") == "polygon" and isinstance(shape.get("points"), list):
        points = [[float(point[0]), float(point[1])] for point in shape["points"] if isinstance(point, list) and len(point) == 2]
        return len(points) >= 3 and point_in_polygon(points, x, y)
    if shape.get("type") == "rect":
        sx = float(shape.get("x") or 0)
        sy = float(shape.get("y") or 0)
        return sx <= x <= sx + float(shape.get("w") or 0) and sy <= y <= sy + float(shape.get("h") or 0)
    return False


def load_walkable_mask(run_root: Path, game_map: Json) -> Image.Image | None:
    mask_ref = game_map.get("walkable_mask_ref")
    if not isinstance(mask_ref, str) or not mask_ref:
        source = game_map.get("boundary_source")
        mask_ref = source.get("mask_ref") if isinstance(source, dict) else None
    if not isinstance(mask_ref, str) or not mask_ref:
        return None
    for base in (run_root / "workspace" / "generated-assets", run_root / "build" / "web-rpg" / "assets"):
        candidate = base / mask_ref
        if candidate.exists():
            with Image.open(candidate) as image:
                return image.convert("RGBA")
    return None


def is_mask_walkable(game_map: Json, x: float, y: float) -> bool | None:
    mask = game_map.get("_walkable_mask")
    if not isinstance(mask, Image.Image):
        return None
    width = float(game_map.get("width") or mask.width)
    height = float(game_map.get("height") or mask.height)
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    px = max(0, min(mask.width - 1, round((x / width) * (mask.width - 1))))
    py = max(0, min(mask.height - 1, round((y / height) * (mask.height - 1))))
    r, g, b, a = mask.getpixel((px, py))
    return a > 0 and (r + g + b) / 3 >= 128


def is_blocked(game_map: Json, x: float, y: float) -> bool:
    width = float(game_map.get("width") or 0)
    height = float(game_map.get("height") or 0)
    foot_x = x
    foot_y = y
    if foot_x < 0 or foot_y < 0 or foot_x >= width or foot_y >= height:
        return True
    mask_walkable = is_mask_walkable(game_map, foot_x, foot_y)
    if mask_walkable is not None:
        return not mask_walkable
    radius = PLAYER_RADIUS
    samples = [
        (foot_x, foot_y),
        (foot_x - radius, foot_y),
        (foot_x + radius, foot_y),
        (foot_x, foot_y - radius),
        (foot_x, foot_y + radius),
        (foot_x - radius * 0.72, foot_y + radius * 0.72),
        (foot_x + radius * 0.72, foot_y + radius * 0.72),
    ]
    shapes = as_list(game_map.get("collision_shapes"))
    for sx, sy in samples:
        if sx < 0 or sy < 0 or sx >= width or sy >= height:
            return True
        if any(isinstance(shape, dict) and shape_contains(shape, sx, sy) for shape in shapes):
            return True
    return False


def tile_neighbors(point: tuple[int, int], width: int, height: int, step: int) -> list[tuple[int, int]]:
    x, y = point
    result = []
    for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            result.append((nx, ny))
    return result


def sample_point(value: float, step: int, width_or_height: int) -> int:
    if step <= 1:
        return int(value)
    sampled = int(round(float(value) / step) * step)
    return max(0, min(width_or_height - 1, sampled))


def reachable_tiles(game_map: Json, start: tuple[int, int]) -> set[tuple[int, int]]:
    width = int(game_map.get("width") or 0)
    height = int(game_map.get("height") or 0)
    step = SAMPLE_STEP
    start = (sample_point(start[0], step, width), sample_point(start[1], step, height))
    if is_blocked(game_map, start[0], start[1]):
        return set()
    seen = {start}
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        point = queue.popleft()
        for neighbor in tile_neighbors(point, width, height, step):
            if neighbor in seen or is_blocked(game_map, neighbor[0], neighbor[1]):
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return seen


def key_points(data: Json, game_map: Json) -> list[Json]:
    points: list[Json] = []
    start_map_id = str(data.get("start_map_id") or "")
    if game_map.get("id") == start_map_id and isinstance(data.get("start_position"), dict):
        points.append({"kind": "start_position", "id": "start", "x": data["start_position"].get("x"), "y": data["start_position"].get("y")})
    for entry in as_list(data.get("entry_points")):
        if isinstance(entry, dict) and entry.get("start_map_id") == game_map.get("id") and isinstance(entry.get("start_position"), dict):
            points.append({"kind": "entry_point", "id": entry.get("id"), "x": entry["start_position"].get("x"), "y": entry["start_position"].get("y")})
    for event in as_list(game_map.get("events")):
        if isinstance(event, dict) and isinstance(event.get("x"), (int, float)) and isinstance(event.get("y"), (int, float)):
            points.append({"kind": "event", "id": event.get("id"), "x": event.get("x"), "y": event.get("y")})
    hint = game_map.get("walkable_hint")
    if isinstance(hint, dict):
        points.append({"kind": "walkable_hint", "id": "walkable_hint", "x": hint.get("x"), "y": hint.get("y")})
    return points


def validate(run_root: Path) -> Json:
    data = load_optional_json(path_for(run_root, "rpg_manifest"))
    if not data:
        report = {"status": "fail", "issues": [{"code": "missing_rpg_manifest", "message": "Missing workspace/rpg/rpg-manifest.json."}], "warnings": []}
        write_json(run_root / "reports" / "boundary-validation-report.json", report)
        return report
    issues: list[Json] = []
    warnings: list[str] = []
    for game_map in as_list(data.get("maps")):
        if not isinstance(game_map, dict):
            continue
        game_map["_walkable_mask"] = load_walkable_mask(run_root, game_map)
        map_id = str(game_map.get("id") or "")
        width = int(game_map.get("width") or 0)
        height = int(game_map.get("height") or 0)
        step = SAMPLE_STEP
        shapes = [shape for shape in as_list(game_map.get("collision_shapes")) if isinstance(shape, dict)]
        if not shapes:
            warnings.append(f"{map_id} has no collision_shapes.")
        for shape in shapes:
            if shape.get("type") not in {"polygon", "rect"}:
                issues.append({"map_id": map_id, "shape_id": shape.get("id"), "code": "unsupported_shape", "message": f"Unsupported boundary shape type: {shape.get('type')}"})
        points = key_points(data, game_map)
        walkable_hint = next((point for point in points if point["kind"] == "walkable_hint"), None)
        if walkable_hint:
            start = (int(walkable_hint["x"]), int(walkable_hint["y"]))
        elif points:
            start = (int(points[0]["x"]), int(points[0]["y"]))
        else:
            start = (min(180, max(0, width - 1)), min(520, max(0, height - 1)))
        reachable = reachable_tiles(game_map, start)
        if not reachable:
            issues.append({"map_id": map_id, "code": "no_reachable_tiles", "message": f"No reachable tiles from {start}."})
            continue
        for point in points:
            x, y = point.get("x"), point.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                issues.append({"map_id": map_id, **point, "code": "invalid_point", "message": "Key point must have numeric x/y."})
                continue
            if x < 0 or y < 0 or x >= width or y >= height:
                issues.append({"map_id": map_id, **point, "code": "out_of_bounds", "message": "Key point is outside map bounds."})
                continue
            if is_blocked(game_map, float(x), float(y)):
                issues.append({"map_id": map_id, **point, "code": "blocked_key_point", "message": "Key point is inside collision."})
                continue
            tile = (sample_point(float(x), step, width), sample_point(float(y), step, height))
            if tile not in reachable:
                issues.append({"map_id": map_id, **point, "code": "unreachable_key_point", "message": f"Key point is not reachable from {start}."})
        sample_count = 0
        walkable_total = 0
        for y in range(0, height, step):
            for x in range(0, width, step):
                sample_count += 1
                if not is_blocked(game_map, x, y):
                    walkable_total += 1
        if walkable_total < max(3, int(sample_count * 0.10)):
            warnings.append(f"{map_id} has very little walkable area: {walkable_total}/{sample_count} sampled points.")
    report = {"status": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}
    write_json(run_root / "reports" / "boundary-validation-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = validate(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
