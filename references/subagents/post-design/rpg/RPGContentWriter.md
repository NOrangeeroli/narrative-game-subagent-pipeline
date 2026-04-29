---
agent: RPGContentWriter
stage: post-design-rpg
canonical_outputs:
  - workspace/rpg/actors.json
  - workspace/rpg/enemies.json
  - workspace/rpg/items.json
  - workspace/rpg/equipment.json
  - workspace/rpg/skills.json
  - workspace/rpg/quests.json
  - workspace/rpg/npc-dialogue.json
  - workspace/rpg/encounter-tables.json
  - workspace/rpg/shops.json
  - workspace/rpg/rest-points.json
contract: references/rpg-artifact-contracts.md
---

# RPGContentWriter

Use `branch_graph.json`, `game_ir.json`, `rpg-campaign.json`, and controller-provided map/event slices. Do not edit design-layer files.

## Task

Author the RPG content tables consumed by the Web RPG runtime:

- Actors and enemies with positive `hp`, `attack`, `defense`, and optional speed.
- Items, equipment, and skills with stable ids and concise effects.
- NPC dialogue entries used by map events.
- Quests with clear active and completion states.
- Encounter tables, shops, and rest points referenced by maps.

Keep numbers simple and playable. The first required battle should be winnable with basic attacks according to `simulate_rpg_balance.py`.

## Output Rules

Return JSON only for the requested artifact. Use arrays under the plural top-level key, such as `{ "actors": [...] }` or `{ "enemies": [...] }`.
