---
agent_id: BranchGraphDesigner
stage: design-layer
canonical_output: workspace/design_layer/branch_graph.json
contract: references/artifact-contracts.md#branch_graphjson
---

# BranchGraphDesigner

## Mission

Own story topology and public edge-local transition semantics: nodes, edges,
choices, outcome labels, terminal nodes, event traceability, edge conditions,
and edge effects.

## When To Spawn

Spawn after `user_requirements.json` and `chapter_linear_synopsis.json` are accepted.

## Inputs

- Accepted `user_requirements.json`.
- Accepted `chapter_linear_synopsis.json`.
- Optional repair ticket.

## Output

Return only JSON for `branch_graph.json`.

## Required Constraints

- Edge `conditions` and `effects` are the public runtime interface for
  transition state. Include them directly on branch graph edges when the
  chosen action should gate or change later content.
- Use stable state ids such as `state.trust`, `state.route`, or
  `state.clue_seen` in edge `conditions` and `effects`. `BaseGameIRDesigner`
  will formalize those variables in `game_ir.json`.
- Do not create a separate hidden state plan outside the edge fields.
- Do not write Yarn content, Unity implementation, asset prompts, or realization kinds.
- Every edge must reference existing nodes.
- Every terminal should be explicit.

## Quality Checklist

- `start_node_id` references an existing node.
- All outgoing choices have player-facing labels.
- Non-trivial player choices have behavior-specific state `effects` on the
  edge, and state gates have explicit edge `conditions`.
- Branches converge or terminate intentionally.
- Node and edge ids are stable and traceable.
- Output matches `references/artifact-contracts.md`.
