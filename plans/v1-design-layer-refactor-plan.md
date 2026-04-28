# V1 Design Layer Refactor Plan

## Goal

Refactor the current design layer without changing the pipeline's external behavior.

The practical target is:

```text
Downstream agents only need:
- workspace/design_layer/game_ir.json
- workspace/design_layer/branch_graph.json
```

The existing v1 front-half concepts remain, but the graph artifact is renamed:

```text
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

`branch_graph.json` must not assume chapter structure. It may describe one chapter, multiple chapters, a quest mesh, a VN route graph, or a scene/storylet graph.

## Current State

The current skill's front-half design concepts are:

```text
user_requirements.json
chapter_linear_synopsis.json
branch_graph.json
game_ir.json
```

The downstream prompts still expect more context than necessary:

```text
NodeRealizationPlanner:
  requirements
  synopsis
  branch graph
  game_ir
  shared-state.schema.json

AssetDirector:
  requirements
  synopsis
  branch graph
  game_ir
  realization manifest
  StoryIR summary
```

This makes downstream production tightly coupled to design-stage artifacts. The graph file must use the neutral `branch_graph.json` name so the story structure is not implicitly chapter-based.

## Target State

After v1 refactor, the design layer has two runtime-facing public artifacts:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

The first two files remain required design-source outputs:

```text
user_requirements.json              required source artifact
chapter_linear_synopsis.json        required source artifact
```

Downstream agents must not need to read `user_requirements.json` or `chapter_linear_synopsis.json` directly. The controller may read them during design validation and repair, but it must pass only `branch_graph.json` and `game_ir.json` slices to later agents.

## Non-Goals

- Do not replace the current v1 generation process with the larger v2 design workflow.
- Do not require a database, vector store, or external narrative engine.
- Do not change Web VN or Unity export semantics.
- Do not make downstream agents parse every internal design note.

## Runtime Artifact Policy

The refactor makes `branch_graph.json` the only graph artifact.

| Artifact | V1 refactor behavior |
| --- | --- |
| `branch_graph.json` | Required graph path for downstream use. |
| `game_ir.json` | Remains semantic authority. It should contain enough context for downstream agents to avoid reading requirements or synopsis. |
| `user_requirements.json` | Required design-source artifact. Validated by the controller. Not passed to downstream agents. |
| `chapter_linear_synopsis.json` | Required design-source artifact. Validated by the controller. Not passed to downstream agents. |
| `shared-state.schema.json` | Controller projection from `game_ir.json`. Not an authored downstream dependency. |

## Public Artifact Contract

### `branch_graph.json`

`branch_graph.json` owns topology only:

```text
nodes
edges
start_node_id
terminal nodes
choice labels
high-level node summaries
trace links back to source events or contracts
```

It should stay mode-neutral and implementation-neutral. It should not contain Yarn, Unity paths, image prompts, or executable state effects.

It may keep the current v1 node and edge fields:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BranchGraphDesigner", "notes": []},
  "title": "Story title",
  "start_node_id": "node.intro",
  "nodes": [],
  "edges": []
}
```

Add optional structure-neutral fields:

```json
{
  "graph_scope": "full_game",
  "clusters": [],
  "source_outline_ids": []
}
```

`graph_scope` examples:

```text
single_chapter
full_game
questline
route_mesh
scene_mesh
storylet_pool
```

### `game_ir.json`

`game_ir.json` owns semantic authority:

```text
world facts needed by downstream agents
entities
state variables
progression stages
edge conditions
transition rules
state effects
knowledge and relationship state
node semantic summaries
design constraints needed for realization
```

To remove downstream dependency on requirements and synopsis, add a compact embedded design brief:

```json
{
  "design_brief": {
    "target_experience": "",
    "tone": "",
    "themes": [],
    "must_keep_constraints": [],
    "production_constraints": {},
    "narrative_bible": {
      "cast": [],
      "locations": [],
      "timeline": [],
      "continuity_rules": []
    }
  }
}
```

This is still mode-neutral. It gives later agents enough facts to plan and write scenes without reopening every upstream document.

## Downstream Agent Interface

### `NodeRealizationPlanner`

Inputs after refactor:

```text
branch_graph.json
game_ir.json
run policy
optional repair ticket
```

The planner derives state references from `game_ir.global_state_variables` or `game_ir.state_variables`. The controller may still project `shared-state.schema.json` for deterministic checks, but this projection is not part of the agent's required input.

### `NodeDialogueWriter`

Inputs after refactor:

```text
one realization plan
branch_graph slice for the source node and neighboring nodes
game_ir slice containing relevant entities, state variables, rules, and narrative brief
allowed commands
optional repair ticket
```

The writer must not read full upstream artifacts. The controller prepares the slice from the two canonical files.

### `AssetDirector`

Inputs after refactor:

```text
branch_graph.json
game_ir.json
realization manifest
StoryIR summary if available
optional repair ticket
```

Visual direction comes from graph nodes, entity descriptions, locations, tone, and realization requirements projected from the two public design artifacts.

### Review Agents

Review agents may inspect reports and outputs. They should treat `branch_graph.json` and `game_ir.json` as design truth unless explicitly reviewing front-half generation quality.

## Implementation Steps

### 1. Rename Graph Path

Update `scripts/pipeline_lib.py`:

```text
STAGE_PATHS["branch_graph"] = "workspace/design_layer/branch_graph.json"
```

Behavior:

```text
Require branch_graph.json.
Do not read or write chapter_branch_graph.json.
Update validation error paths to use branch_graph.*.
Update init todos, artifact contracts, and prompts to name branch_graph.json.
```

### 2. Separate Source Validation From Downstream Inputs

Keep validation conceptually split into two layers:

```text
validate_design_sources()
  requires and validates user_requirements and chapter_linear_synopsis

validate_runtime_design()
  requires only branch_graph and game_ir
```

The controller validates all four design-layer outputs for a complete run, but downstream agent inputs are projected from runtime design only:

```text
branch_graph.json
game_ir.json
node-realization-plans.json
VN fragments
```

`run_pipeline.py init` should list all four required design artifacts, and separately identify `branch_graph.json` plus `game_ir.json` as the runtime-facing design interface.

### 3. Embed Compact Upstream Context in `game_ir.json`

Update `BaseGameIRDesigner` prompt:

```text
It may receive requirements and synopsis during front-half generation.
It must compile the durable downstream context into game_ir.design_brief.
It must not require downstream agents to reopen requirements or synopsis.
```

Validation should warn if `game_ir.design_brief` is missing, but it should not fail old runs immediately.

### 4. Remove Downstream Prompt Dependencies

Update `references/subagent-prompts.md`:

```text
NodeRealizationPlanner input:
  - accepted branch_graph.json
  - accepted game_ir.json
  - run policy
  - optional repair ticket

NodeDialogueWriter input:
  - one realization plan
  - branch_graph node slice
  - game_ir semantic slice
  - allowed commands
  - optional repair ticket

AssetDirector input:
  - accepted branch_graph.json
  - accepted game_ir.json
  - realization manifest
  - StoryIR summary if available
  - optional repair ticket
```

The controller owns slicing. Agents should not decide which upstream files to read.

### 5. Update Realization Validation

`validate_realization_plans()` currently checks state reads and writes against `shared-state.schema.json`.

Keep the projection for deterministic validation, but derive it only from `game_ir.json`.

Acceptance rule:

```text
A realization plan is valid if every state read/write references a variable declared in game_ir.
```

`shared-state.schema.json` remains a report/projection artifact, not an authored dependency.

### 6. Update Artifact Contracts

Update `references/artifact-contracts.md`:

```text
Rename primary graph contract to branch_graph.json.
Document graph_scope and clusters as optional fields.
Document game_ir.design_brief as the downstream context carrier.
Add rule: downstream agents receive only branch_graph/game_ir derived context.
```

### 7. Add Migration Tests and Fixtures

Add fixtures:

```text
tests/fixtures/v1_full_source_run/
```

Test cases:

```text
Complete run validates all four design-layer artifacts.
Run with chapter_branch_graph.json but no branch_graph.json fails with a clear missing-artifact error.
Game IR references to missing nodes/edges fail.
Non-trivial branch graph edges not represented in Game IR warn.
NodeRealizationPlanner prompt no longer references requirements or synopsis.
Build still exports Web VN from a complete four-artifact design layer while exporters consume the runtime-facing pair.
```

### 8. Update Final Reports

Final report should include:

```json
{
  "design_layer": {
    "version": "v1-refactored",
    "source_artifacts": [
      "workspace/design_layer/user_requirements.json",
      "workspace/design_layer/chapter_linear_synopsis.json"
    ],
    "runtime_artifacts": [
      "workspace/design_layer/branch_graph.json",
      "workspace/design_layer/game_ir.json"
    ]
  }
}
```

## Migration Strategy

Use a direct rename.

```text
Old in-progress runs must move workspace/design_layer/chapter_branch_graph.json
to workspace/design_layer/branch_graph.json before validation or build.
```

The controller should fail clearly when only the old filename is present. Do not add a fallback reader, alias writer, or soft-deprecation path.

## Acceptance Criteria

The v1 refactor is complete when:

```text
1. Existing v1 runs validate and build after renaming their graph file to branch_graph.json.
2. Complete runs validate all four design-layer outputs and build from the runtime-facing pair.
3. Downstream prompts mention only branch_graph.json and game_ir.json as design inputs.
4. branch_graph.json is the only supported graph artifact.
5. branch_graph.json can represent non-chapter graphs through graph_scope and optional clusters.
6. shared-state.schema.json is always projected from game_ir.json, not authored by agents.
7. Final reports identify the runtime design artifacts actually used.
```

## Risks

The main risk is under-specifying `game_ir.json`. If `game_ir` does not carry enough narrative brief, downstream agents may produce generic scenes even though the pipeline is formally decoupled.

Mitigation:

```text
Add design_brief and narrative_bible fields.
Validate their presence as warnings first.
Promote missing critical context to errors only after fixtures prove the new contract.
```

The second risk is a stale in-progress run that still contains only the old graph filename.

Mitigation:

```text
Fail validation with a missing branch_graph.json error.
Document the one-file rename in the migration note.
```
