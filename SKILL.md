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

The controller owns global workflow context. It may read `references/design-layer-v2-contracts.md`, validation scripts, and the run directory, but normal clean-context subagents must not be asked to read those global files directly. For each spawn, the controller prepares a role-specific packet and passes only that packet plus the exact role card listed in `references/subagents/README.md`.

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
inputs/source_material/original/
inputs/source_material/full_text.txt
inputs/source_material/source_index.json
inputs/source_material/chunks/*.txt
inputs/source_material/extraction_report.json
workspace/controller-packets/
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/design_layer_v2/
workspace/design_layer_v3/
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

For source-adaptation runs, the first controller-owned preprocessing step is full source extraction. Put the complete extracted text in `inputs/source_material/full_text.txt`, the ordered inventory in `inputs/source_material/source_index.json`, chunk files in `inputs/source_material/chunks/`, and extraction diagnostics in `inputs/source_material/extraction_report.json`. Store a copy or pointer to the original source under `inputs/source_material/original/` only when project policy allows it. Ad hoc names such as `source_full_pdf.txt` or `source_chunks/` must be migrated into these canonical paths before spawning design-layer subagents.

`workspace/controller-packets/` stores the compact packets actually sent to clean-context subagents. A packet should name the role card, list the exact upstream artifact paths included, and include only the source excerpts or slices that role needs. These packets are controller scaffolding, not accepted canonical artifacts.

For long source-adaptation runs, `SourceSegmenter` may be sharded by the controller. Put shard packets under `workspace/controller-packets/source_segmenter/`, run multiple clean-context `SourceSegmenter` workers in parallel, wait for every shard to finish, and store their raw partial payloads under `workspace/controller-packets/source_segmenter_returns/`. The controller then normalizes and merges every accepted shard into the three canonical files: `workspace/design_layer_v2/source_intake/source_segments.json`, `workspace/design_layer_v2/source_intake/source_beat_table.json`, and `workspace/design_layer_v2/source_intake/adaptation_coverage_matrix.json`. Shard workers must not read sibling shard packets, full source text outside their packet, or write canonical artifacts.

## Common Controller Rules

For every clean-context subagent spawn, write or assemble a packet under
`workspace/controller-packets/` and pass only that packet plus the exact role
card. The controller reads contracts and validates outputs; normal authoring
workers do not read global contract files, browse the run directory, or choose
additional upstream files for themselves. Compiler reviewers and repair workers
may receive contract excerpts or validation reports when the controller
explicitly includes them.

If the run adapts an external source, extract the full source before the first
subagent spawn and persist it under `inputs/source_material/` using the
canonical paths above. Do not pass the raw full text to every worker; use it to
prepare role-specific packets.

## V1 Workflow

1. Initialize the run with `scripts/run_pipeline.py init --design-layer v1`.
2. Spawn front-half subagents using role cards under `references/subagents/design-layer/`:
   `PromptAnalyst`, `LinearSynopsisDesigner`, `BranchGraphDesigner`, and `BaseGameIRDesigner`.
3. Save accepted payloads directly to `workspace/design_layer/`:
   `user_requirements.json`, `chapter_linear_synopsis.json`, `branch_graph.json`, and `game_ir.json`.
4. Continue with the common post-design workflow.

## V2 Workflow

1. Initialize the run with `scripts/run_pipeline.py init --design-layer v2`.
2. Spawn front-half subagents using role cards under `references/subagents/design-layer-v2/`:
   `InputProfiler`, `SourceSegmenter`, `SourceFactExtractor`, `AdaptationPolicyDesigner`, `StateModelDesigner`, `MacroGraphDesigner`, `MacroContractWriter`, `MeshExpansionPlanner`, `MeshLayerDesigner`, and optional `DesignV2CompilerReviewer`.
3. For long V2 sources, the controller may split `SourceSegmenter` into shard packets and run those workers in parallel. Wait for all shards to complete, save raw partial returns under `workspace/controller-packets/source_segmenter_returns/`, normalize id/key variants, merge in source order, and only then write the canonical `source_intake/*` JSON files. Do not continue to `SourceFactExtractor` until every source shard is accepted or repaired.
4. For V2 mesh expansion, reuse `MeshLayerDesigner` recursively. Spawn it once per selected parent from `mesh_expansion_policy.json`: depth 1 expands macro nodes, and depth 2+ expands selected `subgraph_node` parents from lower-depth subgraphs. Do not introduce a separate tertiary graph writer role.
5. Save accepted V2 source payloads to `workspace/design_layer_v2/`.
6. Run `scripts/run_pipeline.py compile-design --design-layer v2` to produce `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`.
7. Continue with the common post-design workflow.

## V3 Workflow

1. Initialize the run with `scripts/run_pipeline.py init --design-layer v3`.
2. Spawn V3 subagents using role cards under `references/subagents/design-layer-v3/`:
   `StoryLevelExtractor`, `AdaptationPolicyDesigner`, `LevelStateGraphDesigner`, and optional `DesignV3CompilerReviewer`.
3. Run story extraction from fine to coarse. Every story level supports parallel shard workers by default; the controller owns shard packet creation, raw return storage, and deterministic merge into `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`. Story extraction also captures and aggregates stable facts; the controller persists accepted fact payloads under `workspace/design_layer_v3/facts/`.
4. Design the global adaptation policy from the coarsest story view plus canonical facts. The policy should define route families, tone/style, canon locks, and broad adaptation permissions, not a complete graph/state plan.
5. Run graph/state design from coarse to fine. Each design level supports parallel shard workers by default; each worker receives the global adaptation policy direction plus controller-selected relevant excerpts, then designs state first, then state-dependent routes/choices, then state effects, contracts, and parent settlements. For branch-permitted runs, the task prompt must require visibly networked topology: different node orders or access, state gates, optional/revisit/delayed routes, convergence with route memory, and downstream contracts that read earlier route state. The controller merges shard returns into `state_model.json`, `story_graph.json`, `contracts.json`, and `parent_state_settlements.json`.
6. In V3, design and story must correspond strictly one-to-one at every enabled level: each `linear_story.units[*]` must have exactly one same-level `story_graph.nodes[*]`, and each graph node must reference exactly one same-level story unit. Do not merge multiple story units into fewer design nodes, and do not invent design nodes without story units. Use edges, state, contracts, and parent settlements to express pacing and branching.
7. Every non-coarsest level must write `parent_state_settlements.json`, declaring how local completion or route settlement affects immediate parent state. Settlement effects must not skip the immediate parent level.
8. Run `scripts/run_pipeline.py compile-design --design-layer v3` to produce `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`.
9. Continue with the common post-design workflow.

## Common Post-Design Workflow

1. Downstream agents receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.
2. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
3. Spawn `NodeRealizationPlanner` from `references/subagents/post-design/` after shared state is projected. Its task prompt must make branch realization visible: multi-exit nodes need choice placement, state reads/writes, changed beats before outcomes, downstream payoff notes, and entry variants for nodes with multiple incoming routes.
4. Spawn one `NodeSceneWriter` per `vn_yarn` or `cutscene_yarn` realization plan. For source-adaptation runs, each VN worker must receive and read the exact original source chunk for its own source node, such as `inputs/source_material/chunks/chapter_<NN>.txt`, in addition to the node's plan/graph slice. The worker must not read other source chunks or sibling node packets. It should use the original chunk to preserve source style, scene granularity, and event density while still writing fresh runtime prose instead of copying source text. `NodeDialogueWriter` is a legacy alias only.
5. Spawn gameplay realization writers for supported non-VN plans:
   `BattleRealizationWriter`, `InteractionRealizationWriter`, `PuzzleRealizationWriter`, and `ExplorationRealizationWriter`.
6. Save accepted Yarn fragments under `workspace/vn/fragments/` and accepted gameplay units under their `workspace/realization/<kind>/` directories.
7. Spawn `AssetDirector` after story and gameplay verification when global visual/audio direction is needed. It returns direction only, but it should consolidate and refine scene-authored asset intents from accepted Yarn fragments and manifests instead of inventing unscheduled staging. Voice assets are allowed only for dialogue or monologue line beats; each `voice.*` item must carry the exact spoken text in `text` or `line_text`, plus speaker/line trace when available. Do not use `voice.*` for ambience, UI prompts, scene descriptions that are not spoken/inner monologue, SFX, or BGM.
8. Do not spawn `PresentationDirector`; that role has been removed. Scene staging belongs in `NodeSceneWriter`, while `AssetDirector` only consolidates and prompt-compiles scheduled assets.
9. During build, the controller validates gameplay units, writes `workspace/realization/gameplay-manifest.json`, derives scene asset intents from accepted Yarn fragments and fragment manifests, plans `workspace/asset-manifest.json`, generates runtime assets under `workspace/generated-assets/`, validates them, and binds them into exports. Production image generation for this workflow must use Gemini consistently: run with `--asset-provider gemini` and `GEMINI_API_KEY`. Do not switch to `openai-ppioImage` for final/runtime images unless the user explicitly asks for a provider experiment. Default audio provider is `mock`; use `--audio-provider minimax-ppio` with `AUDIO_API_KEY` or `PPIO_API_KEY` for PPIO MiniMax audio generation. Use `--skip-assets` only for intentionally text-only exports.
    - BGM assets use `bgm.*`, are generated as instrumental loop-friendly music cues, and default to mp3 in `asset-manifest.json`; `minimax-ppio` maps them to MiniMax music generation.
    - AssetDirector should read provider audio capabilities from `references/provider-capabilities/audio-providers.json`, preserve authored voice emotions, and write provider-specific voice emotion/profile bindings under `provider_bindings.<provider>`.
    - AssetDirector must verify recurring character gender/age from story evidence instead of names alone, and portrait directions should state mandatory identity anchors when names, aliases, or nicknames could mislead the image provider.
    - PPIO MiniMax music requests to `https://api.ppio.com/v3/minimax-music` must bypass system proxies. The audio provider enforces this by default; use `AUDIO_NO_PROXY=1` for all audio requests or `PPIO_MINIMAX_MUSIC_NO_PROXY=0` only when explicitly testing proxy routing.
    - Multi-expression portraits use `portrait.<character>.<emotion>` asset ids. The planner groups them per character, stores `expression_asset_ids`, and writes one transparent PNG per expression plus a canonical `charref.*.core` reference. With Gemini, the generator creates a base/neutral portrait first and passes it as a reference image for later expressions so identity and costume stay stable.
    - Voice assets use `voice.*`, are generated through MiniMax TTS when `minimax-ppio` is selected, and are attached only to dialogue/monologue line beats during export.
10. Run `scripts/run_pipeline.py build --run-root <run>`.
11. Inspect `reports/final-report.json`, `reports/validation-report.json`, `reports/gameplay-validation.json`, `reports/gameplay-coverage.json`, `reports/asset-generation-report.json`, `reports/asset-validation.json`, and the playable export.

## Boundaries

Base design artifacts must not contain Yarn syntax, Unity paths, image-generation prompts, or implementation details.

Design Layer V2 has two input modes. `idea` mode creates a synthetic source
segment for a short premise and permits invention inside the brief.
`source_adaptation` mode first creates `workspace/design_layer_v2/source_intake/*`
and requires later macro/mesh agents to cite assigned `source_segment_ids` so
every source segment has explicit coverage. For novel-like source material,
faithfulness comes from sufficiently granular source segments and beat
summaries, not from auxiliary extraction tables. These
source-intake traces are internal and must not change the public
`branch_graph.json` or `game_ir.json` interfaces.
For long or dense novel adaptations, preserve nuance by allocating deeper mesh
where needed and recursively reusing `MeshLayerDesigner` on selected
`subgraph_node` parents. Final playable leaf nodes should represent coherent
scene, dialogue, action, or reveal beats, not whole chapters, when chapter-level
compression would flatten source events or character interaction.
Faithful adaptation also requires reader-experience adaptation. V2 authors must
stage what the player knows, what question is active, what information is still
withheld, what emotion the current beat should produce, and what hook carries
the player into the next beat. Use existing summaries, contracts, continuity
notes, and controller context slices for this internal plan; do not add public
`branch_graph.json` or `game_ir.json` fields for it. Source segment summaries
ground the scene, but runtime prose must be freshly written and must not paste
private summaries as visible text.

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
- `scripts/design_v3_validate.py`: validate V3 hierarchical design artifacts.
- `scripts/design_v3_compile.py`: compile V3 hierarchical design artifacts into `workspace/design_layer/`.
- `scripts/assemble_yarn.py`: assemble per-node Yarn fragments into `workspace/vn/story.yarn`.
- `scripts/story_ir.py`: lower Yarn to a simple StoryIR and verify titles, jumps, and outcomes.
- `scripts/plan_assets.py`: convert `asset-direction.json` plus accepted Yarn/manifest scene asset intents into a deterministic runtime `asset-manifest.json`.
- `scripts/generate_assets.py`: generate or reuse visual and audio assets from `asset-manifest.json`; production images use `gemini` consistently, with `local-svg`/`mock` reserved for tests and `openai-ppioImage` reserved for explicit provider experiments. Audio uses `mock` or `minimax-ppio`.
- `scripts/asset_image_providers.py`: provider adapters, request/response logging, PPIO response parsing, and Gemini image requests.
- `scripts/asset_audio_providers.py`: provider adapters, request/response logging, MiniMax music/TTS parsing, and deterministic local/procedural WAV generation.
- `scripts/generate_audio_asset.py`: generate one BGM, SFX, or voice asset without running the full pipeline.
- `scripts/validate_assets.py`: verify generated asset files and portrait transparency.
- `scripts/export_web_vn.py`: export a self-contained browser-playable VN.
- `scripts/export_unity_project.py`: generate a minimal Unity project from accepted artifacts.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Controller reads `references/artifact-contracts.md` only when exact V1 payload shapes are needed and `references/design-layer-v2-contracts.md` only when exact V2 payload shapes are needed for validation, repair, or packet preparation. Controller reads `references/repair-routing.md` only when validation fails. For subagent dispatch, read `references/subagents/README.md`, then only the specific subagent role card needed for the current spawn. V1 design role cards live under `references/subagents/design-layer/`; V2 design role cards live under `references/subagents/design-layer-v2/`. `references/design-layer-v2-prompts.md` is a compatibility index for the V2 role cards.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.
