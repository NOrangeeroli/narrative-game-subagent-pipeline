#!/usr/bin/env python3
"""Generate RPG collision boundaries from cyan walkable masks.

This is the project-local version of Sprite Forge's walkable-mask workflow:
generate/accept the still RPG map first, ask an agent-mediated image provider
for a cyan walkable mask, extract cyan locally, repair the required walk graph,
then invert the mask into collision rectangles.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from asset_image_providers import generate_provider_images, resolve_provider_model
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, read_json, write_json


DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_CELL = 16
POINT_RADIUS = 54
DEFAULT_CORRIDOR_WIDTH = 86
QA_VERSION = "sprite-forge-cyan-walkmask-v1"
MAX_PARALLEL_REQUESTS = 4


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_boundary_env(run_root: Path, env_file: str | None = None) -> None:
    candidates = [Path(env_file)] if env_file else []
    candidates.extend([run_root / ".env", Path.cwd() / ".env"])
    for candidate in candidates:
        load_dotenv(candidate)


def normalize_boundary_provider(value: str | None) -> str:
    provider = (
        value
        or os.environ.get("BACKGROUND_IMAGE_PROVIDER")
        or os.environ.get("IMAGE_PROVIDER")
        or "local-svg"
    ).strip()
    if provider.lower() in {"imagegen", "codex-imagegen"}:
        return "imagegen"
    if provider.lower() in {"ppio", "openai-ppioimage", "openai-ppioimage"}:
        return "openai-ppioImage"
    if provider.lower() in {"local-svg", "local_svg", "deterministic"}:
        return "local-svg"
    return provider


def asset_manifest_map_assets(run_root: Path) -> dict[str, Json]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    return {
        str(asset.get("asset_id")): asset
        for asset in as_list(manifest.get("map_assets"))
        if isinstance(asset, dict) and isinstance(asset.get("asset_id"), str)
    }


def map_file_stem(map_id: str) -> str:
    return map_id.removeprefix("map.")


def boundary_path_for(run_root: Path, game_map: Json, map_path: Path) -> Path:
    boundary_file = game_map.get("boundary_file") or game_map.get("boundaries_file")
    candidates: list[Path] = []
    if isinstance(boundary_file, str) and boundary_file:
        candidates.append((map_path.parent / boundary_file).resolve())
        candidates.append((run_root / boundary_file).resolve())
    map_id = str(game_map.get("id") or map_path.name.removesuffix(".map.json"))
    candidates.append(run_root / "workspace" / "rpg" / "boundaries" / f"{map_file_stem(map_id)}.boundaries.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def load_rpg_maps(run_root: Path) -> list[Json]:
    maps: list[Json] = []
    maps_root = run_root / "workspace" / "rpg" / "maps"
    for path in sorted(maps_root.glob("*.map.json")):
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        payload["_source_path"] = str(path.relative_to(run_root))
        payload["_absolute_source_path"] = str(path)
        maps.append(payload)
    return maps


def clamp_point(point: Json, width: int, height: int) -> Json | None:
    x = point.get("x")
    y = point.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return {
        **point,
        "x": int(max(0, min(width - 1, round(float(x))))),
        "y": int(max(0, min(height - 1, round(float(y))))),
    }


def route_nodes(run_root: Path, game_map: Json) -> list[Json]:
    width = int(game_map.get("width") or DEFAULT_WIDTH)
    height = int(game_map.get("height") or DEFAULT_HEIGHT)
    map_id = str(game_map.get("id") or "")
    campaign = load_optional_json(path_for(run_root, "rpg_campaign")) or {}
    points: list[Json] = []
    if campaign.get("start_map_id") == map_id and isinstance(campaign.get("start_position"), dict):
        points.append({"kind": "start_position", "id": "start", **campaign["start_position"]})
    for entry in as_list(campaign.get("entry_points")):
        if isinstance(entry, dict) and entry.get("start_map_id") == map_id and isinstance(entry.get("start_position"), dict):
            points.append({"kind": "entry_point", "id": entry.get("id") or "entry", **entry["start_position"]})
    hint = game_map.get("walkable_hint")
    if isinstance(hint, dict):
        points.append({"kind": "walkable_hint", "id": "walkable_hint", **hint})
    for event in as_list(game_map.get("events")):
        if isinstance(event, dict):
            points.append({"kind": str(event.get("type") or "event"), "id": event.get("id") or "event", "x": event.get("x"), "y": event.get("y")})
            if event.get("type") == "transfer":
                points.append({"kind": "transfer_exit", "id": f"{event.get('id') or 'transfer'}.exit", "x": event.get("x"), "y": event.get("y")})
    cleaned: list[Json] = []
    seen: set[tuple[int, int, str]] = set()
    for point in points:
        clamped = clamp_point(point, width, height)
        if not clamped:
            continue
        key = (clamped["x"], clamped["y"], str(clamped.get("id") or ""))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(clamped)
    if not cleaned:
        cleaned.append({"kind": "fallback", "id": "fallback_start", "x": min(180, width - 1), "y": min(520, height - 1)})
    return order_route_nodes(cleaned)


def order_route_nodes(points: list[Json]) -> list[Json]:
    if len(points) <= 2:
        return points
    remaining = points[1:]
    ordered = [points[0]]
    while remaining:
        current = ordered[-1]
        nearest_index = min(
            range(len(remaining)),
            key=lambda index: math.hypot(float(remaining[index]["x"]) - float(current["x"]), float(remaining[index]["y"]) - float(current["y"])),
        )
        ordered.append(remaining.pop(nearest_index))
    return ordered


def map_asset_output(run_root: Path, asset: Json) -> Path | None:
    file_ref = asset.get("file_ref")
    if not isinstance(file_ref, str) or not file_ref:
        return None
    return run_root / "workspace" / "generated-assets" / file_ref


def static_background_for(run_root: Path, game_map: Json, map_assets: dict[str, Json]) -> tuple[str, Path] | None:
    asset_id = str(game_map.get("asset_id") or game_map.get("id") or "")
    asset = map_assets.get(asset_id)
    if not asset:
        return None
    output = map_asset_output(run_root, asset)
    if not output:
        return None
    return asset_id, output


def mask_source_path(run_root: Path, asset_id: str) -> Path:
    return run_root / "workspace" / "generated-assets" / "generated" / "rpg" / "map_boundaries_qa" / QA_VERSION / f"{asset_id}.walkable-mask-source.png"


def imagegen_request_path(run_root: Path, asset_id: str) -> Path:
    return run_root / "workspace" / "generated-assets" / "imagegen-requests" / "rpg-boundaries" / f"{asset_id}.walkable-mask.json"


def build_boundary_prompt(game_map: Json, source_image: Path, nodes: list[Json]) -> str:
    node_lines = [
        f"- {node.get('kind')} {node.get('id')}: approximate point ({node['x']}, {node['y']})"
        for node in nodes
    ]
    title = game_map.get("title") or game_map.get("id")
    return "\n".join([
        "Use the accepted RPG map image as the exact visual reference.",
        "Create a same-aspect cyan walkable-area mask for this accepted still background.",
        f"Map: {title}. Source image path for agent bookkeeping: {source_image}",
        "Mark only player-walkable paths, plazas, bridges, stairs, platforms, entry pads, and event standing spaces in bright cyan at about 50% opacity.",
        "Keep the cyan walkable network continuous across the required route points below, including under non-blocking foreground shadows or visual occluders when gameplay should pass through.",
        "Everything outside cyan will be treated as blocked after local inversion.",
        "Do not add labels, arrows, outlines, grids, text, UI, debug symbols, circles, numbers, or legends.",
        "Do not alter the map layout, camera, scale, landmarks, exits, terrain boundaries, or decorative objects.",
        "Required connected walk graph:",
        *node_lines,
    ])


def write_imagegen_request(run_root: Path, asset_id: str, source_image: Path, output_file: Path, prompt: str, nodes: list[Json]) -> Path:
    request = {
        "asset_id": asset_id,
        "asset_kind": "rpg_walkable_boundary_mask",
        "provider": "imagegen",
        "max_parallel_generation_tasks": MAX_PARALLEL_REQUESTS,
        "source_image_file": str(source_image.relative_to(run_root)),
        "output_file": str(output_file.relative_to(run_root)),
        "prompt": prompt,
        "route_nodes": nodes,
        "note": "RPGBackgroundGenerator must view source_image_file, call image_gen with this prompt, save/copy the mask PNG to output_file, then rerun generate-backgrounds.",
    }
    path = imagegen_request_path(run_root, asset_id)
    write_json(path, request)
    return path


def load_mask(path: Path, width: int, height: int) -> Image.Image:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    arr = np.asarray(image).astype(np.int16)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    cyan = (g > 120) & (b > 120) & ((g - r) > 22) & ((b - r) > 22)
    mask = Image.fromarray((cyan.astype(np.uint8) * 255), mode="L")
    return mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(7))


def generate_ppio_boundary_mask(
    *,
    run_root: Path,
    asset_id: str,
    source_mask: Path,
    prompt: str,
) -> list[str]:
    images = generate_provider_images(
        provider="openai-ppioImage",
        model=resolve_provider_model("openai-ppioImage", os.environ.get("BOUNDARY_IMAGE_MODEL")),
        asset_id=f"boundary.{asset_id}",
        output_root=run_root / "workspace" / "generated-assets",
        prompt=prompt,
        image_type="rpg_walkable_boundary_mask",
        aspect_ratio="16:9",
        expected_count=1,
    )
    if not images:
        raise RuntimeError("PPIO returned no boundary mask image.")
    ensure_dir(source_mask.parent)
    with Image.open(io.BytesIO(images[0].bytes)) as image:
        image.convert("RGB").save(source_mask)
    return ["generated cyan walkable mask with PPIO image provider"]


def deterministic_walk_mask(width: int, height: int, nodes: list[Json]) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    return repair_connectivity(mask, width, height, nodes)


def repair_connectivity(mask: Image.Image, width: int, height: int, nodes: list[Json]) -> Image.Image:
    route = [(int(node["x"]), int(node["y"])) for node in nodes]
    if not route:
        route = [(min(180, width - 1), min(520, height - 1))]
    mask = mask.copy()
    draw = ImageDraw.Draw(mask)
    line_width = max(52, min(118, int(min(width, height) * 0.12)))
    radius = max(34, min(POINT_RADIUS, line_width))
    for x, y in route:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    for start, end in zip(route, route[1:]):
        draw.line((start, end), fill=255, width=line_width, joint="curve")
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    return keep_main_component(mask, route[0])


def keep_main_component(mask: Image.Image, seed: tuple[int, int]) -> Image.Image:
    data = np.asarray(mask) > 0
    height, width = data.shape
    sx, sy = seed
    sx = max(0, min(width - 1, sx))
    sy = max(0, min(height - 1, sy))
    if not data[sy, sx]:
        radius = POINT_RADIUS
        data[max(0, sy - radius): min(height, sy + radius + 1), max(0, sx - radius): min(width, sx + radius + 1)] = True
    seen = np.zeros_like(data, dtype=bool)
    queue: deque[tuple[int, int]] = deque([(sx, sy)])
    seen[sy, sx] = True
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height or seen[ny, nx] or not data[ny, nx]:
                continue
            seen[ny, nx] = True
            queue.append((nx, ny))
    return Image.fromarray((seen.astype(np.uint8) * 255), mode="L")


def merged_block_rects(walkable: Image.Image, cell: int = DEFAULT_CELL) -> list[Json]:
    arr = np.asarray(walkable) > 0
    height, width = arr.shape
    rows = height // cell
    cols = width // cell
    blocked = np.zeros((rows, cols), dtype=bool)
    for row in range(rows):
        y0 = row * cell
        y1 = y0 + cell
        for col in range(cols):
            x0 = col * cell
            x1 = x0 + cell
            blocked[row, col] = arr[y0:y1, x0:x1].mean() < 0.28

    used = np.zeros_like(blocked, dtype=bool)
    rects: list[Json] = []
    for row in range(rows):
        for col in range(cols):
            if used[row, col] or not blocked[row, col]:
                continue
            end_col = col
            while end_col < cols and blocked[row, end_col] and not used[row, end_col]:
                end_col += 1
            end_row = row + 1
            while end_row < rows and all(blocked[end_row, c] and not used[end_row, c] for c in range(col, end_col)):
                end_row += 1
            used[row:end_row, col:end_col] = True
            rects.append({
                "id": f"mask_block_{len(rects):03d}",
                "type": "rect",
                "x": col * cell,
                "y": row * cell,
                "w": (end_col - col) * cell,
                "h": (end_row - row) * cell,
            })
    return rects


def write_overlays(run_root: Path, asset_id: str, background: Path, source_mask: Path, mask: Image.Image, width: int, height: int) -> dict[str, str]:
    asset_root = run_root / "workspace" / "generated-assets"
    qa_root = asset_root / "generated" / "rpg" / "map_boundaries_qa" / QA_VERSION
    ensure_dir(qa_root)
    copied_source = qa_root / f"{asset_id}.walkable-mask-source.png"
    extracted = qa_root / f"{asset_id}.walkable-mask-extracted.png"
    overlay = qa_root / f"{asset_id}.walkable-mask-overlay.png"
    if source_mask.resolve() != copied_source.resolve():
        shutil.copy2(source_mask, copied_source)
    mask.save(extracted)
    with Image.open(background) as base:
        base = base.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
    cyan = Image.new("RGBA", (width, height), (0, 255, 255, 0))
    cyan.putalpha(mask.point(lambda value: 118 if value else 0))
    Image.alpha_composite(base, cyan).save(overlay)
    return {
        "source_ref": str(copied_source.relative_to(asset_root)),
        "mask_ref": str(extracted.relative_to(asset_root)),
        "overlay_ref": str(overlay.relative_to(asset_root)),
    }


def generate_boundaries(
    *,
    run_root: Path,
    provider: str | None = None,
    env_file: str | None = None,
    overwrite: bool = False,
) -> Json:
    load_boundary_env(run_root, env_file)
    provider = normalize_boundary_provider(provider)
    maps = load_rpg_maps(run_root)
    map_assets = asset_manifest_map_assets(run_root)
    entries: list[Json] = []
    status = "pass"

    for game_map in maps:
        map_id = str(game_map.get("id") or "")
        source_map_path = Path(str(game_map["_absolute_source_path"]))
        width = int(game_map.get("width") or DEFAULT_WIDTH)
        height = int(game_map.get("height") or DEFAULT_HEIGHT)
        located = static_background_for(run_root, game_map, map_assets)
        if not located:
            status = "fail"
            entries.append({"map_id": map_id, "status": "fail", "error": "missing_map_asset"})
            continue
        asset_id, background = located
        if not background.exists():
            status = "fail"
            entries.append({"map_id": map_id, "asset_id": asset_id, "status": "fail", "error": f"missing static background: {background}"})
            continue

        nodes = route_nodes(run_root, game_map)
        source_mask = mask_source_path(run_root, asset_id)
        if provider == "imagegen" and (overwrite or not source_mask.exists()):
            prompt = build_boundary_prompt(game_map, background, nodes)
            request = write_imagegen_request(run_root, asset_id, background, source_mask, prompt, nodes)
            status = "needs_boundary_imagegen"
            entries.append({
                "map_id": map_id,
                "asset_id": asset_id,
                "status": "needs_boundary_imagegen",
                "provider": "imagegen",
                "source_image_file": str(background.relative_to(run_root)),
                "request_ref": str(request.relative_to(run_root)),
                "output_file": str(source_mask.relative_to(run_root)),
                "max_parallel_generation_tasks": MAX_PARALLEL_REQUESTS,
            })
            continue

        if provider == "imagegen":
            mask = repair_connectivity(load_mask(source_mask, width, height), width, height, nodes)
            actual_source = source_mask
            final_provider = "imagegen"
            notes: list[str] = []
        elif provider == "openai-ppioImage":
            prompt = build_boundary_prompt(game_map, background, nodes)
            notes = []
            if overwrite or not source_mask.exists():
                try:
                    notes = generate_ppio_boundary_mask(
                        run_root=run_root,
                        asset_id=asset_id,
                        source_mask=source_mask,
                        prompt=prompt,
                    )
                    final_provider = "ppio-image"
                except Exception as exc:  # noqa: BLE001
                    ensure_dir(source_mask.parent)
                    mask = deterministic_walk_mask(width, height, nodes)
                    mask.save(source_mask)
                    actual_source = source_mask
                    final_provider = "local-svg"
                    notes = [f"PPIO boundary mask failed: {exc}", "fell back to deterministic local boundary mask"]
                else:
                    mask = repair_connectivity(load_mask(source_mask, width, height), width, height, nodes)
                    actual_source = source_mask
            else:
                mask = repair_connectivity(load_mask(source_mask, width, height), width, height, nodes)
                actual_source = source_mask
                final_provider = "ppio-image"
                notes = ["used existing PPIO boundary mask source"]
        elif provider == "local-svg":
            ensure_dir(source_mask.parent)
            mask = deterministic_walk_mask(width, height, nodes)
            mask.save(source_mask)
            actual_source = source_mask
            final_provider = "local-svg"
            notes = []
        else:
            ensure_dir(source_mask.parent)
            mask = deterministic_walk_mask(width, height, nodes)
            mask.save(source_mask)
            actual_source = source_mask
            final_provider = "local-svg"
            notes = [f"unsupported boundary provider {provider}; used deterministic local boundary mask"]

        refs = write_overlays(run_root, asset_id, background, actual_source, mask, width, height)
        rects = merged_block_rects(mask)
        boundary_path = boundary_path_for(run_root, game_map, source_map_path)
        payload = {
            "map_id": map_id,
            "coordinate_system": "pixels",
            "description": (
                f"Sprite Forge cyan walkable-mask inversion ({QA_VERSION}). "
                "Cyan walkable pixels were extracted locally, repaired against required RPG route nodes, "
                "then inverted into blocked collision rectangles."
            ),
            "collision_shapes": rects,
            "walkable_hint": {"x": nodes[0]["x"], "y": nodes[0]["y"]},
            "walkable_mask_ref": refs["mask_ref"],
            "boundary_source": {
                "type": "sprite_forge_cyan_walkable_mask_inversion",
                "qa_version": QA_VERSION,
                "provider": final_provider,
                "requested_provider": provider,
                "source_mask_ref": refs["source_ref"],
                "mask_ref": refs["mask_ref"],
                "overlay_ref": refs["overlay_ref"],
                "cell_size": DEFAULT_CELL,
                "repair_nodes": nodes,
                "source_skill": "generate2dmap",
            },
        }
        write_json(boundary_path, payload)
        entries.append({
            "map_id": map_id,
            "asset_id": asset_id,
            "status": "success",
            "requested_provider": provider,
            "final_provider": final_provider,
            "boundary_file": str(boundary_path.relative_to(run_root)),
            "collision_shape_count": len(rects),
            "notes": notes,
            **refs,
        })

    report: Json = {
        "status": status,
        "provider": provider,
        "max_parallel_generation_tasks": MAX_PARALLEL_REQUESTS,
        "entries": entries,
    }
    write_json(run_root / "reports" / "rpg-boundary-mask-generation-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = generate_boundaries(
        run_root=Path(args.run_root).resolve(),
        provider=args.provider,
        env_file=args.env_file,
        overwrite=args.overwrite,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in ("fail", "needs_boundary_imagegen"):
        raise SystemExit(2 if report["status"] == "needs_boundary_imagegen" else 1)


if __name__ == "__main__":
    main()
