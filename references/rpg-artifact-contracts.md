# RPG Artifact Contracts

RPG artifacts are the post-design target for `run_pipeline.py build --target web-rpg`. They must not modify the design-layer schema or silently rewrite verified narrative semantics.

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
- `scene-scripts.json`
- `events.json`
- `shops.json`
- `rest-points.json`
- `progression-rules.json`

`actors.json` is required for `web-rpg`. `enemies.json` is required when maps contain battle or encounter events.

## Story-Carrying Items

Story-critical items must act as readable evidence, keys, memories, or tools,
not only inventory counters. Use `workspace/rpg/items.json` fields like:

```json
{
  "id": "item.tiny_key",
  "name": "Tiny Key",
  "story_role": "key_item",
  "description": "A key small enough for the garden door.",
  "inspect_lines": [
    { "speaker": "Hero", "text": "This does not solve the door by itself. It tells me what size I must become." }
  ],
  "on_pickup": {
    "activate_quest_id": "quest.find_garden_path",
    "set_flags": { "item.tiny_key.collected": true }
  },
  "on_inspect": {
    "set_flags": { "item.tiny_key.inspected": true }
  },
  "quest_id": "quest.find_garden_path",
  "public_node_ids": ["node.locked_hall"]
}
```

Supported item story fields:

- `story_role`: one of `key_item`, `evidence`, `memory`, `tool`, `lore`,
  `quest_item`, or a campaign-specific role.
- `inspect_lines`: dialogue shown from the inventory item panel. Use this for
  interpretation, memory, clues, and character reaction.
- `pickup_lines`: optional dialogue shown immediately when the map pickup is
  collected.
- `on_pickup` and `on_inspect`: outcome objects using the same fields as map
  outcomes: `set_flags`, `quest_updates`, `inventory_delta`,
  `activate_quest_id`, `complete_quest_id`, `reward_item_id`,
  `hero_hp_delta`, `log`, and `ending_id`.

Map pickup events may override item defaults with `pickup_lines` and
`on_pickup`. Story gates should consume item results through
`conditions.inventory`, `conditions.flags`, or `conditions.quests`, or through
scene-script beats such as `take_item`, `set_flag`, and `activate_quest`.

Story-critical items should preserve trace to `slice_id`, story units, public
nodes, public edges, quest ids, or state ids. If an item changes the story, some
later event, scene script, quest, transfer, or dialogue condition should consume
that changed state.

## Narrative Scene Scripts

Use `workspace/rpg/scene-scripts.json` for To the Moon-style story scenes where
dialogue, actor movement, and state changes advance together without waiting for
the player to manually control each action.

```json
{
  "scene_scripts": [
    {
      "id": "scene.alice.riverbank_opening",
      "map_id": "map.riverbank",
      "trigger": { "kind": "on_entry", "map_id": "map.riverbank", "once": true },
      "blocking": true,
      "actors": [
        { "actor_id": "player", "x": 420, "y": 520 },
        { "actor_id": "actor.sister", "event_id": "npc.sister", "x": 540, "y": 500 },
        { "actor_id": "actor.white_rabbit", "event_id": "npc.white_rabbit", "x": 1160, "y": 520 }
      ],
      "beats": [
        { "kind": "dialogue", "speaker_actor_id": "actor.sister", "text": "这本书没有图画，也没有对话。" },
        { "kind": "dialogue", "speaker_actor_id": "player", "text": "那读起来有什么用呢？" },
        { "kind": "move_actor", "actor_id": "actor.white_rabbit", "to": { "x": 760, "y": 520 }, "speed": 360 },
        { "kind": "dialogue", "speaker_actor_id": "actor.white_rabbit", "text": "迟到了，迟到了！" },
        { "kind": "face_actor", "actor_id": "player", "target_actor_id": "actor.white_rabbit" },
        { "kind": "move_actor", "actor_id": "player", "to": { "x": 860, "y": 520 }, "speed": 240 },
        { "kind": "activate_quest", "quest_id": "quest.follow_rabbit" },
        { "kind": "set_flag", "flag": "scene.riverbank_opening.done", "value": true }
      ]
    }
  ]
}
```

Supported triggers:

- `on_entry`: starts when the player enters `trigger.map_id`.
- `interact`: starts when the player interacts with `trigger.event_id`, or with
  a map event that has `scene_id`.
- `touch`: starts when the player reaches the trigger event.
- `manual`: compiled but not auto-triggered by the MVP runtime.

Supported beat kinds in the Web RPG runtime:

- `dialogue` / `line`: show a dialogue line. Prefer explicit
  `speaker_actor_id` and `text`.
- `move_actor`: move `player` or a bound map event actor to `to.x` / `to.y`.
- `set_actor_position`, `teleport_actor`, `place_actor`: immediately reposition
  an actor.
- `face_actor`, `face_direction`: update the player facing direction.
- `wait`: pause for `seconds` or `duration`.
- `show_actor`, `hide_actor`, `show_event`, `hide_event`: control visibility.
- `set_flag`, `activate_quest`, `complete_quest`, `set_quest_state`,
  `give_item`, `take_item`, `inventory_delta`, `transfer`, `play_sfx`, `log`,
  and `end_scene`.

Scene actors bind story characters to runtime map events. Use `player` for the
party lead. For NPCs that must move during the scene, bind `actor_id` to an
existing map event via `event_id`; the runtime stores temporary positions for
that event while preserving normal map-event behavior after the scene.

Every actor or NPC that can move should resolve to a visible sprite. The party
lead should set `sprite_asset_id` and, for final-quality runs,
`walk_sheet_asset_id` or `walk_frame_asset_ids` when available. Moving NPC map
events should set `sprite_asset_id` or an `asset_id` that resolves to a
`sprite.*` asset. The export/runtime media flow generates
`motion.<sprite_asset_id>.walk.gif` fallback loops from accepted sprites, and
the Web RPG runtime switches moving actors to walking motion during scripted or
player movement.

## Event Types

The MVP Web RPG runtime supports:

- `npc`: shows dialogue from `lines` or `dialogue_id`.
- `scene`: starts `scene_id` when interacted with.
- `quest`: marks `quest_id` active or complete.
- `battle` / `encounter`: starts a simple turn battle using `enemy_id` or `encounter_id`.
- `pickup` / `item`: adds `item_id` to inventory, can show pickup dialogue, and
  can apply item/event `on_pickup` story outcomes.
- `rest`: restores HP.
- `shop`: displays shop inventory as dialogue.
- `transfer`: moves to `target_map_id`, `target_x`, and `target_y`.

## Generated Runtime Files

The controller writes:

- `workspace/rpg/rpg-manifest.json`
- `workspace/rpg/scene-scripts.json` is consumed into `rpg-manifest.json` when present
- `reports/rpg-validation.json`
- `reports/rpg-balance-report.json`
- `reports/rpg-coverage.json`
- `build/web-rpg/index.html`
- `build/web-rpg/runtime.js`
- `build/web-rpg/game-data.js`
