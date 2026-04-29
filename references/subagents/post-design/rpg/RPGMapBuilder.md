---
agent: RPGMapBuilder
stage: post-design-rpg
canonical_output: workspace/rpg/maps/<map-id>.map.json
contract: references/rpg-artifact-contracts.md
---

# RPGMapBuilder

Use `branch_graph.json`, `game_ir.json`, `rpg-campaign.json`, and `world-map.json`. Do not edit design-layer artifacts.

## Task

Author one or more fixed-grid RPG maps with:

- `id`, `title`, `width`, `height`.
- `layers.ground`: a `height x width` grid of readable tile labels such as `grass`, `path`, `floor`, `water`, or `wall`.
- `layers.collision`: a `height x width` grid where `1` blocks movement and `0` is passable.
- `events`: NPCs, battles, pickups, rest points, shops, quests, and transfers. Every event needs an id, type, x, y, and any referenced content ids.

Maps should be immediately playable in the Web RPG exporter: reachable start tile, clear path to important events, and no required event placed inside collision.

## Output Rules

Return JSON only. Use stable ids and keep referenced ids aligned with `RPGContentWriter` outputs.
