#!/usr/bin/env python3
"""Write the final report for an RPG narrative pipeline run."""

from __future__ import annotations

import argparse
from pathlib import Path

from design_v3_lib import DESIGN_V3_COMPILE_REPORT, DESIGN_V3_ROOT
from pipeline_lib import STAGE_PATHS, load_optional_json, path_for, read_run_target, write_json


def relative_exists(run_root: Path, key: str) -> bool:
    return path_for(run_root, key).exists()


def write_final_report(run_root: Path) -> Path:
    target = read_run_target(run_root)
    validation = load_optional_json(path_for(run_root, "validation_report")) or {"status": "missing", "findings": []}
    rpg_validation = load_optional_json(path_for(run_root, "rpg_validation_report")) or {"status": "missing", "findings": []}
    rpg_balance = load_optional_json(path_for(run_root, "rpg_balance_report")) or {"status": "missing", "encounters": []}
    rpg_coverage = load_optional_json(path_for(run_root, "rpg_coverage_report")) or {"status": "missing"}
    asset_validation = load_optional_json(path_for(run_root, "asset_validation_report")) or {"status": "missing", "issues": []}
    game_ir = load_optional_json(path_for(run_root, "game_ir")) or {}
    design_layer = game_ir.get("design_layer") if isinstance(game_ir.get("design_layer"), dict) else {}
    design_layer_version = design_layer.get("version")
    v3_compile_report = load_optional_json(run_root / DESIGN_V3_COMPILE_REPORT)
    if design_layer_version == "v3":
        design_layer_report = {
            "version": "v3",
            "source_root": str(DESIGN_V3_ROOT),
            "source_artifacts": sorted(
                str(path.relative_to(run_root))
                for path in (run_root / DESIGN_V3_ROOT).rglob("*.json")
                if "assembled" not in path.relative_to(run_root / DESIGN_V3_ROOT).parts
                and "validation" not in path.relative_to(run_root / DESIGN_V3_ROOT).parts
            ) if (run_root / DESIGN_V3_ROOT).exists() else [],
            "assembled_artifacts": sorted(
                str(path.relative_to(run_root))
                for path in (run_root / DESIGN_V3_ROOT / "assembled").glob("*.json")
            ) if (run_root / DESIGN_V3_ROOT / "assembled").exists() else [],
            "compile_report": str(DESIGN_V3_COMPILE_REPORT) if (run_root / DESIGN_V3_COMPILE_REPORT).exists() else None,
            "compile_status": v3_compile_report.get("status") if isinstance(v3_compile_report, dict) else None,
            "runtime_artifacts": [
                STAGE_PATHS["branch_graph"],
                STAGE_PATHS["game_ir"],
            ],
        }
    else:
        design_layer_report = {
            "version": "v1-refactored",
            "source_artifacts": [
                STAGE_PATHS["requirements"],
                STAGE_PATHS["synopsis"],
            ],
            "runtime_artifacts": [
                STAGE_PATHS["branch_graph"],
                STAGE_PATHS["game_ir"],
            ],
        }
    web_rpg_path = run_root / "build" / "web-rpg" / "index.html"
    web_rpg_asset_root = run_root / "build" / "web-rpg" / "assets"
    web_rpg_assets = sorted(
        str(path.relative_to(run_root))
        for path in web_rpg_asset_root.rglob("*")
        if path.is_file()
    ) if web_rpg_asset_root.exists() else []
    generated_asset_root = run_root / "workspace" / "generated-assets"
    generated_assets = sorted(
        str(path.relative_to(run_root))
        for path in generated_asset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    ) if generated_asset_root.exists() else []
    status = "succeeded"
    if validation.get("status") == "fail" or asset_validation.get("status") == "fail":
        status = "failed"
    if rpg_validation.get("status") == "fail" or rpg_balance.get("status") == "fail" or not web_rpg_path.exists():
        status = "failed"
    payload = {
        "status": status,
        "target": target,
        "run_root": str(run_root),
        "validation_status": validation.get("status"),
        "rpg_validation_status": rpg_validation.get("status"),
        "rpg_balance_status": rpg_balance.get("status"),
        "asset_validation_status": asset_validation.get("status"),
        "playable_exports": {
            "web_rpg": str(web_rpg_path) if web_rpg_path.exists() else None,
        },
        "asset_exports": {
            "asset_manifest": STAGE_PATHS["asset_manifest"] if (run_root / STAGE_PATHS["asset_manifest"]).exists() else None,
            "asset_generation_report": STAGE_PATHS["asset_generation_report"] if (run_root / STAGE_PATHS["asset_generation_report"]).exists() else None,
            "asset_validation_report": STAGE_PATHS["asset_validation_report"] if (run_root / STAGE_PATHS["asset_validation_report"]).exists() else None,
            "generated_asset_count": len(generated_assets),
            "web_rpg_assets": web_rpg_assets,
        },
        "rpg": {
            "manifest": STAGE_PATHS["rpg_manifest"] if (run_root / STAGE_PATHS["rpg_manifest"]).exists() else None,
            "validation_report": STAGE_PATHS["rpg_validation_report"] if (run_root / STAGE_PATHS["rpg_validation_report"]).exists() else None,
            "balance_report": STAGE_PATHS["rpg_balance_report"] if (run_root / STAGE_PATHS["rpg_balance_report"]).exists() else None,
            "coverage_report": STAGE_PATHS["rpg_coverage_report"] if (run_root / STAGE_PATHS["rpg_coverage_report"]).exists() else None,
            "coverage": rpg_coverage,
        },
        "design_layer": design_layer_report,
        "artifacts": {
            key: value
            for key, value in STAGE_PATHS.items()
            if (run_root / value).exists()
        },
        "notes": [
            "Subagents author typed payloads only; this controller validates, persists, assembles, and exports.",
            "Web RPG export is directly playable in a browser.",
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
