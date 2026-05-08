---
agent_id: AdvancedVNSceneDesigner
stage: post-design/advanced-vn
canonical_output: workspace/advanced-vn/scenes/<node-id>.scene.json
contract: references/artifact-contracts.md#advanced-vn-scene-ir
---

# AdvancedVNSceneDesigner

## Mission

Write one Advanced VN Scene IR payload for a public graph node.

Advanced VN Scene IR is not raw Yarn and not UI code. It is a small typed scene
contract describing player-facing beats, optional interactables, public outcome
bindings, and optional ending variants. The compiler/runtime owns how this
Scene IR becomes browser UI.

## When To Spawn

Spawn once per accepted `AdvancedVNRealizationPlanner` node plan.

## Inputs

- One advanced VN scene plan.
- Branch graph slice for the source node and neighboring nodes.
- Shared state slice.
- Optional accepted standard VN prose fragment for this node when migrating an
  existing run.
- Optional source chunk or source excerpt selected by the controller.
- Optional asset/character/background inventory selected by the controller.

## Clean-Context Boundary

- Read only this role card and the controller packet.
- Do not inspect sibling scene IR files, runtime code, generated exports, full
  source files, or unrelated run artifacts.
- Do not invent public graph topology or persistent state variables.

## Output

Return exactly one JSON file:

```text
workspace/advanced-vn/scenes/<source_node_id>.scene.json
```

## Required Scene IR Semantics

- `beats` are ordered visible scene beats. Use only `line`, `command`, and
  `choice` beat types.
- `interactables` are player-clickable or selectable scene objects, people,
  places, sounds, clues, or UI focus targets. Each interactable has `id`,
  `label`, `text`, optional `conditions`, and optional `state_writes`.
- Do not add separate `presentation`, `clues`, `micro_activities`,
  `state_reads`, `asset_refs`, or `source_trace` fields. Use command beats,
  interactables, conditions, and state writes instead.
- `outcomes` bind Scene IR completion to public graph edge ids.
  `outcomes[*].beats` is optional and can hold short feedback before the scene
  moves to the target node.
- State reads are represented by `conditions`; state writes use
  `state_writes`. Both must use declared state variables.
- For multi-exit nodes, every outgoing public edge must be reachable through an
  explicit outcome.
- For terminal nodes, represent ending variants as state-resolved variant
  blocks, not as a final visible menu unless explicitly planned.

## Output Shape

Use this shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNSceneDesigner", "notes": []},
  "source_node_id": "node.example",
  "title": "Scene Title",
  "beats": [{"type": "line", "speaker": "Narrator", "text": "The room is quiet."}],
  "interactables": [{"id": "door", "label": "Inspect the door", "text": "A key mark is visible.", "state_writes": []}],
  "outcomes": [{"id": "continue", "edge_id": "edge.example_continue", "label": "Continue", "conditions": [], "state_writes": []}],
  "ending_variants": []
}
```

## Quality Checklist

- Scene IR parses as JSON.
- Every outcome maps to a public graph edge.
- Every interactable has visible feedback.
- Every condition or state write references declared state.
- The scene gives the player something to do beyond pressing continue.
- No private design terminology appears in visible text.
