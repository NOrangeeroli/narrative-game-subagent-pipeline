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

## User Clarification Gate

At the beginning of a game-generation request, inspect the user's prompt for
the explicit choices below before initializing a run or starting implementation.
If a required high-level choice is missing and cannot be safely inferred, ask
the user once to clarify the overall intent instead of silently choosing. After
the overall intent is clear, proceed without re-asking during later artifact,
asset, script, or export steps unless the user changes scope or a new blocking
ambiguity appears.

This start-of-request check is mandatory: if any required overall-intent choice
is missing, stop immediately and confirm it with the user before creating,
editing, generating, exporting, or validating anything for the game.

- `target`: ask for `web-vn`, `web-rpg`, or `mixed-vn`. Infer `web-rpg` only
  when the prompt clearly asks for RPG exploration, maps, actors, inventory,
  battles, NPCs, quests, or a playable top-down RPG. Infer `web-vn` only for
  visual-novel, branching-story, Yarn, or dialogue-first requests.
- asset quality tier: ask whether the run should be a fast low-tier playable
  prototype or final-quality art. Low tier uses deterministic local visual
  output such as `local-svg` or other placeholders. Final-quality art requires
  generated or supplied production assets.
- external visual provider access: when the user asks for final-quality art,
  resolve provider configuration at initialization with this strict priority:
  active shell environment variables first, then `<run-root>/.env`, then the
  repository root `.env`, then a user question only if the required provider or
  key is still missing. Automatically load discovered `.env` provider settings
  into the active environment/config variables before running provider checks,
  asset generation, background generation, runtime media generation, or export
  commands. Do not conclude that a provider is unavailable until this priority
  chain has been applied. For model-backed still images, use `GEMINI_API_KEY`
  for `gemini` or `IMAGE_API_KEY` / `PPIO_API_KEY` for `openai-ppioImage`. For
  provider-backed I2V background videos, default to PPIO Veo 3.1 Fast
  first/last-frame generation with `I2V_API_KEY`, `VIDEO_API_KEY`, or
  `PPIO_API_KEY`. If the needed key is missing after environment and `.env`
  loading, ask the user at initialization to provide a key, choose a lower tier,
  or supply finished assets as `provider_hints`.

Do not ask for a subagent model. The only model question should be for external
asset providers, and only when the user wants to override the provider default.

If the user asks to generate a game, RPG, map-based game, playable prototype,
visual novel, or mixed VN/RPG and does not explicitly state the asset quality
tier, the controller must ask this at the start of the request:

1. fast playable prototype with local placeholder assets,
2. final-quality generated or supplied art,
3. hybrid partial-quality art, such as final maps and main character with
   placeholder secondary assets.

This initial question is mandatory even when the request mentions
`$generate2dmap`, `$generate2dsprite`, "use skill", "make it playable", or a
specific story prompt. It is a one-time clarification of overall intent, not a
requirement to pause again before every later file write or asset step.

## Provider Resolution

Provider resolution is a controller-owned initialization step for every
generation run. Resolve and freeze provider settings before creating or
regenerating runtime assets.

Use this priority order for every provider family:

1. Active shell environment variables already present in the current process.
2. Values loaded from `<run-root>/.env`.
3. Values loaded from the repository root `.env`.
4. A concise initialization question to the user when required values are still
   missing.

After loading `.env` files, write the discovered values into the active
environment/config variables used by scripts and subagents. Later stages must
receive the resolved provider variables explicitly, either through inherited
environment variables, command flags, or a run-local provider config artifact.
Do not silently replace a missing final-quality provider with `local-svg` or
`mock`; final-quality runs must fail closed or ask the user unless the user
explicitly authorizes fallback.

## Visual Asset Policy

Choose visual asset sources in this priority order:

1. Accepted Sprite Forge or user-supplied production assets bound through
   `provider_hints`. For maps, sprites, props, icons, enemy sprites, battle
   backgrounds, walk sheets, and layered previews, Sprite Forge-generated assets
   are the preferred final-quality path because they preserve transparency,
   layer separation, prompt metadata, and local QC.
2. External model-backed image generation for every required still visual asset
   type when final-quality art is requested and Sprite Forge/source assets are
   not already available. This applies equally to `map_assets`,
   `battle_backgrounds`, `backgrounds`, `tilesets`, `sprites`,
   `enemy_sprites`, `item_icons`, `skill_icons`, `equipment_icons`, `rpg_ui`,
   portraits, props, CGs, hotspot/symbol/effect art, and any other visible
   runtime asset. No visible asset type is lower priority than backgrounds in a
   final-quality run.
3. `local-svg` or other deterministic placeholder output for low-tier playable
   prototypes, tests, and fallback after provider failure only when fallback was
   explicitly allowed by the user or the run quality tier is not final-quality.

Do not route image assets through the `mock` provider in normal generation
prompts. `local-svg` is the default low-tier visual fallback. If a final-quality
external provider fails, preserve the error in reports and stop for repair or
explicit fallback approval; do not describe `local-svg` or `mock` output as
final art.

For final-quality Web RPG runs, Sprite Forge image generation must include
walking animation source art for the controllable player character. Generate a
4x4 four-direction walk sheet or equivalent processed directional frames with
built-in `image_gen`, process it locally, bind it as a runtime asset, and set
the actor's `walk_sheet_asset_id` or `walk_frame_asset_ids` so the runtime plays
walking frames while moving. A single static player sprite plus idle bobbing is
not enough for final-quality RPG movement.

For final-quality RPG map background generation, always produce both still and
dynamic backgrounds in this order: first generate and accept the still
`map_asset`, then run the walkable-mask boundary workflow on that exact still
image, then generate provider-backed I2V dynamic backgrounds from the accepted
still. The still `map_asset` is the runtime fallback only; it is not a
replacement for dynamic `bgv.*` media when final-quality dynamic backgrounds
are requested. Static and dynamic backgrounds for the same map must share the
same boundary contract: dynamic I2V may add only environmental motion and must
not change roads, bridges, exits, blockers, scale, camera, or any
collision-relevant terrain. The default I2V path is PPIO
`veo-3.1-fast-generate-firstlastframe`: pass the same accepted still
`map_asset` as both `image` and `last_image`, require locked camera/no layout
drift, and prompt for a seamless continuous loop. Final-quality map visuals
must be authored or preprocessed as full-frame 16:9 backgrounds before I2V;
never send square maps directly to a 16:9 video endpoint because providers may
add black pillarboxes. Prefer I2V output under
`workspace/generated-assets/generated/videos/bgv.<map_asset_id>.loop.mp4`, then
convert to GIF for browser/static-server compatibility. Only use locally
generated GIF overlays as a fallback when I2V fails or no I2V key is available.

Final validation is mode-specific. In `final-quality` mode, validation must
require background workflow reports, image-derived RPG boundary masks, boundary
validation, provenance, and dynamic `bgv.*` media for every RPG `map_asset`. In
`fast-validation` mode, simple assets are allowed to be generated only through
the low-tier `local-svg` visual path and `mock` audio path, and dynamic
backgrounds or imagegen boundary masks are not required.

## Final-Quality Asset Dispatch

In final-quality runs, every asset section in `workspace/asset-manifest.json`
is a first-class generation target. Do not treat background assets as the only
production-quality assets. The controller must classify and dispatch all
required sections before export:

- `map_assets`
- `battle_backgrounds`
- VN `backgrounds`
- `tilesets`
- `sprites`
- `enemy_sprites`
- `item_icons`
- `skill_icons`
- `equipment_icons`
- `rpg_ui`
- portraits, CGs, props, hotspots, symbols, effects, and any other visible
  section emitted by `plan_assets.py`
- `audio`, BGM, SFX, and voice assets when the requested quality tier includes
  real audio

For Codex-side `imagegen`, script stages should write broker request files
instead of generating placeholders. Treat these statuses as dispatch signals,
not failures:

- `needs_imagegen`: background or map/battle-background image requests
- `needs_boundary_imagegen`: RPG walkable-mask boundary requests
- `needs_asset_imagegen`: non-background visual asset requests such as sprites,
  enemy sprites, icons, tilesets, UI, props, portraits, CGs, symbols, and effects
- `needs_audio_provider`: real audio, BGM, SFX, or voice generation requests

Final-quality generation must not continue to final export until every required
asset section either has accepted production assets, approved user-supplied
`provider_hints`, or an explicit user-approved fallback. Report fallback assets
as fallback, never as final art.

## Required Subagent Dispatch

For final-quality runs, asset generation that requires Codex-side image or
audio work must be delegated to subagents by asset type. Each asset type gets
its own subagent so prompts, references, QC, and retries stay scoped. Dispatch
independent asset-type subagents in parallel to reduce wall-clock time, while
respecting any provider rate limits recorded in the request files.

Required asset-type subagent groups:

- RPG backgrounds: one `rpg_backgrounds` group owned by
  `references/subagents/background/RPGBackgroundGenerator.md`. This single
  subagent owns `map_assets`, `battle_backgrounds`, RPG walkable-mask
  boundaries, boundary validation, provenance, and dynamic `bgv.*` background
  media. Do not spawn a separate dynamic-background subagent or a separate
  `rpg-boundaries` subagent for the same RPG background workflow.
- VN backgrounds: `backgrounds`
- Tilesets: `tilesets`
- Player/NPC sprites and walk sheets: `sprites`
- Enemy sprites: `enemy_sprites`
- Item/equipment/skill icons: `item_icons`, `equipment_icons`, `skill_icons`
- RPG UI: `rpg_ui`
- Portraits/CGs/props/hotspots/symbols/effects: one group per manifest section
- Audio: BGM, SFX, and voice as separate groups when real audio is required:
  `references/subagents/audio/BGMAudioGenerator.md`,
  `references/subagents/audio/SFXAudioGenerator.md`, and
  `references/subagents/audio/VoiceAudioGenerator.md`

Each subagent must receive only the run root, the resolved provider config, and
the request files for its owned asset section. Subagents save outputs to the
exact requested `output_file` paths, write prompt/provenance metadata, and
return a concise status. They must not edit canonical story/RPG artifacts,
runtime templates, or unrelated asset sections. The controller owns final
validation, retries, repair routing, manifest compilation, and export.

When multiple subagent groups are ready and independent, start them in parallel.
Only wait for the specific groups that block the next controller stage. The RPG
background group is internally sequential: static map stills block RPG boundary
masks, boundary validation blocks dynamic `bgv.*` generation, and the group is
not complete until all required `bgv.*` files and reports exist. Icon
generation can still run in parallel with sprite generation and audio
generation.

## Asset Manifest Probe and Dispatch

Before generating assets from `workspace/asset-manifest.json`, probe the
manifest for every runtime asset and write the dispatch plan:

```bash
python3 scripts/run_pipeline.py probe-assets --run-root <run-root> --write-report
```

`reports/asset-manifest-probe.json` is the controller-owned source for deciding
which asset-type subagents are needed. It scans visual, audio, portrait, canon
reference, CG, UI, RPG, and background sections; records each asset's
`output_file` and whether that file already exists; and groups missing assets
under `subagent_dispatch` by asset type. The controller must read this report
instead of guessing which subagents to call.

Background-class inputs are still treated specially because they have boundary
and dynamic-media stages:

- `map_assets` and `battle_backgrounds`: RPG background workflow.
- `backgrounds`: VN background workflow.

If the probe reports `rpg_background: true`, run the RPG background workflow
before simple asset generation:

```bash
python3 scripts/run_pipeline.py generate-backgrounds --run-root <run-root> --scope rpg
```

If the probe reports `vn_background: true`, run the VN background workflow:

```bash
python3 scripts/run_pipeline.py generate-backgrounds --run-root <run-root> --scope vn
```

Both workflows read provider configuration using the global provider priority:
active shell environment variables, then `<run-root>/.env`, then repo `.env`,
then a user question at initialization if required values are still missing:

- `IMAGE_PROVIDER`: `ppio`, `imagegen`, or `local-svg`.
- `VIDEO_PROVIDER`: `ppio` or `none`.
- `IMAGE_MODEL` / `VIDEO_MODEL`: optional provider model overrides.

Keep quality-tier choice out of `.env`; ask the user at the start of the run.
For final-quality runs, use the background workflow. For fast validation, use
the simple local asset path.

`ppio` is script-callable and is executed inside
`scripts/generate_background_assets.py`. `imagegen` is a Codex client-side
provider, so the script writes broker requests under
`workspace/generated-assets/imagegen-requests/` and returns `needs_imagegen`.
That status is not a terminal failure. It is a dispatch signal: the controller
must start the appropriate background subagent and give it the run root plus the
request files. The background subagent calls `image_gen`, saves each generated
image to its requested `output_file`, and reruns `generate-backgrounds`.

For RPG scope, `generate-backgrounds` runs in this strict order:

1. static `map_assets` and `battle_backgrounds`
2. RPG-only cyan walkable-mask boundary generation for `map_assets`
3. boundary preview and validation
4. dynamic video generation
5. provenance recording

The RPG boundary mask provider follows the accepted static background provider.
If static RPG backgrounds are generated with `ppio`, boundary masks are also
generated with PPIO. If static RPG backgrounds are generated with `imagegen`,
boundary masks are generated with Codex `image_gen` through the subagent broker
request flow. The rule is mandatory: every successful RPG `map_asset` still
background must produce a boundary file before video generation or final export.

VN scope skips the RPG boundary stage. If RPG boundary generation needs
Codex-side image generation, the script writes requests under
`workspace/generated-assets/imagegen-requests/rpg-boundaries/` and returns
`needs_boundary_imagegen`. This is also a dispatch signal for
`RPGBackgroundGenerator`, not a terminal failure. The RPG background subagent
must process imagegen tasks in batches with at most 4 concurrent generation
tasks in flight, save each cyan mask to its requested `output_file`, then rerun
`generate-backgrounds` so validation and video generation can continue. Do not
log `imagegen` or boundary success until the requested PNG exists.

Final-quality asset generation writes or should write stage reports for every
asset dispatch class:

- `reports/asset-manifest-probe.json`
- `reports/rpg-background-generation-report.json`
- `reports/vn-background-generation-report.json`
- `reports/rpg-boundary-mask-generation-report.json`
- `reports/boundary-validation-report.json`
- `reports/asset-imagegen-dispatch-report.json` for non-background visual
  imagegen broker requests
- `reports/<asset-section>-generation-report.json` for each generated asset
  section when a section-specific report is available
- `reports/audio-generation-report.json` or provider-specific audio reports
  when real audio is requested
- `reports/asset-provenance-report.json`

The controller should inspect every asset dispatch report before continuing. If
`asset-manifest-probe.json` has status `needs_generation`, spawn the missing
groups listed in `subagent_dispatch` in parallel where dependencies allow. If
any later report status is `needs_imagegen` or `needs_boundary_imagegen`, resume
or re-spawn `RPGBackgroundGenerator` for RPG backgrounds rather than creating a
new boundary or dynamic-media agent. If a later report status is
`needs_asset_imagegen` or `needs_audio_provider`, spawn the matching non-
background visual or audio subagent group from the Required Subagent Dispatch
section. Background-specific subagent role cards are:

- `references/subagents/background/RPGBackgroundGenerator.md` for the full RPG
  background workflow: `map_assets`, `battle_backgrounds`, RPG boundaries, and
  dynamic `bgv.*` backgrounds.
- `references/subagents/background/VNBackgroundGenerator.md` for VN
  `backgrounds`.

For asset types without a specialized role card, create a scoped asset worker
from the generic subagent instructions and assign it exactly one manifest
section. If any report status is `fail`, pause the main pipeline until the
failure is repaired. Continue only after all required asset section reports,
boundary reports for RPG, validation reports, and
`asset-provenance-report.json` are `pass`. The final provider is recorded per
asset as the actual runtime source, such as `ppio-video`, `ppio-image`,
`imagegen`, `local-svg`, `mock`, or `existing`; `local-svg` and `mock` are
acceptable only for non-final tiers or explicit fallback approvals.

Run asset validation with the matching mode:

```bash
python3 scripts/validate_assets.py --run-root <run-root> --asset-mode final-quality
python3 scripts/validate_assets.py --run-root <run-root> --asset-mode fast-validation
```

## Legacy Asset Generator Deprecation

`scripts/generate_assets.py` is a legacy compatibility path. It may remain
temporarily for low-tier local placeholder builds, but it must not be the
final-quality generator for visible assets or real audio. In final-quality
runs, generation is owned by the asset-type subagents above, and runtime
binding is owned by `scripts/bind_generated_assets.py`.

Current removal path:

1. Visible asset generation is assigned to asset-type subagents and broker
   request files.
2. BGM/SFX/voice generation is assigned to dedicated audio subagents.
3. `run_pipeline.py build` uses `scripts/bind_generated_assets.py` whenever a
   final-quality provider such as `imagegen`, PPIO/Gemini image providers, or a
   real audio provider is selected. The binder fails if required files are
   missing or if visual assets are legacy SVG placeholders.
4. `generate_assets.py` remains only for explicit low-tier `local-svg`/`mock`
   playable prototypes until that compatibility path is fully removed.

Until deletion, never run `generate_assets.py` with overwrite in a
final-quality run if it can regenerate images as `local-svg` or audio as
`mock`.

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

For the parallel RPG implementation target, initialize and build with an explicit target:

```bash
python3 ~/.codex/skills/narrative-game-subagent-pipeline/scripts/run_pipeline.py init \
  --prompt "A one-sentence RPG prompt" \
  --target web-rpg \
  --run-root runs/my-rpg

python3 ~/.codex/skills/narrative-game-subagent-pipeline/scripts/run_pipeline.py build \
  --target web-rpg \
  --run-root runs/my-rpg
```

Omitting `--target` preserves the original `web-vn` behavior.

For multi-perspective RPGs, author `campaign.entry_points` in
`workspace/rpg/rpg-campaign.json`. Each entry can set `id`, `title`,
`description`, `start_map_id`, `start_position`, `party`, `initial_quests`,
`initial_quest_states`, `initial_flags`, and `initial_inventory`. The Web RPG
runtime will show an entry selection screen before play. Map events can include
`entry_point_id` or `entry_point_ids` to make events visible only from specific
routes or perspectives.

The upstream hierarchical story design layer is available as `--design-layer
v3`:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A multi-perspective RPG prompt" \
  --target web-rpg \
  --design-layer v3 \
  --run-root runs/my-rpg

python3 scripts/run_pipeline.py compile-design \
  --design-layer v3 \
  --run-root runs/my-rpg
```

V3 authors internal artifacts under `workspace/design_layer_v3/` and compiles
them into the public `workspace/design_layer/` files consumed by both VN and RPG
post-design.

Sprite Forge map and sprite guidance is vendored under
`references/sprite-forge/`, with helper scripts under `scripts/sprite_forge/`.
For final-quality visual output, prefer this Sprite Forge path first for
layered maps, transparent sprites, prop packs, icons, walk sheets, battle
backgrounds, and composed previews. Bind accepted Sprite Forge output through
`provider_hints` before falling back to direct external image providers or the
default local SVG fallback.
Complete upstream Sprite Forge skill snapshots are also vendored under
`references/sprite-forge/upstream-skills/`; load those only when the flattened
reference files are not enough.

For Web RPG runs with speech, music, animated sprites, or dynamic map media,
the runtime media pipeline is documented in
`references/runtime-media-contracts.md`. Use `--audio-provider minimax-ppio`
or a scoped `--bgm-provider`, `--sfx-provider`, or `--voice-provider` when
real audio is required. Keep `--audio-fallback-provider mock` during iteration
so a provider outage does not block deterministic exports.

Map collision boundaries are documented in
`references/rpg-boundary-contracts.md`. Final-quality Web RPG boundaries are
generated from a walkable-area mask, not by guessing blockers directly. The
mask marks where the player can walk; everything outside the accepted mask is
treated as blocked boundary space after vectorization.
For Sprite Forge map backgrounds, do not bake debug boundaries into the
production still image. Generate QA walkable-mask sidecars after the accepted
Sprite Forge still map exists, extract the marked walkable region, invert it
into blocked regions, vectorize those blocked regions into pixel-coordinate
`collision_shapes`, then export boundary preview sidecars so reviewers can see
the shapes over the accepted background without polluting the runtime art.
Web RPG maps are pixel-native: set `coordinate_system: "pixels"`, set `width`
and `height` to the accepted background image
dimensions, author start positions, events, transfers, walkable hints, and
collision shapes in those pixel coordinates, and leave `layers.ground` and
`layers.collision` empty or compact.

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
workspace/rpg/rpg-campaign.json
workspace/rpg/world-map.json
workspace/rpg/maps/*.map.json
workspace/rpg/actors.json
workspace/rpg/classes.json
workspace/rpg/items.json
workspace/rpg/equipment.json
workspace/rpg/skills.json
workspace/rpg/enemies.json
workspace/rpg/encounter-tables.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/events.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
workspace/rpg/progression-rules.json
workspace/rpg/rpg-manifest.json
workspace/rpg/boundaries/*.boundaries.json
workspace/vn/fragments/*.yarn
workspace/vn/fragments/*.manifest.json
workspace/vn/story.yarn
workspace/vn/story.storyir.json
workspace/asset-direction.json
workspace/asset-manifest.json
workspace/generated-assets/
build/web-vn/
build/web-rpg/
build/unity-project/
reports/asset-generation-report.json
reports/asset-validation.json
reports/audio-coverage-report.json
reports/boundary-validation-report.json
reports/video-gif-conversion-report.json
reports/gameplay-validation.json
reports/gameplay-coverage.json
reports/rpg-validation.json
reports/rpg-balance-report.json
reports/rpg-coverage.json
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
9. Spawn `AssetDirector` after story and gameplay verification when visual direction is needed. It returns art direction only.
10. During build, the controller validates gameplay units, writes
    `workspace/realization/gameplay-manifest.json`, plans
    `workspace/asset-manifest.json`, resolves provider configuration, dispatches
    every required final-quality asset section through the asset-type subagent
    flow above, validates generated assets, and binds them into exports. Default
    low-tier visual provider is `local-svg`. For final-quality still art, first
    prefer accepted Sprite Forge or user-supplied assets through
    `provider_hints`; otherwise use the resolved model-backed provider for all
    required still visual asset types. Use `--skip-assets` only for
    intentionally text-only exports.
11. Run `scripts/run_pipeline.py build --run-root <run>`.
12. Inspect `reports/final-report.json`, `reports/validation-report.json`, `reports/gameplay-validation.json`, `reports/gameplay-coverage.json`, `reports/asset-generation-report.json`, `reports/asset-validation.json`, and the playable export.

For `--target web-rpg`, steps 5-8 are replaced by the RPG post-design artifact set under `workspace/rpg/`. Build compiles `workspace/rpg/rpg-manifest.json`, writes RPG validation, balance, and coverage reports, runs the same asset pipeline, and exports `build/web-rpg/`. The base design layer is unchanged; RPG agents consume `branch_graph.json`, `game_ir.json`, and controller-provided slices instead of reopening requirements or synopsis.

For Web RPG media-rich runs, add these checks around the build:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/my-rpg \
  --audio-provider minimax-ppio --audio-fallback-provider mock
python3 scripts/generate_runtime_media.py --run-root runs/my-rpg --overwrite
python3 scripts/convert_runtime_videos_to_gif.py --run-root runs/my-rpg --overwrite
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/my-rpg \
  --audio-provider minimax-ppio --audio-fallback-provider mock
python3 scripts/audit_audio_coverage.py --run-root runs/my-rpg
python3 scripts/validate_boundaries.py --run-root runs/my-rpg
python3 scripts/validate_assets.py --run-root runs/my-rpg --asset-mode final-quality
```

## Complete Asset Generation Workflow

Use this full sequence when the user expects a polished Web RPG experience
similar to the richer reference demos, not just a schema-valid playable export.

1. Author `workspace/asset-direction.json` after RPG content is stable. Include
   every map, actor sprite, enemy sprite, battle background, item/skill icon,
   UI panel, BGM, SFX, and voice-worthy dialogue speaker. The style pack must
   define rendering style, lighting, and palette.
2. Compile once to discover required asset refs:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> \
  --audio-provider mock --audio-fallback-provider mock
```

3. Inspect `workspace/asset-manifest.json`. Confirm all expected sections are
   populated, including maps, battle backgrounds, backgrounds, tilesets,
   sprites, enemy sprites, item/equipment/skill icons, RPG UI, portraits, CGs,
   props, symbols/effects, audio, and voice profiles as applicable.
4. Generate or reuse every required asset section through the final-quality
   dispatch rules above. For fast deterministic previews, use default
   `local-svg`. For final art, use this visual source order: accepted Sprite
   Forge or user-supplied `provider_hints`, then a model-backed image provider
   for every still visual asset type, then `local-svg` only after explicit
   fallback approval. Resolve provider configuration once at initialization
   using shell environment variables, then `<run-root>/.env`, then repo `.env`,
   then a user question if still missing.
5. For Codex-side `imagegen`, run the broker/subagent flow for each asset
   section. Spawn one subagent per asset type and start independent subagents in
   parallel. Do not let the generic asset generator silently replace unresolved
   final-quality assets with `local-svg`.

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> \
  --asset-provider openai-ppioImage \
  --audio-provider minimax-ppio --audio-fallback-provider mock \
  --asset-overwrite
```

   Place accepted Sprite Forge or other external source images under
   `workspace/sprite-forge-assets/`, include them as `provider_hints`, then run
   the project-specific migration helper or copy them into the generated asset
   file refs before validation. These hinted assets outrank direct provider
   generation.
6. Generate runtime media from the accepted still assets:

```bash
python3 scripts/generate_runtime_media.py --run-root <run> --overwrite
```

   This creates `bgv.<map_asset_id>.loop.gif` dynamic backgrounds and
   `motion.<asset_id>.idle.gif` loops for sprites, enemies, and icons.
7. If a provider generated MP4 backgrounds, convert them to GIF and let the
   exporter prefer GIF:

```bash
python3 scripts/convert_runtime_videos_to_gif.py --run-root <run> --overwrite
```

8. Rebuild after runtime media exists so `build/web-rpg/game-data.js` includes
   all dynamic media:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> \
  --audio-provider minimax-ppio --audio-fallback-provider mock
```

9. Run all asset-facing validators:

```bash
python3 scripts/validate_assets.py --run-root <run> --asset-mode final-quality
python3 scripts/audit_audio_coverage.py --run-root <run>
python3 scripts/validate_boundaries.py --run-root <run>
rg "bgv\\.map\\..*\\.gif|motion\\." <run>/build/web-rpg/game-data.js
```

The run is not visually complete until `game-data.js` contains map stills,
dynamic `bgv.*.gif` backgrounds, sprite/enemy `motion.*.gif` entries, BGM,
voice assets, and all validation reports pass.

## Walkable-Mask Boundary Workflow

Use this workflow for final-quality Sprite Forge/Web RPG maps. It replaces
direct blocker guessing. In this project, **the mask means walkable**, not
blocked.

1. Before map image generation, define a gameplay walk graph with required
   route nodes and edges: start, lower hub, central platform, left/right/top
   clearings, bridges, stairs, exits, NPC spaces, battle/event points, and any
   required transfer targets. Roads, bridges, stairs, and platforms must form
   one connected network. This walk graph is the source of truth for gameplay
   reachability.
2. Generate the Sprite Forge background from that walk graph. The prompt must
   require broad readable connected traversal surfaces and no props on required
   routes. Do not decide walkability by material name alone: flower beds,
   petals, clover, shallow water, lily pads, grass, moss, and leaf surfaces may
   be walkable when the gameplay route says they are; walls, deep water,
   cliffs, props, furniture, posts, fences, and outer frame space are blocked
   unless explicitly designed as traversal surfaces.
3. Treat the accepted still background as a visual QA checkpoint before
   boundary generation. Identify route surfaces that are visually easy to miss
   or misread, such as flower interiors behind rims, petal ledges, mossy or
   clover platforms, shallow-water paths, lily pads, stairs partly hidden by
   leaves, bridges under foreground grass, exits at the frame edge, and route
   surfaces covered by shadow or perspective overlap. Also identify visually
   tempting blocked areas such as deep water, dense foliage, rocks, prop
   clusters, flower walls, outer frame space, and decorative foreground cover.
   This checkpoint informs the boundary prompt but does not create a separate
   pre-QA artifact.
4. After the still background is accepted, make that image visible and use
   image generation/editing directly to create a same-aspect walkable path
   boundary mask. The prompt should ask the model to mark the actual visible
   player-walkable paths and traversal surfaces in bright cyan at about 50%
   opacity. It must explicitly name the required walk graph and easy-to-miss
   walkable surfaces from the visual checkpoint, plus tempting blocked surfaces
   to avoid. It should not ask for exact coordinate tracing or a separate
   pre-QA artifact.
5. The mask artifact must preserve the map layout and mark only actual
   player-walkable areas. The cyan region must preserve route continuity,
   including walkable flower/grass/leaf/water surfaces when they are part of
   the route. It must bridge through/under non-blocking visual occluders so
   both sides of an intended path remain connected. Do not mark blockers
   directly. Do not add labels, outlines, grids, arrows, text, or UI.
6. Extract the cyan walkable region locally into a binary mask. Keep extraction
   deterministic: threshold the cyan range, denoise, fill small holes, remove
   tiny islands, and preserve the main connected network.
7. Enforce required connectivity from the walk graph after extraction. If a
   required bridge, stair, platform, exit, or route node is not in the main
   component, repair with a corridor following the intended traversal surface.
   Repairs may cross flowers, grass, clover, shallow water, lily pads, petals,
   moss, leaves, shadows, decorative overlays, or foreground perspective cover
   when those surfaces are intended walkable routes or non-blocking occluders;
   they must not spill into props, walls, deep water, cliffs, furniture, posts,
   fences, or other truly blocked scenery.
8. The game boundary is the inverse of the accepted walkable mask. Convert
   `not walkable` areas into vector `collision_shapes` by contour extraction
   and simplification. Keep the original walkable mask as a QA sidecar, not as
   runtime art unless the runtime explicitly supports masks.
9. Validate before dynamic background generation: all start positions,
   transfers, NPCs, battle/event points, bridges, stairs, and platforms must be
   inside the walkable mask and in the same connected component. Then export the
   red boundary overlay preview from the vectorized blocked shapes.
10. Only after the still background and boundary/walkmask pass validation should
   I2V/dynamic background generation run. I2V prompts must preserve roads,
   bridges, stairs, platforms, and collision-relevant terrain exactly.

### Top-Down RPG Background-to-Boundary Flow

Use this complete flow for generated top-down RPG backgrounds:

1. Select map mode, target resolution/aspect ratio, camera angle, scale, art
   direction, and runtime layering model.
2. Define the walk graph before image generation: start, transfers, hub, side
   pockets, NPC/event/battle spaces, bridges, stairs, platforms, and route
   edges. Decide walkability by gameplay intent, not material name.
3. Write the still-background prompt from that graph. Require broad connected
   traversal surfaces, clear entrances/exits, route continuity, no gameplay
   props on required routes, and standing space around interactables.
4. Generate the still background with image generation, save it, normalize its
   dimensions if needed, and store the prompt with the asset.
5. View the accepted background and do an internal visual checkpoint: list
   easy-to-miss walkable surfaces, tempting blocked surfaces, non-blocking
   occluders that must be bridged, and route nodes that must remain connected.
6. Make the accepted background visible immediately before boundary generation.
   Generate a same-aspect cyan walkable mask. The prompt must preserve the
   exact map layout, mark only walkable surfaces, include the walk graph and
   easy-to-miss walkable areas, exclude tempting blockers, and avoid labels,
   UI, and coordinate tracing.
7. Extract cyan into a binary walkable mask, denoise, fill small gaps, keep the
   main component, and repair only against the required walk graph.
8. Invert the final walkable mask into collision shapes, export QA sidecars,
   wire `walkable_mask_ref` and `boundary_source` into metadata, and run
   boundary validation before dynamic backgrounds or final export.

## Final-Quality Asset Migration Pattern

Use this pattern when the user expects a polished Web RPG result where visual
and audio quality comes from combining this pipeline with Sprite Forge-style
asset generation and provider-backed media.

The migration has five layers:

1. Manifest planning from narrative RPG artifacts.
   `scripts/plan_assets.py` converts `rpg-manifest.json`,
   `asset-direction.json`, NPC dialogue, and map event outcomes into a single
   `asset-manifest.json`. It automatically adds map assets, sprites, enemy
   sprites, icons, battle backgrounds, BGM, and voice assets. Dialogue voice ids
   are deterministic, and non-ASCII speaker names are converted to stable
   hashed `voice_profile.*` ids.
2. High-quality still art from Sprite Forge or generated references.
   The `workspace/sprite-forge-assets/` source files are created by applying
   the vendored `generate2dmap` and `generate2dsprite` skill rules with
   built-in `image_gen`: the agent writes production prompts, generates raw
   map atlases, battle atlases, sprite/icon sheets, and walk sheets, saves the
   prompts beside the raw images, then postprocesses those raw images locally.
   Project-specific migration helpers may crop map atlases, split sprite
   sheets, run `scripts/sprite_forge/generate2dsprite.py process` for
   transparent sprites, and write `provider_hints` back into
   `workspace/asset-direction.json`. The controller or asset-type subagents then
   bind accepted assets into the canonical
   `workspace/generated-assets/generated/rpg/...` file refs. Do not rely on
   `scripts/generate_assets.py` as the final-quality generator.
3. Dynamic visual media.
   RPG map dynamic backgrounds are part of
   `RPGBackgroundGenerator`, not an independent controller stage. The
   background subagent may call `scripts/asset_motion_providers.py` for
   provider-backed I2V, and may call `scripts/generate_runtime_media.py` or
   `scripts/convert_runtime_videos_to_gif.py` as internal tooling after
   boundary validation passes. The controller must not use those local scripts
   as a final-quality replacement for an incomplete RPG background subagent.
   Project-specific scripts can author stable prompts such as "locked camera,
   preserve collision-relevant terrain, animate only water/wind/clouds." For
   fast-validation or explicit fallback only, ImageMagick/ffmpeg helpers may
   create `bgv.<map_asset_id>.loop.gif` and `motion.<asset_id>.idle.gif`.
4. Audio generation.
   `scripts/asset_audio_providers.py` provides `mock`, `local-procedural`, and
   `minimax-ppio` adapters. `minimax-ppio` supports BGM generation, TTS, voice
   design, request/response JSONL logs, fallback providers, and
   `voice-design-cache.json` so each speaker keeps a consistent voice across
   lines.
5. Export/runtime binding.
   `scripts/export_web_rpg.py` copies manifest assets plus
   `generated/videos/` and `generated/rpg-motion/`, preferring GIF over MP4
   when both exist. It also attaches `voice_asset_id` to dialogue and outcome
   lines. `assets/web-rpg-template/runtime.js` then plays per-map BGM, ducks
   BGM under voice playback, renders dynamic map media, and prefers motion GIFs
   over still sprites when available.

Concrete helper roles for a final-quality run:

- a project-specific Sprite Forge migration helper can split generated atlases,
  process transparent sprites with Sprite Forge tooling, and attach
  `provider_hints`.
- a project-specific I2V helper can be used by `RPGBackgroundGenerator` to
  generate locked-camera provider-backed map loops from accepted 16:9 map
  stills. It is not a separate asset-type subagent.
- `scripts/generate_runtime_media.py` creates local animated fallback map media
  and sprite/enemy idle GIFs; for RPG `bgv.*` outputs in final-quality mode,
  this script is only an internal tool of `RPGBackgroundGenerator` or an
  explicitly approved fallback.
- `scripts/convert_runtime_videos_to_gif.py` converts provider MP4 output to
  browser-friendly GIFs.

For a new fast-validation game, first prefer the generic workflow:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> \
  --audio-provider mock --audio-fallback-provider mock
python3 scripts/generate_runtime_media.py --run-root <run> --overwrite
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> \
  --audio-provider mock --audio-fallback-provider mock
```

When final-quality assets are required, run the RPG background subagent for the
full background workflow instead of calling `generate_runtime_media.py` directly
from the controller. Replace the still-art step with project-specific Sprite
Forge/image-generation assets first, attach them as `provider_hints`, then let
`RPGBackgroundGenerator` generate/validate boundaries and produce dynamic
`bgv.*` media before the final rebuild. Use direct external image providers only
for required still assets that do not yet have an accepted Sprite Forge or
user-supplied source.

## Final-Quality Sprite Forge Workflow

Use this workflow when the target game requires final-quality generated HD
maps, transparent character sprites, walk frames, dynamic backgrounds,
per-character TTS, and runtime GIF motion.

1. Read only the relevant Sprite Forge references:
   `references/sprite-forge/generate2dmap.SKILL.md` for maps,
   `references/sprite-forge/generate2dsprite.SKILL.md` for characters,
   `references/sprite-forge/layered-map-contract.md` for layered maps,
   `references/sprite-forge/prop-pack-contract.md` for prop packs, and
   `references/sprite-forge/prompt-rules.md` for strict magenta-background
   sprite prompts.
2. Build the RPG once with mock audio to freeze canonical asset ids:
   `python3 scripts/run_pipeline.py build --target web-rpg --run-root <run> --audio-provider mock --audio-fallback-provider mock`
3. Create source art under `workspace/sprite-forge-assets/raw/`: map atlas,
   battle atlas, sprite/icon sheet, and optional `<hero>-walk-4x4.png`. Save
   each creative prompt next to the accepted image.
   These files should come from built-in `image_gen` following the vendored
   Sprite Forge skills, not from procedural SVG/PIL/canvas placeholders.
   Use `generate2dmap` rules for maps and battle backgrounds, and
   `generate2dsprite` rules for magenta-background sprites, icons, enemies,
   and walk sheets.
4. Process source art with `scripts/sprite_forge/generate2dsprite.py process`.
   Use feet alignment for actors, `component-mode largest` for body sprites,
   `extract_prop_pack.py` for prop packs, and `compose_layered_preview.py` for
   map base plus prop QA. Do not use script-drawn placeholder art as final art.
5. Write a project-specific migration helper when assets are batched. It should
   crop atlases, split sheets, copy processed files into
   `workspace/sprite-forge-assets/{maps,sprites,icons,...}/`, then attach each
   accepted file as `provider_hints` in `workspace/asset-direction.json`. Use
   `scripts/bind_sprite_forge_provider_hints.py` for conventionally named
   assets. Keep the helper project-specific, but keep the workflow generic:
   split or normalize source art, copy accepted files into
   `workspace/sprite-forge-assets/{maps,sprites,icons,...}/`, and attach
   `provider_hints`.
6. Bind hinted still art into canonical generated refs through the controller or
   asset-type subagents, then rebuild without allowing the legacy generator to
   overwrite final-quality assets.
7. For every accepted Sprite Forge map still, run the walkable-mask boundary
   workflow before any dynamic background generation: use imagegen/editing on
   the accepted still to generate the cyan walkable path mask, extract and
   denoise it, repair required route connectivity only when validation shows a
   broken key point, invert the accepted mask into blocked regions, vectorize
   those regions into `collision_shapes`, and export QA overlays. This boundary
   data is shared by both the still fallback and the dynamic runtime background
   for the same map.
8. Resume `RPGBackgroundGenerator` to generate dynamic map media. The subagent
   must verify that the accepted full-frame 16:9 still map and passing boundary
   validation already exist, use that still as first/last-frame I2V input when
   provider video is available, require locked camera and unchanged collision
   terrain, output `generated/videos/bgv.<map_asset_id>.loop.mp4` or an
   approved `.gif` equivalent, and convert provider MP4s to GIF when needed.
   `scripts/generate_runtime_media.py` and
   `scripts/convert_runtime_videos_to_gif.py` may be used only inside this
   background subagent step or for explicitly approved fast-validation/fallback
   output. The controller must not mark the RPG background group complete until
   the subagent reports the `bgv.*` files and final-quality validation passes.
9. Generate final audio with `--audio-provider minimax-ppio
   --audio-fallback-provider mock`. Each distinct speaker should have a distinct
   `voice_profile.*`; keep `voice-design-cache.json` so repeated lines reuse
   stable designed `voice_id` values.
10. Rebuild once more, then run `validate_assets.py --asset-mode final-quality`,
   `audit_audio_coverage.py`, `validate_boundaries.py`, and `rg
   "bgv\\.|motion\\.|voice\\.|bgm\\." <run>/build/web-rpg/game-data.js`.
   Finish with `scripts/audit_final_quality_readiness.py --run-root <run>`;
   use `--strict` when final-quality Sprite Forge/model art is required.

Do not claim final-quality output until the export contains still assets,
`bgv.*` backgrounds, `motion.*` GIFs, BGM, full voice coverage, and the still
assets came from accepted Sprite Forge or model-generated `provider_hints`, not
only local SVG fallbacks.

If serving from WSL to other devices on the LAN, prefer the Windows-side
static server:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts/serve_web_rpg_windows.ps1 `
  -Root runs/my-rpg/build/web-rpg -HostName 0.0.0.0 -Port 8765
```

## Boundaries

Base design artifacts must not contain Yarn syntax, Unity paths, image-generation prompts, or implementation details.

`game_ir.json` is the semantic authority for state variables, transition conditions, world-state effects, and progression rules.

`shared-state.schema.json` is projected from `game_ir.json`; do not author it by hand unless repairing the projector itself.

Every branch graph node maps to exactly one realization plan. Per-node workers produce fragments, gameplay units, or stubs; the controller exports one game, not one project per node.

Supported gameplay adapters are declarative and fixed by the controller:
`battle.choice_duel`, `interaction.inspect_scene`, `puzzle.sequence_lock`, and `exploration.room_nav`.
Subagents do not write runtime code for these adapters.

`external_stub` and unsupported adapters become typed not-implemented stubs. Supported `battle`, `interaction`, `puzzle`, and `exploration` plans require matching gameplay unit artifacts.

RPG implementation is a parallel target, not a replacement for VN. Use `--target web-rpg` only when the run has RPG artifacts under `workspace/rpg/`; default builds and old runs remain `web-vn`. RPG runtime assets are planned through the same `asset-direction.json`/`asset-manifest.json` split, with extra sections such as `tilesets`, `sprites`, `enemy_sprites`, `item_icons`, `skill_icons`, `battle_backgrounds`, and `rpg_ui`.

Audio assets are planned in the `audio` section of `asset-manifest.json`.
Dialogue lines and event outcome lines should receive stable `voice_asset_id`
bindings during export. Different speakers should map to different voice
profiles unless a shared voice is intentional.

Dynamic map backgrounds use asset ids shaped like `bgv.<map_asset_id>.loop`.
The Web RPG exporter copies `workspace/generated-assets/generated/videos/` and
`workspace/generated-assets/generated/rpg-motion/`. If both `.mp4` and `.gif`
exist for the same background stem, the exporter prefers the `.gif`.
Provider-backed I2V background generation should always preserve gameplay
geometry: locked camera, no terrain warping, no changed bridges/roads/cliffs,
and no characters or UI. Animate only environmental layers such as water, mist,
clouds, grass, leaves, dust, haze, light shimmer, and particles.

Boundary files are loaded through each map's `boundary_file` or
`boundaries_file` field. The compiled manifest embeds normalized
`collision_shapes`, and the runtime samples the player's foot position against
these shapes.
The Web RPG runtime is pixel-native. Positions are rendered directly as image
pixels, movement speed/radius use pixel values, and boundary validation samples
the map at a coarse pixel interval rather than building a huge per-pixel grid.
`scripts/export_boundary_previews.py --run-root <run>` overlays those compiled
shapes onto generated map stills under
`workspace/generated-assets/generated/rpg/map_boundaries/` for QA. The normal
Web RPG asset build also runs this export when RPG artifacts are present.

## Tools

- `scripts/run_pipeline.py`: initialize runs and build/export accepted artifacts.
- `scripts/export_boundary_previews.py`: export QA-only SVG/PNG previews that
  overlay compiled map collision shapes on generated map stills.
- `scripts/validate_artifacts.py`: validate core artifacts and write shared-state projection.
- `scripts/validate_gameplay.py`: validate gameplay realization units and write gameplay reports.
- `scripts/compile_gameplay_manifest.py`: compile gameplay unit artifacts into `workspace/realization/gameplay-manifest.json`.
- `scripts/validate_rpg.py`: validate RPG artifacts and refresh the RPG manifest.
- `scripts/compile_rpg_manifest.py`: compile RPG post-design artifacts into `workspace/rpg/rpg-manifest.json`.
- `scripts/simulate_rpg_balance.py`: run a deterministic first-pass RPG encounter balance check.
- `scripts/assemble_yarn.py`: assemble per-node Yarn fragments into `workspace/vn/story.yarn`.
- `scripts/story_ir.py`: lower Yarn to a simple StoryIR and verify titles, jumps, and outcomes.
- `scripts/plan_assets.py`: convert `asset-direction.json` into a deterministic runtime `asset-manifest.json`.
- `scripts/bind_generated_assets.py`: bind and report subagent-generated assets without generating placeholders; final-quality builds use this path.
- `scripts/generate_assets.py`: legacy low-tier compatibility generator for `local-svg`/`mock` prototype assets. It is being deprecated and must not be used to overwrite final-quality subagent-generated assets.
- `scripts/generate_background_assets.py`: dedicated RPG/VN background workflow with static image, RPG boundary, video, and provenance stages.
- `scripts/generate_rpg_boundaries_from_masks.py`: Sprite Forge-derived RPG cyan walkable-mask boundary workflow; writes imagegen requests when Codex-side mask generation is needed.
- `scripts/asset_image_providers.py`: provider adapters, request/response logging, PPIO response parsing, and Gemini image requests.
- `scripts/asset_audio_providers.py`: provider adapters for BGM, SFX, TTS, MiniMax/PPIO voice design, mock fallback, and audio request logs.
- `scripts/generate_audio_asset.py`: generate a single BGM, SFX, or voice file without running the full asset pipeline.
- `scripts/asset_motion_providers.py`: provider adapters for image-to-video and runtime motion assets.
- `scripts/generate_runtime_media.py`: generate reusable dynamic map background GIFs and idle motion GIFs from existing generated assets.
- `scripts/convert_runtime_videos_to_gif.py`: convert generated MP4 map backgrounds to GIF files that the exporter will prefer.
- `scripts/bind_sprite_forge_provider_hints.py`: attach conventionally named Sprite Forge source art to `asset-direction.json` as `provider_hints`.
- `scripts/audit_audio_coverage.py`: verify exported Web RPG dialogue and event outcome lines have valid runtime voice assets.
- `scripts/audit_final_quality_readiness.py`: verify final-quality completeness: provider hints, dynamic media, BGM, voice, asset validation, and boundary validation.
- `scripts/validate_boundaries.py`: verify RPG collision shapes, key points, and coarse map reachability.
- `scripts/validate_assets.py`: verify generated asset files and portrait transparency. Always pass `--asset-mode final-quality` or `--asset-mode fast-validation`; do not rely on implicit `auto` in controller workflows.
- `scripts/export_web_vn.py`: export a self-contained browser-playable VN.
- `scripts/export_web_rpg.py`: export a self-contained browser-playable RPG.
- `scripts/export_unity_project.py`: generate a minimal Unity project from accepted artifacts.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.
- `scripts/generate_sanda_ppio_i2v_backgrounds.py`: example San Da Bai Gu Jing-specific PPIO I2V background generator.
- `scripts/migrate_sanda_sprite_forge_assets.py`: example San Da Bai Gu Jing-specific Sprite Forge imagegen asset migration helper.
- `scripts/serve_web_rpg_windows.ps1`: serve a built Web RPG from Windows so LAN devices can reach WSL-generated files.

Read `references/artifact-contracts.md` only when you need exact payload shapes. Read `references/runtime-media-contracts.md` for audio, motion GIF, and dynamic background conventions. Read `references/rpg-boundary-contracts.md` before editing collision boundaries. Read `references/repair-routing.md` only when validation fails. Read `references/subagents/README.md`, then only the specific subagent role card needed for the current spawn.

## Completion

A run is complete when `reports/final-report.json` exists, required validation reports pass, and at least one playable export path exists.

Final responses should include the run root, final report path, playable export path, Unity export path if requested, skipped steps, and residual risks such as unrun Unity compilation.
