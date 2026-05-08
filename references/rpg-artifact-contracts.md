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
  "map_asset_id": "map.village",
  "tileset_asset_id": "tileset.village",
  "layers": {
    "ground": [["grass"]],
    "collision": [[0]],
    "objects": [[""]],
    "overlay": [[""]]
  },
  "events": [
    { "id": "npc.elder", "type": "npc", "x": 3, "y": 3, "dialogue_id": "dialogue.elder" },
    { "id": "battle.slime", "type": "battle", "x": 7, "y": 4, "enemy_id": "enemy.slime", "once": true },
    { "id": "rest.camp", "type": "rest", "x": 5, "y": 6 }
  ]
}
```

`layers.ground` and `layers.collision` should be `height x width` arrays. The compiler will normalize missing cells, but authored maps should be complete. `layers.objects` and `layers.overlay` are optional visual layers for map props and foreground cover; the Web RPG runtime renders them when present.

Maps may also provide a higher-level `map_design` object. The compiler expands it into `ground`, `collision`, `objects`, `overlay`, generated map events, a canvas-facing `scene` object, and required asset ids. This is preferred for authored RPG maps because it keeps layouts coherent and easier to repair:

```json
{
  "id": "map.village",
  "title": "River Village",
  "width": 40,
  "height": 30,
  "map_design": {
    "player_spawn": { "x": 2, "y": 15 },
    "terrain": [
      { "kind": "water", "type": "rect", "x0": 18, "y0": 0, "x1": 20, "y1": 29 },
      { "kind": "bridge", "type": "rect", "x0": 18, "y0": 14, "x1": 20, "y1": 15 }
    ],
    "paths": [
      { "type": "rect", "x0": 0, "y0": 14, "x1": 39, "y1": 15 },
      { "type": "line", "x0": 8, "y0": 8, "x1": 8, "y1": 20, "width": 2 }
    ],
    "houses": [
      { "kind": "house_small", "x": 4, "y": 6, "w": 4, "h": 4, "door": { "x": 5, "y": 9 }, "name": "Miller Cottage" }
    ],
    "trees": [{ "x": 12, "y": 7 }],
    "gardens": [{ "x0": 14, "y0": 8, "x1": 17, "y1": 11, "fenced": true, "flowers": [{ "x": 15, "y": 9 }] }],
    "props": [{ "kind": "chest", "x": 34, "y": 4, "event": "chest", "item_id": "item.gold" }],
    "npcs": [{ "kind": "npc1", "x": 10, "y": 15, "name": "Villager", "lines": ["The bridge is safe now."] }]
  }
}
```

Supported `map_design` prop kinds: `fence`, `barrel`, `crate`, `chest`, `flower`, `rock`, `tree`, `house_small`, `house_big`, `roof`, and `bridge`. The compiler adds `map.<map-slug>`, `tileset.<map-slug>`, per-terrain `tile.<map-slug>.<terrain>`, `mapprop.*`, and `sprite.*` assets when needed. The Web RPG runtime prefers the per-terrain `tile.*` images for block-stitched maps; `tileset.*` and `map.*` remain fallback assets.

The compiled `scene` object is runtime-facing and controller-owned. Authors normally write `map_design`; the compiler writes:

```json
{
  "scene": {
    "renderer": "canvas-scene",
    "tile": 48,
    "width": 40,
    "height": 30,
    "map_asset_id": "map.village",
    "tileset_asset_id": "tileset.village",
    "terrain_asset_ids": {
      "grass": "tile.village.grass",
      "path": "tile.village.path"
    },
    "player_spawn": { "x": 2, "y": 15 },
    "props": [
      {
        "id": "sceneprop.chest.gold",
        "asset_id": "mapprop.chest",
        "asset": "chest",
        "name": "Old Chest",
        "x": 34,
        "y": 4,
        "w": 1,
        "h": 1,
        "blocking": true,
        "layer": "object",
        "item_id": "item.gold"
      }
    ]
  }
}
```

`scene.props` supports `layer` values `floor_decor`, `object`, and `overlay`. The Web RPG canvas runtime uses prop rectangles, `render_scale`, generated asset bounds, and facing-tile hit tests so map props can be drawn and interacted with like scene objects instead of DOM markers.

## Per-Map Scene Packages

The compiler also writes an `rpg-map-designer`-style package for each map:

- `workspace/rpg/scenes/<map-slug>/scene-spec.json`
- `workspace/rpg/scenes/<map-slug>/assets-request.json`
- `workspace/rpg/scenes/<map-slug>/grids/floor_layer.txt`
- `workspace/rpg/scenes/<map-slug>/grids/barrier_layer.txt`
- `workspace/rpg/scenes/<map-slug>/grids/collision_layer.txt`
- `workspace/rpg/scenes/<map-slug>/grids/interaction_layer.txt`

These packages are map-local planning and generation surfaces. `scene-spec.json` follows the `rpg_map_designer/skills/rpg-map-designer/references/scene_spec_schema.md` shape (`map`, `player_spawn`, `regions`, `barriers`, `openings`, `props`, `validation`). `assets-request.json` lists only the assets needed by that map: per-terrain `tile.*` images, map-local `sceneprop.<map>.*` object art, and event sprites. This keeps scene generation from collapsing into one global atlas or one full-map background.

The runtime still consumes `workspace/rpg/rpg-manifest.json`; the scene packages are the deterministic bridge that lets each map be planned, generated, inspected, and repaired independently before export.

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
- `quest`: marks `quest_id` active or complete. Set `complete: true` when the marker represents the objective payoff rather than only an accept point.
- `battle` / `encounter`: starts a simple turn battle using `enemy_id` or `encounter_id`.
- `pickup` / `item`: adds `item_id` to inventory.
- `rest`: restores HP.
- `shop`: displays shop inventory as dialogue.
- `transfer`: moves to `target_map_id`, `target_x`, and `target_y`. It may also carry `complete_quest_id`, which is the preferred way to complete a final "reach the door/exit/home" objective.

Quest progression expectations:

- `rpg-campaign.json.final_quest_id` must reference an id in `quests.json`; if it is omitted, the compiler infers the last runtime quest.
- Every runtime quest should have at least one completion source: a `quest` event with `complete: true`, a dialogue/event with `complete_quest_id`, or a battle/encounter with `quest_id`.
- The compiler now reports inferred quest completion anchors in `reports/rpg-validation.json` so generated games do not silently ship with impossible endings.

Reachability expectations:

- The campaign `start_position` or map `map_design.player_spawn` must be passable.
- Required touch/transfer events should be reachable from the spawn.
- NPCs, chests, doors, and other interactables may sit on blocked object tiles only if an adjacent tile is reachable.

## Generated Runtime Files

The controller writes:

- `workspace/rpg/rpg-manifest.json`
- `reports/rpg-scene-packages.json`
- `reports/rpg-validation.json`
- `reports/rpg-balance-report.json`
- `reports/rpg-coverage.json`
- `build/web-rpg/index.html`
- `build/web-rpg/runtime.js`
- `build/web-rpg/game-data.js`
