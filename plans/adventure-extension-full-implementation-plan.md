# Side-Scroller Mobile Adventure Extension Full Implementation Plan

## Goal

Add a first-class `side_scroller_adventure` game category to the existing
narrative pipeline.

The extension must generate a complete playable 2D horizontal mobile adventure
game from the same V3 narrative foundation that currently exports visual
novels. The result should preserve V3 narrative semantics:

```text
V3 story/design graph -> runtime state graph -> playable spatial adventure
```

The final system must support full runs, not a one-off template demo. A
template may provide Unity runtime scaffolding, but the generated game must be
driven by typed adventure artifacts, compiled bindings, validators, assets, and
engine export.

Primary full target:

```text
Unity 2D mobile side-scroller export
```

Secondary debug target:

```text
deterministic JSON reports and optional desktop/WebGL Unity build
```

## Non-Goals

Do not replace V3 narrative design. V3 remains the authority for story
topology, state models, ending ownership, and path closure.

Do not ask subagents to write arbitrary Unity scenes, C# gameplay code, or
manually placed engine assets. Subagents produce typed adventure artifacts; the
controller validates, compiles, exports, and tests them.

Do not treat a Unity template as the solution. The template is only the runtime
starter. The important implementation is the adventure intermediate
representation, compiler, validator, and engine binding layer.

Do not reduce the feature set to an MVP. The implementation plan below targets
the complete category: world maps, level layouts, movement, interactions,
quests, dialogue, state gates, endings, assets, mobile controls, build, and
playtest validation.

## Existing Baseline

The current pipeline produces these stable downstream design artifacts:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/state/shared-state.schema.json
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/vn/story.yarn
workspace/vn/story.storyir.json
build/web-vn/index.html
```

V3 now guarantees:

- coarsest designers own ending families;
- lower-level designers may refine ending variants;
- every public path must eventually reach a terminal ending node;
- public branch graph terminal nodes preserve ending metadata.

The adventure extension should use that work instead of inventing a separate
story pipeline.

## Target Architecture

Add an adventure pipeline beside the VN realization/export path:

```text
branch_graph.json + game_ir.json + shared-state.schema.json
  -> AdventureGenrePlanner
  -> WorldMapDesigner
  -> LevelBlockoutDesigner
  -> InteractionQuestDesigner
  -> AdventureNarrativeBinder
  -> AdventureAssetDirector
  -> adventure compiler
  -> adventure validators
  -> Unity 2D mobile runtime export
  -> build and playtest reports
```

The adventure artifacts become the new public runtime contract for this genre:

```text
workspace/adventure/genre-policy.json
workspace/adventure/world-map.json
workspace/adventure/levels/*.level.json
workspace/adventure/interactions/*.interaction.json
workspace/adventure/quests/*.quest.json
workspace/adventure/dialogue/*.dialogue.json
workspace/adventure/bindings/narrative-bindings.json
workspace/adventure/adventure-manifest.json
workspace/assets/adventure/asset-direction.json
workspace/assets/adventure/asset-manifest.json
reports/adventure-validation.json
reports/adventure-coverage.json
reports/adventure-playtest.json
build/unity-adventure/
```

## Core Principle

The V3 graph is a narrative graph, not a level graph.

The adventure extension must add a spatial layer. A story node may become a
room, corridor segment, trigger sequence, NPC encounter, interactive object
chain, short cutscene, or quest step. An edge becomes a spatially triggered
transition, a completed interaction, a dialogue decision, or an unlocked route.

## Complete Artifact Contracts

### `genre-policy.json`

Defines how this run should become a side-scroller:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "AdventureGenrePlanner"
  },
  "genre_id": "side_scroller_adventure",
  "engine_target": "unity_2d_mobile",
  "camera_style": "horizontal_follow",
  "movement_model": {
    "walk": true,
    "run": false,
    "jump": "limited_contextual",
    "climb": "contextual",
    "crouch": "contextual"
  },
  "player_verbs": [
    "move",
    "inspect",
    "listen",
    "open",
    "pick_up",
    "use_item",
    "talk",
    "tend_garden",
    "hide_or_wait"
  ],
  "mobile_controls": {
    "left": "virtual_joystick",
    "primary": "context_action",
    "secondary": "listen_or_observe",
    "pause": "menu"
  },
  "forbidden_adaptations": [
    "combat_as_primary_loop",
    "long_menu_only_branching",
    "unvalidated_arbitrary_scene_code"
  ]
}
```

### `world-map.json`

Defines global spatial structure:

```json
{
  "world_id": "world.secret_garden",
  "start_level_id": "level.india_bungalow",
  "level_order": [],
  "regions": [],
  "connections": [],
  "global_state_gates": [],
  "narrative_node_coverage": []
}
```

Required fields per region:

- `region_id`
- `title`
- `narrative_scope_node_ids`
- `level_ids`
- `available_after`
- `emotional_function`
- `visual_function`

### `*.level.json`

Defines each playable level:

```json
{
  "level_id": "level.misselthwaite_corridor",
  "region_id": "region.manor",
  "source_node_ids": [],
  "dimensions": {"width": 96, "height": 18, "unit": "tile"},
  "layers": [],
  "collision": [],
  "walkable_surfaces": [],
  "camera_bounds": [],
  "spawn_points": [],
  "exits": [],
  "interactable_refs": [],
  "npc_refs": [],
  "ambient_audio": [],
  "state_variants": []
}
```

Required level semantics:

- every playable level has at least one valid player spawn;
- every non-terminal level has at least one reachable exit or interaction that
  advances narrative state;
- camera bounds cover all required interactables and exits;
- collision never blocks all paths to required objectives;
- state variants can change props, lighting, locked doors, NPC presence, and
  garden vitality, but not narrative state directly.

### `*.interaction.json`

Defines concrete player interactions:

```json
{
  "interaction_id": "interaction.listen_corridor_cry",
  "source_node_id": "node.l1.arc01.ch05.corridor_cry_after_garden",
  "level_id": "level.manor_corridor",
  "kind": "listen",
  "position": {"x": 42, "y": 2},
  "activation": {
    "input": "secondary",
    "radius": 2.0,
    "conditions": []
  },
  "feedback": {
    "animation": "mary_listen",
    "sfx": "sfx.house.distant_cry",
    "caption": "A child's cry threads through the corridor."
  },
  "completion": {
    "edge_id": "edge.l1.arc01.cry_after_garden_to_interleaved",
    "outcome_id": "edge_l1_arc01_cry_after_garden_to_interleaved",
    "state_writes": []
  },
  "source_trace": {
    "node_ids": [],
    "edge_ids": []
  }
}
```

Interaction kinds:

```text
inspect
listen
door
pickup
use_item
talk
tend_garden
wait_or_hide
cutscene_trigger
ending_trigger
```

### `*.quest.json`

Defines multi-step spatial tasks:

```json
{
  "quest_id": "quest.find_secret_garden_wall",
  "source_node_ids": [],
  "steps": [
    {
      "step_id": "step.follow_robin",
      "level_id": "level.garden_wall",
      "required_interaction_ids": [],
      "optional_interaction_ids": [],
      "completion_edge_id": "edge.example"
    }
  ],
  "state_reads": [],
  "state_writes": [],
  "failure_policy": "fail_forward",
  "source_trace": {}
}
```

Quests are allowed to span multiple story nodes, but each step must identify
which graph edge or state transition it completes.

### `*.dialogue.json`

Defines dialogue that can run inside the side-scroller:

```json
{
  "dialogue_id": "dialogue.mary_martha_cry_denial",
  "source_node_id": "node.example",
  "speaker_bindings": [],
  "lines": [],
  "choices": [],
  "state_reads": [],
  "state_writes": [],
  "exit_edge_bindings": []
}
```

Dialogue choices may exist, but the genre should prefer spatial action over
long VN-style menus.

### `narrative-bindings.json`

Compiles all graph-to-space bindings:

```json
{
  "node_bindings": [
    {
      "node_id": "node.example",
      "level_id": "level.example",
      "binding_kind": "interaction_sequence",
      "required_interaction_ids": [],
      "quest_id": null
    }
  ],
  "edge_bindings": [
    {
      "edge_id": "edge.example",
      "trigger_kind": "interaction_completion",
      "trigger_id": "interaction.example",
      "target_node_id": "node.next",
      "conditions": [],
      "effects": []
    }
  ],
  "ending_bindings": [
    {
      "ending_id": "ending.example",
      "terminal_node_id": "node.terminal",
      "level_id": "level.final_garden",
      "ending_sequence_id": "ending_sequence.example"
    }
  ]
}
```

### `adventure-manifest.json`

The final compiler output consumed by Unity:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "compile_adventure_manifest.py"
  },
  "genre_policy": {},
  "world_map": {},
  "levels": [],
  "interactions": [],
  "quests": [],
  "dialogue": [],
  "bindings": {},
  "initial_state": {},
  "state_schema": {},
  "assets": [],
  "ending_catalog": [],
  "build_settings": {}
}
```

## New Role Cards And Prompts

Add role references under:

```text
references/subagents/adventure/
```

### `AdventureGenrePlanner`

Input:

- user prompt;
- `branch_graph.json`;
- `game_ir.json`;
- genre reference contract.

Output:

- `genre-policy.json`;
- adaptation notes for how the story should become horizontal mobile
  exploration.

Responsibility:

- decide player verbs;
- decide movement limits;
- decide mobile input model;
- preserve global conflict and ending structure;
- identify which narrative choices should become spatial actions.

### `WorldMapDesigner`

Input:

- `genre-policy.json`;
- compact branch graph clusters;
- design summaries.

Output:

- `world-map.json`.

Responsibility:

- divide the story into regions and levels;
- map story arcs to spaces;
- define global connections and unlock order;
- preserve narrative coverage.

### `LevelBlockoutDesigner`

Input:

- one world region or level packet;
- relevant source nodes and edge exits;
- player verb contract.

Output:

- one or more `*.level.json` files.

Responsibility:

- create spatial blockouts;
- place walkable surfaces, exits, spawn points, camera bounds, interactable
  slots, NPC slots, and state variants;
- avoid decorative detail that belongs to asset direction.

### `InteractionQuestDesigner`

Input:

- level packets;
- node and edge packets;
- state read/write packets.

Output:

- `*.interaction.json`;
- `*.quest.json`;
- `*.dialogue.json`.

Responsibility:

- translate narrative choices into spatial tasks;
- bind every non-terminal edge to an interaction, quest step, dialogue choice,
  or automatic trigger;
- keep all state writes traceable to branch graph edges or game IR rules.

### `AdventureNarrativeBinder`

Input:

- all world, level, interaction, quest, dialogue artifacts;
- public branch graph;
- shared state schema.

Output:

- `narrative-bindings.json`;
- repair packet for missing bindings.

Responsibility:

- guarantee every public graph node has a playable binding;
- guarantee every public edge has a trigger binding;
- preserve V3 ending metadata in ending bindings;
- reject unreachable or unbound topology.

### `AdventureAssetDirector`

Input:

- adventure manifest draft;
- genre policy;
- style bible;
- existing asset direction.

Output:

- `workspace/assets/adventure/asset-direction.json`.

Responsibility:

- plan tile sets, props, character sprites, animations, UI icons, audio cues,
  and state-variant visuals;
- bind assets to levels and interactions;
- define reuse groups so generated assets remain coherent.

### `AdventureCompilerReviewer`

Input:

- complete adventure artifact set;
- validator reports.

Output:

- review findings and repair routing.

Responsibility:

- distinguish authoring issues from compiler/runtime bugs;
- route fixes to design, spatial, interaction, asset, or runtime layer.

## Script And Pipeline Additions

Add these scripts:

```text
scripts/adventure_schema.py
scripts/compile_adventure_manifest.py
scripts/validate_adventure.py
scripts/validate_adventure_spatial.py
scripts/validate_adventure_bindings.py
scripts/export_unity_adventure.py
scripts/simulate_adventure_paths.py
scripts/capture_unity_adventure.py
```

Update:

```text
scripts/run_pipeline.py
scripts/pipeline_lib.py
scripts/plan_assets.py
scripts/generate_assets.py
scripts/validate_assets.py
scripts/write_report.py
SKILL.md
references/artifact-contracts.md
references/post-design-prompts.md
references/repair-routing.md
```

Add pipeline commands:

```text
run_pipeline.py plan-adventure
run_pipeline.py compile-adventure
run_pipeline.py validate-adventure
run_pipeline.py export-adventure-unity
run_pipeline.py build-adventure
run_pipeline.py test-adventure
```

`build` should accept:

```text
--genre vn
--genre side_scroller_adventure
--engine unity
--platform android
--platform ios
--platform desktop
--platform webgl
```

## Unity Runtime Implementation

Add a generated Unity project target under:

```text
build/unity-adventure/
```

Add or template these runtime systems:

```text
AdventureStateStore
AdventureManifestLoader
AdventureGraphRunner
MobileInputController
PlayerController2D
CameraFollow2D
LevelLoader
CollisionBuilder
ParallaxLayerBuilder
InteractionController
QuestController
DialogueController
InventoryController
NPCController
GardenTendingController
AudioCueController
CutsceneController
EndingController
SaveLoadController
DebugStateOverlay
BuildAutomation
PlaytestAutomation
```

Runtime responsibilities:

- load `adventure-manifest.json`;
- build level geometry and colliders from level specs;
- place player, NPCs, interactables, and props;
- evaluate state gates using the same operators as Web VN runtime;
- apply state writes including `append_unique`;
- advance graph edges only through compiled bindings;
- trigger ending sequences only from terminal ending bindings;
- support mobile touch controls and keyboard fallback;
- support deterministic playtest hooks.

State condition operators must match existing design semantics:

```text
equals
not_equals
in
not_in
contains
not_contains
exists
not_exists
greater_than
greater_than_or_equal
less_than
less_than_or_equal
```

State write operations:

```text
set
increment
decrement
append
append_unique
remove
clear
```

## Asset System

Extend asset planning for adventure-specific asset kinds:

```text
tileset
tile_rule
character_sprite
character_animation
npc_sprite
prop_sprite
foreground_occluder
background_layer
parallax_layer
interaction_icon
mobile_control_icon
ambient_loop
interaction_sfx
footstep_sfx
ui_sfx
ending_still
```

Each asset direction must include:

- `asset_id`;
- `asset_kind`;
- `runtime_path`;
- `source_trace`;
- `style_tags`;
- `reuse_group`;
- `required_level_ids`;
- `required_interaction_ids`;
- `state_variant_ids`;
- `fallback_policy`.

The asset validator must check:

- every level references valid background and collision visual assets;
- every interactable has visible affordance or intentional hidden affordance;
- every player/NPC state requiring animation has an animation clip;
- mobile UI icons exist;
- terminal endings have ending sequence assets or valid cutscene fallback.

## Validators

### Schema Validator

Checks every adventure artifact shape and source trace.

Required command:

```text
python3 scripts/validate_adventure.py --run-root <run>
```

### Narrative Binding Validator

Checks:

- every public branch graph node has one playable binding;
- every public branch graph edge has one trigger binding;
- no trigger references missing graph edges;
- edge effects match public branch graph effects;
- state gates reference declared state variables;
- V3 ending families and variants are preserved;
- no non-terminal node can become an unbound sink.

### Spatial Validator

Checks:

- every spawn can reach at least one required objective;
- every required objective can reach its exit;
- collisions do not seal required paths;
- camera bounds include all required interactions;
- exits connect to valid target levels or narrative bindings;
- hidden interactables have discovery affordances;
- mobile controls do not cover required UI prompts.

Implementation:

- convert level walkable surfaces and collisions into a grid graph;
- run pathfinding from each spawn to required interactions/exits;
- report exact blocked segment or missing connector.

### State Reachability Validator

Checks:

- every state-gated interaction has at least one preceding path that can
  satisfy it;
- every `in` condition has compatible state writes somewhere upstream;
- `append_unique` and `contains` conditions are type-compatible;
- no required edge can only be unlocked by impossible state.

### Runtime Softlock Validator

Checks:

- every playable non-terminal runtime state has at least one available action;
- player cannot lose required inventory without fail-forward;
- ending triggers cannot fire before terminal node state;
- scene reload/save/load preserves current graph node and level state.

### Playtest Validator

Automated Unity playtest must:

- start the game;
- move the player in at least one generated level;
- activate at least one interaction of each kind present in the run;
- complete at least one full path to a terminal ending;
- capture screenshots for start, mid-run, and ending;
- write `reports/adventure-playtest.json`.

## Implementation Phases

### Phase 1: Contracts And Docs

Files:

```text
references/artifact-contracts.md
references/post-design-prompts.md
references/repair-routing.md
references/subagents/adventure/*.md
plans/adventure-extension-full-implementation-plan.md
```

Tasks:

1. Add `side_scroller_adventure` as a supported genre.
2. Document all adventure artifact contracts.
3. Add role cards for the six adventure roles.
4. Define repair ownership for each validator finding.
5. Add examples for Secret Garden-style adaptation.

Verification:

```text
python3 -m py_compile scripts/*.py tests/*.py
```

### Phase 2: Adventure Schema Library

Files:

```text
scripts/adventure_schema.py
scripts/validate_adventure.py
tests/run_adventure_regression.py
tests/fixtures/adventure_minimal/
```

Tasks:

1. Implement shared JSON loading and finding reporting.
2. Implement schema checks for all adventure artifact types.
3. Add fixtures for:
   - valid minimal full adventure;
   - missing node binding;
   - missing edge trigger;
   - impossible state gate;
   - blocked spatial path;
   - missing ending binding.
4. Add regression tests that assert expected finding kinds.

Verification:

```text
python3 tests/run_adventure_regression.py
```

### Phase 3: Adventure Planning Controller

Files:

```text
scripts/run_pipeline.py
scripts/pipeline_lib.py
references/subagents/adventure/*.md
```

Tasks:

1. Add `plan-adventure` command.
2. Build compact packets from public branch graph and game IR.
3. Persist adventure artifacts under `workspace/adventure`.
4. Prevent adventure workers from reading private V3 artifacts directly.
5. Add repair packet writing for invalid/missing artifacts.

Verification:

```text
python3 scripts/run_pipeline.py plan-adventure --run-root tests/fixtures/adventure_minimal
python3 scripts/validate_adventure.py --run-root tests/fixtures/adventure_minimal
```

### Phase 4: Compiler

Files:

```text
scripts/compile_adventure_manifest.py
scripts/run_pipeline.py
scripts/write_report.py
```

Tasks:

1. Load genre policy, world map, levels, interactions, quests, dialogue,
   narrative bindings, state schema, branch graph, game IR, and assets.
2. Normalize state conditions and writes.
3. Expand graph edge bindings into runtime trigger bindings.
4. Build `ending_catalog` from public terminal nodes.
5. Emit `workspace/adventure/adventure-manifest.json`.
6. Add compile report path to final report.

Verification:

```text
python3 scripts/compile_adventure_manifest.py --run-root tests/fixtures/adventure_minimal
python3 scripts/validate_adventure.py --run-root tests/fixtures/adventure_minimal
```

### Phase 5: Spatial And State Validators

Files:

```text
scripts/validate_adventure_spatial.py
scripts/validate_adventure_bindings.py
scripts/validate_adventure.py
```

Tasks:

1. Implement graph binding coverage checks.
2. Implement state reachability checks.
3. Implement level grid/pathfinding checks.
4. Implement softlock checks.
5. Merge reports into `reports/adventure-validation.json`.

Verification:

```text
python3 scripts/validate_adventure.py --run-root tests/fixtures/adventure_minimal --write-report
python3 tests/run_adventure_regression.py
```

### Phase 6: Unity Adventure Runtime Starter

Files:

```text
assets/unity-adventure-template/
scripts/export_unity_adventure.py
```

Tasks:

1. Add Unity template with runtime scripts listed above.
2. Add generated manifest loader.
3. Add generated scene builder.
4. Add mobile input and keyboard fallback.
5. Add interaction prompts.
6. Add state condition evaluator and state writer.
7. Add deterministic playtest hooks.

Verification:

```text
python3 scripts/export_unity_adventure.py --run-root tests/fixtures/adventure_minimal
```

If Unity Editor is available:

```text
Unity -batchmode -projectPath build/unity-adventure -runTests
```

### Phase 7: Unity Exporter

Files:

```text
scripts/export_unity_adventure.py
scripts/run_pipeline.py
scripts/write_report.py
```

Tasks:

1. Copy Unity template.
2. Write `Assets/StreamingAssets/adventure-manifest.json`.
3. Copy generated assets.
4. Generate build settings for Android, iOS, desktop, and WebGL.
5. Generate `BuildAutomation` entry points.
6. Emit export report.

Verification:

```text
python3 scripts/run_pipeline.py export-adventure-unity --run-root tests/fixtures/adventure_minimal
```

### Phase 8: Asset Pipeline

Files:

```text
scripts/plan_assets.py
scripts/generate_assets.py
scripts/validate_assets.py
scripts/export_unity_adventure.py
references/provider-capabilities/*.json
```

Tasks:

1. Add adventure asset kinds.
2. Generate or copy placeholder-safe sprites and tilesets.
3. Validate animation requirements.
4. Bind asset runtime paths into adventure manifest.
5. Add fallback assets for missing provider output.

Verification:

```text
python3 scripts/plan_assets.py --run-root tests/fixtures/adventure_minimal --genre side_scroller_adventure
python3 scripts/generate_assets.py --run-root tests/fixtures/adventure_minimal --allow-placeholders
python3 scripts/validate_assets.py --run-root tests/fixtures/adventure_minimal
```

### Phase 9: Build And Playtest Automation

Files:

```text
scripts/capture_unity_adventure.py
scripts/simulate_adventure_paths.py
scripts/run_pipeline.py
```

Tasks:

1. Add automated route simulation from branch graph and adventure bindings.
2. Generate one deterministic playtest route per ending family.
3. Drive Unity test hooks for movement and interaction activation.
4. Capture screenshots and logs.
5. Fail build on hard softlocks.

Verification:

```text
python3 scripts/run_pipeline.py build-adventure --run-root tests/fixtures/adventure_minimal --platform desktop
python3 scripts/run_pipeline.py test-adventure --run-root tests/fixtures/adventure_minimal
```

### Phase 10: Secret Garden Full Conversion

Target run:

```text
runs/secret-garden-v3
```

Required regions:

```text
region.india_bungalow
region.moor_arrival
region.manor_rooms
region.manor_corridors
region.garden_wall
region.secret_garden
region.colin_room
region.final_garden
```

Required player verbs in this run:

```text
move
inspect
listen
open
pick_up
talk
tend_garden
wait_or_hide
```

Required state mappings:

```text
state.l1.arc01.garden_mystery_status -> wall and key unlocks
state.l1.arc01.corridor_cry_status -> corridor listen triggers
state.l2.arc03_secret_expands_to_colin.permission_status -> garden access and adult pressure
state.l3.global_secret_garden.secret_circle_trust -> NPC availability
state.l3.global_secret_garden.colin_recovery_stage -> Colin movement and final garden sequence
state.l3.global_secret_garden.magic_interpretation_focus -> ending presentation
state.game.ending_id -> terminal ending sequence
```

Required ending exports:

```text
ending_family.public_reunion_bloom
ending_family.children_guardianship
ending_family.marys_belonging
ending_family.magic_open_afterglow
```

Tasks:

1. Generate adventure genre policy for Secret Garden.
2. Generate world map and all level blockouts.
3. Generate interactions and quests for every public node/edge.
4. Compile and validate adventure manifest.
5. Generate placeholder-complete assets if final assets are unavailable.
6. Export Unity adventure project.
7. Run route simulation for all four ending families.
8. Run Unity playtest for at least one route per ending family.
9. Capture screenshots for:
   - Mary arrival;
   - first corridor cry;
   - garden wall;
   - first secret garden entry;
   - Colin room;
   - final garden ending.

Verification:

```text
python3 scripts/design_v3_validate.py --run-root runs/secret-garden-v3
python3 scripts/validate_artifacts.py --run-root runs/secret-garden-v3 --write-projections
python3 scripts/run_pipeline.py plan-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py compile-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py validate-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py build-adventure --run-root runs/secret-garden-v3 --platform desktop
python3 scripts/run_pipeline.py test-adventure --run-root runs/secret-garden-v3
```

## Repair Routing

Use these finding ownership rules:

```text
missing_adventure_genre_policy -> AdventureGenrePlanner
missing_world_region -> WorldMapDesigner
missing_level_binding -> LevelBlockoutDesigner
blocked_spatial_path -> LevelBlockoutDesigner
missing_interaction_binding -> InteractionQuestDesigner
missing_edge_trigger -> AdventureNarrativeBinder
impossible_state_gate -> AdventureNarrativeBinder or V3 design repair
missing_asset_for_level -> AdventureAssetDirector
missing_runtime_adapter -> controller/runtime implementation
runtime_softlock -> AdventureNarrativeBinder, LevelBlockoutDesigner, or runtime
ending_binding_mismatch -> AdventureNarrativeBinder or V3 ending repair
```

## Acceptance Criteria

The adventure extension is complete when all of these are true:

1. `side_scroller_adventure` is documented as a supported genre.
2. All adventure artifact contracts are implemented and validated.
3. The pipeline can compile adventure artifacts into
   `workspace/adventure/adventure-manifest.json`.
4. Unity export creates a runnable 2D adventure project from the manifest.
5. The runtime supports mobile controls, keyboard fallback, collisions,
   camera, interactions, quests, dialogue, inventory, state gates, state
   writes, endings, save/load, and debug state overlay.
6. The validators catch missing bindings, blocked paths, impossible gates,
   missing assets, and terminal path failures.
7. Secret Garden exports as a full playable side-scroller adventure with all
   four ending families reachable.
8. Automated route simulation reaches every ending family.
9. Automated Unity playtest runs at least one complete path per ending family.
10. Final report includes adventure validation, build, asset, and playtest
    status.

## Required Regression Commands

Run before merging the adventure extension:

```text
python3 -m py_compile scripts/*.py tests/*.py
python3 tests/run_v1_regression.py
python3 tests/run_v3_regression.py
python3 tests/run_adventure_regression.py
python3 scripts/design_v3_validate.py --run-root runs/secret-garden-v3
python3 scripts/validate_artifacts.py --run-root runs/secret-garden-v3 --write-projections
python3 scripts/run_pipeline.py build --run-root runs/secret-garden-v3 --skip-assets
python3 scripts/run_pipeline.py plan-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py compile-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py validate-adventure --run-root runs/secret-garden-v3
python3 scripts/run_pipeline.py build-adventure --run-root runs/secret-garden-v3 --platform desktop
python3 scripts/run_pipeline.py test-adventure --run-root runs/secret-garden-v3
```

Unity-specific checks should run whenever Unity is installed:

```text
Unity -batchmode -projectPath runs/secret-garden-v3/build/unity-adventure -runTests
Unity -batchmode -projectPath runs/secret-garden-v3/build/unity-adventure -executeMethod BuildAutomation.BuildDesktop
```

## Implementation Order Summary

```text
1. Contracts and role cards.
2. Schema library and fixtures.
3. Adventure planning controller.
4. Manifest compiler.
5. Binding, spatial, state, and softlock validators.
6. Unity runtime starter.
7. Unity exporter.
8. Asset planning and generation support.
9. Build and playtest automation.
10. Secret Garden full conversion.
11. Regression hardening and docs.
```

This order keeps narrative semantics stable while adding spatial playability in
layers that can be validated independently.
