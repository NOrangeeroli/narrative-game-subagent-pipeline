#!/usr/bin/env python3
"""Write the final report for a self-contained narrative game pipeline run."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_lib import STAGE_PATHS, load_optional_json, path_for, write_json


def relative_exists(run_root: Path, key: str) -> bool:
    return path_for(run_root, key).exists()


def write_final_report(run_root: Path) -> Path:
    validation = load_optional_json(path_for(run_root, "validation_report")) or {"status": "missing", "findings": []}
    story_report = load_optional_json(path_for(run_root, "story_report")) or {"status": "missing", "findings": []}
    web_path = run_root / "build" / "web-vn" / "index.html"
    unity_path = run_root / "build" / "unity-project"
    status = "succeeded"
    if validation.get("status") == "fail" or story_report.get("status") == "fail" or not web_path.exists():
        status = "failed"
    payload = {
        "status": status,
        "run_root": str(run_root),
        "validation_status": validation.get("status"),
        "story_verification_status": story_report.get("status"),
        "playable_exports": {
            "web_vn": str(web_path) if web_path.exists() else None,
            "unity_project": str(unity_path) if unity_path.exists() and any(unity_path.iterdir()) else None,
        },
        "artifacts": {
            key: value
            for key, value in STAGE_PATHS.items()
            if (run_root / value).exists()
        },
        "notes": [
            "Subagents author typed payloads only; this controller validates, persists, assembles, and exports.",
            "Web VN export is directly playable in a browser.",
            "Unity export is a generated project; compiling it requires a local Unity Editor.",
        ],
    }
    return write_json(path_for(run_root, "final_report"), payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(write_final_report(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()

