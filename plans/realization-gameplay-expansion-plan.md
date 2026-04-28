# Realization Gameplay Expansion Plan

## Goal

Extend the existing realization layer so the reserved realization kinds become first-class playable units:

```text
battle
interaction
puzzle
exploration
```

The current pipeline already exposes these ports through `node-realization-plans.json`, but non-VN kinds are written as not-implemented stubs. This plan turns those ports into typed, validated, exportable realization artifacts while preserving the existing design-layer boundary.

The design layer still compiles into the same downstream-facing interface:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

No gameplay writer should read `user_requirements.json`, `chapter_linear_synopsis.json`, v2 internal design artifacts, generated assets, Web runtime code, or Unity project files directly. The controller prepares compact graph and IR slices for each worker.

## Non-Goals

Do not make subagents write arbitrary JavaScript, C#, Unity scenes, Yarn runtime code, or generated asset files.

Do not move gameplay rules into `branch_graph.json`. The graph remains topology authority: nodes, edges, labels, and reachability.

Do not move runtime implementation details into `game_ir.json`. Game IR remains semantic and state authority: variables, rules, conditions, effects, entities, and durable design context.

Do not replace the current VN flow. `vn_yarn` and `cutscene_yarn` remain supported, and mixed VN plus gameplay runs should be valid.

## Current Baseline

The current realization layer has:

```text
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/realization/stubs/*.not-implemented.json
workspace/vn/fragments/*.yarn
workspace/vn/fragments/*.manifest.json
workspace/vn/story.yarn
workspace/vn/story.storyir.json
```

`NodeRealizationPlanner` maps every branch graph node to one realization plan. The controller validates plan coverage and writes stubs for unsupported non-VN kinds.

The Web VN exporter compiles graph, plan, shared state, Yarn fragments, and assets into `build/web-vn/story-data.js`. The browser runtime executes this JSON payload with a JavaScript VN player.

The Unity exporter currently generates a minimal project skeleton. It is not yet equivalent to `unity-vn-studio`, which uses a fixed Unity runtime template, native Yarn/Ink integrations, manifest-driven content packages, `BuildAutomation`, and build/playtest stages.

## Target Architecture

The realization layer should become:

```text
branch_graph.json + game_ir.json
  -> NodeRealizationPlanner
  -> per-kind realization writers
  -> gameplay unit artifacts
  -> gameplay-manifest.json
  -> Web VN runtime adapters
  -> optional Unity runtime adapters
```

Subagents produce typed payloads only. The controller owns persistence, validation, compilation, export, runtime binding, reports, and repair routing.

## Execution Checklist

Implement in this order:

```text
1. Add gameplay artifact paths, adapter registry, and run-layout directories.
2. Add shared gameplay unit validation for battle, interaction, puzzle, and exploration.
3. Compile gameplay-manifest.json and write gameplay validation and coverage reports.
4. Make run_pipeline.py fail on invalid gameplay units before export.
5. Update Web export so story-data.js carries gameplay unit data by source node.
6. Implement Web runtime adapters for:
   - battle.choice_duel
   - interaction.inspect_scene
   - puzzle.sequence_lock
   - exploration.room_nav
7. Extend asset planning so gameplay asset kinds can be generated and bound.
8. Update SKILL.md, artifact contracts, subagent prompts, and repair routing.
9. Add or generate a mixed run containing one node for each gameplay kind.
10. Run py_compile, node --check, pipeline build, and browser smoke validation.
```

The first complete implementation should target Web VN playability. Unity should export or report gameplay manifest support honestly until Unity-side adapters are implemented.

## Artifact Layout

Add these canonical paths:

```text
workspace/realization/battles/<node-id>.battle.json
workspace/realization/interactions/<node-id>.interaction.json
workspace/realization/puzzles/<node-id>.puzzle.json
workspace/realization/explorations/<node-id>.exploration.json
workspace/realization/gameplay-manifest.json
reports/gameplay-validation.json
reports/gameplay-coverage.json
```

Keep not-implemented stubs only for:

```text
external_stub
unsupported adapter_id
explicitly skipped gameplay under run policy
```

`battle`, `interaction`, `puzzle`, and `exploration` should not become stubs by default once their first adapters exist.

## Shared Gameplay Unit Contract

All four gameplay unit files should share a common outer shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "BattleRealizationWriter",
    "notes": []
  },
  "source_node_id": "node.example",
  "realization_unit_id": "realization.node_example",
  "realization_kind": "battle",
  "adapter_id": "battle.choice_duel",
  "entry_text": "Short player-facing setup text.",
  "exit_bindings": [
    {
      "outcome_id": "victory",
      "edge_id": "edge.example_to_next",
      "label": "Press on",
      "state_writes": []
    }
  ],
  "required_state_reads": [],
  "state_writes": [],
  "required_assets": [],
  "runtime_spec": {},
  "fail_forward": {
    "enabled": true,
    "outcome_id": "partial_success",
    "summary": "How the story continues if the player does not fully succeed."
  },
  "continuity_summary": "What this unit preserves for downstream nodes.",
  "source_trace": {
    "requirement_ids": [],
    "event_ids": [],
    "node_ids": ["node.example"],
    "edge_ids": ["edge.example_to_next"],
    "game_ir_ids": []
  }
}
```

The outer contract stays stable. Kind-specific data lives under `runtime_spec`.

## Realization Writers

### BattleRealizationWriter

Input:

```text
one battle realization plan
branch_graph slice for the source node and neighboring nodes
game_ir semantic slice with relevant entities, state variables, rules, and design brief
allowed battle adapters
optional repair ticket
```

Output:

```text
workspace/realization/battles/<node-id>.battle.json
```

Responsibilities:

```text
battle promise
player verbs and each verb's job
enemy or opponent pattern
arena tactical role
turn or phase structure
readability and feedback cues
victory, defeat, escape, or partial-success outcomes
state reads and writes already declared in game_ir
asset references for backgrounds, enemies, effects, and icons
```

The writer must make at least one important player verb necessary. It should avoid a single safe fallback action solving every beat.

First adapter:

```text
battle.choice_duel
```

This is a deterministic choice-based duel suitable for Web VN and later Unity template playback. It can represent emotional debates, tactical standoffs, creature fights, rival contests, or boss phases without requiring real-time action code.

### InteractionRealizationWriter

Input:

```text
one interaction realization plan
branch_graph slice for the source node and neighboring nodes
game_ir semantic slice with relevant entities, objects, state variables, rules, and design brief
allowed interaction adapters
optional repair ticket
```

Output:

```text
workspace/realization/interactions/<node-id>.interaction.json
```

Responsibilities:

```text
hotspots
inspectables
usable objects
collection or delivery steps
feedback text
completion condition
optional missable discoveries
success, skip, blocked, or partial-success outcomes
state reads and writes already declared in game_ir
asset references for props, hotspots, icons, backgrounds, and SFX
```

First adapter:

```text
interaction.inspect_scene
```

This presents a scene with clickable or selectable hotspots. Hotspots can reveal clues, set local completion flags, unlock choices, and complete the node through a planned outcome.

### PuzzleRealizationWriter

Input:

```text
one puzzle realization plan
branch_graph slice for the source node and neighboring nodes
game_ir semantic slice with relevant clues, state variables, rules, and design brief
allowed puzzle adapters
optional repair ticket
```

Output:

```text
workspace/realization/puzzles/<node-id>.puzzle.json
```

Responsibilities:

```text
puzzle rule
input space
solution
clues
hint ladder
attempt limits
feedback for wrong attempts
fail-forward path
solved, failed, bypassed, or partial-success outcomes
state reads and writes already declared in game_ir
asset references for locks, panels, clue props, symbols, and UI
```

First adapter:

```text
puzzle.sequence_lock
```

This covers ordered-symbol locks, ritual steps, code entry, route ordering, recipe ordering, and clue-sequence puzzles. The adapter should support hints and fail-forward rather than forcing a hard stop.

### ExplorationRealizationWriter

Input:

```text
one exploration realization plan
branch_graph slice for the source node and neighboring nodes
game_ir semantic slice with relevant locations, objects, state variables, rules, and design brief
allowed exploration adapters
optional repair ticket
```

Output:

```text
workspace/realization/explorations/<node-id>.exploration.json
```

Responsibilities:

```text
local navigation graph
areas or rooms
exits
discoveries
gates
optional interactions
completion condition
success, timeout, retreat, or partial-success outcomes
state reads and writes already declared in game_ir
asset references for area backgrounds, map UI, props, and ambience
```

First adapter:

```text
exploration.room_nav
```

This represents small local spaces through rooms, exits, area descriptions, discoveries, and gate conditions. It should compile into Web runtime data without requiring a tilemap or physics engine.

## Gameplay Manifest

The controller writes `workspace/realization/gameplay-manifest.json` after all gameplay units validate:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "narrative_game_pipeline"
  },
  "source_plan_path": "workspace/realization/node-realization-plans.json",
  "units": [
    {
      "source_node_id": "node.example",
      "realization_unit_id": "realization.node_example",
      "realization_kind": "battle",
      "adapter_id": "battle.choice_duel",
      "artifact_path": "workspace/realization/battles/node.example.battle.json",
      "status": "implemented"
    }
  ],
  "adapter_support": {
    "battle.choice_duel": {"web_vn": true, "unity": false},
    "interaction.inspect_scene": {"web_vn": true, "unity": false},
    "puzzle.sequence_lock": {"web_vn": true, "unity": false},
    "exploration.room_nav": {"web_vn": true, "unity": false}
  }
}
```

The manifest is the exporter's gameplay lookup table. Exporters should not scan arbitrary directories to infer implemented gameplay.

## NodeRealizationPlanner Update

The planner should receive run policy:

```json
{
  "playable_kinds": ["vn_yarn", "cutscene_yarn", "battle", "interaction", "puzzle", "exploration"],
  "allowed_adapters": [
    "battle.choice_duel",
    "interaction.inspect_scene",
    "puzzle.sequence_lock",
    "exploration.room_nav"
  ],
  "fallback_policy": "stub_external_only"
}
```

It may select a gameplay kind when that kind is better than pure VN delivery. It must not select an adapter directly unless the plan contract is extended to include `preferred_adapter_id`; otherwise adapter choice belongs to the per-kind writer.

The planner still maps every branch graph node to exactly one realization plan and must cover every outgoing edge through exit bindings.

## Workflow Update

The expanded workflow:

```text
1. Generate and validate design artifacts.
2. Project shared-state.schema.json from game_ir.json.
3. Spawn NodeRealizationPlanner.
4. For vn_yarn and cutscene_yarn plans, spawn NodeDialogueWriter.
5. For battle plans, spawn BattleRealizationWriter.
6. For interaction plans, spawn InteractionRealizationWriter.
7. For puzzle plans, spawn PuzzleRealizationWriter.
8. For exploration plans, spawn ExplorationRealizationWriter.
9. Validate VN fragments and gameplay units.
10. Compile realization-manifest.json and gameplay-manifest.json.
11. Assemble Yarn and verify StoryIR.
12. Run asset direction, asset manifest planning, generation, and validation.
13. Export Web VN with VN nodes and gameplay adapters.
14. Optionally export Unity project.
15. Write final reports.
```

The controller may batch per-kind workers, but each worker owns exactly one source node artifact.

## Validation Rules

Add `scripts/validate_gameplay.py` or extend `validate_artifacts.py` with gameplay validation.

Common rules:

```text
every gameplay plan has exactly one matching unit artifact
unit source_node_id matches plan source_node_id
unit realization_unit_id matches plan unit_id
unit realization_kind matches plan realization_kind
unit adapter_id is supported by the configured adapter registry
unit exit_bindings cover every planned exit binding exactly once
unit outcomes do not introduce branch edges not in the plan
unit required_state_reads and state_writes reference only game_ir-declared variables
unit required_assets use stable asset prefixes
unit source_trace includes the source node id
unit runtime_spec is present and object-shaped
```

Battle rules:

```text
has at least two player verbs
has at least one opponent or pressure source
has at least one victory outcome
has readable feedback for major enemy actions
has escalation or phase pressure when the encounter has more than one round
does not make one zero-risk verb dominate every beat
```

Interaction rules:

```text
has at least one hotspot or interactable
has a reachable completion condition
blocked interactions explain the missing requirement
optional discoveries cannot block required branch progress unless planned
```

Puzzle rules:

```text
has a deterministic solution
has at least one clue
has wrong-attempt feedback
has hint or fail-forward behavior
the solved outcome is reachable from the initial puzzle state
```

Exploration rules:

```text
has at least one area
local exits reference existing local areas
gates reference valid state variables or local discoveries
at least one planned outcome is reachable
retreat or timeout outcomes are bound only when present in the plan
```

Write reports:

```text
reports/gameplay-validation.json
reports/gameplay-coverage.json
```

## Web VN Export

The Web VN exporter should extend `story-data.js` with gameplay node data:

```json
{
  "nodes": [
    {
      "id": "node.example",
      "title": "Example",
      "realization_kind": "battle",
      "gameplay_unit_id": "realization.node_example",
      "gameplay": {
        "adapter_id": "battle.choice_duel",
        "runtime_spec": {}
      },
      "choices": []
    }
  ],
  "gameplay_units": {}
}
```

The Web runtime should dispatch by `adapter_id`:

```text
vn_yarn / cutscene_yarn -> existing dialogue flow
battle.choice_duel -> battle panel
interaction.inspect_scene -> hotspot panel
puzzle.sequence_lock -> puzzle panel
exploration.room_nav -> room navigation panel
```

All adapters complete through the same controller-owned transition function:

```text
completeActivity(outcome_id)
```

That function applies state writes, resolves the bound edge, and moves to the next branch graph node.

## Unity Export

Unity support should follow the `unity-vn-studio` direction rather than the current minimal OnGUI skeleton:

```text
fixed Unity runtime template
generated content package
runtime-config.json
asset-manifest.json
layout-manifest.json
gameplay-manifest.json
BuildAutomation.cs
smoke tests
optional player capture
```

Do not generate bespoke C# gameplay code from subagents for each node. Unity adapters should consume the same typed gameplay unit JSON as Web adapters.

Initial Unity milestone can be export-only:

```text
copy gameplay units into Assets/Resources/Generated/VNContent/Gameplay
write gameplay-manifest.json
report adapter_support unity=false
do not claim Unity gameplay support until runtime adapters exist
```

Later Unity runtime milestone:

```text
BattleChoiceDuelController
InteractionInspectSceneController
PuzzleSequenceLockController
ExplorationRoomNavController
GameplayBridge
BuildAutomation smoke test that completes one gameplay node
```

## Asset Integration

Gameplay units only declare `required_assets`. They do not write provider prompts, file paths, or generated bytes.

Extend `asset-direction.json` and `asset-manifest.json` support for gameplay-oriented kinds:

```text
enemy
prop
hotspot
symbol
effect
icon
map
ui
sfx
bgm
```

The controller should derive or request asset direction after gameplay units are accepted, because gameplay writers may introduce required props, enemies, locks, symbols, and exploration areas that were not present in pure VN dialogue plans.

The build phase should bind generated asset paths back into Web and Unity exports through manifest IDs, not direct file paths in writer output.

## Repair Routing

Route failures to the smallest owner:

```text
missing plan or wrong realization kind -> NodeRealizationPlanner
invalid battle unit -> BattleRealizationWriter
invalid interaction unit -> InteractionRealizationWriter
invalid puzzle unit -> PuzzleRealizationWriter
invalid exploration unit -> ExplorationRealizationWriter
state reference failure -> writer first, BaseGameIRDesigner only if state is truly missing from design authority
asset id mismatch -> AssetDirector or asset planner
adapter runtime failure -> controller or runtime adapter bug
export failure -> exporter bug first
```

Repair tickets should include:

```text
failed artifact path
validation findings
source realization plan
branch graph slice
game_ir semantic slice
allowed adapter list
exact expected contract
```

## Tests And Fixtures

Add deterministic fixtures:

```text
tests/fixtures/gameplay_mixed_minimal/
tests/fixtures/gameplay_battle_choice_duel/
tests/fixtures/gameplay_interaction_inspect_scene/
tests/fixtures/gameplay_puzzle_sequence_lock/
tests/fixtures/gameplay_exploration_room_nav/
```

Minimum checks:

```text
python3 -m py_compile scripts/*.py
validate_artifacts passes existing VN fixtures
validate_gameplay passes four gameplay fixtures
Web export contains gameplay_units
node --check assets/web-vn-template/runtime.js
Playwright can complete each adapter and reach a planned next node
asset generation still works with gameplay required_assets
Unity export copies gameplay manifests without claiming unsupported runtime support
```

## Implementation Phases

### Phase 1: Contracts And Prompts

Update:

```text
SKILL.md
references/artifact-contracts.md
references/subagent-prompts.md
references/repair-routing.md
```

Add the four writer roles, gameplay artifact paths, adapter registry, and updated workflow.

### Phase 2: Gameplay Validation And Manifest Compilation

Implement:

```text
scripts/validate_gameplay.py
scripts/compile_gameplay_manifest.py
pipeline_lib helpers for gameplay paths and adapter registry
reports/gameplay-validation.json
reports/gameplay-coverage.json
```

Keep this phase independent from Web runtime changes so artifact correctness can be tested first.

### Phase 3: Web Runtime Adapters

Implement:

```text
battle.choice_duel
interaction.inspect_scene
puzzle.sequence_lock
exploration.room_nav
```

Modify:

```text
scripts/export_web_vn.py
assets/web-vn-template/runtime.js
assets/web-vn-template/styles.css
```

Maintain the existing VN playback path.

### Phase 4: Asset Direction Integration

Update asset planning so gameplay units contribute required assets to `asset-direction.json` and `asset-manifest.json`.

Validation should fail when a gameplay unit references an asset that cannot be directed, generated, or bound.

### Phase 5: Unity Export Alignment

Replace the current minimal Unity skeleton with a manifest-based content package approach modeled after `unity-vn-studio`.

First export gameplay manifests and report unsupported runtime adapters. Then add Unity gameplay controllers and smoke tests one adapter at a time.

### Phase 6: End-To-End Mixed Runs

Create an end-to-end run that includes:

```text
one VN node
one battle node
one interaction node
one puzzle node
one exploration node
at least two conditional branches
generated assets
Web playable smoke test
Unity export smoke test if supported
```

## Acceptance Criteria

The expansion is complete when:

```text
all four realization writer prompts exist
all four gameplay artifact contracts exist
all four first adapters validate
all four first adapters are playable in Web VN
unsupported gameplay no longer becomes a stub by default
gameplay-manifest.json is generated deterministically
reports expose implemented, skipped, and unsupported gameplay coverage
existing VN-only runs still build
asset generation includes gameplay assets
Unity export either supports the gameplay adapter or reports it as unsupported without pretending it is playable
```

## Main Risks

The first risk is letting per-kind writers invent topology or state. Mitigation: edge coverage and state-reference validation must be strict.

The second risk is allowing arbitrary runtime code generation. Mitigation: only allow registered declarative adapters.

The third risk is bloating `game_ir.json` with runtime data. Mitigation: keep runtime behavior in gameplay units and keep Game IR mode-neutral.

The fourth risk is promising Unity parity too early. Mitigation: report per-adapter export support separately for Web and Unity.

The fifth risk is treating puzzles or exploration as dead ends. Mitigation: require deterministic reachability and fail-forward validation.
