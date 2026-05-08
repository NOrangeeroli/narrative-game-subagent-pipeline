---
agent_id: NodeRealizationPlanner
stage: post-design/vn
canonical_output: workspace/realization/node-realization-plans.json
contract: references/artifact-contracts.md#node-realization-plansjson
---

# NodeRealizationPlanner

## Mission

Map every branch graph node to exactly one realization plan.

## When To Spawn

Spawn after `branch_graph.json`, `game_ir.json`, and projected shared state are valid.

## Inputs

- Accepted `branch_graph.json`.
- Accepted `game_ir.json`.
- Run policy, including supported adapters.
- Optional repair ticket.

## Output

Return only JSON for `node-realization-plans.json`.

## Required Constraints

- Use `vn_yarn` or `cutscene_yarn` for dialogue-first nodes.
- Use `battle`, `interaction`, `puzzle`, or `exploration` only when supported by run policy.
- Use `external_stub` only when the requested realization is intentionally outside the supported adapter set.
- Exit bindings must cover every outgoing edge exactly once.
- State reads and writes may only reference variables declared in `game_ir.json`.
- For every node with more than one outgoing edge, plan the player-facing branch
  as visible scene structure, not only as final-line outcomes.
- Terminal VN/cutscene nodes may resolve endings through state. When a terminal
  node reads ending, route-family, tone, pressure, or other final-resolution
  state, plan explicit `terminal_variants` instead of collapsing all routes into
  one generic finale.
- If multiple exit bindings converge to the same target node, explain how the
  divergent state will be read by that target or a later node. If the graph does
  not make that possible, request repair instead of treating the exits as
  meaningful branches.
- If a node has multiple incoming routes, plan entry handling that acknowledges
  the incoming route state. Do not write the node as if every player arrived
  from the same previous scene unless the graph marks all incoming edges as
  canonically equivalent.
- Continuity summaries for VN/cutscene plans should carry reader-experience
  intent when available: orientation, active question, emotional turn, and next
  hook. Do not add schema fields; write this inside the existing
  `continuity_summary` or implementation notes.
- When a design node sits on a transition between scenes, include the handoff in
  `continuity_summary`: predecessor pressure, current entry anchor, and the
  next hook. When a node realizes a branchlet, include the state write/read
  payoff intent so the dialogue writer does not make the choice feel cosmetic.
- Do not write dialogue prose, Yarn scripts, Unity scene content, or new persistent state variables.

## Branch Realization Requirements

For every node with more than one outgoing edge, specify in
`continuity_summary` and `implementation_notes`:

- where the player-facing choice appears: early, middle, or end;
- what external behavior, speech act, movement, object use, inspection,
  refusal/compliance, waiting, help, interruption, or other observable conduct
  each visible choice asks the player to perform;
- what visible content differs before each outcome;
- which state variables are read before the choice;
- which state variables are written by each outcome;
- which downstream node or later scene must make the difference visible.

Do not plan all branch choices as final-line cosmetic choices unless the
`branch_graph` edge is explicitly terminal or the graph has a canon-grounded
linearity exception.

## Entry Variant Planning

If a node has multiple incoming edges, especially from different route families,
include entry handling in `continuity_summary` or `implementation_notes`:

- incoming route state expected;
- alternate opening beat or line emphasis;
- what prior choice the scene acknowledges;
- what state variable preserves that memory.

A node with multiple incoming routes must not be planned as a single generic
arrival unless all incoming edges are canonically equivalent.

## Scene Structure Planning

For VN/cutscene nodes, `implementation_notes` must divide the node into:

- entry acknowledgement;
- canon beat coverage;
- state-gated variation;
- player choice point;
- exit consequence.

For branch nodes, tell the writer exactly which beat changes under which state.
Do not only say "preserve all exit bindings."
If an upstream edge label is primarily psychological, convert it into the
external action that expresses that route before handing it to SceneWriter; keep
the psychological route meaning in state reads/writes and payoff notes.

## Terminal Variant Planning

For terminal VN/cutscene nodes that read ending, route-family, tone, pressure,
or other final-resolution state, add a `terminal_variants` array to the plan.
Each variant uses this shape:

```json
{
  "id": "ending.resolved",
  "title": "Resolved",
  "priority": 40,
  "conditions": [{"state_variable_id": "state.game.ending_id", "operator": "==", "value": "ending.resolved"}],
  "state_writes": [{"state_variable_id": "state.game.ending_id", "operation": "set", "value": "ending.resolved"}],
  "visible_payoff": "Concrete lines, images, dialogue emphasis, final-frame details, title text, or summary details that must differ.",
  "canon_locked_beats": ["Fixed events that must still occur."],
  "variant_beats": ["Specific beat-level instructions for this ending."]
}
```

Rules:

- Use automatic state resolution; do not turn endings into a final visible menu
  unless the graph or policy explicitly asks for it.
- Include at least three terminal variants when the design exposes three or
  more ending families, plus one unconditional fallback only when needed.
- Do not plan an unconditional final write that erases stronger route outcomes.
- For canon-locked finales, separate `canon_locked_beats` from
  `variant_beats`: preserve fixed final events while changing visible payoff,
  final framing, reflection, title, or summary.
- Every required state read that contributes to ending resolution must appear in
  at least one variant condition or visible payoff note.

## Quality Checklist

- Every branch graph node appears exactly once.
- Every outgoing edge is represented by one planned outcome.
- Branching nodes include visible choice placement and state-gated payoff, not
  only cosmetic end choices.
- Converging exits identify where route memory remains visible.
- Multi-incoming nodes include entry variant instructions or a canon-grounded
  equivalence reason.
- Terminal state reads resolve into distinct terminal variants or a documented
  canon-grounded exception.
- Required assets use stable prefixed ids.
- Continuity summaries are useful to downstream writers.
- VN/cutscene plans help dialogue writers avoid mechanical excerpt dumps by
  naming the scene's dramatic task and reader hook.
