# RPG Artifact Contracts

RPG artifacts are a parallel post-design target for `run_pipeline.py build --target web-rpg`. They must not modify the design-layer schema or VN realization artifacts.

## Required Core

`workspace/rpg/rpg-campaign.json`

```json
{
  "title": "Example RPG",
  "start_map_id": "map.village",
  "start_position": { "x": 2, "y": 3 },
  "party": ["actor.hero"],
  "goal": "Find the missing keepsake.",
  "major_quest_ids": ["quest.main"],
  "required_assets": ["tileset.village", "sprite.hero", "battlebg.field"]
}
```

`workspace/rpg/world-map.json`

```json
{
  "title": "World",
  "start_map_id": "map.village",
  "maps": [
    { "id": "map.village", "title": "Village", "role": "hub" }
  ]
}
```

`workspace/rpg/maps/<map-id>.map.json`

```json
{
  "id": "map.village",
  "title": "Village",
  "width": 12,
  "height": 8,
  "layers": {
    "ground": [["grass"]],
    "collision": [[0]]
  },
  "events": [
    { "id": "npc.elder", "type": "npc", "x": 3, "y": 3, "dialogue_id": "dialogue.elder" },
    { "id": "battle.slime", "type": "battle", "x": 7, "y": 4, "enemy_id": "enemy.slime", "once": true },
    { "id": "rest.camp", "type": "rest", "x": 5, "y": 6 }
  ]
}
```

`layers.ground` and `layers.collision` should be `height x width` arrays. The compiler will normalize missing cells, but authored maps should be complete.

## Content Tables

Each content table should use an array under its plural key:

```json
{ "actors": [{ "id": "actor.hero", "name": "Hero", "stats": { "hp": 36, "attack": 9, "defense": 3, "speed": 4 } }] }
```

Supported files:

- `actors.json`
- `classes.json`
- `items.json`
- `equipment.json`
- `skills.json`
- `enemies.json`
- `encounter-tables.json`
- `quests.json`
- `npc-dialogue.json`
- `events.json`
- `shops.json`
- `rest-points.json`
- `progression-rules.json`

`actors.json` is required for `web-rpg`. `enemies.json` is required when maps contain battle or encounter events.

## Event Types

The MVP Web RPG runtime supports:

- `npc`: shows dialogue from `lines` or `dialogue_id`.
- `quest`: marks `quest_id` active or complete.
- `battle` / `encounter`: starts a simple turn battle using `enemy_id` or `encounter_id`.
- `pickup` / `item`: adds `item_id` to inventory.
- `rest`: restores HP.
- `shop`: displays shop inventory as dialogue.
- `transfer`: moves to `target_map_id`, `target_x`, and `target_y`.

## Generated Runtime Files

The controller writes:

- `workspace/rpg/rpg-manifest.json`
- `reports/rpg-validation.json`
- `reports/rpg-balance-report.json`
- `reports/rpg-coverage.json`
- `build/web-rpg/index.html`
- `build/web-rpg/runtime.js`
- `build/web-rpg/game-data.js`
