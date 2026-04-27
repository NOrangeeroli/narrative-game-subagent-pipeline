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

Use `references/subagent-prompts.md` to spawn clean-context authoring subagents. Save accepted payloads into the run layout described below.

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
workspace/design_layer/chapter_branch_graph.json
workspace/design_layer/game_ir.json
workspace/state/shared-state.schema.json
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/realization/stubs/*.not-implemented.json
workspace/vn/fragments/*.yarn
workspace/vn/fragments/*.manifest.json
workspace/vn/story.yarn
workspace/vn/story.storyir.json
workspace/asset-direction.json
build/web-vn/
build/unity-project/
reports/*.json
```

Large generated payloads stay on disk. Keep summaries in chat concise and point to run paths.

## Workflow

1. Initialize the run with `scripts/run_pipeline.py init`.
2. Spawn front-half subagents using `references/subagent-prompts.md`:
   `PromptAnalyst`, `LinearSynopsisDesigner`, `BranchGraphDesigner`, and `BaseGameIRDesigner`.
3. Save accepted payloads to `workspace/design_layer/`.
4. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
5. Spawn `NodeRealizationPlanner` after shared state is projected.
6. Spawn one `NodeDialogueWriter` per `vn_yarn` or `cutscene_yarn` realization plan. Batch these workers when there are many nodes.
7. Save each accepted Yarn fragment and sidecar manifest under `workspace/vn/fragments/`.
8. Spawn `AssetDirector` after story verification when visual direction is needed. It returns art direction only.
9. Run `scripts/run_pipeline.py build --run-root <run>`.
10. Inspect `reports/final-report.json`, `reports/validation-report.json`, and the playable export.

## Boundaries

Base design artifacts must not contain Yarn syntax, Unity paths, image-generation prompts, or implementation details.

`game_ir.json` is the semantic authority for state variables, transition conditions, world-state effects, and progression rules.

`shared-state.schema.json` is projected from `game_ir.json`; do not author it by hand unless repairing the projector itself.

Every branch graph node maps to exactly one realization plan. Per-node workers produce fragments or stubs; the controller exports one game, not one project per node.

Unsupported `battle`, `interaction`, `puzzle`, `exploration`, and `external_stub` units become typed not-implemented stubs unless the user asks for an implemented custom adapter.

## Tools

- `scripts/run_pipeline.py`: initialize runs and build/export accepted artifacts.
- `scripts/validate_artifacts.py`: validate core artifacts and write shared-state projection.
- `scripts/assemble_yarn.py`: assemble per-node Yarn fragments into `workspace/vn/story.yarn`.
- `scripts/story_ir.py`: lower Yarn to a simple StoryIR and verify titles, jumps, and outcomes.
- `scripts/export_web_vn.py`: export a self-contained browser-playable VN.
- `scripts/export_unity_project.py`: generate a minimal Unity project from accepted artifacts.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Read `references/artifact-contracts.md` only when you need exact payload shapes. Read `references/repair-routing.md` only when validation fails. Read `references/subagent-prompts.md` before spawning authoring workers.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.
