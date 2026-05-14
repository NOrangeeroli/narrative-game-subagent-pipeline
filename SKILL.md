---
name: narrative-game-subagent-pipeline-rpg
description: Generate a playable narrative RPG by coordinating Codex subagents through RPG-first design, realization, asset, validation, and Web RPG export stages.
---

# Narrative RPG Subagent Pipeline

## Controller Rule

Act as the workflow controller. This skill is self-contained: use only files
bundled in this skill's `scripts/`, `assets/`, and `references/` directories.

When spawning subagents, do not set a `model` override. Omit the `model` field
unless the user explicitly requests a specific model.

Subagents author typed payloads only. They do not write canonical artifacts,
edit generated runtime code, run exporters, or decide whether a stage passes.
The controller owns run layout, persistence, validation, repair tickets,
asset dispatch, export, and final reporting.

The only supported playable target is `web-rpg`. Treat the RPG interaction
layer as a way to reenact narrative beats through maps, actors, objects,
dialogue, quests, scene scripts, and battles. Do not replace the source
narrative with generic RPG systems.

## Start Gate

At the beginning of a game-generation request, confirm only choices that cannot
be safely inferred:

- `target`: use `web-rpg`. No alternate runtime target is supported.
- asset quality tier: ask once when missing.
  - fast playable prototype with local placeholder assets
  - final-quality generated or supplied art
  - hybrid partial-quality art
- external provider access: when final-quality art or audio is requested,
  resolve provider settings from active environment variables, then
  `<run-root>/.env`, then repo `.env`, then a concise user question if required
  keys are still missing.

Do not ask for a subagent model. The only model/provider question should be for
external visual or audio providers, and only when needed for the requested
quality tier.

## Unified Design Layer

Use one RPG design layer, not separate V3 and RPG design systems.

For small prompts, the controller may create the public design artifacts
directly:

```text
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

For source adaptations, multi-perspective stories, or long campaigns, use the
hierarchical design flow under `workspace/design_layer_v3/`, then run the RPG
overlay stages before post-design:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A multi-perspective RPG prompt" \
  --target web-rpg \
  --design-layer v3 \
  --run-root runs/my-rpg

python3 scripts/run_pipeline.py compile-design \
  --design-layer v3 \
  --run-root runs/my-rpg

python3 scripts/run_pipeline.py validate-rpg-overlay --run-root runs/my-rpg
python3 scripts/run_pipeline.py freeze-narrative --run-root runs/my-rpg
python3 scripts/run_pipeline.py prepare-rpg-postdesign-slices --run-root runs/my-rpg
```

`RPGSystemPlanner` reads V3 story hierarchy, facts, state contracts, and
adaptation policy. It outputs RPG intent that can bind back to public graph
nodes, story units, route state, and required narrative beats.

`RPGDesignReviewer` checks whether the overlay preserves source beats,
correctly maps RPG systems to graph/state contracts, and avoids inventing
progression that is not traceable to the design layer.

Post-design agents should prefer
`workspace/controller-packets/postdesign/rpg/*.json` instead of reading the full
public graph. Those packets carry the bounded source story, public graph ids,
RPG overlay intent ids, required quest/object/dialogue hooks, and
`scene_script_obligations`.

## RPG Beat Realization

RPG post-design must make narrative beats playable in space:

- `RPGCampaignPlanner` owns campaign entry points, world map, route framing,
  and high-level quest flow.
- `RPGMapBuilder` owns walkable maps, exits, collision, event placement,
  transfer points, and spatial staging.
- `RPGContentWriter` owns actors, enemies, items, skills, quests, shops, rest
  points, encounter tables, and NPC dialogue.
- `RPGSceneScriptWriter` owns scheduled scene beats: entrances, exits,
  movement, facing, dialogue, waits, state writes, item reveals, quest updates,
  and transfers.
- `RPGBalanceReviewer` checks encounter and resource pressure without changing
  narrative outcomes.

NPC dialogue is not automatically a scene script. Dialogue becomes actor
blocking only when timing, positioning, movement, facing, or stateful staging
matters. Ambient or repeatable NPC lines may stay in `npc-dialogue.json`.

Story-critical items must carry plot:

- include `story_role` and readable `inspect_lines`;
- use `on_pickup` or `on_inspect` outcomes when the item advances a beat;
- bind those outcomes to quests, scene scripts, event conditions, transfers,
  or dialogue branches;
- avoid key items, evidence, memories, or tools that are only pickup counters.

## Artifact Layout

Use these canonical paths inside each run:

```text
inputs/prompt.txt
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/design_layer_rpg/rpg-overlay-plan.json
workspace/design_layer_rpg/rpg-overlay-review.json
workspace/narrative-freeze.json
workspace/controller-packets/postdesign/rpg/*.json
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
workspace/rpg/scene-scripts.json
workspace/rpg/events.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
workspace/rpg/progression-rules.json
workspace/rpg/boundaries/*.boundaries.json
workspace/rpg/rpg-manifest.json
workspace/asset-direction.json
workspace/asset-manifest.json
workspace/generated-assets/
build/web-rpg/
reports/validation-report.json
reports/rpg-overlay-validation.json
reports/narrative-freeze-report.json
reports/rpg-postdesign-slices-report.json
reports/rpg-validation.json
reports/rpg-balance-report.json
reports/rpg-coverage.json
reports/asset-generation-report.json
reports/asset-validation.json
reports/audio-coverage-report.json
reports/boundary-validation-report.json
reports/final-report.json
```

Large generated payloads stay on disk. Keep chat summaries concise and point to
run paths.

## Workflow

1. Initialize the run with `scripts/run_pipeline.py init --target web-rpg`.
2. Author the design layer. For large adaptations, use V3 and the unified RPG
   overlay flow.
3. Validate with `scripts/validate_artifacts.py --run-root <run> --write-projections`.
4. Validate RPG overlay, freeze narrative, and prepare RPG post-design slices
   when the run uses V3/RPG overlay.
5. Spawn only the RPG post-design role cards listed in
   `references/subagents/README.md`.
6. Save accepted RPG payloads under `workspace/rpg/`.
7. Build with `scripts/run_pipeline.py build --target web-rpg --run-root <run>`.
8. Inspect `reports/final-report.json`, validation reports, and
   `build/web-rpg/`.

## Asset Policy

Choose visual asset sources in this priority order:

1. Accepted Sprite Forge or user-supplied production assets bound through
   `provider_hints`.
2. External model-backed image generation for every required still visual asset
   type when final-quality art is requested.
3. `local-svg` or other deterministic placeholder output for low-tier playable
   prototypes, tests, and explicitly approved fallback.

For final-quality Web RPG runs, visible map, sprite, icon, UI, battle, and
audio sections are first-class targets. Do not treat map backgrounds as the
only production-quality assets.

For final-quality maps, generate an accepted still map first, then generate a
walkable-mask boundary for that exact still, validate connectivity, and only
then generate dynamic background media. Dynamic media must preserve gameplay
geometry: locked camera, no changed bridges, roads, cliffs, exits, blockers,
scale, or camera.

Use:

```bash
python3 scripts/run_pipeline.py probe-assets --run-root <run-root> --write-report
python3 scripts/run_pipeline.py generate-backgrounds --run-root <run-root> --scope rpg
python3 scripts/run_pipeline.py dispatch-asset-imagegen --run-root <run-root>
python3 scripts/validate_assets.py --run-root <run-root> --asset-mode final-quality
```

`RPGBackgroundGenerator` owns map assets, battle backgrounds, walkable-mask
boundaries, boundary validation, and dynamic `bgv.*` media. Do not split those
dependencies across unrelated agents.

## Runtime Media

For media-rich runs, the build can include dynamic map loops, sprite/enemy
motion, BGM, SFX, and voice. Use:

```bash
python3 scripts/generate_runtime_media.py --run-root <run> --overwrite
python3 scripts/convert_runtime_videos_to_gif.py --run-root <run> --overwrite
python3 scripts/audit_audio_coverage.py --run-root <run>
python3 scripts/validate_boundaries.py --run-root <run>
```

`scripts/export_web_rpg.py` copies manifest assets plus generated videos and
motion media into `build/web-rpg/`, preferring GIF over MP4 when both exist for
the same runtime asset stem.

## Boundaries

Base design artifacts must not contain implementation details, image-generation
prompts, runtime scripts, or engine paths.

`game_ir.json` is the semantic authority for state variables, transition
conditions, world-state effects, and progression rules.

Scene and interaction layers may realize verified semantics, but must not
silently rewrite them. Preserve traceability ids across layers.

Web RPG maps are pixel-native. Positions are rendered directly as image pixels,
movement speed/radius use pixel values, and boundary validation samples map
coordinates at a coarse interval. Boundary files are loaded through each map's
`boundary_file` or `boundaries_file` field, and compiled collision shapes are
embedded into `workspace/rpg/rpg-manifest.json`.

## Tools

- `scripts/run_pipeline.py`: initialize, compile design, build, validate, and
  export RPG runs.
- `scripts/validate_artifacts.py`: validate core design artifacts and write
  shared-state projection.
- `scripts/design_v3_validate.py`: validate hierarchical design artifacts.
- `scripts/validate_rpg_overlay.py`: validate RPG overlay binding to design
  hierarchy and public graph.
- `scripts/freeze_narrative.py`: freeze public narrative ids before RPG
  post-design.
- `scripts/prepare_rpg_postdesign_slices.py`: create bounded packets for RPG
  post-design agents.
- `scripts/validate_rpg.py`: validate RPG artifacts and refresh the RPG
  manifest.
- `scripts/compile_rpg_manifest.py`: compile RPG post-design artifacts into
  `workspace/rpg/rpg-manifest.json`.
- `scripts/simulate_rpg_balance.py`: run deterministic first-pass encounter
  balance checks.
- `scripts/plan_assets.py`: convert RPG artifacts and asset direction into a
  deterministic runtime asset manifest.
- `scripts/probe_assets.py` through `scripts/run_pipeline.py probe-assets`:
  discover missing asset sections and dispatch groups.
- `scripts/generate_background_assets.py`: RPG background, boundary, dynamic
  media, and provenance workflow.
- `scripts/generate_assets.py`: low-tier local placeholder generator only.
- `scripts/generate_asset_imagegen_requests.py`: write broker requests for
  Codex-side image generation.
- `scripts/bind_generated_assets.py`: bind subagent-generated assets without
  creating placeholders.
- `scripts/generate_audio_asset.py`: generate a single BGM, SFX, or voice file.
- `scripts/generate_runtime_media.py`: generate dynamic map and motion fallback
  GIFs from accepted still assets.
- `scripts/convert_runtime_videos_to_gif.py`: convert generated MP4 map media
  to browser-friendly GIFs.
- `scripts/validate_assets.py`: verify generated asset files; always pass
  `--asset-mode final-quality` or `--asset-mode fast-validation`.
- `scripts/validate_boundaries.py`: verify collision shapes, key points, and
  coarse map reachability.
- `scripts/export_web_rpg.py`: export a self-contained browser-playable RPG.
- `scripts/write_report.py`: write or refresh `reports/final-report.json`.

Read `references/artifact-contracts.md` for base design payload shapes,
`references/design-layer-v3-contracts.md` for hierarchical design payloads,
`references/design-layer-rpg-contracts.md` for RPG overlay contracts,
`references/rpg-artifact-contracts.md` for RPG post-design payloads,
`references/runtime-media-contracts.md` for audio and dynamic media conventions,
`references/rpg-boundary-contracts.md` before editing collision boundaries, and
`references/subagents/README.md` before spawning a role-specific subagent.

## Completion

A run is complete when `reports/final-report.json` exists, required validation
reports pass, and `build/web-rpg/` exists.

Final responses should include the run root, final report path, playable export
path, skipped steps, and residual risks.
