# Design Layer V2 Contracts

V2 artifacts are internal authoring inputs. The compiler projects them into the
V1 public interface under `workspace/design_layer/`. Downstream production agents
must receive only `branch_graph.json`, `game_ir.json`, or deterministic context
slices derived from those files.

## Path Layout

```text
workspace/design_layer_v2/
  source_facts/
  adaptation/
  state/
  macro/
  subgraphs/
  control/
  validation/
  compiled/
```

V2 uses adjustable multi-level mesh expansion. The root layer is
`macro/macro_story_graph.json`; every deeper layer is a subgraph with an
`expansion_depth`. There is no separate storylet pool in V2.

## `source_facts/fact_book.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "facts": [
    {
      "id": "fact.central_loss",
      "kind": "event",
      "summary": "A locked canon fact.",
      "source_span": {"source_id": "prompt", "start": 0, "end": 0},
      "confidence": "canonical",
      "tags": [],
      "locked": true
    }
  ]
}
```

Facts are stable canon units. Branching artifacts reference fact ids instead of
restating canon freely.

## `source_facts/character_graph.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "characters": [
    {"id": "char.hero", "name": "Hero", "summary": "Playable viewpoint character.", "fact_ids": []}
  ],
  "relationships": [
    {"id": "rel.hero_friend", "from": "char.hero", "to": "char.friend", "summary": "Shared history."}
  ]
}
```

## `source_facts/event_timeline.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "events": [
    {"id": "event.opening", "order": 1, "summary": "The story begins.", "fact_ids": ["fact.central_loss"]}
  ]
}
```

## `source_facts/world_rules.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "rules": [
    {"id": "rule.no_resurrection", "summary": "The central loss cannot be undone.", "locked": true}
  ]
}
```

## `source_facts/foreshadowing_table.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "foreshadowing": [
    {"id": "foreshadow.letter", "setup_fact_ids": [], "payoff_fact_ids": ["fact.central_loss"]}
  ]
}
```

## `source_facts/theme_constraints.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceFactExtractor", "notes": []},
  "tone": "quiet mystery",
  "themes": [{"id": "theme.incomplete_truth", "summary": "Truth may remain partial."}],
  "motifs": ["letters"],
  "prohibited_content": []
}
```

## `adaptation/adaptation_policy.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdaptationPolicyDesigner", "notes": []},
  "fixed_fact_ids": ["fact.central_loss"],
  "variable_processes": [
    {
      "id": "process.investigation_order",
      "description": "The player may inspect clues in different order.",
      "allowed_fact_ids": ["fact.central_loss"]
    }
  ],
  "variable_endings": [
    {
      "id": "ending.acceptance",
      "title": "Acceptance",
      "allowed_state_requirements": ["state.acceptance >= 1"],
      "must_preserve_theme_ids": ["theme.incomplete_truth"]
    }
  ],
  "forbidden_changes": [
    {"id": "forbid.erase_loss", "description": "Do not undo the central loss."}
  ]
}
```

## `adaptation/canon_lock_table.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdaptationPolicyDesigner", "notes": []},
  "locked_fact_ids": ["fact.central_loss"],
  "locks": [
    {"id": "lock.central_loss", "fact_id": "fact.central_loss", "reason": "Theme anchor."}
  ]
}
```

## `adaptation/variable_process_table.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdaptationPolicyDesigner", "notes": []},
  "processes": [
    {"id": "process.investigation_order", "description": "Route order can vary.", "state_variable_ids": []}
  ]
}
```

## `adaptation/ending_space.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdaptationPolicyDesigner", "notes": []},
  "endings": [
    {
      "id": "ending.acceptance",
      "title": "Acceptance",
      "state_requirements": ["state.acceptance >= 1"],
      "theme_ids": ["theme.incomplete_truth"],
      "status": "enabled"
    }
  ]
}
```

Use `status: "unavailable"` when an ending is intentionally designed but not
reachable in the current build.

`ending_space.json` is an ending candidate library, not a player-facing ending
menu. Enabled endings must later be resolved through authored state payoffs:
use `state_gate` routes for automatic ending resolution, or conditioned
`player_choice` routes only when the design explicitly wants the player to pick
among a small number of already-unlocked interpretations.

## `state/world_state_model.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "StateModelDesigner", "notes": []},
  "variables": [
    {
      "id": "state.acceptance",
      "scope": "global",
      "type": "integer",
      "initial_value": 0,
      "allowed_values": [],
      "readable_by": ["macro.*", "subgraph.*", "node.*"],
      "writable_by": ["subgraph.*", "node.*"],
      "affects": ["ending.acceptance"],
      "invariants": ["state.acceptance >= 0"],
      "description": "How much the player accepts incomplete truth."
    }
  ]
}
```

Allowed `type`: `boolean`, `integer`, `number`, `string`, `enum`.

## `state/state_permissions.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "StateModelDesigner", "notes": []},
  "permissions": [
    {
      "state_variable_id": "state.acceptance",
      "readable_by": ["macro.*", "subgraph.*", "node.*"],
      "writable_by": ["subgraph.*", "node.*"]
    }
  ]
}
```

Permissions may repeat the permissions embedded on variables. The validator uses
the explicit permissions file first, then falls back to variable fields.

## `state/state_invariants.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "StateModelDesigner", "notes": []},
  "invariants": [
    {"id": "invariant.acceptance_nonnegative", "expression": "state.acceptance >= 0", "state_variable_ids": ["state.acceptance"]}
  ]
}
```

## `macro/macro_story_graph.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "MacroGraphDesigner", "notes": []},
  "title": "Story Title",
  "summary": "High-level story mesh.",
  "start_macro_node_id": "macro.opening",
  "nodes": [
    {
      "id": "macro.opening",
      "kind": "mainline",
      "title": "Opening",
      "summary": "The player enters the situation.",
      "entry_conditions": [],
      "allowed_exits": ["exit.continue"],
      "optional": false,
      "skippable": false,
      "failure_allowed": false,
      "is_terminal": false
    }
  ],
  "edges": [
    {"id": "edge.opening_continue", "from": "macro.opening", "to": "macro.choice", "label": "Continue", "exit_id": "exit.continue", "condition_type": "unconditional"}
  ]
}
```

## `macro/macro_node_contracts.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "MacroContractWriter", "notes": []},
  "contracts": [
    {
      "id": "contract.opening",
      "macro_node_id": "macro.opening",
      "narrative_function": "Introduce the mystery.",
      "entry_conditions": [],
      "must_accomplish": ["Show the core loss."],
      "allowed_characters": ["char.hero"],
      "allowed_locations": ["loc.station"],
      "allowed_state_reads": ["state.acceptance"],
      "allowed_state_writes": ["state.acceptance"],
      "forbidden_events": [],
      "exits": [
        {
          "id": "exit.continue",
          "label": "Continue",
          "effects": [{"state_variable_id": "state.acceptance", "operation": "increment", "value": 1}]
        }
      ],
      "dependencies": [],
      "source_fact_ids": ["fact.central_loss"]
    }
  ]
}
```

## `subgraphs/subgraph.<parent_ref_id>.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "MeshLayerDesigner", "notes": []},
  "id": "subgraph.opening",
  "expansion_depth": 1,
  "root_macro_node_id": "macro.opening",
  "parent_macro_node_id": "macro.opening",
  "parent_ref_id": "macro.opening",
  "parent_ref_kind": "macro_node",
  "entry_node_id": "node.opening.entry",
  "nodes": [
    {
      "id": "node.opening.entry",
      "node_type": "scene",
      "title": "Opening",
      "summary": "A local scene.",
      "is_terminal": false,
      "expandable": true,
      "target_child_depth": 2
    },
    {
      "id": "node.opening.exit",
      "node_type": "convergence",
      "title": "Continue",
      "summary": "Exit point.",
      "is_terminal": false
    }
  ],
  "edges": [
    {"id": "edge.opening.local_continue", "from": "node.opening.entry", "to": "node.opening.exit", "label": "Continue", "condition_type": "unconditional"}
  ],
  "exit_mappings": [
    {"local_exit_id": "node.opening.exit", "macro_exit_id": "exit.continue"}
  ]
}
```

`expansion_depth` starts at `1` for subgraphs under macro nodes. Deeper
subgraphs set `parent_ref_kind: "subgraph_node"` and point `parent_ref_id` to an
expandable node from a lower depth. Every exported local exit maps to one root
macro contract exit.

Subgraph edges use existing `condition_type` values as runtime presentation
semantics. This does not add fields to the public compiled graph:

- `player_choice`: a player-visible button. Use for concrete decisions, not
  repeated score templates.
- `unconditional`: an ordinary continuation or automatic route stitch.
- `state_gate`: an automatic conditional route that reads `conditions`.

Prefer one `unconditional` continuation for linear delivery beats. Use
`player_choice` only at authored decision points, and use later `state_gate` or
conditioned `player_choice` edges to pay off earlier state writes. A repeated
set of identical visible choices across many nodes is considered a pacing
warning.

Ending resolver hubs should default to `condition_type: "state_gate"` plus
`conditions`, with one unconditional fallback when no gated ending applies.
Do not translate every enabled ending into a visible button. Ending hubs that
intentionally present unlocked endings may use conditioned `player_choice`
edges, but they must keep visible ending pressure small and explain why player
selection is part of the authored payoff.

## `control/mesh_expansion_policy.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "MeshExpansionPlanner", "notes": []},
  "max_expansion_depth": 3,
  "target_expansion_depth": 2,
  "default_branching_budget": {
    "max_nodes_per_subgraph": 6,
    "max_edges_per_subgraph": 8
  },
  "depth_budget_by_parent": [
    {"parent_ref_id": "macro.opening", "target_expansion_depth": 1},
    {"parent_ref_id": "node.opening.entry", "target_expansion_depth": 2}
  ],
  "choice_classes": [
    {"id": "choice_class.method", "description": "Method choices converge after recording state differences."}
  ],
  "notes": []
}
```

## `control/route_merge_policy.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "MacroGraphDesigner", "notes": []},
  "merge_points": [
    {"id": "merge.after_opening", "node_id": "macro.choice", "preserved_state_variable_ids": ["state.acceptance"]}
  ]
}
```

`node_id` may reference a macro node, an enabled mesh node, or a mapped subgraph
exit. Merge policies must not point at disabled depths unless those depths are
explicitly enabled by `mesh_expansion_policy.json`.

## `validation/simulation_profiles.json`

The validator writes deterministic simulation profiles after blocking
structural checks pass:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV2Validator"},
  "profiles": [
    {
      "id": "profile.current_policy",
      "target_expansion_depth": 2,
      "parent_depth_overrides": {"node.opening.entry": 3},
      "enabled_subgraph_ids": ["subgraph.macro.opening"],
      "enabled_mesh_depths": [1, 2],
      "node_count": 8,
      "edge_count": 9,
      "reachable_node_ids": ["node.opening.entry"],
      "unreachable_node_ids": [],
      "terminal_node_ids": ["node.ending.good"],
      "reachable_terminal_node_ids": ["node.ending.good"],
      "dead_end_node_ids": [],
      "max_choice_count": 3
    }
  ]
}
```

The required profile ids are `profile.current_policy` and
`profile.max_depth`. Simulation warnings are reported in
`validation/validation_report.json`; the profile file is evidence for those
warnings and for regression tests.

## Compiled Public Files

The compiler writes staging files first:

```text
workspace/design_layer_v2/compiled/user_requirements.json
workspace/design_layer_v2/compiled/chapter_linear_synopsis.json
workspace/design_layer_v2/compiled/branch_graph.json
workspace/design_layer_v2/compiled/game_ir.json
```

After V2 and V1 validation pass, the same files are copied to:

```text
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```
