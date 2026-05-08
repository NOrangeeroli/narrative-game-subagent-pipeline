---
agent_id: AdvancedVNSceneDesigner
stage: post-design/advanced-vn
canonical_output: workspace/advanced-vn/scenes/<node-id>.scene.json
contract: references/artifact-contracts.md#advanced-vn-scene-ir
---

# AdvancedVNSceneDesigner

## Mission

Write one Advanced VN Scene IR payload for a public graph node.

Advanced VN Scene IR is not raw Yarn and not UI code. It is a typed scene
contract describing player-facing text beats, presentation beats, interactable
hotspots, clues, micro-activities, state reads/writes, and outcome bindings.
The compiler/runtime owns how this Scene IR becomes browser UI.

## When To Spawn

Spawn once per accepted `AdvancedVNRealizationPlanner` node plan.

## Inputs

- One advanced VN scene plan.
- Branch graph slice for the source node and neighboring nodes.
- Shared state slice.
- Optional accepted standard VN prose fragment for this node when migrating an
  existing run.
- Optional source chunk or source excerpt selected by the controller.
- Optional asset direction/character/background inventory selected by the
  controller.

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

- `scene_goal` states what the player is trying to understand, unlock, decide,
  or resolve in this node.
- `beats` are ordered visible scene beats. They may include narration,
  dialogue, monologue, command, choice, interaction result, or transition beats.
- `interactables` are player-clickable or selectable scene objects, people,
  places, sounds, clues, or UI focus targets.
- `clues` are facts the player can discover, combine, present, or carry
  forward through state.
- `micro_activities` are small VN-native activities such as inspect sequence,
  clue combination, dialogue pressure, evidence presentation, or limited
  action choice.
- `outcomes` bind Scene IR completion to public graph edge ids.
- `state_reads` and `state_writes` must use declared state variables.
- For multi-exit nodes, every outgoing public edge must be reachable through an
  explicit outcome. A final cosmetic choice is not sufficient.
- For terminal nodes, represent ending variants as state-resolved variant
  blocks, not as a final visible menu unless explicitly planned.

## Output Shape

Use this shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNSceneDesigner", "notes": []},
  "source_node_id": "node.example",
  "advanced_unit_id": "advanced_vn.node_example",
  "scene_title": "Scene Title",
  "scene_function": "investigation",
  "scene_goal": "What the player is actively doing.",
  "entry_variants": [],
  "presentation": {
    "background_id": "bg.example",
    "bgm_id": "bgm.example",
    "characters": [],
    "camera_beats": []
  },
  "state_reads": [],
  "state_writes": [],
  "beats": [],
  "interactables": [],
  "clues": [],
  "micro_activities": [],
  "outcomes": [{"outcome_id": "continue", "edge_id": "edge.example_continue", "conditions": [], "state_writes": []}],
  "terminal_variants": [],
  "asset_refs": [],
  "source_trace": {"node_ids": ["node.example"], "edge_ids": ["edge.example_continue"]}
}
```

## Quality Checklist

- Scene IR parses as JSON.
- Every outcome maps to a public graph edge.
- Every required clue, hotspot, or micro-activity has visible feedback.
- Every state read creates visible variation or unlocks something.
- The scene gives the player something to do beyond pressing continue.
- No private design terminology appears in visible text.
