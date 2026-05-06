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
workspace/state/shared-state.schema.json
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/realization/gameplay-manifest.json
workspace/realization/battles/*.battle.json
workspace/realization/interactions/*.interaction.json
workspace/realization/puzzles/*.puzzle.json
workspace/realization/explorations/*.exploration.json
workspace/realization/stubs/*.not-implemented.json
workspace/presentation/presentation-plan.json
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
2. Spawn front-half subagents using the role cards under `references/subagents/design-layer/`:
   `PromptAnalyst`, `LinearSynopsisDesigner`, `BranchGraphDesigner`, and `BaseGameIRDesigner`.
3. Save accepted payloads to `workspace/design_layer/`. The design layer produces all four files, while downstream agents receive only `branch_graph.json` and `game_ir.json` derived context.
4. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
5. Spawn `NodeRealizationPlanner` from `references/subagents/post-design/` after shared state is projected.
6. Spawn one `NodeDialogueWriter` per `vn_yarn` or `cutscene_yarn` realization plan. Batch these workers when there are many nodes.
7. Spawn gameplay realization writers for supported non-VN plans:
   `BattleRealizationWriter`, `InteractionRealizationWriter`, `PuzzleRealizationWriter`, and `ExplorationRealizationWriter`.
8. Save accepted Yarn fragments under `workspace/vn/fragments/` and accepted gameplay units under their `workspace/realization/<kind>/` directories.
9. Spawn `AssetDirector` after story and gameplay verification when visual direction is needed. It returns direction only. Voice assets are allowed only for dialogue or monologue line beats; each `voice.*` item must carry the exact spoken text in `text` or `line_text`, plus speaker/line trace when available. Do not use `voice.*` for ambience, UI prompts, scene descriptions that are not spoken/inner monologue, SFX, or BGM.
10. Optionally spawn `PresentationDirector` after `workspace/asset-manifest.json` exists when VN staging needs richer portrait expression and entrance/exit direction. It returns `workspace/presentation/presentation-plan.json` only. The controller applies it with `scripts/apply_presentation_plan.py`, inserting safe `show_char`, `set_expression`, and `hide_char` commands into accepted Yarn fragments without changing text, state, outcomes, voice, SFX, or BGM.
11. During build, the controller validates gameplay units, writes `workspace/realization/gameplay-manifest.json`, plans `workspace/asset-manifest.json`, applies `workspace/presentation/presentation-plan.json` when present, generates runtime assets under `workspace/generated-assets/`, validates them, and binds them into exports. Default image asset provider is `local-svg`; use `--asset-provider gemini` with `GEMINI_API_KEY` or `--asset-provider openai-ppioImage` with `IMAGE_API_KEY` for model-backed image generation. Default audio provider is `mock`; use `--audio-provider minimax-ppio` with `AUDIO_API_KEY` or `PPIO_API_KEY` for PPIO MiniMax audio generation. Use `--skip-assets` only for intentionally text-only exports.
    - BGM assets use `bgm.*`, are generated as instrumental loop-friendly music cues, and default to mp3 in `asset-manifest.json`; `minimax-ppio` maps them to MiniMax music generation.
    - Multi-expression portraits use `portrait.<character>.<emotion>` asset ids. The planner groups them per character, stores `expression_asset_ids`, and writes one transparent PNG per expression plus a canonical `charref.*.core` reference. With Gemini, the generator creates a base/neutral portrait first and passes it as a reference image for later expressions so identity and costume stay stable.
    - Voice assets use `voice.*`, are generated through MiniMax TTS when `minimax-ppio` is selected, and are attached only to dialogue/monologue line beats during export.
12. Run `scripts/run_pipeline.py build --run-root <run>`.
13. Inspect `reports/final-report.json`, `reports/validation-report.json`, `reports/gameplay-validation.json`, `reports/gameplay-coverage.json`, `reports/presentation-validation.json`, `reports/asset-generation-report.json`, `reports/asset-validation.json`, and the playable export.

## Boundaries

Base design artifacts must not contain Yarn syntax, Unity paths, image-generation prompts, or implementation details.

`game_ir.json` is the semantic authority for state variables, transition conditions, world-state effects, and progression rules.

`shared-state.schema.json` is projected from `game_ir.json`; do not author it by hand unless repairing the projector itself.

Every branch graph node maps to exactly one realization plan. Per-node workers produce fragments, gameplay units, or stubs; the controller exports one game, not one project per node.

Supported gameplay adapters are declarative and fixed by the controller:
`battle.choice_duel`, `interaction.inspect_scene`, `puzzle.sequence_lock`, and `exploration.room_nav`.
Subagents do not write runtime code for these adapters.

`interaction.inspect_scene` supports both minimal hotspot inspection and richer scene-local loops: visual hotspot overlays, optional action budgets, local items, item use on gated hotspots, hidden hotspot reveals, evidence combinations, compact evidence presentation, and planned completion outcomes. Local interaction items and evidence are not persistent game state; durable consequences still go through `game_ir.json` variables and validated `state_writes`.

`external_stub` and unsupported adapters become typed not-implemented stubs. Supported `battle`, `interaction`, `puzzle`, and `exploration` plans require matching gameplay unit artifacts.

## Tools

- `scripts/run_pipeline.py`: initialize runs and build/export accepted artifacts.
- `scripts/validate_artifacts.py`: validate core artifacts and write shared-state projection.
- `scripts/validate_gameplay.py`: validate gameplay realization units and write gameplay reports.
- `scripts/compile_gameplay_manifest.py`: compile gameplay unit artifacts into `workspace/realization/gameplay-manifest.json`.
- `scripts/assemble_yarn.py`: assemble per-node Yarn fragments into `workspace/vn/story.yarn`.
- `scripts/story_ir.py`: lower Yarn to a simple StoryIR and verify titles, jumps, and outcomes.
- `scripts/plan_assets.py`: convert `asset-direction.json` into a deterministic runtime `asset-manifest.json`.
- `scripts/apply_presentation_plan.py`: apply `PresentationDirector` command insertions to accepted Yarn fragments and refresh fragment manifests.
- `scripts/generate_assets.py`: generate or reuse visual and audio assets from `asset-manifest.json`; images use `local-svg`, `mock`, `gemini`, or `openai-ppioImage`, while audio uses `mock` or `minimax-ppio`.
- `scripts/asset_image_providers.py`: provider adapters, request/response logging, PPIO response parsing, and Gemini image requests.
- `scripts/asset_audio_providers.py`: provider adapters, request/response logging, MiniMax music/TTS parsing, and deterministic local/procedural WAV generation.
- `scripts/generate_audio_asset.py`: generate one BGM, SFX, or voice asset without running the full pipeline.
- `scripts/validate_assets.py`: verify generated asset files and portrait transparency.
- `scripts/export_web_vn.py`: export a self-contained browser-playable VN.
- `scripts/export_unity_project.py`: generate a minimal Unity project from accepted artifacts.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Read `references/artifact-contracts.md` only when you need exact payload shapes. Read `references/repair-routing.md` only when validation fails. Read `references/subagents/README.md`, then only the specific subagent role card needed for the current spawn.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.
