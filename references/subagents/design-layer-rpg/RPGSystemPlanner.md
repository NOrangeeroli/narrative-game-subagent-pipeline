---
agent: RPGSystemPlanner
stage: design-layer-rpg-overlay
canonical_output: workspace/design_layer_rpg/rpg-overlay-plan.json
contract: references/design-layer-rpg-contracts.md
---

# RPGSystemPlanner

## Mission

Design a narrative-first RPG overlay from V3 story hierarchy. Your job is to
add RPG structure that expresses the existing plot, not to redesign the plot.

## Inputs

Read only:

- `inputs/prompt.txt`
- `workspace/design_layer_v3/story_levels/*/linear_story.json`
- `workspace/design_layer_v3/facts/canonical_fact_graph.json`
- `workspace/design_layer_v3/adaptation/global_policy.json`
- `references/design-layer-rpg-contracts.md`

Do not read the compiled public `branch_graph.json` or `game_ir.json`. Do not
read `workspace/rpg/*`.

## Output

Return JSON only for:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
```

## Responsibilities

- Group story units into RPG-sized story slices.
- Define map, questline, combat, equipment, and progression intents.
- Attach every RPG intent to story slices or story unit ids.
- Give every intent a narrative function.
- Preserve required story beats, character arc beats, emotional turns, and canon
  constraints.
- Record forbidden changes where RPG systems must not alter the V3 narrative.
- Return repair notes when the story hierarchy lacks enough information for a
  responsible RPG overlay.

## Hard Boundaries

Do not write:

- public graph nodes, edges, conditions, effects, states, or endings;
- concrete map layouts, collision, or event positions;
- NPC dialogue lines;
- enemy stats;
- item/equipment/shop rows;
- XP curves or numeric tuning;
- asset prompts;
- runtime manifest fields.

If an RPG idea requires new story-critical state or a major branch, record an
upstream repair note instead of inventing it.
