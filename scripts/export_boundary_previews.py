#!/usr/bin/env python3
"""Export map boundary preview overlays from compiled RPG collision shapes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, write_json, write_text


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def asset_file_refs(asset_manifest: Json) -> dict[str, str]:
    refs: dict[str, str] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            asset_id = value.get("asset_id")
            file_ref = value.get("file_ref")
            if isinstance(asset_id, str) and isinstance(file_ref, str):
                refs[asset_id] = file_ref
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(asset_manifest)
    return refs


def svg_points(points: Any, scale_x: float, scale_y: float) -> str:
    result = []
    for point in as_list(points):
        if not isinstance(point, list) or len(point) != 2:
            continue
        if not isinstance(point[0], (int, float)) or not isinstance(point[1], (int, float)):
            continue
        result.append(f"{float(point[0]) * scale_x:.2f},{float(point[1]) * scale_y:.2f}")
    return " ".join(result)


def render_shape(shape: Json, scale_x: float, scale_y: float) -> str:
    shape_id = str(shape.get("id") or "")
    if shape.get("type") == "polygon":
        points = svg_points(shape.get("points"), scale_x, scale_y)
        if not points:
            return ""
        return f'<polygon data-boundary-id="{shape_id}" points="{points}" />'
    if shape.get("type") == "rect":
        values = [shape.get(key) for key in ("x", "y", "w", "h")]
        if not all(isinstance(value, (int, float)) for value in values):
            return ""
        x, y, width, height = [float(value) for value in values]
        return (
            f'<rect data-boundary-id="{shape_id}" '
            f'x="{x * scale_x:.2f}" y="{y * scale_y:.2f}" '
            f'width="{width * scale_x:.2f}" height="{height * scale_y:.2f}" />'
        )
    return ""


def export_boundary_previews(run_root: Path) -> Json:
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    rpg_manifest = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    output_root = generated_root / "generated" / "rpg" / "map_boundaries"
    ensure_dir(output_root)
    refs = asset_file_refs(asset_manifest)
    entries: list[Json] = []
    warnings: list[str] = []

    for game_map in as_list(rpg_manifest.get("maps")):
        if not isinstance(game_map, dict):
            continue
        map_id = str(game_map.get("id") or "")
        asset_id = str(game_map.get("asset_id") or game_map.get("map_asset_id") or map_id)
        file_ref = refs.get(asset_id)
        if not file_ref:
            warnings.append(f"{map_id} has no generated map asset file_ref.")
            continue
        background_path = generated_root / file_ref
        if not background_path.exists():
            warnings.append(f"{map_id} background is missing: {file_ref}.")
            continue
        image_size = png_size(background_path) or (int(game_map.get("width") or 1280), int(game_map.get("height") or 720))
        image_width, image_height = image_size
        map_width = float(game_map.get("width") or 1)
        map_height = float(game_map.get("height") or 1)
        coordinate_system = "pixels"
        scale_x = image_width / map_width
        scale_y = image_height / map_height
        shapes = [shape for shape in as_list(game_map.get("collision_shapes")) if isinstance(shape, dict)]
        shape_nodes = [node for node in (render_shape(shape, scale_x, scale_y) for shape in shapes) if node]
        output_svg = output_root / f"{asset_id}.boundaries.svg"
        relative_background = Path(os.path.relpath(background_path, output_svg.parent))
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{image_width}" height="{image_height}" viewBox="0 0 {image_width} {image_height}">
  <image href="{relative_background.as_posix()}" x="0" y="0" width="{image_width}" height="{image_height}" />
  <g class="boundary-shapes" fill="#ff0000" fill-opacity="0.5" stroke="none">
    {"\n    ".join(shape_nodes)}
  </g>
</svg>
'''
        write_text(output_svg, svg)
        output_png = output_svg.with_suffix(".png")
        rasterized = False
        if shutil.which("magick"):
            try:
                subprocess.run(
                    ["magick", output_svg.name, f"PNG32:{output_png}"],
                    cwd=output_svg.parent,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                rasterized = True
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Could not rasterize {output_svg.name}: {exc}")
        entries.append({
            "map_id": map_id,
            "asset_id": asset_id,
            "background_ref": file_ref,
            "svg_ref": str(output_svg.relative_to(generated_root)),
            "png_ref": str(output_png.relative_to(generated_root)) if rasterized else None,
            "collision_shape_count": len(shape_nodes),
            "coordinate_system": coordinate_system,
            "image_size": {"width": image_width, "height": image_height},
            "map_size": {"width": map_width, "height": map_height},
        })

    report = {
        "status": "pass" if entries else "warning",
        "entries": entries,
        "warnings": warnings,
    }
    write_json(run_root / "reports" / "boundary-preview-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = export_boundary_previews(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
