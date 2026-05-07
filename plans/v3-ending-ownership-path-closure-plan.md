# V3 Ending Ownership And Path Closure Plan

## Goal

Make V3 ending design explicit, reviewable, and mechanically enforceable.

The coarsest enabled `LevelStateGraphDesigner` must design the full set of
ending family nodes. Lower-level designers may expand those ending nodes into
finer terminal variants, but they must not invent new top-level ending
families. The V3 validator and compiler must guarantee that every runtime path
in the compiled public graph can eventually reach a terminal ending node.

The downstream public interface remains unchanged:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

V3 may add private ending metadata in `workspace/design_layer_v3/*`, and the
compiler may preserve selected ending metadata on public finest-level terminal
nodes, but post-design workers and exporters should not need to reopen private
V3 design artifacts.

## Design Principles

Ending design is part of top-level adaptation structure, not a late export
fallback. The highest design level owns the ending families because it is the
only level with global route-family context, canon-lock context, and final
state-settlement authority.

Lower levels own concrete realization pressure. They can expand a top-level
ending into route-specific, cost-specific, relationship-specific, or
payoff-specific variants, but those variants must remain descendants of a
declared coarsest ending family.

The compiler should not synthesize endings. If an ending family, terminal
descendant, or path-to-ending closure is missing, validation should fail and
route the repair to the responsible design level.

## Target Semantics

### Ending Family

An ending family is declared by a coarsest-level terminal graph node:

```json
{
  "id": "v3.l3.ending.truth_preserved",
  "title": "The Archive Remembers",
  "node_type": "terminal",
  "is_terminal": true,
  "ending_id": "ending.truth_preserved",
  "story_unit_ids": ["story.l3.final_arc"],
  "source_derivation": {
    "kind": "canon",
    "base_story_unit_ids": ["story.l3.final_arc"],
    "canon_function": "Resolve the global truth-preservation route family.",
    "invented_content_scope": "ending family only"
  }
}
```

Required meaning:

- `ending_id` identifies the top-level ending family.
- Coarsest ending nodes have no outgoing graph edges.
- Every coarsest ending node must have a unique `ending_id`.
- Every declared `ending_id` must eventually have at least one finest-level
  terminal descendant after lower-level expansion.

### Ending Variant

A lower-level terminal node may expand a declared ending family:

```json
{
  "id": "v3.l1.ending.truth_preserved.cost_paid",
  "title": "The Archive Remembers, At A Cost",
  "node_type": "terminal",
  "is_terminal": true,
  "parent_node_id": "v3.l2.ending.truth_preserved",
  "ending_id": "ending.truth_preserved",
  "ending_variant_id": "ending.truth_preserved.cost_paid",
  "variant_of_ending_id": "ending.truth_preserved",
  "story_unit_ids": ["story.l1.final_scene"],
  "source_derivation": {
    "kind": "consequence",
    "base_story_unit_ids": ["story.l1.final_scene"],
    "canon_function": "Show the same ending family after a high-cost route.",
    "required_prior_state": ["state.l2.archive_arc.result", "state.l1.key_found"],
    "divergence_from_source": "Local emotional and cost payoff differs by route memory.",
    "invented_content_scope": "ending variant payoff"
  }
}
```

Required meaning:

- `ending_id` points to a coarsest ending family.
- `ending_variant_id` identifies the concrete descendant version.
- `variant_of_ending_id`, when present, must equal `ending_id`.
- The node's `parent_node_id` chain must eventually reach the coarsest
  terminal node with the same `ending_id`.
- Lower-level designers may add variants, not new ending families.

### Ending Matrix

The coarsest design should also provide an ending matrix in either
`adaptation/global_policy.json`, coarsest `contracts.json`, or a clearly
defined optional field on coarsest terminal nodes. This matrix is primarily a
design/review artifact, not runtime schema.

Recommended shape:

```json
{
  "ending_id": "ending.truth_preserved",
  "result_summary": "The truth survives in the archive.",
  "route_family": "truth_route",
  "required_prior_state": ["state.l3.truth_route_committed"],
  "preserved_canon": ["fact.archive_truth_survives"],
  "cost_paid": ["The public relationship with the keeper is damaged."],
  "unresolved_pressure": ["The recovered truth changes who controls the city."],
  "emotional_resolution": "Clear victory with visible personal cost.",
  "fallback_priority": 80
}
```

The validator should not require every qualitative field in the first pass, but
the role cards and reviewer prompts should make these fields the expected
design standard.

## Ending Design Rules

Hard rules should be enforced by the validator where practical:

1. The coarsest enabled `story_graph.json` must contain at least one terminal
   ending node.
2. Every coarsest terminal node must declare a non-empty unique `ending_id`.
3. Coarsest terminal nodes must not have outgoing edges.
4. Lower-level terminal nodes that declare `ending_id` must reference an
   `ending_id` declared by the coarsest level.
5. Lower-level `ending_variant_id` values must be unique within a run.
6. A lower-level ending variant must be traceable through `parent_node_id` to a
   coarsest terminal node with the same `ending_id`.
7. Every coarsest `ending_id` must have at least one finest-level terminal
   descendant so the public runtime graph can actually end in that family.
8. Every public terminal node compiled from V3 must have `ending_id`.
9. Every node reachable from the public `branch_graph.start_node_id` must be
   able to reach at least one public terminal node.
10. A reachable public sink node must be terminal.

Soft rules should be enforced through prompts, review, and warnings:

1. Endings should be accumulated outcomes, not a final arbitrary menu.
2. Each ending should have a preserved value, a cost, and an unresolved
   consequence.
3. Two ending families should differ in real world/relationship/knowledge/result
   state, not only mood or prose tone.
4. Failure endings should pay off known risk or reveal new understanding, not
   merely punish the player.
5. True or hidden endings should have fair earlier clues and state evidence.
6. Ending titles should describe the result, not use player-facing labels such
   as `Good Ending`, `Bad Ending`, or `True Ending` unless the project brief
   explicitly wants that style.
7. Every major route-memory state should have at least one ending or ending
   variant payoff.

## Artifact Contract Changes

Update `references/design-layer-v3-contracts.md`.

Add an `Ending Ownership` section under Design Levels:

- Define `ending_id`, `ending_variant_id`, and `variant_of_ending_id`.
- State that the coarsest enabled level owns all ending families.
- State that lower levels may only expand declared ending families into
  variants.
- State that every ending family needs at least one finest-level terminal
  descendant.
- State that V3 compile fails if the public graph contains a reachable path
  that cannot reach an ending node.

Extend the `story_graph.json` node example:

```json
{
  "id": "v3.l2.ending.example",
  "node_type": "terminal",
  "is_terminal": true,
  "ending_id": "ending.example",
  "ending_variant_id": "ending.example.low_cost",
  "variant_of_ending_id": "ending.example"
}
```

Add an optional ending matrix example either in `global_policy.json` or
coarsest `contracts.json`. Prefer `global_policy.json` for broad route-family
meaning and contracts for local realization constraints.

Update `references/artifact-contracts.md` only if public `branch_graph.nodes`
will document optional V3 ending metadata:

```json
{
  "ending_id": "ending.truth_preserved",
  "ending_variant_id": "ending.truth_preserved.cost_paid",
  "ending_lineage": [
    "v3.l3.ending.truth_preserved",
    "v3.l2.ending.truth_preserved",
    "v3.l1.ending.truth_preserved.cost_paid"
  ]
}
```

These fields are optional for V1 and expected on V3 public terminal nodes.

## Role Card And Prompt Changes

Update `references/subagents/design-layer-v3/LevelStateGraphDesigner.md`.

Add a `Ending Ownership` section:

- Coarsest worker must design all ending family nodes before lower levels
  expand them.
- Coarsest worker should define `state.game.ending_id` or an equivalent
  ending-resolution state when the run has multiple endings.
- Lower-level workers may add terminal variants only under assigned parent
  ending nodes.
- Lower-level workers must not create new ending families. If needed, they
  should return a repair note requesting a coarsest-level ending-family update.
- Ending choices must be behavior/state consequences, not final menu labels.

Update `references/design-layer-v3-prompts.md`.

Coarsest `LevelStateGraphDesigner` packet template should require:

```text
- ending family catalog
- terminal coarsest ending nodes with unique ending_id values
- ending-resolution state and fallback ordering when multiple endings exist
- ending matrix showing route family, preserved canon, cost, unresolved pressure,
  and required prior state
```

Non-coarsest `LevelStateGraphDesigner` packet template should require:

```text
- parent ending context slice when assigned parent contains or leads to an ending
- no new ending family ids
- optional ending_variant_id expansion under a declared ending_id
- parent_state_settlements that write only immediate parent state
```

Update `DesignV3CompilerReviewer.md` or the reviewer prompt so it flags:

- missing ending matrix;
- ending variants with no visible route-memory payoff;
- endings decided by final arbitrary choice;
- ending families that differ only in tone;
- hidden endings with no fair clue trail.

## Validator Changes

Implement in `scripts/design_v3_lib.py`.

### Add Helpers

Add graph helpers near existing validation helpers:

```python
def graph_adjacency(edges: list[Json]) -> dict[str, list[str]]
def reachable_nodes(start_node_id: str, adjacency: dict[str, list[str]]) -> set[str]
def nodes_that_can_reach_terminals(nodes: dict[str, Json], adjacency: dict[str, list[str]]) -> set[str]
def terminal_node_ids(nodes: dict[str, Json]) -> set[str]
def parent_chain(node_id: str, graph_nodes_by_level: dict[int, dict[str, Json]], node_level: dict[str, int]) -> list[str]
```

Use these helpers for both private V3 graph validation and compiled public graph
validation.

### Validate Coarsest Ending Ownership

Inside `validate_design_v3`, after graph nodes/edges are loaded:

- identify `coarsest = max(levels)`;
- collect coarsest terminal nodes from `design_levels[coarsest].story_graph`;
- fail if none;
- fail if any coarsest terminal node lacks `ending_id`;
- fail on duplicate `ending_id`;
- fail if a coarsest terminal node has outgoing edges.

Suggested finding kinds:

```text
missing_coarsest_ending
missing_ending_id
duplicate_ending_id
terminal_has_outgoing_edge
```

### Validate Lower-Level Ending Variants

After all levels are loaded and `graph_nodes_by_level` exists:

- build `ending_ids_by_coarsest_node`;
- build `declared_ending_ids`;
- build `node_level` for every graph node id;
- for every lower-level terminal node with `ending_id`:
  - fail if `ending_id` is not declared by coarsest level;
  - fail if `variant_of_ending_id` exists and differs;
  - fail if `ending_variant_id` duplicates another variant id;
  - follow `parent_node_id` upward and ensure the chain reaches a coarsest
    terminal node with the same `ending_id`.

Suggested finding kinds:

```text
unknown_ending_id
ending_variant_mismatch
duplicate_ending_variant_id
ending_lineage_mismatch
```

### Validate Finest Descendants

For each coarsest `ending_id`, ensure at least one finest-level terminal node
descends from it and carries the same `ending_id`.

Suggested finding kind:

```text
ending_without_finest_terminal
```

This is important because only finest-level nodes are compiled into the public
runtime graph.

### Validate Path Closure Per Design Level

For each enabled private design level:

- from that level's `start_node_id`, compute reachable nodes;
- compute nodes that can reach a terminal node in the same level graph;
- fail every reachable non-terminal node that cannot reach terminal;
- fail every reachable sink node that is not terminal;
- fail or warn on reachable terminal-free cycles.

Initial implementation can fail only on unreachable-terminal nodes and
non-terminal sinks. Terminal-free cycle detection can be a follow-up warning
unless the runtime needs strict finite-play guarantees.

Suggested finding kinds:

```text
path_without_terminal
nonterminal_sink
terminal_free_cycle
```

### Validate Compiled Public Graph Closure

After `public_graph_from_v3` and before copying staged public artifacts:

- run the same closure check on staged `branch_graph.json`;
- require every public terminal node to have `ending_id` for V3;
- require every reachable node from `start_node_id` to reach a terminal;
- fail public validation if not.

This may live in `validate_compiled_public` or a V3-specific wrapper called by
`compile_design_v3`.

Suggested finding kinds:

```text
public_terminal_missing_ending_id
public_path_without_terminal
public_nonterminal_sink
```

## Compiler Changes

Update `public_graph_from_v3`.

When compiling finest-level public nodes:

1. Build a complete private node map across all levels.
2. For each finest-level node, walk its `parent_node_id` chain upward.
3. Find the nearest or coarsest ancestor with `ending_id`.
4. If the finest node is terminal or declares ending metadata, copy:

```json
{
  "ending_id": "...",
  "ending_variant_id": "...",
  "variant_of_ending_id": "...",
  "ending_lineage": ["coarsest", "middle", "finest"]
}
```

5. If a finest terminal descends from a coarsest ending node but lacks
   `ending_id`, inherit the coarsest `ending_id` and synthesize a stable
   `ending_variant_id` only if the lower node does not already provide one.

Do not synthesize missing terminal nodes or missing ending families. Metadata
inheritance is acceptable because it preserves already-designed lineage;
creating endings is not acceptable.

Update `compile_game_ir` only if ending-resolution state needs stronger public
audit:

- preserve `state.game.ending_id` in `global_state_variables` when authored;
- include settlement-generated `event_rules` that write ending state;
- optionally add a `game_ir.ending_catalog` compiled from coarsest ending
  matrix, stripped of private source refs.

The first implementation can keep `ending_catalog` out of public Game IR if the
public branch graph carries enough terminal metadata.

## Regression Tests

Extend `tests/run_v3_regression.py` and fixtures.

### Passing Fixture Update

Update `tests/fixtures/v3_hierarchical_minimal`:

- add one or more coarsest terminal nodes with `ending_id`;
- ensure finest-level graph has terminal descendants with matching `ending_id`;
- ensure every public path from start reaches a terminal.

Update assertions:

- compiled public terminal nodes have `ending_id`;
- every public reachable node can reach a terminal;
- ending lineage does not leak private file paths or shard metadata.

### Failure Cases

Add temporary-copy mutations in `tests/run_v3_regression.py`:

1. `v3_missing_coarsest_ending`
   - remove all coarsest terminal nodes;
   - expect `missing_coarsest_ending`.

2. `v3_coarsest_terminal_missing_ending_id`
   - remove `ending_id` from coarsest terminal;
   - expect `missing_ending_id`.

3. `v3_duplicate_ending_id`
   - assign the same `ending_id` to two coarsest terminal nodes;
   - expect `duplicate_ending_id`.

4. `v3_lower_invents_ending`
   - set a lower-level terminal to `ending_id` not declared by coarsest;
   - expect `unknown_ending_id`.

5. `v3_ending_lineage_mismatch`
   - lower terminal declares `ending_id=A` but parent chain reaches coarsest
     ending `B`;
   - expect `ending_lineage_mismatch`.

6. `v3_ending_without_finest_terminal`
   - coarsest ending exists but no finest descendant carries/reaches it;
   - expect `ending_without_finest_terminal`.

7. `v3_public_path_without_terminal`
   - remove terminal-reachable edge or terminal flag from public finest path;
   - expect `public_path_without_terminal` or `public_nonterminal_sink`.

8. `v3_public_terminal_missing_ending_id`
   - create a finest terminal not under declared ending lineage;
   - expect `public_terminal_missing_ending_id`.

### V1 Compatibility

Run existing V1 regression unchanged:

```bash
python3 tests/run_v1_regression.py
```

V1 should not require `ending_id` unless a future V1 contract explicitly adds
that requirement. The V3-specific public terminal ending check should be gated
by `game_ir.design_layer.version == "v3"` or by the V3 compile path.

## Execution Checklist

Implement in this order:

```text
1. Update V3 contracts with ending ownership, variants, and path closure.
2. Update LevelStateGraphDesigner role card with coarsest ending-family
   ownership and lower-level variant rules.
3. Update V3 prompt templates for coarsest ending catalog and non-coarsest
   variant expansion.
4. Add graph closure and ending-lineage helper functions to design_v3_lib.py.
5. Add coarsest ending ownership validation.
6. Add lower-level ending variant and lineage validation.
7. Add finest terminal descendant validation.
8. Add private per-level path-to-terminal closure validation.
9. Add public compiled graph path-to-terminal closure validation.
10. Preserve ending_id, ending_variant_id, variant_of_ending_id, and
    ending_lineage in public_graph_from_v3.
11. Update V3 fixtures to include valid ending families and finest descendants.
12. Add V3 failure-case regression mutations.
13. Run:
    - python3 tests/run_v1_regression.py
    - python3 tests/run_v3_regression.py
    - python3 -m py_compile scripts/*.py tests/*.py
14. Smoke-build at least one V3 run with --skip-assets to verify Web export
    still reads the compiled public graph only.
```

## Acceptance Criteria

- A V3 run fails validation if the coarsest level does not declare ending
  family terminal nodes.
- A lower-level designer cannot introduce a new top-level ending family.
- Every declared coarsest ending family has at least one finest-level terminal
  descendant.
- Every reachable node in the compiled public graph can reach a terminal.
- Every reachable public terminal node compiled from V3 has `ending_id`.
- Public terminal nodes preserve ending metadata without exposing private V3
  file paths, source refs, shard ids, or shard return details.
- Existing V1 regression remains green.
- Existing V3 regression is updated to prove both valid ending compilation and
  invalid ending failure modes.

## Non-Goals

- Do not make the compiler create missing ending nodes.
- Do not require V1 public branch graphs to use `ending_id`.
- Do not make post-design workers read private V3 artifacts by default.
- Do not enforce subjective ending quality entirely in Python validation.
- Do not solve runtime finite-loop proof for arbitrary state-gated cycles in
  the first pass. Start with static path-to-terminal reachability and
  non-terminal sink failures, then add stronger cycle proof if runtime design
  needs it.
