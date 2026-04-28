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
    gameplay_validation = load_optional_json(path_for(run_root, "gameplay_validation_report")) or {"status": "missing", "findings": []}
    gameplay_coverage = load_optional_json(path_for(run_root, "gameplay_coverage_report")) or {"status": "missing"}
    asset_validation = load_optional_json(path_for(run_root, "asset_validation_report")) or {"status": "missing", "issues": []}
    web_path = run_root / "build" / "web-vn" / "index.html"
    unity_path = run_root / "build" / "unity-project"
    web_asset_root = run_root / "build" / "web-vn" / "assets"
    web_assets = sorted(
        str(path.relative_to(run_root))
        for path in web_asset_root.rglob("*")
        if path.is_file()
    ) if web_asset_root.exists() else []
    generated_asset_root = run_root / "workspace" / "generated-assets"
    generated_assets = sorted(
        str(path.relative_to(run_root))
        for path in generated_asset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    ) if generated_asset_root.exists() else []
    status = "succeeded"
    if validation.get("status") == "fail" or story_report.get("status") == "fail" or gameplay_validation.get("status") == "fail" or asset_validation.get("status") == "fail" or not web_path.exists():
        status = "failed"
    payload = {
        "status": status,
        "run_root": str(run_root),
        "validation_status": validation.get("status"),
        "story_verification_status": story_report.get("status"),
        "gameplay_validation_status": gameplay_validation.get("status"),
        "asset_validation_status": asset_validation.get("status"),
        "playable_exports": {
            "web_vn": str(web_path) if web_path.exists() else None,
            "unity_project": str(unity_path) if unity_path.exists() and any(unity_path.iterdir()) else None,
        },
        "asset_exports": {
            "asset_manifest": STAGE_PATHS["asset_manifest"] if (run_root / STAGE_PATHS["asset_manifest"]).exists() else None,
            "asset_generation_report": STAGE_PATHS["asset_generation_report"] if (run_root / STAGE_PATHS["asset_generation_report"]).exists() else None,
            "asset_validation_report": STAGE_PATHS["asset_validation_report"] if (run_root / STAGE_PATHS["asset_validation_report"]).exists() else None,
            "generated_asset_count": len(generated_assets),
            "web_vn_assets": web_assets,
        },
        "gameplay": {
            "manifest": STAGE_PATHS["gameplay_manifest"] if (run_root / STAGE_PATHS["gameplay_manifest"]).exists() else None,
            "validation_report": STAGE_PATHS["gameplay_validation_report"] if (run_root / STAGE_PATHS["gameplay_validation_report"]).exists() else None,
            "coverage_report": STAGE_PATHS["gameplay_coverage_report"] if (run_root / STAGE_PATHS["gameplay_coverage_report"]).exists() else None,
            "coverage": gameplay_coverage,
        },
        "design_layer": {
            "version": "v1-refactored",
            "source_artifacts": [
                STAGE_PATHS["requirements"],
                STAGE_PATHS["synopsis"],
            ],
            "runtime_artifacts": [
                STAGE_PATHS["branch_graph"],
                STAGE_PATHS["game_ir"],
            ],
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
