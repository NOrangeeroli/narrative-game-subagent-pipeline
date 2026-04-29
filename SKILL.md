---
name: narrative-game-subagent-pipeline
description: Generate a playable branching narrative game by coordinating multiple Codex subagents through a self-contained artifact pipeline. Use when the user wants prompt-to-game generation, VN/Yarn-style realization, branching story graphs, Game IR, asset direction, Web VN export, Unity project export, subagent fan-out, artifact validation, or repair routing without depending on an external repository.
---

# Narrative Game Subagent Pipeline

## Controller Rule

Act as the workflow controller. This skill is self-contained: use only files bundled in this skill's `scripts/`, `assets/`, and `references/` directories.

When spawning subagents, do not set a `model` override. Omit the `model` field unless the user explicitly requests a specific model.

Subagents author typed payloads only. They do not write canonical artifacts, edit generated runtime code, run exporters, or decide whether a stage passes.

The controller owns run layout, artifact persistence, schema validation, deterministic verification, repair tickets, retries, per-node fan-out, story assembly, export, and final reporting.

## Quick Start

Create a run:

```bash
python3 ~/.codex/skills/narrative-game-subagent-pipeline/scripts/run_pipeline.py init \
  --prompt "A one-sentence game prompt" \
  --run-root runs/my-game
```

Use `references/subagents/README.md` to find the specific subagent role card needed for a clean-context authoring spawn. Save accepted payloads into the run layout described below.

Build and export after required artifacts exist:

```bash
python3 ~/.codex/skills/narrative-game-subagent-pipeline/scripts/run_pipeline.py build \
  --run-root runs/my-game
```

This writes a browser-playable VN under `build/web-vn/` by default. Use `--export-unity` to also generate a minimal Unity project under `build/unity-project/`.

## Artifact Layout

Use these canonical paths inside each run:

```text
inputs/prompt.txt
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/design_layer_v2/
workspace/state/shared-state.schema.json
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/realization/gameplay-manifest.json
workspace/realization/battles/*.battle.json
workspace/realization/interactions/*.interaction.json
workspace/realization/puzzles/*.puzzle.json
workspace/realization/explorations/*.exploration.json
workspace/realization/stubs/*.not-implemented.json
workspace/vn/fragments/*.yarn
workspace/vn/fragments/*.manifest.json
workspace/vn/story.yarn
workspace/vn/story.storyir.json
workspace/asset-direction.json
workspace/asset-manifest.json
workspace/generated-assets/
build/web-vn/
build/unity-project/
reports/asset-generation-report.json
reports/asset-validation.json
reports/gameplay-validation.json
reports/gameplay-coverage.json
reports/*.json
```

Large generated payloads stay on disk. Keep summaries in chat concise and point to run paths.

## Workflow

1. Initialize the run with `scripts/run_pipeline.py init`.
2. For V1, spawn front-half subagents using role cards under `references/subagents/design-layer/`:
   `PromptAnalyst`, `LinearSynopsisDesigner`, `BranchGraphDesigner`, and `BaseGameIRDesigner`.
3. For V2, spawn front-half subagents using role cards under `references/subagents/design-layer-v2/`:
   `SourceFactExtractor`, `AdaptationPolicyDesigner`, `StateModelDesigner`, `MacroGraphDesigner`, `MacroContractWriter`, `MeshExpansionPlanner`, `MeshLayerDesigner`, and optional `DesignV2CompilerReviewer`.
4. Save accepted V1 payloads to `workspace/design_layer/`. Save accepted V2 source payloads to `workspace/design_layer_v2/`, then run `scripts/run_pipeline.py compile-design --design-layer v2` to produce `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`.
5. Downstream agents receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.
6. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
7. Spawn `NodeRealizationPlanner` from `references/subagents/post-design/` after shared state is projected.
8. Spawn one `NodeDialogueWriter` per `vn_yarn` or `cutscene_yarn` realization plan. Batch these workers when there are many nodes.
9. Spawn gameplay realization writers for supported non-VN plans:
   `BattleRealizationWriter`, `InteractionRealizationWriter`, `PuzzleRealizationWriter`, and `ExplorationRealizationWriter`.
10. Save accepted Yarn fragments under `workspace/vn/fragments/` and accepted gameplay units under their `workspace/realization/<kind>/` directories.
11. Spawn `AssetDirector` after story and gameplay verification when visual direction is needed. It returns art direction only.
12. During build, the controller validates gameplay units, writes `workspace/realization/gameplay-manifest.json`, plans `workspace/asset-manifest.json`, generates runtime assets under `workspace/generated-assets/`, validates them, and binds them into exports. Default asset provider is `local-svg`; use `--asset-provider gemini` with `GEMINI_API_KEY` or `--asset-provider openai-ppioImage` with `IMAGE_API_KEY` for model-backed image generation. Use `--skip-assets` only for intentionally text-only exports.
13. Run `scripts/run_pipeline.py build --run-root <run>`.
14. Inspect `reports/final-report.json`, `reports/validation-report.json`, `reports/gameplay-validation.json`, `reports/gameplay-coverage.json`, `reports/asset-generation-report.json`, `reports/asset-validation.json`, and the playable export.

## Boundaries

Base design artifacts must not contain Yarn syntax, Unity paths, image-generation prompts, or implementation details.

`game_ir.json` is the semantic authority for state variables, transition conditions, world-state effects, and progression rules.

`shared-state.schema.json` is projected from `game_ir.json`; do not author it by hand unless repairing the projector itself.

Every branch graph node maps to exactly one realization plan. Per-node workers produce fragments, gameplay units, or stubs; the controller exports one game, not one project per node.

Supported gameplay adapters are declarative and fixed by the controller:
`battle.choice_duel`, `interaction.inspect_scene`, `puzzle.sequence_lock`, and `exploration.room_nav`.
Subagents do not write runtime code for these adapters.

`external_stub` and unsupported adapters become typed not-implemented stubs. Supported `battle`, `interaction`, `puzzle`, and `exploration` plans require matching gameplay unit artifacts.

## Tools

- `scripts/run_pipeline.py`: initialize runs and build/export accepted artifacts.
- `scripts/validate_artifacts.py`: validate core artifacts and write shared-state projection.
- `scripts/validate_gameplay.py`: validate gameplay realization units and write gameplay reports.
- `scripts/compile_gameplay_manifest.py`: compile gameplay unit artifacts into `workspace/realization/gameplay-manifest.json`.
- `scripts/design_v2_validate.py`: validate V2 source design artifacts.
- `scripts/design_v2_compile.py`: compile V2 source artifacts into `workspace/design_layer/`.
- `scripts/design_v2_project_context.py`: project a focused node context from compiled V2 artifacts.
- `scripts/assemble_yarn.py`: assemble per-node Yarn fragments into `workspace/vn/story.yarn`.
- `scripts/story_ir.py`: lower Yarn to a simple StoryIR and verify titles, jumps, and outcomes.
- `scripts/plan_assets.py`: convert `asset-direction.json` into a deterministic runtime `asset-manifest.json`.
- `scripts/generate_assets.py`: generate or reuse visual assets from `asset-manifest.json` through `local-svg`, `mock`, `gemini`, or `openai-ppioImage` providers.
- `scripts/asset_image_providers.py`: provider adapters, request/response logging, PPIO response parsing, and Gemini image requests.
- `scripts/validate_assets.py`: verify generated asset files and portrait transparency.
- `scripts/export_web_vn.py`: export a self-contained browser-playable VN.
- `scripts/export_unity_project.py`: generate a minimal Unity project from accepted artifacts.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Read `references/artifact-contracts.md` only when you need exact V1 payload shapes. Read `references/design-layer-v2-contracts.md` only when you need exact V2 payload shapes. Read `references/repair-routing.md` only when validation fails. Read `references/subagents/README.md`, then only the specific subagent role card needed for the current spawn. V1 design role cards live under `references/subagents/design-layer/`; V2 design role cards live under `references/subagents/design-layer-v2/`. `references/design-layer-v2-prompts.md` is a compatibility index for the V2 role cards.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.
