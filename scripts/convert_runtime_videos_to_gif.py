#!/usr/bin/env python3
"""Convert runtime background MP4 files to GIF files.

The Web RPG exporter prefers a GIF when a same-stem MP4 and GIF are both
present, so this script can be run before `run_pipeline.py build`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_dir, write_json


def ffmpeg_bin() -> str:
    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return executable
    windows_ffmpeg = Path("/mnt/c/ffmpeg/bin/ffmpeg.exe")
    if windows_ffmpeg.exists():
        return str(windows_ffmpeg)
    raise FileNotFoundError("ffmpeg is required; install ffmpeg or place it at /mnt/c/ffmpeg/bin/ffmpeg.exe.")


def ffmpeg_path(path: Path) -> str:
    resolved = path.resolve()
    if str(resolved).startswith("/mnt/"):
        try:
            return subprocess.check_output(["wslpath", "-w", str(resolved)], text=True).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            return str(resolved)
    return str(resolved)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def convert_one(ffmpeg: str, source: Path, width: int, fps: int, colors: int, overwrite: bool) -> dict[str, Any]:
    destination = source.with_suffix(".gif")
    if destination.exists() and not overwrite:
        return {
            "source": str(source),
            "output": str(destination),
            "status": "skipped",
            "reason": "exists",
            "bytes": destination.stat().st_size,
        }
    ensure_dir(destination.parent)
    palette = source.with_suffix(".palette.png")
    scale = f"scale={width}:-1:flags=lanczos"
    try:
        run([
            ffmpeg,
            "-y",
            "-i",
            ffmpeg_path(source),
            "-vf",
            f"fps={fps},{scale},palettegen=max_colors={colors}",
            "-frames:v",
            "1",
            "-update",
            "1",
            ffmpeg_path(palette),
        ])
        run([
            ffmpeg,
            "-y",
            "-i",
            ffmpeg_path(source),
            "-i",
            ffmpeg_path(palette),
            "-lavfi",
            f"fps={fps},{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
            ffmpeg_path(destination),
        ])
    finally:
        palette.unlink(missing_ok=True)
    return {
        "source": str(source),
        "output": str(destination),
        "status": "converted",
        "bytes": destination.stat().st_size,
        "fps": fps,
        "width": width,
        "colors": colors,
    }


def convert(run_root: Path, width: int, fps: int, colors: int, overwrite: bool) -> dict[str, Any]:
    video_root = run_root / "workspace" / "generated-assets" / "generated" / "videos"
    entries: list[dict[str, Any]] = []
    if not video_root.exists():
        report = {"status": "skipped", "video_root": str(video_root), "entries": [], "warnings": ["No generated video directory found."]}
        write_json(run_root / "reports" / "video-gif-conversion-report.json", report)
        return report
    ffmpeg = ffmpeg_bin()
    for source in sorted(video_root.glob("*.mp4")):
        entries.append(convert_one(ffmpeg, source, width=width, fps=fps, colors=colors, overwrite=overwrite))
    report = {
        "status": "pass",
        "video_root": str(video_root),
        "entries": entries,
        "warnings": [] if entries else ["No MP4 files found."],
    }
    write_json(run_root / "reports" / "video-gif-conversion-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--colors", type=int, default=128)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = convert(Path(args.run_root).resolve(), width=args.width, fps=args.fps, colors=args.colors, overwrite=args.overwrite)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
