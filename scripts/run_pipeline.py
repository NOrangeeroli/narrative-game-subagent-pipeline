#!/usr/bin/env python3
"""Controller CLI for the self-contained narrative game pipeline skill."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from adventure_schema import build_adventure_manifest, plan_default_adventure, simulate_adventure_routes, validate_adventure_artifacts
from export_unity_project import export_unity_project
from export_unity_adventure import export_unity_adventure
from export_web_adventure import export_web_adventure
from export_web_vn import export_web_vn
from generate_assets import generate_assets
from design_v3_lib import compile_design_v3, ensure_design_v3_layout
from pipeline_lib import (
    build_gameplay_manifest,
    build_realization_manifest,
    ensure_run_layout,
    load_optional_json,
    path_for,
    read_json,
    validate_all,
    write_json,
    write_not_implemented_stubs,
    write_text,
)
from plan_assets import plan_asset_manifest
from story_ir import collect_private_authoring_phrases, parse_yarn, verify_story_ir
from validate_assets import validate_assets
from write_report import write_final_report


V3_AUTHORING_ROLES = [
    "StoryLevelExtractor",
    "AdaptationPolicyDesigner",
    "LevelStateGraphDesigner",
    "DesignV3CompilerReviewer",
]


def refresh_story_outputs(run_root: Path) -> dict:
    from pipeline_lib import assemble_yarn_text, load_yarn_fragments

    fragments = load_yarn_fragments(run_root)
    if not fragments:
        raise SystemExit("Missing VN fragments under workspace/vn/fragments/.")
    story_yarn = assemble_yarn_text(fragments)
    write_text(path_for(run_root, "story_yarn"), story_yarn)
    story_ir = parse_yarn(story_yarn)
    story_report = verify_story_ir(story_ir, collect_private_authoring_phrases(run_root))
    story_ir["verification"] = story_report
    write_json(path_for(run_root, "story_ir"), story_ir)
    write_json(path_for(run_root, "story_report"), story_report)
    if story_report["status"] == "fail":
        print(json.dumps(story_report, indent=2))
        raise SystemExit(1)
    return story_report


def init_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    design_layer = getattr(args, "design_layer", "v1")
    if design_layer == "v3":
        ensure_design_v3_layout(run_root)
    write_text(path_for(run_root, "prompt"), args.prompt.strip() + "\n")
    write_json(run_root / "graph" / "state.json", {
        "run_root": str(run_root),
        "current_stage": f"initialized_{design_layer}_design_layer" if design_layer == "v3" else "initialized",
        "design_layer": design_layer,
        "next_actions": (
            [
                "For source-adaptation runs, extract the full source into inputs/source_material/ before spawning authoring agents.",
                "Create role-specific clean-context packets under workspace/controller-packets/; render the separate prompt template and pass only that prompt, the packet content, and the exact role card to each subagent.",
                "Author V3 story levels from fine to coarse. Long source-adaptation VN runs should use three levels by default: level_01 source scene/chapter chunks, level_02 arc packets, and level_03 global story/design. For source-adaptation level_01, shard StoryLevelExtractor work so every source_index chunk/span is assigned, returned, audited, and merged; representative chapters are not sufficient. Non-coarsest higher story levels must also be sharded/sliced and may not receive full lower-level linear_story files. The coarsest enabled StoryLevelExtractor must be one global worker that sees only immediate child summaries/fact view and produces the global story line/fact view. Story extraction should capture facts for controller persistence under facts/*.",
                "Write adaptation/global_policy.json from the coarsest story view plus canonical facts; keep policy broad and leave concrete state/topology decisions to level design.",
                "Author V3 graph/state design from coarse to fine. The coarsest enabled LevelStateGraphDesigner must be one global worker over coarsest story units only; non-coarsest design levels must be sharded by immediate parent graph node or parent packet. Non-coarsest workers receive only parent graph/state/contracts slices, assigned same-level story-unit slices, local fact/policy slices, and relevant excerpts, then design state first, then state-dependent routes, behavior-first player choices, effects, contracts, and parent settlements. For branch-permitted runs, task prompts must require visibly networked topology: different node orders/access, state gates, optional/revisit/delayed routes, convergence with route memory, player choices framed as external actions rather than only internal attitudes, and no cosmetic final-line branching.",
                "For every non-coarsest design level, write parent_state_settlements.json describing how this level affects immediate parent state.",
                "Treat only the finest enabled design level, normally level_01, as the source of public/runtime branch_graph nodes and edges. Coarser story_graph outputs are design/context artifacts and must not create runtime-visible choices.",
                "Run run_pipeline.py compile-design --design-layer v3.",
                "Run validate_artifacts.py --write-projections on the compiled public artifacts.",
                "Use references/post-design-prompts.md when spawning NodeRealizationPlanner and large-run NodeSceneWriter chapter/source-chunk shards.",
                "After NodeSceneWriter fragments are accepted, run run_pipeline.py check-v3-scene-choice-labels --run-root <run-root> before export/build so player-facing choices come from SceneWriter-authored Yarn labels, not designer fallback labels.",
            ]
            if design_layer == "v3"
            else [
                "For source-adaptation runs, extract the full source into inputs/source_material/ before spawning authoring agents.",
                "Create role-specific clean-context packets under workspace/controller-packets/; render the separate prompt template and pass only that prompt, the packet content, and the exact role card to each subagent.",
                "Spawn PromptAnalyst, LinearSynopsisDesigner, BranchGraphDesigner, and BaseGameIRDesigner.",
                "For V1 public runtime semantics, put transition gates/effects on branch_graph.edges[*].conditions/effects; BaseGameIRDesigner must declare the referenced state variables and mirror non-trivial edges in game_ir.event_rules.",
                "Write accepted payloads to workspace/design_layer/.",
                "Run validate_artifacts.py --write-projections.",
                ]
        ),
    })
    write_json(run_root / "reports" / "controller-todo.json", {
        "status": "initialized",
        "design_layer": design_layer,
        "authoring_roles": (
            V3_AUTHORING_ROLES if design_layer == "v3"
            else [
                "PromptAnalyst",
                "LinearSynopsisDesigner",
                "BranchGraphDesigner",
                "BaseGameIRDesigner",
            ]
        ),
        "prompt_path": "inputs/prompt.txt",
        "required_design_artifacts": (
            [
                "workspace/design_layer_v3/hierarchy_policy.json",
                "workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json",
                "workspace/design_layer_v3/facts/canonical_fact_graph.json",
                "workspace/design_layer_v3/adaptation/global_policy.json",
                "workspace/design_layer_v3/design_levels/level_<NN>/state_model.json",
                "workspace/design_layer_v3/design_levels/level_<NN>/story_graph.json",
                "workspace/design_layer_v3/design_levels/level_<NN>/contracts.json",
                "workspace/design_layer_v3/design_levels/level_<NN>/parent_state_settlements.json",
            ]
            if design_layer == "v3"
            else [
                "workspace/design_layer/user_requirements.json",
                "workspace/design_layer/chapter_linear_synopsis.json",
                "workspace/design_layer/branch_graph.json",
                "workspace/design_layer/game_ir.json",
            ]
        ),
        "runtime_design_artifacts": [
            "workspace/design_layer/branch_graph.json",
            "workspace/design_layer/game_ir.json",
        ],
        "source_material_paths": {
            "original": "inputs/source_material/original/",
            "full_text": "inputs/source_material/full_text.txt",
            "source_index": "inputs/source_material/source_index.json",
            "chunks": "inputs/source_material/chunks/*.txt",
            "extraction_report": "inputs/source_material/extraction_report.json",
        },
        "subagent_input_policy": {
            "packet_root": "workspace/controller-packets/",
            "v3_parallel_level_policy": {
                "story_level_shards": "workspace/design_layer_v3/story_levels/level_<NN>/shards/*.json",
                "story_level_returns": "workspace/design_layer_v3/story_levels/level_<NN>/shard_returns/*.json",
                "fine_level_source_coverage": "For source-adaptation level_01, shard packets must cover every entry in inputs/source_material/source_index.json before merge; do not use representative-only chapters.",
                "three_level_default": "Long source-adaptation VN runs should use level_01 source scene/chapter chunks, level_02 arc packets, and level_03 global story/design.",
                "coarsest_story_global": "The coarsest enabled StoryLevelExtractor is a single global packet/return that covers every immediate lower-level story unit.",
                "coarsest_design_global": "The coarsest enabled LevelStateGraphDesigner is a single global packet/return that owns the global graph and state model.",
                "non_coarsest_slice_only": "Non-coarsest story/design packets must include a scope declaration and use controller-made slices instead of full same-level or full lower-level artifacts.",
                "design_level_shards": "workspace/design_layer_v3/design_levels/level_<NN>/shards/*.json",
                "design_level_returns": "workspace/design_layer_v3/design_levels/level_<NN>/shard_returns/*.json",
                "merge_owner": "controller",
                "public_branch_graph_source": "finest_enabled_design_level_only",
            },
            "prompt_template_files": [
                "references/design-layer-prompts.md",
                "references/design-layer-v3-prompts.md",
                "references/post-design-prompts.md",
            ],
            "normal_authoring_inputs": "rendered separate prompt template plus exact role card plus role-specific controller packet only",
            "controller_only_context": [
                "validation scripts",
                "full run directory traversal",
                "full extracted source text unless a role packet explicitly includes it",
            ],
            "contract_exceptions": [
                "targeted repair workers that receive explicit validation or contract excerpts",
            ],
            "v3_scene_choice_label_check": "run_pipeline.py check-v3-scene-choice-labels --run-root <run-root>",
            "post_design_prompt_templates": "references/post-design-prompts.md",
        },
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
    })
    print(str(run_root))


def compile_design_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    if args.design_layer == "v3":
        result = compile_design_v3(run_root)
        report_path = run_root / "workspace" / "design_layer_v3" / "compile_report.json"
    else:
        raise SystemExit("compile-design currently supports --design-layer v3.")
    payload = load_optional_json(report_path) or result.to_json()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result.status == "fail":
        raise SystemExit(1)


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

    refresh_story_outputs(run_root)

    if not args.skip_assets:
        plan_asset_manifest(run_root)
        generate_assets(
            run_root,
            provider=args.asset_provider,
            model=args.asset_model,
            overwrite=args.asset_overwrite,
            remove_backgrounds=args.asset_remove_backgrounds,
            audio_provider=args.audio_provider,
            audio_model=args.audio_model,
            audio_fallback_provider=args.audio_fallback_provider,
            bgm_provider=args.bgm_provider,
            sfx_provider=args.sfx_provider,
            voice_provider=args.voice_provider,
            audio_concurrency=args.audio_concurrency,
            image_concurrency=args.image_concurrency,
        )
        asset_report = validate_assets(run_root)
        if asset_report["status"] == "fail":
            print(json.dumps(asset_report, indent=2))
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


def check_v3_scene_choice_labels_run(args: argparse.Namespace) -> None:
    from check_v3_scene_choice_labels import check_scene_choice_labels, is_v3_run

    run_root = Path(args.run_root).resolve()
    if not is_v3_run(run_root):
        raise SystemExit("check-v3-scene-choice-labels expects a compiled V3 run.")
    report = check_scene_choice_labels(run_root)
    report_path = run_root / "reports" / "v3-scene-choice-labels.json"
    write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


def plan_adventure_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    validation = validate_all(run_root, write_projections=True)
    if validation.status == "fail":
        print(json.dumps(validation.to_json(), ensure_ascii=False, indent=2))
        raise SystemExit(1)
    report = plan_default_adventure(run_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def compile_adventure_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    if not args.skip_validation:
        validation = validate_adventure_artifacts(run_root, write_report=True)
        if validation.status == "fail":
            print(json.dumps(validation.to_json(), ensure_ascii=False, indent=2))
            raise SystemExit(1)
    manifest = build_adventure_manifest(run_root)
    print(json.dumps({
        "status": "compiled",
        "manifest": "workspace/adventure/adventure-manifest.json",
        "levels": len(manifest.get("levels", [])),
        "interactions": len(manifest.get("interactions", [])),
        "ending_catalog": len(manifest.get("ending_catalog", [])),
    }, ensure_ascii=False, indent=2))


def validate_adventure_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    result = validate_adventure_artifacts(run_root, write_report=True)
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


def export_adventure_unity_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    project = export_unity_adventure(run_root)
    print(json.dumps({"status": "exported", "unity_adventure": str(project)}, ensure_ascii=False, indent=2))


def export_adventure_web_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    index = export_web_adventure(run_root)
    print(json.dumps({"status": "exported", "web_adventure": str(index)}, ensure_ascii=False, indent=2))


def build_adventure_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    if args.skip_web and args.skip_unity:
        raise SystemExit("No adventure exporter selected.")
    if args.skip_unity and args.run_unity_build:
        raise SystemExit("--run-unity-build requires Unity export.")
    if args.plan:
        plan_default_adventure(run_root)
    validation = validate_adventure_artifacts(run_root, write_report=True)
    if validation.status == "fail":
        print(json.dumps(validation.to_json(), ensure_ascii=False, indent=2))
        raise SystemExit(1)
    build_adventure_manifest(run_root)
    web_path = None if args.skip_web else export_web_adventure(run_root)
    project = None if args.skip_unity else export_unity_adventure(run_root)
    unity = args.unity_executable or shutil.which("Unity") or shutil.which("unity")
    build_report = {
        "status": "exported",
        "platform": args.platform,
        "web_adventure": str(web_path) if web_path else None,
        "unity_project": str(project) if project else None,
        "unity_executable": unity,
        "unity_build_attempted": False,
        "unity_build_status": "skipped",
        "notes": [],
    }
    if args.run_unity_build:
        if not unity:
            build_report["status"] = "failed"
            build_report["unity_build_status"] = "missing_unity"
            build_report["notes"].append("Unity executable was not found.")
        else:
            command = [
                unity,
                "-batchmode",
                "-quit",
                "-projectPath",
                str(project),
                "-executeMethod",
                "BuildAutomation.BuildDesktop",
            ]
            build_report["unity_build_attempted"] = True
            completed = subprocess.run(command, text=True, capture_output=True)
            build_report["unity_build_status"] = "pass" if completed.returncode == 0 else "fail"
            build_report["stdout_tail"] = completed.stdout[-4000:]
            build_report["stderr_tail"] = completed.stderr[-4000:]
            if completed.returncode != 0:
                build_report["status"] = "failed"
    write_json(run_root / "reports" / "adventure-build-report.json", build_report)
    final_report = write_final_report(run_root)
    build_report["final_report"] = str(final_report)
    write_json(run_root / "reports" / "adventure-build-report.json", build_report)
    print(json.dumps(build_report, ensure_ascii=False, indent=2))
    if build_report["status"] == "failed":
        raise SystemExit(1)


def test_adventure_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    report = simulate_adventure_routes(run_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--prompt", required=True)
    init_parser.add_argument("--run-root", required=True)
    init_parser.add_argument("--design-layer", choices=["v1", "v3"], default="v1")
    init_parser.set_defaults(func=init_run)

    compile_design_parser = subparsers.add_parser("compile-design")
    compile_design_parser.add_argument("--run-root", required=True)
    compile_design_parser.add_argument("--design-layer", choices=["v3"], default="v3")
    compile_design_parser.set_defaults(func=compile_design_run)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--run-root", required=True)
    build_parser.add_argument("--skip-web", action="store_true")
    build_parser.add_argument("--skip-assets", action="store_true")
    build_parser.add_argument("--asset-provider", default=None)
    build_parser.add_argument("--asset-model", default=None)
    build_parser.add_argument("--audio-provider", default=None)
    build_parser.add_argument("--audio-model", default=None)
    build_parser.add_argument("--audio-fallback-provider", default=None)
    build_parser.add_argument("--bgm-provider", default=None)
    build_parser.add_argument("--sfx-provider", default=None)
    build_parser.add_argument("--voice-provider", default=None)
    build_parser.add_argument("--audio-concurrency", type=int, default=None)
    build_parser.add_argument("--image-concurrency", type=int, default=None)
    build_parser.add_argument("--asset-overwrite", action="store_true")
    build_parser.add_argument("--no-asset-remove-backgrounds", action="store_false", dest="asset_remove_backgrounds")
    build_parser.set_defaults(asset_remove_backgrounds=True)
    build_parser.add_argument("--export-unity", action="store_true")
    build_parser.set_defaults(func=build_run)

    check_v3_choices_parser = subparsers.add_parser("check-v3-scene-choice-labels")
    check_v3_choices_parser.add_argument("--run-root", required=True)
    check_v3_choices_parser.set_defaults(func=check_v3_scene_choice_labels_run)

    plan_adventure_parser = subparsers.add_parser("plan-adventure")
    plan_adventure_parser.add_argument("--run-root", required=True)
    plan_adventure_parser.set_defaults(func=plan_adventure_run)

    compile_adventure_parser = subparsers.add_parser("compile-adventure")
    compile_adventure_parser.add_argument("--run-root", required=True)
    compile_adventure_parser.add_argument("--skip-validation", action="store_true")
    compile_adventure_parser.set_defaults(func=compile_adventure_run)

    validate_adventure_parser = subparsers.add_parser("validate-adventure")
    validate_adventure_parser.add_argument("--run-root", required=True)
    validate_adventure_parser.set_defaults(func=validate_adventure_run)

    export_adventure_parser = subparsers.add_parser("export-adventure-unity")
    export_adventure_parser.add_argument("--run-root", required=True)
    export_adventure_parser.set_defaults(func=export_adventure_unity_run)

    export_adventure_web_parser = subparsers.add_parser("export-adventure-web")
    export_adventure_web_parser.add_argument("--run-root", required=True)
    export_adventure_web_parser.set_defaults(func=export_adventure_web_run)

    build_adventure_parser = subparsers.add_parser("build-adventure")
    build_adventure_parser.add_argument("--run-root", required=True)
    build_adventure_parser.add_argument("--platform", choices=["desktop", "webgl", "android", "ios"], default="desktop")
    build_adventure_parser.add_argument("--plan", action="store_true")
    build_adventure_parser.add_argument("--skip-web", action="store_true")
    build_adventure_parser.add_argument("--skip-unity", action="store_true")
    build_adventure_parser.add_argument("--run-unity-build", action="store_true")
    build_adventure_parser.add_argument("--unity-executable", default=None)
    build_adventure_parser.set_defaults(func=build_adventure_run)

    test_adventure_parser = subparsers.add_parser("test-adventure")
    test_adventure_parser.add_argument("--run-root", required=True)
    test_adventure_parser.set_defaults(func=test_adventure_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
