# RPG Artifact Contracts

RPG artifacts are a parallel post-design target for `run_pipeline.py build --target web-rpg`. They must not modify the design-layer schema or VN realization artifacts.

## Required Core

`workspace/rpg/rpg-campaign.json`

```json
{
  "title": "Example RPG",
  "start_map_id": "map.village",
  "start_position": { "x": 240, "y": 520 },
  "party": ["actor.hero"],
  "entry_points": [
    {
      "id": "entry.hero",
      "title": "Hero's View",
      "description": "Start from the protagonist's route.",
      "start_map_id": "map.village",
      "start_position": { "x": 240, "y": 520 },
      "party": ["actor.hero"],
      "initial_quests": ["quest.main"],
      "initial_flags": { "route.hero": true },
      "initial_inventory": { "item.ration": 1 }
    }
  ],
  "goal": "Find the missing keepsake.",
  "major_quest_ids": ["quest.main"],
  "required_assets": ["tileset.village", "sprite.hero", "battlebg.field"]
}
```

`entry_points` is optional but recommended for RPGs with multiple narrative
angles. When present, the Web RPG runtime shows an entry selection screen before
play. Each entry can choose a start map, start position, party, initial quests,
initial flags, and initial inventory. Map events may include `entry_point_id` or
`entry_point_ids` to appear only for specific entries.

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
  "width": 1280,
  "height": 720,
  "coordinate_system": "pixels",
  "layers": {
    "ground": [],
    "collision": []
  },
  "events": [
    { "id": "npc.elder", "type": "npc", "x": 420, "y": 300, "dialogue_id": "dialogue.elder" },
    { "id": "battle.slime", "type": "battle", "x": 860, "y": 360, "enemy_id": "enemy.slime", "once": true },
    { "id": "rest.camp", "type": "rest", "x": 640, "y": 520 }
  ]
}
```

`coordinate_system` must be `pixels`. Map coordinates directly match the
accepted background image pixels, for example `width: 1280, height: 720`.
Do not author a per-pixel collision grid; leave tile layers empty or compact,
and use vector `collision_shapes`, event points, and trigger zones.

For hand-painted or scene-style maps, prefer mask-derived polygon boundaries
over grid collision. A map may reference a boundary file:

```json
{
  "id": "map.village",
  "boundary_file": "../boundaries/village.boundaries.json",
  "layers": {
    "ground": [],
    "collision": []
  }
}
```

`workspace/rpg/boundaries/<map-id>.boundaries.json`

```json
{
  "map_id": "map.village",
  "coordinate_system": "pixels",
  "walkable_mask_ref": "workspace/generated-assets/generated/rpg/map_walkmasks/map.village.walkable.png",
  "boundary_source": {
    "type": "walkable_mask_inversion",
    "mask_ref": "workspace/generated-assets/generated/rpg/map_walkmasks/map.village.walkable.png",
    "vectorizer": "contour_simplify"
  },
  "collision_shapes": [
    { "id": "pond", "type": "polygon", "points": [[0, 405], [214, 450], [160, 720], [0, 720]] },
    { "id": "hut", "type": "rect", "x": 780, "y": 110, "w": 220, "h": 150 }
  ],
  "walkable_hint": { "x": 240, "y": 520 }
}
```

Boundary coordinates use the same pixel coordinate system as event positions:
`x=0,y=0` is the upper-left of the map and `x=width,y=height` is the lower-right.
For final-quality map art, prefer producing these `collision_shapes` by
extracting a cyan walkable mask, repairing required connectivity, inverting the
accepted mask, and vectorizing the blocked regions. The compiler merges
`collision_shapes` into the runtime manifest. The Web RPG runtime blocks
movement against `collision_shapes`, and its `Walls` toggle visualizes authored
boundary polygons for tuning.

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
