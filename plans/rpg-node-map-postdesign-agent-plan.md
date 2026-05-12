# RPG Node-Map Postdesign Agent Plan

## Goal

Change only the RPG post-design agent instructions so RPG authoring follows a
node-map discipline:

```text
branch_graph.nodes[*] -> exactly one RPG map
```

Each graph node should own one map, and all playable RPG content for that node
should be authored as node-owned content. The generated canonical RPG output
layout must stay unchanged:

```text
workspace/rpg/rpg-campaign.json
workspace/rpg/world-map.json
workspace/rpg/maps/*.map.json
workspace/rpg/actors.json
workspace/rpg/enemies.json
workspace/rpg/items.json
workspace/rpg/equipment.json
workspace/rpg/skills.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/encounter-tables.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
workspace/rpg/progression-rules.json
```

No new RPG output directory, no `node_slices/`, no compiler change, no runtime
change, and no schema-level artifact migration are part of this plan.

## Scope

Allowed implementation files:

```text
references/subagents/post-design/rpg/RPGCampaignPlanner.md
references/subagents/post-design/rpg/RPGMapBuilder.md
references/subagents/post-design/rpg/RPGContentWriter.md
references/subagents/post-design/rpg/RPGBalanceReviewer.md
```

Do not change:

```text
scripts/
assets/web-rpg-template/
references/rpg-artifact-contracts.md
references/subagents/README.md
workspace/rpg/ output structure
```

If the subagent index needs to mention the revised behavior later, request a
separate scope expansion before editing it.

## Design Constraint

Because the current canonical RPG files are global, node ownership is expressed
inside the existing files rather than through new per-node artifact files.

The practical interpretation is:

- each graph node gets one map file under `workspace/rpg/maps/`;
- that map file owns the node's spatial layout and events;
- global content tables remain global, but each row is node-owned through id
  naming and trace fields;
- shared rows are allowed only for durable shared concepts such as party actors,
  core skills, reusable UI, or common recovery items.

This preserves the current output file structure while making the authored RPG
decomposable by graph node.

## Naming Rules

All node-owned ids should include the source node slug.

Example for `node.loom_lesson`:

```text
map.node_loom_lesson
quest.node_loom_lesson
npc.node_loom_lesson.meng_ke
dialogue.node_loom_lesson.meng_ke
battle.node_loom_lesson.laziness_shadow
enemy.node_loom_lesson.laziness_shadow
item.node_loom_lesson.loom_shuttle
rest.node_loom_lesson.bench
exit.node_loom_lesson.to_scholar_path
```

Shared ids may stay short only when they are intentionally cross-node:

```text
actor.meng_mu
skill.mother_teaching
ui.bamboo_scroll_panel
```

## Agent Changes

### RPGCampaignPlanner

Update the role card so it must:

- create one `world-map.json` map entry for every `branch_graph.nodes[*]`;
- derive each map id deterministically from the node id;
- set `start_map_id` from `branch_graph.start_node_id`;
- set campaign start position to the start position of the start node map;
- define `major_quest_ids` as the ordered node quest ids, excluding purely
  terminal maps only when the terminal node has no playable action;
- preserve `final_quest_id` by pointing at the last required playable node
  quest;
- write `required_assets` with one map asset per node map plus shared actor,
  UI, sprite, enemy, icon, and battle background ids as needed;
- include a planning note that all downstream map/content work must preserve
  the node-to-map mapping.

It should not author individual NPC dialogue, enemy stats, item details, or
event placements.

### RPGMapBuilder

Update the role card so it must:

- write exactly one `workspace/rpg/maps/<node-slug>.map.json` for each graph
  node;
- set `map.id` to the map id assigned by `RPGCampaignPlanner`;
- add `source_node_id` to the map payload for traceability;
- place all node-local events in that node's map only;
- bind every outgoing branch edge to at least one event in the source node map;
- use transfer events for edges that move to another node map;
- include these trace fields on edge-carrying events:

```json
{
  "source_node_id": "node.current",
  "edge_id": "edge.current.next",
  "target_node_id": "node.next"
}
```

- still include runtime-required transfer fields:

```json
{
  "target_map_id": "map.node_next",
  "target_x": 180,
  "target_y": 520
}
```

- avoid placing events that complete or mutate another node's quest unless the
  event is explicitly the outgoing edge handoff.

The map output remains the existing map JSON shape. Trace fields are additive
metadata and must not replace current runtime fields.

### RPGContentWriter

Update the role card so it must:

- keep writing the existing global content table files;
- treat each content row as owned by exactly one source node unless marked
  shared;
- add `source_node_id` or `source_node_ids` to node-owned entries where useful;
- generate one default quest per playable node:

```text
quest.<node-slug>
```

- ensure each node quest has activation and completion events in that node's map;
- keep dialogue ids, enemy ids, item ids, shop ids, and rest point ids aligned
  with map events;
- avoid content rows that are never referenced by any map event, campaign field,
  or asset requirement;
- keep shared actor and shared skill definitions reusable across node maps
  instead of duplicating them per node.

The content files keep their current top-level plural arrays, such as
`{"quests": [...]}` and `{"enemies": [...]}`.

### RPGBalanceReviewer

Update the role card so it reviews node-map discipline in addition to combat
numbers:

- every branch graph node has one map;
- every map has `source_node_id`;
- every non-terminal node has at least one outgoing edge event;
- every edge event targets the expected next node map;
- every node quest has an activation path and completion path in the same map;
- node-owned enemies/items/dialogues are referenced by the owning node map;
- shared rows are intentionally shared and not accidental duplicates;
- battle tuning still passes the existing deterministic balance report.

Repairs should remain small and should prefer:

```text
id alignment
missing event reference fixes
quest activation/completion wiring
stat tuning
rest or pickup placement
```

over changing branch graph topology or campaign structure.

## Runtime Limitation

The current Web RPG runtime does not fully gate event visibility by
`event.conditions`; it already supports conditions for outcome selection and
ending selection, but event rendering/interactability is not a complete
progression lock.

Under this agent-only plan, edge coverage and node ownership become authoring
requirements and review requirements. Hard runtime locks for exits or events
would require a later script/runtime scope expansion, which is intentionally
out of scope here.

## Acceptance Criteria

After the agent-file changes are implemented:

- a generated RPG still writes the same canonical RPG files;
- no `workspace/rpg/node_slices/` files are required or produced;
- `compile_rpg_manifest.py` can still consume the output without schema changes;
- every branch graph node corresponds to exactly one map;
- every outgoing branch edge is represented by an event in the source node map;
- global content tables contain node-owned ids or explicit shared ids;
- existing Web RPG export remains compatible.

## Suggested Implementation Order

1. Update `RPGCampaignPlanner.md` with the node-to-map mapping contract.
2. Update `RPGMapBuilder.md` with one-map-per-node and edge-event rules.
3. Update `RPGContentWriter.md` with node-owned global content table rules.
4. Update `RPGBalanceReviewer.md` with node-map coverage checks.
5. Generate or inspect one small RPG run and confirm the output file layout is
   unchanged.
6. Run the existing RPG validation and balance checks.

## Out Of Scope Follow-Up

If later scope expands beyond agent files, the next technical step should be a
deterministic validator that checks node-map coverage directly from
`branch_graph.json` and `workspace/rpg/rpg-manifest.json`. That should be a
separate plan because it requires script changes.
