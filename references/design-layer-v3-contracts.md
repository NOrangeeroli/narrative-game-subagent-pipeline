# Design Layer V3 Contracts

V3 is a hierarchical design layer. It compiles into the same public files used
by downstream production:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

V3 internal artifacts live under:

```text
workspace/design_layer_v3/
```

Downstream realization, gameplay, asset, and export agents should not read raw
V3 artifacts by default.

## Direction

V3 uses two opposite flows:

```text
story extraction:   fine -> coarse
graph/state design: coarse -> fine
```

Story extraction levels support controller sharding by default. Graph/state
design proceeds coarse-to-fine, but the coarsest enabled graph/state level must
be designed by exactly one clean-context `LevelStateGraphDesigner` worker. That
top-level worker owns the global graph, global state model, route-family
settlement, cross-act consistency, and ending-resolution state. Non-coarsest
graph/state levels may then be sharded by immediate parent packet. Workers
return partial payloads only; the controller merges shard returns
deterministically before the next level begins.

Design must preserve source anchoring at every enabled level, but graph/state
design is allowed to expand one source story unit into multiple state-dependent
graph nodes. For each `story_levels/level_<NN>/linear_story.json` unit, the
same-level `design_levels/level_<NN>/story_graph.json` must contain at least one
node that references that unit in `story_unit_ids`. A design level must not
invent graph nodes that have no same-level source anchor, but it may create
canon, variant, failure, delayed, revisit, consequence, or bridge nodes derived
from an existing story unit.

This rule applies at every abstraction level. A level 3 story unit can expand
into alternate act-level event spaces; a level 2 story unit can expand into
alternate arc-level event spaces; a level 1 story unit can expand into concrete
scene or short episode variants. Branching should be expressed through these
source-anchored graph nodes, edges, state, contracts, and parent settlements.
Invented material must be causally derived from source anchors and adaptation
state, not an unrelated plot addition.

## `hierarchy_policy.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "V3Controller"},
  "enabled_levels": [
    {"level": 1, "id": "level_01", "granularity": "chapter", "required": true},
    {"level": 2, "id": "level_02", "granularity": "arc", "required": true}
  ],
  "finest_level": 1,
  "coarsest_level": 2,
  "parallelism": {
    "story_extraction": "enabled_by_default",
    "fact_capture": "inside_story_extraction",
    "design_levels": "enabled_by_default"
  }
}
```

Enabled levels must form a continuous range. `level_01` is the finest level;
larger numbers are coarser.

## Story Levels

Path:

```text
story_levels/level_<NN>/linear_story.json
```

Shape:

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
      "summary": "What happens at this abstraction level.",
      "sequence_index": 1,
      "source_refs": [],
      "child_unit_ids": [],
      "parent_unit_id": "story.l2.arc01",
      "key_events": [],
      "protagonist_action_beats": [
        {
          "id": "action.l1.ch01.follow_signal",
          "actor": "Protagonist",
          "action": "The protagonist takes a concrete source-grounded action.",
          "action_type": "movement",
          "target": "",
          "immediate_effect": "",
          "state_or_access_effect": "",
          "social_effect": "",
          "unresolved_impact": "",
          "source_refs": []
        }
      ],
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

For higher levels, `child_unit_ids` must reference units from the immediate
lower level. For non-coarsest levels, `parent_unit_id` must reference a unit in
the immediate higher level.

`protagonist_action_beats` records source-grounded protagonist behavior and its
impact. Use it to distinguish what the protagonist actively does from external
events in `key_events`. Fine-level action beats should preserve concrete source
actions. Higher-level action beats should summarize and condense child-level
behavior into action patterns and trajectory changes, not concatenate child
action lists.

## Facts

Facts are captured as part of story extraction. Finest-level story extraction
captures local facts from assigned source/story units; higher-level story
aggregation also aggregates fact views upward. The controller persists the
accepted fact payloads into the existing `facts/*` files so validation and
compilation keep a stable interface.

Canonical path:

```text
facts/canonical_fact_graph.json
```

The canonical fact graph should include stable facts, characters, locations,
objects, events, relationships, world rules, themes, and evidence anchors.
Evidence anchors are internal and must not leak into public player-facing text.

## Adaptation

Paths:

```text
adaptation/global_policy.json
```

`global_policy.json` is designed from the coarsest story perspective plus the
canonical fact graph. It defines broad route families, tone/style, canon locks,
and adaptation permissions. The controller may excerpt relevant policy portions
when dispatching `LevelStateGraphDesigner`, but there is no separate policy
slice artifact or policy assembler role.

## Design Levels

Each enabled level writes four files:

```text
design_levels/level_<NN>/state_model.json
design_levels/level_<NN>/story_graph.json
design_levels/level_<NN>/contracts.json
design_levels/level_<NN>/parent_state_settlements.json
```

### `state_model.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "variables": [
    {
      "id": "state.l2.truth_pressure",
      "scope": "level",
      "type": "integer",
      "initial_value": 0,
      "allowed_values": [],
      "description": "Arc-level truth pressure.",
      "owner_story_unit_id": "story.l2.arc01",
      "readable_by": ["level_02.*", "level_01.*"],
      "writable_by": ["level_02.*", "level_01.*"]
    }
  ]
}
```

Allowed `type`: `boolean`, `integer`, `number`, `string`, `enum`.

### `story_graph.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "start_node_id": "v3.l2.arc01",
  "nodes": [
    {
      "id": "v3.l2.arc01",
      "title": "Arc 01",
      "summary": "The arc begins.",
      "node_type": "scene",
      "story_unit_ids": ["story.l2.arc01"],
      "parent_node_id": "v3.l3.act01",
      "is_terminal": false,
      "source_derivation": {
        "kind": "canon",
        "base_story_unit_ids": ["story.l2.arc01"],
        "canon_function": "What source function this node preserves.",
        "required_prior_state": [],
        "divergence_from_source": "",
        "invented_content_scope": "none"
      }
    }
  ],
  "edges": [
    {
      "id": "edge.v3.l2.arc01.continue",
      "from": "v3.l2.arc01",
      "to": "v3.l2.arc01.resolve",
      "label": "Continue",
      "condition_type": "unconditional",
      "conditions": [],
      "effects": []
    }
  ]
}
```

Non-coarsest graph nodes must reference an immediate parent-level graph node via
`parent_node_id`.

At each level, every graph node must reference at least one same-level
`linear_story.units[*].id` in `story_unit_ids`, and every same-level story unit
id must appear in at least one graph node. Multiple graph nodes may reference
the same story unit when they are state-conditioned variants or consequences of
that source anchor. A graph node may reference more than one same-level story
unit only when it is a deliberate bridge or convergence node whose contract
preserves the source function of every referenced anchor.

`source_derivation` is optional for backward compatibility, but should be
present for newly generated V3 designs. Its `kind` should describe the node's
relationship to the source anchor, such as `canon`, `variant`, `failure`,
`delayed`, `revisit`, `consequence`, or `bridge`. `required_prior_state` should
name the state conditions that make the node causally valid. `divergence_from_source`
and `invented_content_scope` should explain what changed and why it remains
canon-compatible at this abstraction level.

For `story_graph.edges[*]`, `condition_type: "player_choice"` means a
player-visible choice of external behavior. The edge `label` should describe an
observable action, speech act, movement, object use, refusal/compliance,
inspection, waiting, help, interruption, bargain, accusation, experiment, or
other conduct that can be realized by downstream scene writing. It should not
primarily name an internal mood, belief, interpretation, preference, or abstract
stance. Psychological or interpretive consequences belong in edge `effects`,
state variables, contracts, node summaries, and later visible payoff.

### `contracts.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 2,
  "contracts": [
    {
      "id": "contract.l2.arc01",
      "graph_node_id": "v3.l2.arc01",
      "story_unit_ids": ["story.l2.arc01"],
      "allowed_characters": [],
      "allowed_locations": [],
      "allowed_state_reads": ["state.l3.truth_pressure"],
      "allowed_state_writes": ["state.l2.arc01.local_flag"],
      "required_functions": [],
      "forbidden_events": [],
      "allowed_child_story_unit_ids": []
    }
  ]
}
```

### `parent_state_settlements.json`

Every non-coarsest level must declare how this level settles into the immediate
parent level state.

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LevelStateGraphDesigner"},
  "level": 1,
  "parent_level": 2,
  "settlements": [
    {
      "id": "settlement.l1.ch02.to.l2.arc01",
      "source_graph_node_id": "v3.l1.ch02.resolve",
      "parent_graph_node_id": "v3.l2.arc01",
      "trigger": "on_node_complete",
      "conditions": [
        {"state_variable_id": "state.l1.key_found", "operator": "==", "value": true}
      ],
      "effects_on_parent_state": [
        {"state_variable_id": "state.l2.truth_pressure", "operation": "increment", "value": 1}
      ],
      "evidence": {"story_unit_ids": ["story.l1.ch02"], "fact_ids": ["fact.ledger_opens"]},
      "reason": "Opening the ledger changes the parent arc pressure."
    }
  ]
}
```

For the coarsest level, `parent_level` must be `null` and `settlements` should
be empty.

Validation fails if `effects_on_parent_state` writes a state variable that is
not owned by the immediate parent level.

## Compilation

Use:

```bash
python3 scripts/run_pipeline.py compile-design --run-root <run> --design-layer v3
```

The compiler validates V3 artifacts, assembles staged public outputs under
`workspace/design_layer_v3/assembled/`, validates the public files, then copies
them to `workspace/design_layer/`.

Runtime-facing graph export has one hard boundary: public
`workspace/design_layer/branch_graph.json` nodes and edges are exported from
the finest enabled design level only, normally `level_01`. Coarser
`level_02+` `story_graph` files are design artifacts for parent context,
state/result settlement, trace, and validation. They must not directly add
public branch nodes, public branch edges, runtime-visible choice labels, or
SceneWriter targets. Coarser state variables, contracts, and
`parent_state_settlements` may still be compiled into `game_ir.json` when they
settle onto finest-level public nodes.
