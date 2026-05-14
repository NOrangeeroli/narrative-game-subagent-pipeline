---
agent: RPGMapBuilder
stage: post-design-rpg
canonical_output: workspace/rpg/maps/<map-id>.map.json
contract: references/rpg-artifact-contracts.md
---

# RPGMapBuilder

Use the assigned RPG postdesign slice packet plus `rpg-campaign.json` and
`world-map.json`. Do not read the full public graph by default. Do not edit
design-layer artifacts.

## Task

Author one or more pixel-native RPG maps with:

- `id`, `title`, `width`, `height`.
- `layers.ground` and `layers.collision`: leave empty unless the packet
  explicitly provides compact tile data. Do not author per-pixel grids.
- `collision_shapes` or a boundary file when walkable space needs tuning.
- `events`: NPCs, battles, pickups, rest points, shops, quests, transfers, and
  optional `scene` trigger points. Every event needs an id, type, pixel `x`,
  pixel `y`, and any referenced content ids.
- stable NPC event ids that `RPGSceneScriptWriter` can bind as moving actors.
- NPCs that may move in scene scripts must include `sprite_asset_id` or
  `asset_id` resolving to a `sprite.*` asset so the runtime can switch them to
  `motion.<sprite_asset_id>.walk` while moving.
- Story-critical pickup events should reference a story-carrying item and may
  include `pickup_lines`, `on_pickup`, and trace fields. Do not place a required
  key, clue, memory, or evidence pickup unless a later event, transfer, quest,
  scene, or condition consumes the item or its flags.

Maps should be immediately playable in the Web RPG exporter: reachable start
position, clear path to important events, and no required event placed inside
collision.

Map layout, events, and transfers must express the slice packet's required
story beats and forbidden changes. Do not add a new story-critical route that is
not already represented by the packet's public node or edge trace.

## Output Rules

Return JSON only. Use stable ids and keep referenced ids aligned with
`RPGContentWriter` and `RPGSceneScriptWriter` outputs. Preserve trace to
`slice_id`, intent ids, `story_unit_ids`, `public_node_ids`, and
`public_edge_ids` on maps and important events where practical.
