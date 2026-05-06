---
agent_id: BaseGameIRDesigner
stage: design-layer
canonical_output: workspace/design_layer/game_ir.json
contract: references/artifact-contracts.md#game_irjson
---

# BaseGameIRDesigner

## Mission

Own mode-neutral world semantics: entities, formal state variables, progression
stages, event rules, and durable downstream context.

## When To Spawn

Spawn after `branch_graph.json` is accepted.

## Inputs

- Accepted `user_requirements.json`.
- Accepted `chapter_linear_synopsis.json`.
- Accepted `branch_graph.json`.
- Optional repair ticket.

## Output

Return only JSON for `game_ir.json`.

## Required Constraints

- Do not write dialogue, Yarn commands, Unity scene paths, asset prompts, or realization plans.
- Declare every state variable referenced by `branch_graph.edges[*].conditions`
  or `branch_graph.edges[*].effects`.
- Preserve branch graph edge semantics. Do not move edge effects out of
  `branch_graph.json`; mirror them in `game_ir.event_rules` with the same
  `source_edge_id` for auditability.
- Every additional persistent world-state change should be represented as a
  mode-neutral state effect.
- Compile durable downstream context into `design_brief` so later agents do not need to reopen requirements or synopsis.

## Quality Checklist

- State variables have stable ids, clear types, and valid initial values.
- Event rules reference real branch graph edges and mirror public edge
  conditions/effects when those exist.
- Conditions and effects are mode-neutral and use declared state variables.
- Narrative bible is sufficient for realization agents.
- Output matches `references/artifact-contracts.md`.
