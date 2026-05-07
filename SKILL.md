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

The controller owns global workflow context. It may read validation scripts, contract references, and the run directory, but subagents must be spawned in clean-context mode: they must not browse global files directly or receive an open-ended instruction to inspect the run. For every subagent spawn, including design, V3, post-design, review, and repair workers, the controller prepares a role-specific packet, uses the separate prompt template listed in `references/subagents/README.md`, and passes only the rendered prompt, packet content, and exact role card. Prompt templates must live outside role card files.

## Quick Start

Create a run:

```bash
python3 ~/.codex/skills/narrative-game-subagent-pipeline/scripts/run_pipeline.py init \
  --prompt "A one-sentence game prompt" \
  --run-root runs/my-game
```

Use `references/subagents/README.md` to find the specific subagent role card and prompt template needed for a clean-context authoring spawn. Save accepted payloads into the run layout described below.

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
build/web-adventure/
build/unity-adventure/
reports/asset-generation-report.json
reports/asset-validation.json
reports/gameplay-validation.json
reports/gameplay-coverage.json
reports/*.json
```

Large generated payloads stay on disk. Keep summaries in chat concise and point to run paths.

For source-adaptation runs, the first controller-owned preprocessing step is full source extraction. Put the complete extracted text in `inputs/source_material/full_text.txt`, the ordered inventory in `inputs/source_material/source_index.json`, chunk files in `inputs/source_material/chunks/`, and extraction diagnostics in `inputs/source_material/extraction_report.json`. Store a copy or pointer to the original source under `inputs/source_material/original/` only when project policy allows it. Ad hoc names such as `source_full_pdf.txt` or `source_chunks/` must be migrated into these canonical paths before spawning design-layer subagents.

`workspace/controller-packets/` stores the compact packets actually sent to clean-context subagents. A packet should name the role card, list the exact upstream artifact paths included, and include only the source excerpts or slices that role needs. These packets are controller scaffolding, not accepted canonical artifacts.

For large V3 story levels, do not send a whole `linear_story.json` to shard
workers. The controller keeps `story_levels/level_<NN>/linear_story.json` as the
canonical merged validation/compile artifact, then deterministically derives
shard-sized input files under `story_levels/level_<NN>/slices/` and, when
needed, matching fact/policy slices under `facts/level_<NN>/slices/`.
`slices/` files are controller-generated projections from canonical artifacts:
they must be reproducible, must not contain new creative content, and are not
accepted canonical artifacts. Subagent packets point to these slice files, not
to the full canonical story file.

For V3 source-adaptation runs, finest-level `StoryLevelExtractor` sharding must cover the full source inventory, not a representative sample. The controller partitions every entry in `inputs/source_material/source_index.json` across shard packets under `workspace/design_layer_v3/story_levels/level_01/shards/`, waits for every shard, stores raw returns under `workspace/design_layer_v3/story_levels/level_01/shard_returns/`, and verifies that every source chunk/span was either extracted or explicitly compressed before merging `level_01/linear_story.json` and `facts/level_01/local_facts.json`. Do not proceed to higher story levels, policy design, or graph/state design while any source chunk is unassigned, unfinished, or failed.

## Common Controller Rules

For every subagent spawn, write or assemble a packet under
`workspace/controller-packets/` and use a role-specific prompt template from
`references/design-layer-prompts.md`, `references/design-layer-v3-prompts.md`,
or `references/post-design-prompts.md`. Keep prompt templates separate from role
cards. The controller reads contracts and validates outputs; workers do not read
global contract files, browse the run directory, or choose additional upstream
files for themselves. Compiler reviewers and repair workers may receive contract
excerpts or validation reports when the controller explicitly includes them. Do
not spawn a worker from a loose natural-language task if the corresponding role
card and controller prompt template have not both been selected.

Every packet must declare its scope. At minimum include the role, level,
`shard_id`, whether it is `global`, assigned source chunk ids or story unit ids,
parent story/graph node ids when applicable, allowed input paths, and forbidden
input path patterns. Non-coarsest packets must use controller-made slices, not
full same-level or full lower-level canonical artifacts. Coarsest/global V3
packets are the only exception: they may see all immediate child summaries or
all coarsest same-level story units needed for global coordination, but must not
receive full source text, all L1 detail, sibling shard packets, or lower-level
design artifacts.

If the run adapts an external source, extract the full source before the first
subagent spawn and persist it under `inputs/source_material/` using the
canonical paths above. Do not pass the raw full text to every worker; use it to
prepare role-specific packets.

## Design Layer Modules

The design layer has exactly two parallel modules: V1 and V3. Choose one module at run initialization and keep its authoring flow separate. Both modules must ultimately produce the same public runtime interface under `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`, but their upstream authoring artifacts, role cards, controller packets, validation, and compile steps are different.

Do not mix V1 and V3 role cards in the same design pass. Downstream post-design agents receive the compiled public artifacts plus controller-made slices; they should not depend on private V3 hierarchy files unless a targeted repair explicitly requires them.

## V1 Module Workflow

1. Initialize the run with `scripts/run_pipeline.py init --design-layer v1`.
2. Spawn front-half subagents using role cards under `references/subagents/design-layer/`:
   `PromptAnalyst`, `LinearSynopsisDesigner`, `BranchGraphDesigner`, and `BaseGameIRDesigner`.
3. In V1, `branch_graph.edges[*].conditions` and
   `branch_graph.edges[*].effects` are the same public runtime transition
   interface used by compiled V3. `BranchGraphDesigner` should put edge-local
   state gates/effects directly on edges, and `BaseGameIRDesigner` should
   declare the referenced state variables and mirror non-trivial edge semantics
   in `game_ir.event_rules`.
4. Save accepted payloads directly to `workspace/design_layer/`:
   `user_requirements.json`, `chapter_linear_synopsis.json`, `branch_graph.json`, and `game_ir.json`.
5. Continue with the common post-design workflow.

## V3 Module Workflow

1. Initialize the run with `scripts/run_pipeline.py init --design-layer v3`.
2. Spawn V3 subagents using role cards under `references/subagents/design-layer-v3/`:
   `StoryLevelExtractor`, `AdaptationPolicyDesigner`, `LevelStateGraphDesigner`, and optional `DesignV3CompilerReviewer`.
3. Run story extraction from fine to coarse. Long source-adaptation VN runs should use three enabled story levels by default: `level_01` scene/chapter chunks, `level_02` arc packets, and `level_03` global story line. Non-coarsest story levels support parallel shard workers; each worker receives only its assigned source chunks or immediate child story-unit slice. The controller owns shard packet creation, raw return storage, and deterministic merge into `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`. The coarsest enabled story level must be handled by exactly one global `StoryLevelExtractor` worker so the run has one global story line and one global aggregated fact view before policy or graph/state design begins; this global worker receives only the immediate lower-level summaries/fact view needed for global aggregation, not full source or all lower-level detail. For source adaptations, the finest level must partition and cover every source chunk/span from `inputs/source_material/source_index.json`; representative excerpts are not valid input coverage. Story extraction also captures and aggregates stable facts; the controller persists accepted fact payloads under `workspace/design_layer_v3/facts/`.
4. Design the global adaptation policy from the coarsest story view plus canonical facts. The policy should define route families, tone/style, canon locks, and broad adaptation permissions, not a complete graph/state plan.
5. Run graph/state design from coarse to fine. The coarsest design level, normally `level_03` in long adaptations, must be handled by exactly one global `LevelStateGraphDesigner` worker so the run has one global graph and one global state model. Lower design levels must be sharded by immediate parent graph node or parent story packet. Each non-coarsest worker receives only the parent graph/state/contracts slice, assigned same-level story-unit slice, assigned fact/policy slice, and controller-selected evidence excerpts needed for that parent. It must not receive all same-level story units, all sibling parent contexts, full lower-level story files, full source text, or sibling shard packets. For branch-permitted runs, the task prompt must require visibly networked topology: different node orders or access, state gates, optional/revisit/delayed routes, convergence with route memory, and downstream contracts that read earlier route state. The controller merges shard returns into `state_model.json`, `story_graph.json`, `contracts.json`, and `parent_state_settlements.json`.
6. In V3, design and story must preserve source anchoring at every enabled level, but graph/state design may expand one same-level story unit into multiple state-dependent graph nodes. Each `linear_story.units[*]` must be referenced by at least one same-level `story_graph.nodes[*].story_unit_ids`, and every graph node must reference one or more same-level story units. Do not invent graph nodes without source anchors; use source-anchored canon, variant, failure, delayed, revisit, consequence, or bridge nodes plus edges, state, contracts, and parent settlements to express pacing and branching.
7. Every non-coarsest level must write `parent_state_settlements.json`, declaring how local completion or route settlement affects immediate parent state. Settlement effects must not skip the immediate parent level.
8. Run `scripts/run_pipeline.py compile-design --design-layer v3` to produce `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`.
9. Continue with the common post-design workflow.

## Common Post-Design Workflow

1. Downstream agents receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.
2. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
3. Spawn `NodeRealizationPlanner` from `references/subagents/post-design/` after shared state is projected. Its task prompt must make branch realization visible: multi-exit nodes need choice placement, state reads/writes, changed beats before outcomes, downstream payoff notes, and entry variants for nodes with multiple incoming routes. Use the controller-facing template in `references/post-design-prompts.md`.
4. Spawn `NodeSceneWriter` workers for accepted `vn_yarn` and `cutscene_yarn` realization plans. For small runs, one worker per plan is acceptable. For large source-adaptation VN runs, the controller may shard by source chunk or chapter using the `NodeSceneWriterChapterShard` packet shape and spawn template in `references/post-design-prompts.md`; each shard worker writes multiple per-node fragment pairs, but each assigned node still gets exactly one separate `<source_node_id>.yarn` and one separate `<source_node_id>.manifest.json`. Each VN worker must receive and read the exact original source chunk assigned in its packet, such as `inputs/source_material/chunks/chapter_<NN>.txt`, and must not read other source chunks or sibling packets. It should use the original chunk to preserve source style, scene granularity, and event density while still writing fresh runtime prose instead of copying source text. `NodeDialogueWriter` is a legacy alias only.
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
- `scripts/validate_adventure.py`: validate side-scroller adventure artifacts.
- `scripts/compile_adventure_manifest.py`: compile adventure artifacts into `workspace/adventure/adventure-manifest.json`.
- `scripts/export_web_adventure.py`: export a self-contained browser-playable side-scroller adventure.
- `scripts/export_unity_adventure.py`: generate a Unity 2D side-scroller adventure project.
- `scripts/simulate_adventure_paths.py`: simulate adventure bindings across public graph paths and ending families.
- `scripts/capture_unity_adventure.py`: run route simulation and record Unity availability for adventure playtests.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Controller reads `references/artifact-contracts.md` only when exact V1 payload shapes are needed and `references/design-layer-v3-contracts.md` only when exact V3 payload shapes are needed for validation, repair, or packet preparation. Controller reads `references/repair-routing.md` only when validation fails. For subagent dispatch, read `references/subagents/README.md`, then only the specific subagent role card and separate prompt template needed for the current spawn. V1 design role cards live under `references/subagents/design-layer/`, with templates in `references/design-layer-prompts.md`; V3 design role cards live under `references/subagents/design-layer-v3/`, with templates in `references/design-layer-v3-prompts.md`.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.

## Side-Scroller Adventure Workflow

Use `side_scroller_adventure` when the same V3 narrative graph should become a
2D horizontal mobile adventure instead of a visual novel. The genre adds a
spatial layer while preserving `branch_graph.json`, `game_ir.json`, shared
state, and V3 ending path closure.

Adventure roles live under `references/subagents/adventure/`:

- `AdventureGenrePlanner`
- `WorldMapDesigner`
- `LevelBlockoutDesigner`
- `InteractionQuestDesigner`
- `AdventureNarrativeBinder`
- `AdventureAssetDirector`
- `AdventureCompilerReviewer`

Controller commands:

```bash
python3 scripts/run_pipeline.py plan-adventure --run-root <run-root>
python3 scripts/run_pipeline.py compile-adventure --run-root <run-root>
python3 scripts/run_pipeline.py validate-adventure --run-root <run-root>
python3 scripts/run_pipeline.py export-adventure-web --run-root <run-root>
python3 scripts/run_pipeline.py export-adventure-unity --run-root <run-root>
python3 scripts/run_pipeline.py build-adventure --run-root <run-root> --platform desktop
python3 scripts/run_pipeline.py test-adventure --run-root <run-root>
```

Generated artifacts:

```text
workspace/adventure/
workspace/assets/adventure/
build/web-adventure/
build/unity-adventure/
reports/adventure-validation.json
reports/adventure-coverage.json
reports/adventure-playtest.json
reports/adventure-export.json
reports/web-adventure-export-report.json
```

Web adventure export is manifest-driven and self-contained. It writes an
`index.html` side-scroller under `build/web-adventure/` that can be opened
directly in a browser without Unity or a local server.

Unity adventure export is manifest-driven. It produces a runnable project
scaffold with 2D movement, camera follow, interactions, mobile controls, and
ending route bindings; compiling the player still requires a local Unity Editor.
