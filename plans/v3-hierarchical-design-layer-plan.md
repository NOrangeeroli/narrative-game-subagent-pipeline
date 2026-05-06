# V3 Hierarchical Design Layer Plan

## Goal

Implement a new `v3` design layer that builds narrative game design through
multi-level story abstraction and multi-level graph/state design, while keeping
the downstream public design interface unchanged:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

V3 compiles into the same public graph/state interface consumed by realization,
gameplay, asset, and export stages.

## Core Direction

V3 separates two opposite flows:

```text
story extraction:       fine -> coarse
graph/state design:     coarse -> fine
```

Story extraction starts from the finest enabled story level, usually chapter or
scene-level source units, then progressively aggregates related units into
higher-level story structures.

Graph/state design starts from the coarsest enabled story level, then expands
down toward finer playable units. Every design level must declare how its local
state settlement affects the immediate parent level's state.

Every story extraction level should support multi-agent parallelism by default.
For graph/state design, the coarsest enabled level is a single global design
pass, while lower levels may be sharded by parent packet. The controller should
collect all worker returns, then run a deterministic merge step before the next
level begins.

## Public Interface

The public design files remain:

```text
branch_graph.json = topology authority
game_ir.json      = state, condition, effect, and semantic authority
```

Downstream agents should not read raw V3 internal artifacts by default. They
continue to receive public `branch_graph.json`, public `game_ir.json`, and
controller-generated local context slices.

## V3 Workspace Layout

Add a parallel internal workspace:

```text
workspace/design_layer_v3/
  hierarchy_policy.json
  story_levels/
    level_01/
      linear_story.json
      shards/
      shard_returns/
      merge_report.json
    level_02/
      linear_story.json
      shards/
      shard_returns/
      merge_report.json
    level_03/
      linear_story.json
      shards/
      shard_returns/
      merge_report.json
  facts/
    level_01/
      local_facts.json
      shards/
      shard_returns/
      merge_report.json
    level_02/
      fact_view.json
      shards/
      shard_returns/
      merge_report.json
    level_03/
      fact_view.json
      shards/
      shard_returns/
      merge_report.json
    canonical_fact_graph.json
  adaptation/
    global_policy.json
    policy_slices.json
  design_levels/
    level_03/
      state_model.json
      story_graph.json
      contracts.json
      parent_state_settlements.json
      shards/
      shard_returns/
      merge_report.json
    level_02/
      state_model.json
      story_graph.json
      contracts.json
      parent_state_settlements.json
      shards/
      shard_returns/
      merge_report.json
    level_01/
      state_model.json
      story_graph.json
      contracts.json
      parent_state_settlements.json
      shards/
      shard_returns/
      merge_report.json
  assembled/
    branch_graph.json
    game_ir.json
    assembly_report.json
  validation/
    validation_report.json
```

`level_01` is the finest story level. Larger numbers are coarser levels. A
minimal V3 run may use only `level_01` and `level_02`; a long novel adaptation
may enable `level_03` or higher later.

## Hierarchy Policy

`hierarchy_policy.json` defines enabled levels and their granularities:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "V3Controller"},
  "enabled_levels": [
    {"level": 1, "id": "level_01", "granularity": "chapter", "required": true},
    {"level": 2, "id": "level_02", "granularity": "chapter_group", "required": true},
    {"level": 3, "id": "level_03", "granularity": "act", "required": false}
  ],
  "finest_level": 1,
  "coarsest_level": 3,
  "parallelism": {
    "story_extraction": "enabled_by_default",
    "fact_extraction": "enabled_by_default",
    "design_levels": "enabled_by_default"
  }
}
```

The validator must check that enabled levels form a continuous range from
`finest_level` to `coarsest_level`.

## Story Extraction Flow

Story extraction proceeds from fine to coarse:

```text
source/chunks -> level_01 linear_story
level_01 linear_story -> level_02 linear_story
level_02 linear_story -> level_03 linear_story
```

Non-coarsest levels may be sharded:

```text
controller creates story_levels/level_N/shards/*.json
parallel StoryLevelExtractor workers return partial payloads
controller stores raw returns in story_levels/level_N/shard_returns/
deterministic merge writes story_levels/level_N/linear_story.json
```

Shard workers must only read their assigned packet and the exact role card.
They must not inspect sibling shards or write canonical artifacts.

For source-adaptation `level_01`, sharding is a full-coverage partition of the
source inventory, not sampling. The controller must assign every entry in
`inputs/source_material/source_index.json` to exactly one or more shard packets,
wait for all shard returns, and reject the merge if any source chunk/span is
unassigned, unfinished, or absent from accepted extraction trace. Representative
chapters may be useful for planning, but they are not valid extraction coverage.

The coarsest enabled story level is the global story-line layer. It must be
produced by one `StoryLevelExtractor` worker with every immediate lower-level
story unit, not by parallel act/arc/source shards. If a source-adaptation run has
only one enabled story level, the controller must either use one global extractor
packet or enable a coarser aggregation level before policy and graph/state
design.

### `linear_story.json`

Each story level writes:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "StoryLevelExtractor"},
  "level": 1,
  "level_id": "level_01",
  "granularity": "chapter",
  "units": [
    {
      "id": "story.l1.ch01",
      "title": "Chapter 1",
      "summary": "What happens at this level of abstraction.",
      "sequence_index": 1,
      "source_refs": [],
      "child_unit_ids": [],
      "parent_unit_id": "story.l2.arc01",
      "key_events": [],
      "characters": [],
      "locations": [],
      "open_questions": [],
      "resolved_questions": [],
      "reader_experience": {
        "known_now": "",
        "active_question": "",
        "withheld_information": "",
        "emotional_purpose": "",
        "hook": ""
      }
    }
  ]
}
```

For `level_01`, `child_unit_ids` is normally empty and `source_refs` points to
source chunks, chapters, or spans. For higher levels, `child_unit_ids` points to
units from the immediate lower level.

## Facts Flow

`StoryLevelExtractor` captures stable facts while extracting story levels. The
finest story level remains the primary evidence source, not the coarsest
summary.

Recommended flow:

```text
level_01 linear_story -> level_01 local_facts
level_01 local_facts + level_02 linear_story -> level_02 fact_view
level_02 fact_view + level_03 linear_story -> level_03 fact_view
all fact views -> canonical_fact_graph
```

Fact capture and fact aggregation should support parallel sharding by story
unit or story-unit group. The deterministic merge step is responsible for
deduplicating facts, reconciling aliases, and preserving fine-grained evidence
anchors.

### `canonical_fact_graph.json`

The canonical fact graph should contain:

```text
characters
locations
objects
factions
events
relationships
world rules
causal links
foreshadowing setup/payoff pairs
themes
locked facts
evidence anchors to story units and source refs
```

Fine-grained anchors must be preserved internally, but they must not leak into
public `branch_graph.json` or player-facing prose.

## Adaptation Policy Flow

`AdaptationPolicyDesigner` should operate from the coarsest story perspective
while still referencing canonical facts and fine-grained evidence anchors.

Input:

```text
coarsest enabled linear_story
canonical_fact_graph
user adaptation brief
fine-grained evidence anchors
```

Output:

```text
adaptation/global_policy.json
adaptation/policy_slices.json
```

`global_policy.json` defines fixed facts, forbidden changes, variable processes,
ending families, tone, themes, and allowed reinterpretation zones.

`policy_slices.json` maps the global policy to each enabled story/design level,
story unit, and design parent so that lower-level graph/state designers do not
need to read the full source or full policy.

## Graph/State Design Flow

Graph/state design proceeds from coarse to fine:

```text
level_03 linear_story + level_03 fact_view + policy slice
  -> level_03 state_model/story_graph/contracts/parent_state_settlements

level_02 linear_story + level_02 fact_view + level_03 graph/state/contracts + policy slice
  -> level_02 state_model/story_graph/contracts/parent_state_settlements

level_01 linear_story + level_01 fact view + level_02 graph/state/contracts + policy slice
  -> level_01 state_model/story_graph/contracts/parent_state_settlements
```

If only two levels are enabled, design starts at `level_02`.

Non-coarsest design levels should support multi-agent parallelism by default.
The coarsest enabled design level is one global graph/state pass. For lower
levels, the controller shards by parent unit or parent graph node:

```text
controller creates design_levels/level_N/shards/*.json
each LevelStateGraphDesigner worker receives:
  - one parent graph/state/context slice from level_N+1
  - same-level story units assigned to that parent
  - same-level fact view slice
  - same-level policy slice
worker returns partial state/graph/contracts/settlements
controller stores raw returns in design_levels/level_N/shard_returns/
deterministic merge writes canonical design_levels/level_N/*.json
```

Workers must not write canonical artifacts or inspect sibling shard packets.

## Design Level Artifacts

Each enabled design level writes four files.

### `state_model.json`

Defines state variables owned by this level:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "variables": [
    {
      "id": "state.l2.arc01.trust_path",
      "scope": "level",
      "type": "integer",
      "initial_value": 0,
      "allowed_values": [],
      "description": "Trust accumulated inside arc 01.",
      "owner_story_unit_id": "story.l2.arc01",
      "readable_by": ["level_02.*", "level_01.*"],
      "writable_by": ["level_02.*", "level_01.*"]
    }
  ]
}
```

### `story_graph.json`

Defines the graph at this abstraction level:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "start_node_id": "v3.l2.arc01.start",
  "nodes": [
    {
      "id": "v3.l2.arc01.start",
      "title": "Arc 01 Opening",
      "summary": "The arc begins.",
      "node_type": "scene",
      "story_unit_ids": ["story.l2.arc01"],
      "parent_node_id": "v3.l3.act01",
      "is_terminal": false
    }
  ],
  "edges": [
    {
      "id": "v3.edge.l2.arc01.start.resolve",
      "from": "v3.l2.arc01.start",
      "to": "v3.l2.arc01.resolve",
      "label": "Continue",
      "condition_type": "unconditional",
      "conditions": [],
      "effects": []
    }
  ]
}
```

### `contracts.json`

Defines local design boundaries:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "contracts": [
    {
      "id": "contract.l2.arc01",
      "graph_node_id": "v3.l2.arc01.start",
      "story_unit_ids": ["story.l2.arc01"],
      "allowed_characters": [],
      "allowed_locations": [],
      "allowed_state_reads": ["state.l3.truth_pressure"],
      "allowed_state_writes": ["state.l2.arc01.trust_path"],
      "required_functions": [],
      "forbidden_events": [],
      "allowed_child_story_unit_ids": ["story.l1.ch01", "story.l1.ch02"]
    }
  ]
}
```

### `parent_state_settlements.json`

Every non-coarsest level must declare how this level's state settlement affects
the immediate parent level state.

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "parent_level": 3,
  "settlements": [
    {
      "id": "settlement.l2.arc01.to.l3.act01",
      "source_graph_node_id": "v3.l2.arc01.resolve",
      "parent_graph_node_id": "v3.l3.act01",
      "trigger": "on_node_complete",
      "conditions": [
        {"state_variable_id": "state.l2.arc01.trust_path", "operator": ">=", "value": 1}
      ],
      "effects_on_parent_state": [
        {
          "state_variable_id": "state.l3.truth_pressure",
          "operation": "increment",
          "value": 1
        }
      ],
      "evidence": {
        "story_unit_ids": ["story.l2.arc01"],
        "fact_ids": ["fact.oath"]
      },
      "reason": "Resolving this arc changes the act-level truth pressure."
    }
  ]
}
```

The coarsest level should still write this file, but with an empty settlements
array and `parent_level: null`.

The validator must fail when a non-coarsest design level omits the file. It
must also fail when `effects_on_parent_state` references a state variable that
is not owned by the immediate parent level.

## Deterministic V3 Assembler

Add a deterministic assembler in `scripts/design_v3_lib.py`.

Primary functions:

```python
ensure_design_v3_layout(run_root: Path) -> None
validate_design_v3(run_root: Path, write_report: bool = True) -> ValidationResult
assemble_design_v3(run_root: Path) -> ValidationResult
compile_design_v3(run_root: Path) -> ValidationResult
```

The assembler must:

1. Load hierarchy, story levels, facts, adaptation policy, and all design levels.
2. Validate story parent/child references.
3. Validate graph parent references across design levels.
4. Validate state variables and detect duplicate ids with incompatible types or initial values.
5. Validate each non-coarsest level's `parent_state_settlements`.
6. Merge all level state variables into `game_ir.global_state_variables`.
7. Compile graph nodes and edges into public `branch_graph.json`.
8. Compile graph edge effects and parent settlements into `game_ir.event_rules`.
9. Write staged outputs under `workspace/design_layer_v3/assembled/`.
10. Copy staged outputs to `workspace/design_layer/` after public validation passes.

## Graph Assembly Strategy

The assembler directly generates public `branch_graph.json`.

Recommended behavior:

```text
coarsest level graph provides top-level ordering and clusters
finer level graph nodes replace or expand assigned parent graph nodes
entry/exit stitch edges are generated deterministically where needed
finest enabled level nodes become the default playable public nodes
```

If a parent graph node has no lower-level expansion, it remains as a public
node. If it has child-level expansion, the public graph should use the child
entry and child exits while preserving parent cluster trace internally.

## State Assembly Strategy

State assembly should preserve all level-owned variables, but ids should be
namespaced by level or deliberately declared as shared:

```text
state.l3.*
state.l2.*
state.l1.*
state.shared.*
```

Validation rules:

```text
duplicate state id with same type/initial value -> allowed with warning or merge
duplicate state id with conflicting type/initial value -> error
child settlement writes missing parent state -> error
child settlement writes non-parent state through effects_on_parent_state -> error
parent state never read or written by lower-level settlement -> warning
```

Parent state settlement compilation:

```text
parent_state_settlements[*] -> game_ir.event_rules[*]
source_graph_node_id       -> source_node_id or source_edge_id
effects_on_parent_state    -> effects
conditions                 -> conditions
```

## CLI Changes

Update `scripts/run_pipeline.py`:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "..." \
  --run-root runs/my-v3-game \
  --design-layer v3

python3 scripts/run_pipeline.py compile-design \
  --run-root runs/my-v3-game \
  --design-layer v3
```

`build` should remain unchanged because it consumes only public design files.

Optionally add direct scripts:

```bash
python3 scripts/design_v3_validate.py --run-root runs/my-v3-game
python3 scripts/design_v3_compile.py --run-root runs/my-v3-game
```

## V3 Role Cards

Add role cards under:

```text
references/subagents/design-layer-v3/
```

Initial roles:

```text
StoryLevelExtractor
AdaptationPolicyDesigner
LevelStateGraphDesigner
DesignV3CompilerReviewer
```

The role card index should state that non-coarsest story extraction and
non-coarsest level design are parallel by default, while the coarsest story
extractor and coarsest graph/state designer are single global workers. The
controller should spawn one worker per allowed shard or parent packet, then merge
returns deterministically.

## Implementation Steps

1. Add `references/design-layer-v3-contracts.md` with the artifact contracts above.
2. Add `scripts/design_v3_lib.py` with layout helpers, validation, assembly, and compile functions.
3. Add `scripts/design_v3_validate.py` and `scripts/design_v3_compile.py`.
4. Update `scripts/run_pipeline.py` to accept `--design-layer v3` for `init` and `compile-design`.
5. Add V3 role cards and update `references/subagents/README.md`.
6. Update `README.md` and `SKILL.md` with the V3 workflow summary.
7. Add `tests/fixtures/v3_hierarchical_minimal/`.
8. Add `tests/fixtures/v3_contract_violation/`.
9. Add `tests/run_v3_regression.py`.
10. Run V3 regressions.

## Regression Tests

Minimum V3 regression coverage:

```text
v3_hierarchical_minimal validates
v3_hierarchical_minimal compiles
public branch_graph.json exists
public game_ir.json exists
compiled game_ir contains event_rules from parent_state_settlements
validate_artifacts.py passes on compiled public files
build --skip-assets passes with generated minimal realization fixtures
public files do not leak source coverage ids or V3 shard paths
invalid story parent/child references fail validation
child settlement writing missing parent state fails validation
child settlement writing non-parent state through effects_on_parent_state fails validation
parallel shard merge rejects duplicate ids with conflicting payloads
```

## Acceptance Criteria

The V3 implementation is complete when:

```bash
python3 tests/run_v3_regression.py
python3 scripts/run_pipeline.py compile-design \
  --run-root tests/fixtures/v3_hierarchical_minimal \
  --design-layer v3
python3 scripts/validate_artifacts.py \
  --run-root tests/fixtures/v3_hierarchical_minimal \
  --write-projections
```

all pass, and `workspace/design_layer/branch_graph.json` plus
`workspace/design_layer/game_ir.json` are the only required design inputs for
downstream realization.
