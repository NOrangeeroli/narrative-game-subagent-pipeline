# Design Layer V2 Contracts

V2 artifacts are internal authoring inputs. The compiler projects them into the
V1 public interface under `workspace/design_layer/`. Downstream production agents
must receive only `branch_graph.json`, `game_ir.json`, or deterministic context
slices derived from those files.

## Path Layout

```text
workspace/design_layer_v2/
  source_intake/
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
`expansion_depth`. All deeper layers are authored by repeated
`MeshLayerDesigner` passes over selected parents; there is no separate tertiary
graph-writer role and no separate storylet pool in V2.

V2 supports two input modes:

- `idea`: a short game idea. The controller still creates a synthetic source
  segment such as `idea.root`, but later agents may invent within the brief.
- `source_adaptation`: a full source, excerpt, or novel adaptation. The
  controller segments the source first, and graph/mesh authors must preserve
  segment coverage and cite assigned `source_segment_ids`. For novel-like
  sources, grounding comes from granular source segments and beat summaries.
  Chapters may remain as grouping metadata, but source segments should normally
  be scene/dialogue/action/reveal beats rather than whole chapters. V2 no
  longer creates auxiliary extraction tables for individual detail or dialogue
  rows.

`source_intake/*` and `source_segment_ids` are internal V2 trace data. They are
used for validation and repair routing, then stripped or folded away before
publishing `workspace/design_layer/branch_graph.json` and
`workspace/design_layer/game_ir.json`.

V2 adaptation also carries an internal reader-experience plan without adding
public fields. Macro summaries, macro contracts, subgraph node summaries, and
realization continuity notes should state, in ordinary prose where useful: what
the player knows now, what question or tension is active, what must stay
withheld, the emotional purpose of the beat, and the hook into the next beat.
This plan decides how each segment becomes a playable scene; it is not a
license to paste source segment summaries into player-facing text.

## `source_intake/input_profile.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "InputProfiler", "notes": []},
  "input_mode": "idea",
  "source_kind": "one_line_idea",
  "coverage_policy": "inventive"
}
```

Allowed `input_mode`: `idea`, `source_adaptation`.
Allowed `coverage_policy`: `inventive`, `faithful_adaptation`.

## `source_intake/source_segments.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceSegmenter", "notes": []},
  "segments": [
    {
      "id": "seg.001",
      "summary": "A source paragraph or chapter beat.",
      "source_span": {"source_id": "source", "start": 0, "end": 120},
      "events": ["event.opening"],
      "characters": ["char.hero"],
      "importance": "must_cover",
      "adaptation_freedom": "locked"
    }
  ]
}
```

Allowed `importance`: `must_cover`, `compressible`, `optional`.
Allowed `adaptation_freedom`: `locked`, `expandable`,
`reinterpret_allowed`.

## `source_intake/source_beat_table.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceSegmenter", "notes": []},
  "beats": [
    {"id": "beat.opening", "summary": "Opening beat.", "source_segment_ids": ["seg.001"]}
  ]
}
```

## `source_intake/adaptation_coverage_matrix.json`

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "SourceSegmenter", "notes": []},
  "coverage": [
    {
      "id": "coverage.seg_001",
      "segment_id": "seg.001",
      "coverage_status": "covered",
      "covered_by": {
        "macro_node_ids": ["macro.opening"],
        "contract_ids": ["contract.opening"],
        "subgraph_ids": ["subgraph.macro.opening"],
        "subgraph_node_ids": ["node.opening.entry"]
      },
      "reason": "The segment is playable as the opening scene."
    }
  ]
}
```

Allowed `coverage_status`: `covered`, `compressed`, `omitted`, `deferred`.
In `source_adaptation` mode every source segment needs a coverage row. A
`must_cover` segment must be `covered`; omitted segments need a reason.

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
      "source_segment_ids": ["seg.001"],
      "confidence": "canonical",
      "tags": [],
      "locked": true
    }
  ]
}
```

Facts are stable canon units. Branching artifacts reference fact ids instead of
restating canon freely.

In `source_adaptation` mode locked or fixed facts must be anchored to source
segments via `source_segment_ids` or a `source_span.source_id` matching a
segment id.

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
      "allowed_fact_ids": ["fact.central_loss"],
      "source_segment_ids": ["seg.002"]
    }
  ],
  "variable_endings": [
    {
      "id": "ending.acceptance",
      "title": "Acceptance",
      "allowed_state_requirements": ["state.acceptance >= 1"],
      "must_preserve_theme_ids": ["theme.incomplete_truth"],
      "source_segment_ids": ["seg.003"]
    }
  ],
  "forbidden_changes": [
    {"id": "forbid.erase_loss", "description": "Do not undo the central loss."}
  ]
}
```

In `source_adaptation` mode variable processes need `source_segment_ids` and
must cite at least one segment whose `adaptation_freedom` is `expandable` or
`reinterpret_allowed`. Variable endings should cite the source segment or
source tension they reinterpret.

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
      "status": "enabled",
      "source_segment_ids": ["seg.003"]
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

Enabled endings need `source_segment_ids` in `source_adaptation` mode.

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
      "source_segment_ids": ["seg.001"],
      "entry_conditions": [],
      "allowed_exits": ["exit.continue"],
      "optional": false,
      "skippable": false,
      "failure_allowed": false,
      "is_terminal": false
    }
  ],
  "edges": [
    {"id": "edge.opening_continue", "from": "macro.opening", "to": "macro.choice", "label": "Continue", "exit_id": "exit.continue", "condition_type": "unconditional", "source_segment_ids": ["seg.001"]}
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
      "source_fact_ids": ["fact.central_loss"],
      "source_segment_ids": ["seg.001"]
    }
  ]
}
```

In `source_adaptation` mode every macro node and macro contract needs
`source_segment_ids`. Contract segment ids must carry the source coverage
assigned by the corresponding macro node. These fields are internal V2 trace
data and are removed from public `game_ir.node_contracts`.

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
  "source_segment_ids": ["seg.001"],
  "nodes": [
    {
      "id": "node.opening.entry",
      "node_type": "scene",
      "title": "Opening",
      "summary": "A local scene.",
      "source_segment_ids": ["seg.001"],
      "is_terminal": false,
      "expandable": true,
      "target_child_depth": 2
    },
    {
      "id": "node.opening.exit",
      "node_type": "convergence",
      "title": "Continue",
      "summary": "Exit point.",
      "source_segment_ids": ["seg.001"],
      "is_terminal": false
    }
  ],
  "edges": [
    {"id": "edge.opening.local_continue", "from": "node.opening.entry", "to": "node.opening.exit", "label": "Continue", "condition_type": "unconditional", "source_segment_ids": ["seg.001"]}
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

In `source_adaptation` mode every subgraph and every subgraph node needs
`source_segment_ids`. Player-visible choice edges also need `source_segment_ids`.
Subgraph and local node segment ids must stay inside the parent packet assigned
by the root macro contract or parent subgraph node.

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

## `validation/source_coverage_report.json`

The validator writes this derived report after source-intake checks. It records
the effective coverage status, actual macro/contract/subgraph anchors, and
declared coverage matrix refs for each segment. It is internal evidence only;
downstream realization agents should still receive public design artifacts or
controller-made slices.

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

The compiler must not leak `source_intake/*` paths, `source_segment_ids`,
detail/dialogue coverage rows, or coverage matrix data into these public files.
