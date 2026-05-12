#!/usr/bin/env python3
"""Generate Alice in Wonderland map background videos with the PPIO I2V provider."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from asset_motion_providers import generate_background_video
from pipeline_lib import ensure_dir, write_json


VIDEO_SPECS = [
    {
        "asset_id": "bgv.map.rabbit_hole_garden.loop",
        "source": "generated/rpg/map_assets/map.rabbit_hole_garden.png",
        "file_ref": "generated/videos/bgv.map.rabbit_hole_garden.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted Victorian storybook RPG rabbit-hole garden map. "
            "Keep the camera locked and preserve the paths, tiny door, mushroom ring, hedge boundaries, exits, NPC walk space, and all collision-relevant terrain exactly in place. "
            "Animate only environmental motion: soft leaves swaying, tiny glowing motes, flower heads gently turning, pocket-watch sparkles, and slow dream haze near the rabbit hole. "
            "No camera pan, no zoom, no terrain warping, no moving obstacles into paths, no characters, no UI, no readable text."
        ),
    },
    {
        "asset_id": "bgv.map.mad_tea_party.loop",
        "source": "generated/rpg/map_assets/map.mad_tea_party.png",
        "file_ref": "generated/videos/bgv.map.mad_tea_party.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted Victorian storybook RPG Mad Tea Party map. "
            "Keep the camera locked and preserve the long tea table, chair positions, walkable lanes, tree and hedge collision shapes, exits, and encounter spaces exactly fixed. "
            "Animate only subtle ambient motion: tea steam curling upward, cup ripples, tablecloth edge flutter, clock hands trembling, and falling sugar grains catching light. "
            "Do not move tables, chairs, paths, trees, or terrain; no characters, no monsters, no UI, no labels, no readable text."
        ),
    },
    {
        "asset_id": "bgv.map.queen_court.loop",
        "source": "generated/rpg/map_assets/map.queen_court.png",
        "file_ref": "generated/videos/bgv.map.queen_court.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted Victorian storybook RPG Queen of Hearts court map. "
            "Keep the camera locked and preserve the checkerboard floor, red carpet, throne block, jury benches, card walls, exits, and all collision-relevant boundaries exactly unchanged. "
            "Animate only environmental motion: rose petals drifting, card banners fluttering in place, faint spotlight shimmer on the court floor, and tiny dust motes in theatrical air. "
            "No terrain deformation, no moving props across walkable spaces, no camera motion, no characters, no monsters, no UI, no text."
        ),
    },
]


def generate(run_root: Path) -> dict[str, Any]:
    output_root = run_root / "workspace" / "generated-assets"
    entries: list[dict[str, Any]] = []
    for spec in VIDEO_SPECS:
        source_path = output_root / spec["source"]
        output_path = output_root / spec["file_ref"]
        ensure_dir(output_path.parent)
        result = generate_background_video(
            provider="openai_I2V_PPIO",
            video={
                "asset_id": spec["asset_id"],
                "kind": "background_video",
                "file_ref": spec["file_ref"],
                "generation_interface": "I2V",
                "spec": {
                    "prompt": spec["prompt"],
                    "source_file_ref": spec["source"],
                    "loop": True,
                    "camera_fixed": True,
                },
            },
            source_path=source_path,
            output_path=output_path,
            run_root=run_root,
        )
        entries.append({
            "asset_id": spec["asset_id"],
            "role": "background_video",
            "provider": result.get("provider"),
            "model": result.get("model"),
            "source_file": str(source_path),
            "output_files": [str(output_path)],
            "notes": result.get("notes", []),
            "prompt": spec["prompt"],
        })
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provider": "openai_I2V_PPIO",
        "entries": entries,
    }
    write_json(run_root / "reports" / "ppio-i2v-background-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/alice-wonderland-rpg")
    args = parser.parse_args()
    report = generate(Path(args.run_root).resolve())
    print(json.dumps({
        "status": "pass",
        "provider": report["provider"],
        "count": len(report["entries"]),
        "report": "reports/ppio-i2v-background-report.json",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
