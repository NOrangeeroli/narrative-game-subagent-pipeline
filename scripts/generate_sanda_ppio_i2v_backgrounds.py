#!/usr/bin/env python3
"""Generate San Da Bai Gu Jing map background videos with the PPIO I2V provider."""

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
        "asset_id": "bgv.map.white_tiger_ridge.loop",
        "source": "generated/rpg/map_assets/map.white_tiger_ridge.png",
        "file_ref": "generated/videos/bgv.map.white_tiger_ridge.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted Journey to the West RPG mountain ridge map. "
            "Keep the camera fully locked and preserve the road, cliffs, ravine edges, walkable clearing, and all collision-relevant terrain exactly in place. "
            "Animate only environmental motion: pale ridge mist drifting across the path, pine needles and low grasses swaying in gusts, dust motes and loose leaves crossing the road, and faint light shimmer in the bone-white haze. "
            "The scene should feel alive while remaining gameplay-readable. No camera pan, no zoom, no terrain warping, no moving props into the path, no characters, no monsters, no UI, no text."
        ),
    },
    {
        "asset_id": "bgv.map.abandoned_hamlet.loop",
        "source": "generated/rpg/map_assets/map.abandoned_hamlet.png",
        "file_ref": "generated/videos/bgv.map.abandoned_hamlet.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted abandoned mountain hamlet RPG map. "
            "Keep the camera fully locked and preserve hut foundation pads, roads, courtyard ground, dry well marking, exits, and collision-relevant walkable areas exactly fixed. "
            "Animate only subtle environmental life: dead grass and weeds moving in uneasy wind, thin dust curling through the empty square, hanging pale fog sliding between foundation pads, and tiny ash-like particles drifting. "
            "Do not move buildings, roads, ground pads, or terrain shapes; no characters, no monsters, no UI, no labels, no text."
        ),
    },
    {
        "asset_id": "bgv.map.bone_cave.loop",
        "source": "generated/rpg/map_assets/map.bone_cave.png",
        "file_ref": "generated/videos/bgv.map.bone_cave.loop.mp4",
        "prompt": (
            "Create a seamless looping image-to-video background from this top-down hand-painted White Bone Cave RPG map. "
            "Keep the camera fully locked and preserve the cave paths, ritual floor pad, rib-like rock markings, shadow pools, walls, and all collision-relevant boundaries exactly unchanged. "
            "Animate only supernatural environmental motion: cold blue cave haze breathing slowly, ghostly white wisps curling along the floor edges, faint bone dust drifting, and soft glints pulsing on pale bone-stone markings. "
            "Make the cave feel haunted but stable for gameplay. No terrain deformation, no moving walls, no camera motion, no characters, no monsters, no UI, no text."
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
    parser.add_argument("--run-root", default="runs/sanda-baigujing-rpg")
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
