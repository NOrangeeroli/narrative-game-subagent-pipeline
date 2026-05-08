---
agent_id: AdvancedVNRealizationPlanner
stage: post-design/advanced-vn
canonical_output: workspace/advanced-vn/scene-plan.json
contract: references/artifact-contracts.md#advanced-vn-scene-plan
---

# AdvancedVNRealizationPlanner

## Mission

Plan how the compiled public branch graph should become advanced VN scenes
instead of standard Yarn-only scenes.

This role does not write dialogue prose, UI code, runtime code, or final Scene
IR. It decides which public graph nodes need advanced scene treatment and what
playable VN verbs, state reads, clues, hotspots, and micro-activities each scene
must expose.

## When To Spawn

Spawn after `branch_graph.json`, `game_ir.json`, and projected shared state are
valid, before `AdvancedVNSceneDesigner`.

## Inputs

- Accepted `branch_graph.json`.
- Accepted `game_ir.json`.
- Shared state schema.
- Optional V3 trace excerpts supplied by the controller.
- Run policy saying the post-design branch is `advanced-vn`.

## Output

Return only JSON for:

```text
workspace/advanced-vn/scene-plan.json
```

## Required Constraints

- Cover every public branch graph node exactly once.
- Preserve public graph topology. Do not add hidden runtime edges.
- Every outgoing public edge must be represented by a planned outcome.
- Use advanced VN verbs only when they make the node more playable:
  `inspect`, `listen`, `ask`, `present_clue`, `combine_clues`, `use_item`,
  `wait`, `move_focus`, `choose_speech`, and `commit_choice`.
- State reads/writes may only reference variables declared in shared state or
  `game_ir`.
- Convert abstract branch meanings into concrete player actions.
- For each node, declare the scene's playable purpose: investigation, dialogue
  pressure, route commitment, clue synthesis, emotional confrontation, quiet
  transition, or ending resolution.
- For terminal nodes, plan ending variant resolution from state. Do not turn
  endings into a visible menu unless the graph explicitly calls for that.

## Output Shape

Use this shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNRealizationPlanner", "notes": []},
  "plans": [
    {
      "source_node_id": "node.example",
      "advanced_unit_id": "advanced_vn.node_example",
      "scene_function": "investigation",
      "scene_goal": "The player connects the locked room with the hidden crying.",
      "allowed_verbs": ["inspect", "listen", "ask"],
      "required_state_reads": [],
      "state_writes": [],
      "required_clues": [],
      "planned_interactables": [],
      "planned_micro_activities": [],
      "outcomes": [{"outcome_id": "continue", "edge_id": "edge.example_continue"}],
      "entry_variant_notes": [],
      "terminal_variant_notes": [],
      "source_trace": {"node_ids": ["node.example"], "edge_ids": ["edge.example_continue"]}
    }
  ]
}
```

## Quality Checklist

- Every node has one plan.
- Every outgoing edge is covered by one outcome.
- Multi-exit nodes expose meaningful player action before the outcome.
- Planned interactables and micro-activities read/write declared state only.
- The plan explains how later scenes can make route memory visible.
