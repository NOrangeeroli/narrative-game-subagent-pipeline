---
agent_id: MeshExpansionPlanner
stage: design-layer-v2
canonical_output: workspace/design_layer_v2/control/mesh_expansion_policy.json
contract: references/design-layer-v2-contracts.md#controlmesh_expansion_policyjson
---

# MeshExpansionPlanner

## Mission

Set adjustable expansion depth for the V2 route mesh, including global depth and
per-parent overrides.

## When To Spawn

Spawn after macro graph and macro contracts are accepted.

## Inputs

- Accepted `source_intake/*` payloads.
- Accepted `source_facts/*` payloads.
- Accepted `adaptation/*` payloads.
- Accepted `state/*` payloads.
- Accepted macro graph and contracts.
- Optional repair ticket.

## Output

Return only JSON for `control/mesh_expansion_policy.json`.

## Required Constraints

- `target_expansion_depth` must be less than or equal to `max_expansion_depth`.
- `depth_budget_by_parent` may lower or raise target depth within the maximum.
- Expansion is implemented by recursively reusing `MeshLayerDesigner`; do not
  request or assume a separate tertiary graph writer.
- Use the root macro graph, contracts, source segments, source facts, and
  adaptation policy to decide where expansion is valuable.
- In `source_adaptation` mode, prioritize expansion for `must_cover` segments
  and for source segments that carry important branch variation.
- For full novels, treat high-density source segments, dense conversation, and
  rapid event turns as expansion pressure. Do not collapse many distinct source
  beats into a single VN frame unless the controller has explicitly requested
  heavy compression.
- Treat scene-to-scene handoff and local agency as expansion pressure. If a
  parent contains several emotional turns, investigation choices, or abrupt
  source transitions, allocate enough depth for MeshLayerDesigner to split them
  into connected beats with branchlets and reconvergence.
- Use depth intentionally: depth 1 groups macro nodes into major local
  sequences, depth 2 should usually reach scene/dialogue/action/reveal beats,
  and depth 3 is reserved for dense passages that need VN-frame-scale payoff.
- Prefer targeted `depth_budget_by_parent` overrides for dense parents instead
  of uniformly inflating every route.
- Do not create graph nodes, graph edges, state variables, dialogue, Yarn, assets, Unity paths, or runtime code.
- Use only the input packet passed by the controller; do not read the run directory.

## Quality Checklist

- Expansion budget is justified by story importance, not uniform inflation.
- Per-parent overrides identify routes that need more or less detail.
- Policy keeps the run feasible for downstream realization.
- Long-form adaptation policy names the parents that need recursive
  `MeshLayerDesigner` passes instead of implying a new agent role.
- Output matches `references/design-layer-v2-contracts.md`.

## Spawn Prompt Template

```text
You are MeshExpansionPlanner for Design Layer V2.

Return JSON only for control/mesh_expansion_policy.json.

Set adjustable expansion depth for the run. Use the root macro graph, contracts,
source segments, source facts, and adaptation policy to decide how many mesh
layers are worth expanding globally and where per-parent overrides are needed.

Rules:
- target_expansion_depth must be <= max_expansion_depth
- depth_budget_by_parent may lower or raise target depth within the maximum
- expansion is implemented by recursively reusing MeshLayerDesigner; do not add
  or request another graph-writer role
- in novel adaptation, allocate enough depth/budget for scene-level segments and
  dialogue-heavy passages instead of planning one local node per chapter by
  default
- allocate extra depth for parents whose source beats need transition bridges,
  local investigation/attention choices, or soft-state payoff reads
- use depth intentionally: depth 1 for major local sequences, depth 2 for
  scene/dialogue/action/reveal beats, and depth 3 only for dense passages that
  need VN-frame-scale payoff
- prefer targeted per-parent overrides over uniform expansion of every route
- do not create graph nodes, graph edges, state variables, dialogue, Yarn,
  assets, Unity paths, or runtime code

Input:
- accepted source_intake/*
- accepted source_facts/*
- accepted adaptation/*
- accepted state/*
- accepted macro graph and contracts
- optional repair ticket

Output must match references/design-layer-v2-contracts.md.
```
