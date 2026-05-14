#!/usr/bin/env python3
"""Generate generic Web RPG runtime media from existing generated assets.

This is the reusable counterpart to project-specific motion scripts. It reads
`workspace/asset-manifest.json`, creates animated map background GIFs under
`generated/videos/`, and creates simple idle/walk motion GIFs under
`generated/rpg-motion/`. The Web RPG exporter automatically binds these by
asset id stem.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, write_json


MAP_VIDEO_ROOT = Path("generated/videos")
MOTION_ROOT = Path("generated/rpg-motion")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def source_path(output_root: Path, asset: Json) -> Path | None:
    file_ref = asset.get("file_ref")
    if not isinstance(file_ref, str) or not file_ref:
        return None
    path = output_root / file_ref
    return path if path.exists() else None


def effect_color(asset_id: str) -> tuple[str, str]:
    token = asset_id.lower()
    if "cave" in token or "bone" in token:
        return "rgba(188,222,255,0.22)", "rgba(255,255,255,0.26)"
    if "hamlet" in token or "village" in token:
        return "rgba(232,226,190,0.18)", "rgba(255,248,210,0.24)"
    if "ridge" in token or "trail" in token or "summit" in token:
        return "rgba(210,224,230,0.20)", "rgba(255,255,245,0.24)"
    return "rgba(210,225,235,0.18)", "rgba(255,255,255,0.22)"


def create_map_loop(source: Path, destination: Path, asset_id: str, width: int, fps: int, frames: int) -> None:
    ensure_dir(destination.parent)
    haze, line = effect_color(asset_id)
    delay = max(1, round(100 / max(1, fps)))
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        frame_paths: list[Path] = []
        for index in range(frames):
            phase = index / max(1, frames - 1)
            x_shift = int(phase * width * 0.32)
            overlay = temp / f"overlay-{index:03d}.png"
            frame = temp / f"frame-{index:03d}.png"
            run([
                "magick",
                "-size",
                f"{width}x{round(width * 9 / 16)}",
                "xc:none",
                "-fill",
                haze,
                "-stroke",
                "none",
                "-draw",
                f"ellipse {120 + x_shift},110 220,42 0,360",
                "-draw",
                f"ellipse {520 - x_shift // 2},430 260,58 0,360",
                "-draw",
                f"ellipse {900 + x_shift // 3},210 240,50 0,360",
                "-stroke",
                line,
                "-strokewidth",
                "5",
                "-fill",
                "none",
                "-draw",
                f"path 'M {-120 + x_shift},250 C {120 + x_shift},190 {240 + x_shift},280 {460 + x_shift},210'",
                "-draw",
                f"path 'M {780 - x_shift},520 C {940 - x_shift},470 {1060 - x_shift},540 {1240 - x_shift},480'",
                "-blur",
                "0x1.0",
                str(overlay),
            ])
            run([
                "magick",
                str(source),
                "-resize",
                f"{width}x{round(width * 9 / 16)}!",
                str(overlay),
                "-composite",
                str(frame),
            ])
            frame_paths.append(frame)
        run([
            "magick",
            "-delay",
            str(delay),
            *[str(path) for path in frame_paths],
            "-loop",
            "0",
            str(destination),
        ])


def create_idle_motion(source: Path, destination: Path, size: int, frames: int) -> None:
    ensure_dir(destination.parent)
    offsets = [0, 3, 6, 3, 0, -2, 0, 2]
    scales = [0.82, 0.84, 0.86, 0.84, 0.82, 0.80, 0.82, 0.84]
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        frame_paths: list[Path] = []
        for index in range(frames):
            frame = temp / f"frame-{index:03d}.png"
            scale = scales[index % len(scales)]
            offset = offsets[index % len(offsets)]
            frame_size = max(1, int(size * scale))
            run([
                "magick",
                "-size",
                f"{size}x{size}",
                "xc:none",
                str(source),
                "-background",
                "none",
                "-resize",
                f"{frame_size}x{frame_size}",
                "-gravity",
                "center",
                "-geometry",
                f"+0+{offset}",
                "-composite",
                str(frame),
            ])
            frame_paths.append(frame)
        run([
            "magick",
            "-delay",
            "12",
            "-dispose",
            "Background",
            *[str(path) for path in frame_paths],
            "-loop",
            "0",
            str(destination),
        ])


def create_walk_motion(source: Path, destination: Path, size: int, frames: int) -> None:
    ensure_dir(destination.parent)
    x_offsets = [-7, -3, 3, 7, 3, -3, -7, 0]
    y_offsets = [2, -5, 1, -6, 2, -4, 1, -2]
    scales = [0.84, 0.88, 0.84, 0.88, 0.84, 0.88, 0.84, 0.86]
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        frame_paths: list[Path] = []
        for index in range(frames):
            frame = temp / f"frame-{index:03d}.png"
            scale = scales[index % len(scales)]
            frame_size = max(1, int(size * scale))
            x_offset = x_offsets[index % len(x_offsets)]
            y_offset = y_offsets[index % len(y_offsets)]
            run([
                "magick",
                "-size",
                f"{size}x{size}",
                "xc:none",
                str(source),
                "-background",
                "none",
                "-resize",
                f"{frame_size}x{frame_size}",
                "-gravity",
                "center",
                "-geometry",
                f"{x_offset:+d}{y_offset:+d}",
                "-composite",
                str(frame),
            ])
            frame_paths.append(frame)
        run([
            "magick",
            "-delay",
            "8",
            "-dispose",
            "Background",
            *[str(path) for path in frame_paths],
            "-loop",
            "0",
            str(destination),
        ])


def media_assets(manifest: Json, sections: list[str]) -> list[Json]:
    assets: list[Json] = []
    for section in sections:
        assets.extend(asset for asset in as_list(manifest.get(section)) if isinstance(asset, dict))
    return assets


def generate(run_root: Path, overwrite: bool, map_width: int, fps: int, frames: int) -> Json:
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not manifest:
        raise FileNotFoundError("Missing workspace/asset-manifest.json. Run plan_assets.py or build first.")
    output_root = run_root / "workspace" / "generated-assets"
    entries: list[Json] = []
    for asset in media_assets(manifest, ["map_assets"]):
        asset_id = str(asset.get("asset_id") or "")
        source = source_path(output_root, asset)
        if not asset_id or source is None:
            continue
        destination = output_root / MAP_VIDEO_ROOT / f"bgv.{asset_id}.loop.gif"
        if destination.exists() and not overwrite:
            status = "skipped"
        else:
            create_map_loop(source, destination, asset_id=asset_id, width=map_width, fps=fps, frames=frames)
            status = "generated"
        entries.append({"asset_id": f"bgv.{asset_id}.loop", "source": str(source), "output": str(destination), "status": status, "bytes": destination.stat().st_size})
    for asset in media_assets(manifest, ["sprites", "enemy_sprites", "item_icons", "skill_icons", "equipment_icons"]):
        asset_id = str(asset.get("asset_id") or "")
        source = source_path(output_root, asset)
        if not asset_id or source is None:
            continue
        destination = output_root / MOTION_ROOT / f"motion.{asset_id}.idle.gif"
        if destination.exists() and not overwrite:
            status = "skipped"
        else:
            create_idle_motion(source, destination, size=160 if asset_id.startswith("sprite.") else 144, frames=8)
            status = "generated"
        entries.append({"asset_id": f"motion.{asset_id}.idle", "source": str(source), "output": str(destination), "status": status, "bytes": destination.stat().st_size})
        if asset_id.startswith(("sprite.", "enemy.")):
            walk_destination = output_root / MOTION_ROOT / f"motion.{asset_id}.walk.gif"
            if walk_destination.exists() and not overwrite:
                walk_status = "skipped"
            else:
                create_walk_motion(source, walk_destination, size=160 if asset_id.startswith("sprite.") else 144, frames=8)
                walk_status = "generated"
            entries.append({"asset_id": f"motion.{asset_id}.walk", "source": str(source), "output": str(walk_destination), "status": walk_status, "bytes": walk_destination.stat().st_size})
    report = {
        "status": "pass",
        "entries": entries,
        "generated_count": sum(1 for entry in entries if entry["status"] == "generated"),
        "skipped_count": sum(1 for entry in entries if entry["status"] == "skipped"),
    }
    write_json(run_root / "reports" / "runtime-media-generation-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--map-width", type=int, default=960)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--frames", type=int, default=24)
    args = parser.parse_args()
    report = generate(Path(args.run_root).resolve(), overwrite=args.overwrite, map_width=args.map_width, fps=args.fps, frames=args.frames)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
