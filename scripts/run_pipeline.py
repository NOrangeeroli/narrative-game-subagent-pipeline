#!/usr/bin/env python3
"""Controller CLI for the self-contained narrative game pipeline skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compile_rpg_manifest import compile_rpg_manifest
from export_unity_project import export_unity_project
from export_web_rpg import export_web_rpg
from export_web_vn import export_web_vn
from generate_assets import generate_assets
from pipeline_lib import (
    build_gameplay_manifest,
    build_realization_manifest,
    ensure_run_layout,
    load_optional_json,
    normalize_target,
    path_for,
    read_json,
    validate_all,
    write_json,
    write_not_implemented_stubs,
    write_text,
)
from plan_assets import plan_asset_manifest
from simulate_rpg_balance import simulate_rpg_balance
from story_ir import parse_yarn, verify_story_ir
from validate_assets import validate_assets
from write_report import write_final_report


def write_controller_state(run_root: Path, target: str, current_stage: str, next_actions: list[str]) -> None:
    write_json(run_root / "graph" / "state.json", {
        "run_root": str(run_root),
        "target": target,
        "current_stage": current_stage,
        "next_actions": next_actions,
    })


def run_asset_pipeline(args: argparse.Namespace, run_root: Path, force: bool = False) -> None:
    if args.skip_assets:
        return
    if not force and not path_for(run_root, "asset_direction").exists():
        return
    plan_asset_manifest(run_root)
    generate_assets(
        run_root,
        provider=args.asset_provider,
        model=args.asset_model,
        overwrite=args.asset_overwrite,
        remove_backgrounds=args.asset_remove_backgrounds,
    )
    asset_report = validate_assets(run_root)
    if asset_report["status"] == "fail":
        print(json.dumps(asset_report, indent=2))
        raise SystemExit(1)


def init_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    target = normalize_target(args.target)
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), args.prompt.strip() + "\n")
    next_actions = [
        "Spawn PromptAnalyst, LinearSynopsisDesigner, BranchGraphDesigner, and BaseGameIRDesigner.",
        "Write accepted payloads to workspace/design_layer/.",
        "Run validate_artifacts.py --write-projections.",
    ]
    if target == "web-rpg":
        next_actions.append("Author RPG post-design artifacts under workspace/rpg/ before building.")
    else:
        next_actions.append("Author VN realization plans and Yarn fragments before building.")
    write_controller_state(run_root, target, "initialized", next_actions)
    write_json(run_root / "reports" / "controller-todo.json", {
        "status": "initialized",
        "target": target,
        "prompt_path": "inputs/prompt.txt",
        "required_design_artifacts": [
            "workspace/design_layer/user_requirements.json",
            "workspace/design_layer/chapter_linear_synopsis.json",
            "workspace/design_layer/branch_graph.json",
            "workspace/design_layer/game_ir.json",
        ],
        "runtime_design_artifacts": [
            "workspace/design_layer/branch_graph.json",
            "workspace/design_layer/game_ir.json",
        ],
        "asset_pipeline_artifacts": [
            "workspace/asset-direction.json",
            "workspace/asset-manifest.json",
            "workspace/generated-assets/",
            "reports/asset-generation-report.json",
            "reports/asset-validation.json",
        ],
        "gameplay_pipeline_artifacts": [
            "workspace/realization/battles/*.battle.json",
            "workspace/realization/interactions/*.interaction.json",
            "workspace/realization/puzzles/*.puzzle.json",
            "workspace/realization/explorations/*.exploration.json",
            "workspace/realization/gameplay-manifest.json",
            "reports/gameplay-validation.json",
            "reports/gameplay-coverage.json",
        ],
        "rpg_pipeline_artifacts": [
            "workspace/rpg/rpg-campaign.json",
            "workspace/rpg/world-map.json",
            "workspace/rpg/maps/*.map.json",
            "workspace/rpg/actors.json",
            "workspace/rpg/enemies.json",
            "workspace/rpg/quests.json",
            "workspace/rpg/rpg-manifest.json",
            "reports/rpg-validation.json",
            "reports/rpg-balance-report.json",
            "reports/rpg-coverage.json",
            "build/web-rpg/",
        ],
    })
    print(str(run_root))


def build_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    target = normalize_target(args.target)
    ensure_run_layout(run_root)
    write_controller_state(run_root, target, "building", ["Validate artifacts and export the requested playable target."])

    validation = validate_all(run_root, write_projections=True)
    if validation.status == "fail":
        print(json.dumps(validation.to_json(), indent=2))
        raise SystemExit(1)

    if target == "web-rpg":
        _, rpg_report = compile_rpg_manifest(run_root)
        if rpg_report["status"] == "fail":
            print(json.dumps(rpg_report, indent=2))
            raise SystemExit(1)
        balance_report = simulate_rpg_balance(run_root)
        if balance_report["status"] == "fail":
            print(json.dumps(balance_report, indent=2))
            raise SystemExit(1)
        run_asset_pipeline(args, run_root, force=True)
        web_path = None
        if not args.skip_web:
            web_path = export_web_rpg(run_root)
        if args.export_unity:
            print("Unity export is currently implemented for VN targets; skipping for web-rpg.")
        report_path = write_final_report(run_root)
        write_controller_state(run_root, target, "complete", ["Inspect reports/final-report.json and build/web-rpg/index.html."])
        print(json.dumps({
            "run_root": str(run_root),
            "target": target,
            "web_rpg": str(web_path) if web_path else None,
            "unity_project": None,
            "final_report": str(report_path),
        }, indent=2))
        return

    if target == "mixed-vn" and path_for(run_root, "rpg_campaign").exists():
        _, rpg_report = compile_rpg_manifest(run_root)
        if rpg_report["status"] == "fail":
            print(json.dumps(rpg_report, indent=2))
            raise SystemExit(1)
        balance_report = simulate_rpg_balance(run_root)
        if balance_report["status"] == "fail":
            print(json.dumps(balance_report, indent=2))
            raise SystemExit(1)

    plans = load_optional_json(path_for(run_root, "realization_plans"))
    if not plans:
        raise SystemExit("Missing workspace/realization/node-realization-plans.json")
    manifest = build_realization_manifest(plans)
    write_json(path_for(run_root, "realization_manifest"), manifest)
    shared_state = read_json(path_for(run_root, "shared_state")) if path_for(run_root, "shared_state").exists() else {"variables": []}
    gameplay_manifest, gameplay_validation = build_gameplay_manifest(run_root, plans, shared_state)
    if gameplay_validation.status == "fail":
        print(json.dumps(gameplay_validation.to_json(), indent=2))
        raise SystemExit(1)
    stubs = write_not_implemented_stubs(run_root, plans, gameplay_manifest)
    write_json(run_root / "reports" / "not-implemented-realizations.json", {
        "status": "has_stubs" if stubs else "clear",
        "count": len(stubs),
        "stubs": [stub["source_node_id"] for stub in stubs],
    })

    from pipeline_lib import assemble_yarn_text, load_yarn_fragments

    fragments = load_yarn_fragments(run_root)
    if not fragments:
        raise SystemExit("Missing VN fragments under workspace/vn/fragments/.")
    story_yarn = assemble_yarn_text(fragments)
    write_text(path_for(run_root, "story_yarn"), story_yarn)
    story_ir = parse_yarn(story_yarn)
    story_report = verify_story_ir(story_ir)
    story_ir["verification"] = story_report
    write_json(path_for(run_root, "story_ir"), story_ir)
    write_json(path_for(run_root, "story_report"), story_report)
    if story_report["status"] == "fail":
        print(json.dumps(story_report, indent=2))
        raise SystemExit(1)

    run_asset_pipeline(args, run_root, force=target == "mixed-vn" and path_for(run_root, "rpg_manifest").exists())

    web_path = None
    if not args.skip_web:
        web_path = export_web_vn(run_root)
    unity_path = None
    if args.export_unity:
        unity_path = export_unity_project(run_root)
    report_path = write_final_report(run_root)
    write_controller_state(run_root, target, "complete", ["Inspect reports/final-report.json and build/web-vn/index.html."])
    print(json.dumps({
        "run_root": str(run_root),
        "target": target,
        "web_vn": str(web_path) if web_path else None,
        "unity_project": str(unity_path) if unity_path else None,
        "final_report": str(report_path),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--prompt", required=True)
    init_parser.add_argument("--run-root", required=True)
    init_parser.add_argument("--target", choices=("web-vn", "web-rpg", "mixed-vn"), default="web-vn")
    init_parser.set_defaults(func=init_run)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--run-root", required=True)
    build_parser.add_argument("--target", choices=("web-vn", "web-rpg", "mixed-vn"), default="web-vn")
    build_parser.add_argument("--skip-web", action="store_true")
    build_parser.add_argument("--skip-assets", action="store_true")
    build_parser.add_argument("--asset-provider", default=None)
    build_parser.add_argument("--asset-model", default=None)
    build_parser.add_argument("--asset-overwrite", action="store_true")
    build_parser.add_argument("--no-asset-remove-backgrounds", action="store_false", dest="asset_remove_backgrounds")
    build_parser.set_defaults(asset_remove_backgrounds=True)
    build_parser.add_argument("--export-unity", action="store_true")
    build_parser.set_defaults(func=build_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
