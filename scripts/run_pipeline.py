#!/usr/bin/env python3
"""Controller CLI for the self-contained narrative game pipeline skill."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from compile_rpg_manifest import compile_rpg_manifest
from design_v3_lib import compile_design_v3, ensure_design_v3_layout
from export_web_rpg import export_web_rpg
from bind_generated_assets import bind_generated_assets, load_provider_environment
from pipeline_lib import (
    ensure_run_layout,
    load_optional_json,
    normalize_target,
    path_for,
    validate_all,
    write_json,
    write_text,
)
from plan_assets import plan_asset_manifest
from simulate_rpg_balance import simulate_rpg_balance
from validate_assets import validate_assets
from write_report import write_final_report


V3_AUTHORING_ROLES = [
    "StoryLevelExtractor",
    "AdaptationPolicyDesigner",
    "LevelStateGraphDesigner",
    "DesignV3CompilerReviewer",
]


def write_controller_state(
    run_root: Path,
    target: str,
    current_stage: str,
    next_actions: list[str],
    design_layer: str | None = None,
) -> None:
    payload = {
        "run_root": str(run_root),
        "target": target,
        "current_stage": current_stage,
        "next_actions": next_actions,
    }
    if design_layer:
        payload["design_layer"] = design_layer
    write_json(run_root / "graph" / "state.json", payload)


LOW_TIER_VISUAL_PROVIDERS = {"", "local-svg", "mock"}
LOW_TIER_AUDIO_PROVIDERS = {"", "mock"}
BINDER_PROVIDER_ALIASES = {"bind", "binder", "bind-existing", "existing", "subagent", "subagents", "imagegen"}


def normalized_provider(value: str | None) -> str:
    return (value or "").strip().lower()


def should_bind_existing_assets(args: argparse.Namespace) -> bool:
    if getattr(args, "asset_mode", "auto") == "final-quality":
        return True
    if getattr(args, "asset_mode", "auto") == "fast-validation":
        return False
    image_provider = normalized_provider(
        args.asset_provider
        or os.environ.get("IMAGE_ASSET_PROVIDER")
        or os.environ.get("IMAGE_PROVIDER")
    )
    audio_provider = normalized_provider(
        args.audio_provider
        or os.environ.get("AUDIO_ASSET_PROVIDER")
        or os.environ.get("AUDIO_PROVIDER")
    )
    audio_family_providers = [
        normalized_provider(args.bgm_provider or os.environ.get("BGM_PROVIDER")),
        normalized_provider(args.sfx_provider or os.environ.get("SFX_PROVIDER")),
        normalized_provider(args.voice_provider or os.environ.get("VOICE_PROVIDER")),
    ]
    if image_provider in BINDER_PROVIDER_ALIASES:
        return True
    if image_provider and image_provider not in LOW_TIER_VISUAL_PROVIDERS:
        return True
    if audio_provider and audio_provider not in LOW_TIER_AUDIO_PROVIDERS:
        return True
    return any(provider and provider not in LOW_TIER_AUDIO_PROVIDERS for provider in audio_family_providers)


def run_asset_pipeline(args: argparse.Namespace, run_root: Path, force: bool = False) -> None:
    if args.skip_assets:
        return
    if not force and not path_for(run_root, "asset_direction").exists():
        return
    load_provider_environment(run_root, getattr(args, "env_file", None))
    plan_asset_manifest(run_root)
    if should_bind_existing_assets(args):
        from asset_manifest_probe import probe_asset_manifest

        probe_report = probe_asset_manifest(run_root)
        write_json(run_root / "reports" / "asset-manifest-probe.json", probe_report)
        if probe_report["status"] in ("fail", "needs_generation"):
            print(json.dumps(probe_report, ensure_ascii=False, indent=2))
            raise SystemExit(2 if probe_report["status"] == "needs_generation" else 1)
        asset_generation_report = bind_generated_assets(run_root, env_file=getattr(args, "env_file", None))
        if asset_generation_report["status"] == "fail":
            print(json.dumps(asset_generation_report, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    else:
        from generate_assets import generate_assets

        generate_assets(
            run_root,
            provider=args.asset_provider or ("local-svg" if getattr(args, "asset_mode", "auto") == "fast-validation" else None),
            model=args.asset_model,
            overwrite=args.asset_overwrite,
            audio_provider=args.audio_provider or ("mock" if getattr(args, "asset_mode", "auto") == "fast-validation" else None),
            audio_model=args.audio_model,
            audio_fallback_provider=args.audio_fallback_provider,
            bgm_provider=args.bgm_provider,
            sfx_provider=args.sfx_provider,
            voice_provider=args.voice_provider,
        )
    validation_mode = getattr(args, "asset_mode", "auto")
    if validation_mode == "auto":
        validation_mode = "final-quality" if should_bind_existing_assets(args) else "fast-validation"
    asset_report = validate_assets(run_root, asset_mode=validation_mode)
    if asset_report["status"] == "fail":
        print(json.dumps(asset_report, indent=2))
        raise SystemExit(1)
    if path_for(run_root, "rpg_manifest").exists():
        from export_boundary_previews import export_boundary_previews
        from generate_runtime_media import generate as generate_runtime_media

        generate_runtime_media(run_root, overwrite=args.asset_overwrite, map_width=960, fps=12, frames=24)
        export_boundary_previews(run_root)


def init_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    target = normalize_target(args.target)
    design_layer = args.design_layer
    ensure_run_layout(run_root)
    if design_layer == "v3":
        ensure_design_v3_layout(run_root)
    write_text(path_for(run_root, "prompt"), args.prompt.strip() + "\n")
    if design_layer == "v3":
        next_actions = [
            "For source-adaptation runs, extract the full source into inputs/source_material/ before spawning authoring agents.",
            "Create role-specific clean-context packets under workspace/controller-packets/; render the separate prompt template and pass only that prompt, the packet content, and the exact role card to each subagent.",
            "Run StoryLevelExtractor from fine to coarse, using V3 sharding/slicing rules and full source coverage where source material exists.",
            "Run AdaptationPolicyDesigner from the coarsest story view plus canonical facts.",
            "Run RPGSystemPlanner from story levels, canonical facts, adaptation policy, and inputs/prompt.txt only; do not pass the compiled public branch graph.",
            "Run RPGDesignReviewer and write workspace/design_layer_rpg/rpg-overlay-review.json.",
            "Run validate-rpg-overlay and repair the RPG overlay before graph design if it fails.",
            "Run LevelStateGraphDesigner normally. RPG overlay is narrative-first read-only context only if the controller explicitly includes a small excerpt; do not let it rewrite public narrative topology.",
            "Run run_pipeline.py compile-design --design-layer v3.",
            "Run run_pipeline.py freeze-narrative.",
            "Run run_pipeline.py prepare-rpg-postdesign-slices.",
            "Run RPG post-design agents from workspace/controller-packets/postdesign/rpg/*.json, including RPGSceneScriptWriter for staged dialogue/action scenes, preserving RPG overlay and public graph trace in workspace/rpg/* outputs.",
            "Run run_pipeline.py build --target web-rpg.",
        ]
    else:
        next_actions = [
            "For source-adaptation runs, extract the full source into inputs/source_material/ before spawning authoring agents.",
            "Create role-specific clean-context packets under workspace/controller-packets/; render the separate prompt template and pass only that prompt, the packet content, and the exact role card to each subagent.",
            "Spawn PromptAnalyst, LinearSynopsisDesigner, BranchGraphDesigner, and BaseGameIRDesigner.",
            "For V1 public runtime semantics, put transition gates/effects on branch_graph.edges[*].conditions/effects; BaseGameIRDesigner must declare the referenced state variables and mirror non-trivial edges in game_ir.event_rules.",
            "Write accepted payloads to workspace/design_layer/.",
            "Run validate_artifacts.py --write-projections.",
        ]
    if design_layer != "v3":
        next_actions.append("Author RPG post-design artifacts under workspace/rpg/, including scene-scripts.json for staged dialogue/action scenes, before building.")
    write_controller_state(
        run_root,
        target,
        f"initialized_{design_layer}_design_layer" if design_layer == "v3" else "initialized",
        next_actions,
        design_layer=design_layer,
    )
    write_json(run_root / "reports" / "controller-todo.json", {
        "status": "initialized",
        "target": target,
        "design_layer": design_layer,
        "authoring_roles": (
            (V3_AUTHORING_ROLES + ["RPGSystemPlanner", "RPGDesignReviewer"]) if design_layer == "v3"
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
                "three_level_default": "Long source-adaptation runs should use level_01 source scene/chapter chunks, level_02 arc packets, and level_03 global story/design.",
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
                "references/design-layer-rpg-prompts.md",
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
        },
        "design_layer_v3_artifacts": [
            "workspace/design_layer_v3/hierarchy_policy.json",
            "workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json",
            "workspace/design_layer_v3/facts/canonical_fact_graph.json",
            "workspace/design_layer_v3/adaptation/global_policy.json",
            "workspace/design_layer_v3/design_levels/level_<NN>/state_model.json",
            "workspace/design_layer_v3/design_levels/level_<NN>/story_graph.json",
            "workspace/design_layer_v3/design_levels/level_<NN>/contracts.json",
            "workspace/design_layer_v3/design_levels/level_<NN>/parent_state_settlements.json",
        ],
        "sprite_forge_asset_guidance": [
            "references/sprite-forge/layered-map-contract.md",
            "references/sprite-forge/sprite-modes.md",
            "scripts/sprite_forge/compose_layered_preview.py",
            "scripts/sprite_forge/generate2dsprite.py",
        ],
        "asset_pipeline_artifacts": [
            "workspace/asset-direction.json",
            "workspace/asset-manifest.json",
            "workspace/generated-assets/",
            "reports/asset-generation-report.json",
            "reports/asset-validation.json",
        ],
        "rpg_pipeline_artifacts": [
            "workspace/design_layer_rpg/rpg-overlay-plan.json",
            "workspace/design_layer_rpg/rpg-overlay-review.json",
            "workspace/design_layer_rpg/narrative-freeze.json",
            "workspace/design_layer_rpg/rpg-postdesign-slices.json",
            "workspace/rpg/rpg-campaign.json",
            "workspace/rpg/world-map.json",
            "workspace/rpg/maps/*.map.json",
            "workspace/rpg/actors.json",
            "workspace/rpg/enemies.json",
            "workspace/rpg/quests.json",
            "workspace/rpg/scene-scripts.json",
            "workspace/rpg/rpg-manifest.json",
            "reports/rpg-validation.json",
            "reports/rpg-balance-report.json",
            "reports/rpg-coverage.json",
            "build/web-rpg/",
        ],
    })
    print(str(run_root))


def compile_design_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    if args.design_layer != "v3":
        raise SystemExit("compile-design currently supports --design-layer v3.")
    result = compile_design_v3(run_root)
    report_path = run_root / "workspace" / "design_layer_v3" / "compile_report.json"
    report = load_optional_json(report_path) or result.to_json()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


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
        report_path = write_final_report(run_root)
        write_controller_state(run_root, target, "complete", ["Inspect reports/final-report.json and build/web-rpg/index.html."])
        print(json.dumps({
            "run_root": str(run_root),
            "target": target,
            "web_rpg": str(web_path) if web_path else None,
            "final_report": str(report_path),
        }, indent=2))
        return


def validate_rpg_overlay_run(args: argparse.Namespace) -> None:
    from validate_rpg_overlay import validate_overlay_plan

    run_root = Path(args.run_root).resolve()
    result = validate_overlay_plan(run_root)
    report = load_optional_json(path_for(run_root, "rpg_overlay_validation_report")) or result.to_json()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


def freeze_narrative_run(args: argparse.Namespace) -> None:
    from freeze_narrative import freeze_narrative, verify_narrative_freeze

    run_root = Path(args.run_root).resolve()
    report = verify_narrative_freeze(run_root) if args.verify else freeze_narrative(run_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") == "fail":
        raise SystemExit(1)


def prepare_rpg_postdesign_slices_run(args: argparse.Namespace) -> None:
    from prepare_rpg_postdesign_slices import prepare_rpg_postdesign_slices

    run_root = Path(args.run_root).resolve()
    report = prepare_rpg_postdesign_slices(run_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") == "fail":
        raise SystemExit(1)


def probe_assets_run(args: argparse.Namespace) -> None:
    from asset_manifest_probe import probe_asset_manifest

    run_root = Path(args.run_root).resolve()
    report = probe_asset_manifest(run_root)
    if args.write_report:
        write_json(run_root / "reports" / "asset-manifest-probe.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def generate_backgrounds_run(args: argparse.Namespace) -> None:
    from generate_background_assets import generate_backgrounds

    run_root = Path(args.run_root).resolve()
    report = generate_backgrounds(
        run_root=run_root,
        scope=args.scope,
        image_provider=args.image_provider,
        video_provider=args.video_provider,
        image_model=args.image_model,
        overwrite=args.overwrite,
        env_file=args.env_file,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in ("fail", "needs_imagegen", "needs_boundary_imagegen"):
        raise SystemExit(2 if report["status"] in ("needs_imagegen", "needs_boundary_imagegen") else 1)


def generate_rpg_boundaries_run(args: argparse.Namespace) -> None:
    from generate_rpg_boundaries_from_masks import generate_boundaries as generate_rpg_boundaries

    run_root = Path(args.run_root).resolve()
    report = generate_rpg_boundaries(
        run_root=run_root,
        provider=args.provider,
        env_file=args.env_file,
        overwrite=args.overwrite,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in ("fail", "needs_boundary_imagegen"):
        raise SystemExit(2 if report["status"] == "needs_boundary_imagegen" else 1)


def bind_assets_run(args: argparse.Namespace) -> None:
    run_root = Path(args.run_root).resolve()
    report = bind_generated_assets(run_root, allow_svg=args.allow_svg, env_file=args.env_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


def dispatch_asset_imagegen_run(args: argparse.Namespace) -> None:
    from generate_asset_imagegen_requests import dispatch_asset_imagegen_requests

    run_root = Path(args.run_root).resolve()
    report = dispatch_asset_imagegen_requests(
        run_root,
        overwrite=args.overwrite,
        accept_existing=args.accept_existing,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in ("fail", "needs_asset_imagegen"):
        raise SystemExit(2 if report["status"] == "needs_asset_imagegen" else 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--prompt", required=True)
    init_parser.add_argument("--run-root", required=True)
    init_parser.add_argument("--target", choices=("web-rpg",), default="web-rpg")
    init_parser.add_argument("--design-layer", choices=("v1", "v3"), default="v1")
    init_parser.set_defaults(func=init_run)

    compile_design_parser = subparsers.add_parser("compile-design")
    compile_design_parser.add_argument("--run-root", required=True)
    compile_design_parser.add_argument("--design-layer", choices=("v3",), default="v3")
    compile_design_parser.set_defaults(func=compile_design_run)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--run-root", required=True)
    build_parser.add_argument("--target", choices=("web-rpg",), default="web-rpg")
    build_parser.add_argument("--skip-web", action="store_true")
    build_parser.add_argument("--skip-assets", action="store_true")
    build_parser.add_argument("--asset-provider", default=None)
    build_parser.add_argument("--asset-mode", choices=("auto", "final-quality", "fast-validation"), default="auto")
    build_parser.add_argument("--asset-model", default=None)
    build_parser.add_argument("--audio-provider", default=None)
    build_parser.add_argument("--audio-model", default=None)
    build_parser.add_argument("--audio-fallback-provider", default=None)
    build_parser.add_argument("--bgm-provider", default=None)
    build_parser.add_argument("--sfx-provider", default=None)
    build_parser.add_argument("--voice-provider", default=None)
    build_parser.add_argument("--env-file", default=None)
    build_parser.add_argument("--asset-overwrite", action="store_true")
    build_parser.set_defaults(func=build_run)

    validate_rpg_overlay_parser = subparsers.add_parser("validate-rpg-overlay")
    validate_rpg_overlay_parser.add_argument("--run-root", required=True)
    validate_rpg_overlay_parser.set_defaults(func=validate_rpg_overlay_run)

    freeze_narrative_parser = subparsers.add_parser("freeze-narrative")
    freeze_narrative_parser.add_argument("--run-root", required=True)
    freeze_narrative_parser.add_argument("--verify", action="store_true")
    freeze_narrative_parser.set_defaults(func=freeze_narrative_run)

    prepare_rpg_slices_parser = subparsers.add_parser("prepare-rpg-postdesign-slices")
    prepare_rpg_slices_parser.add_argument("--run-root", required=True)
    prepare_rpg_slices_parser.set_defaults(func=prepare_rpg_postdesign_slices_run)

    probe_parser = subparsers.add_parser("probe-assets")
    probe_parser.add_argument("--run-root", required=True)
    probe_parser.add_argument("--write-report", action="store_true")
    probe_parser.set_defaults(func=probe_assets_run)

    backgrounds_parser = subparsers.add_parser("generate-backgrounds")
    backgrounds_parser.add_argument("--run-root", required=True)
    backgrounds_parser.add_argument("--scope", choices=("rpg",), default="rpg")
    backgrounds_parser.add_argument("--image-provider", default=None)
    backgrounds_parser.add_argument("--video-provider", default=None)
    backgrounds_parser.add_argument("--image-model", default=None)
    backgrounds_parser.add_argument("--env-file", default=None)
    backgrounds_parser.add_argument("--overwrite", action="store_true")
    backgrounds_parser.set_defaults(func=generate_backgrounds_run)

    rpg_boundaries_parser = subparsers.add_parser("generate-rpg-boundaries")
    rpg_boundaries_parser.add_argument("--run-root", required=True)
    rpg_boundaries_parser.add_argument("--provider", default=None)
    rpg_boundaries_parser.add_argument("--env-file", default=None)
    rpg_boundaries_parser.add_argument("--overwrite", action="store_true")
    rpg_boundaries_parser.set_defaults(func=generate_rpg_boundaries_run)

    bind_assets_parser = subparsers.add_parser("bind-assets")
    bind_assets_parser.add_argument("--run-root", required=True)
    bind_assets_parser.add_argument("--env-file", default=None)
    bind_assets_parser.add_argument("--allow-svg", action="store_true")
    bind_assets_parser.set_defaults(func=bind_assets_run)

    dispatch_asset_imagegen_parser = subparsers.add_parser("dispatch-asset-imagegen")
    dispatch_asset_imagegen_parser.add_argument("--run-root", required=True)
    dispatch_asset_imagegen_parser.add_argument("--overwrite", action="store_true")
    dispatch_asset_imagegen_parser.add_argument("--accept-existing", action="store_true")
    dispatch_asset_imagegen_parser.set_defaults(func=dispatch_asset_imagegen_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
