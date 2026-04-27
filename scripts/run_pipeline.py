#!/usr/bin/env python3
"""Controller CLI for the self-contained narrative game pipeline skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from export_unity_project import export_unity_project
from export_web_vn import export_web_vn
from pipeline_lib import (
    build_realization_manifest,
    ensure_run_layout,
    load_optional_json,
    path_for,
    validate_all,
    write_json,
    write_not_implemented_stubs,
    write_text,
)
from story_ir import parse_yarn, verify_story_ir
from write_report import write_final_report


def init_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), args.prompt.strip() + "\n")
    write_json(run_root / "graph" / "state.json", {
        "run_root": str(run_root),
        "current_stage": "initialized",
        "next_actions": [
            "Spawn PromptAnalyst, LinearSynopsisDesigner, BranchGraphDesigner, and BaseGameIRDesigner.",
            "Write accepted payloads to workspace/design_layer/.",
            "Run validate_artifacts.py --write-projections.",
        ],
    })
    write_json(run_root / "reports" / "controller-todo.json", {
        "status": "initialized",
        "prompt_path": "inputs/prompt.txt",
        "required_next_artifacts": [
            "workspace/design_layer/user_requirements.json",
            "workspace/design_layer/chapter_linear_synopsis.json",
            "workspace/design_layer/chapter_branch_graph.json",
            "workspace/design_layer/game_ir.json",
        ],
    })
    print(str(run_root))


def build_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)

    validation = validate_all(run_root, write_projections=True)
    if validation.status == "fail":
        print(json.dumps(validation.to_json(), indent=2))
        raise SystemExit(1)

    plans = load_optional_json(path_for(run_root, "realization_plans"))
    if not plans:
        raise SystemExit("Missing workspace/realization/node-realization-plans.json")
    manifest = build_realization_manifest(plans)
    write_json(path_for(run_root, "realization_manifest"), manifest)
    stubs = write_not_implemented_stubs(run_root, plans)
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

    web_path = None
    if not args.skip_web:
        web_path = export_web_vn(run_root)
    unity_path = None
    if args.export_unity:
        unity_path = export_unity_project(run_root)
    report_path = write_final_report(run_root)
    print(json.dumps({
        "run_root": str(run_root),
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
    init_parser.set_defaults(func=init_run)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--run-root", required=True)
    build_parser.add_argument("--skip-web", action="store_true")
    build_parser.add_argument("--export-unity", action="store_true")
    build_parser.set_defaults(func=build_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
