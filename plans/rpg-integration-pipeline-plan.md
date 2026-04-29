# RPG Integration Pipeline Plan

## Goal

Add a design-layer downstream branch that can generate RPG Maker-style, turn-based single-player RPGs in parallel with the existing VN pipeline.

The target experience is the kind of game shown in the reference video:

```text
top-down tile-map exploration
NPC dialogue
quest progression
party/actor stats
equipment and inventory
skills and limited-use actions
sleep/rest recovery
turn-based combat
enemy drops, gold, and rewards
longer-term progression
static Web playable export
```

This should not be implemented as a large `web-vn` gameplay panel. It should be a separate RPG branch that uses the same upstream design interface, then compiles into RPG-specific artifacts and a dedicated Web RPG runtime.

## Non-Goals

Do not replace the existing VN pipeline.

Do not make subagents write arbitrary JavaScript, Phaser scenes, C#, Unity scene files, or generated image files.

Do not move tilemaps, enemy stats, inventory definitions, encounter tables, or battle formulas into `branch_graph.json`.

Do not overload `game_ir.json` with runtime implementation details. It remains semantic authority and durable design context.

Do not attempt a full commercial RPG system in v1. The first version should produce a compact but real playable loop.

## Compatibility Requirements

The RPG branch must be strictly additive.

Existing VN runs must continue to work without changing their artifacts, commands, reports, or exported runtime. The following commands must keep their current behavior:

```bash
python3 scripts/run_pipeline.py init --prompt "..." --run-root runs/example
python3 scripts/run_pipeline.py build --run-root runs/example
```

The default build target remains the current Web VN pipeline. RPG behavior should only activate when explicitly requested:

```bash
python3 scripts/run_pipeline.py init --target web-rpg ...
python3 scripts/run_pipeline.py build --target web-rpg ...
```

The public design-layer contract must not change:

```text
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

`branch_graph.json` and `game_ir.json` must remain valid inputs for both downstream branches. RPG-specific data must be projected into `workspace/rpg/` by post-design RPG agents and controller compilers, not by changing the design-layer schema.

The existing VN downstream artifacts must remain unchanged:

```text
workspace/realization/node-realization-plans.json
workspace/realization/realization-manifest.json
workspace/realization/gameplay-manifest.json
workspace/vn/fragments/
workspace/vn/story.yarn
workspace/vn/story.storyir.json
build/web-vn/
```

RPG adds parallel artifacts only:

```text
workspace/rpg/
reports/rpg-*.json
build/web-rpg/
```

Asset pipeline changes must be backward compatible. Existing asset manifest sections and kinds must keep their meaning. RPG should add new optional sections and kinds, not rename or reinterpret existing ones:

```text
tileset.*
sprite.*
icon.item.*
icon.skill.*
icon.equip.*
battlebg.*
ui.rpg.*
```

Final reports may add RPG fields, but existing fields must remain stable:

```text
status
validation_status
story_verification_status
gameplay_validation_status
asset_validation_status
playable_exports.web_vn
asset_exports
gameplay
design_layer
artifacts
```

When `--target web-vn` or no target is used, RPG validation, RPG balance simulation, RPG manifest compilation, and Web RPG export must be skipped.

## Current Baseline

The current public design-layer interface is:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

The current downstream flow is VN-centered:

```text
branch_graph.json + game_ir.json
  -> NodeRealizationPlanner
  -> VN fragments and gameplay unit JSON
  -> story.yarn / story.storyir.json
  -> asset-manifest.json
  -> build/web-vn/
```

Implemented non-VN gameplay adapters are still local panels inside the Web VN runtime:

```text
battle.choice_duel
interaction.inspect_scene
puzzle.sequence_lock
exploration.room_nav
```

Those adapters are useful for mixed VN prototypes, but they are not enough for an RPG Maker-like game because they lack persistent map state, avatar movement, tile collision, RPG combat, inventory, equipment, shops, rest points, drops, and quest logs.

## Target Architecture

Keep the upstream design layer shared:

```text
Prompt
  -> design-layer agents
  -> branch_graph.json
  -> game_ir.json
```

Then branch downstream by target:

```text
branch_graph.json + game_ir.json
  -> VN downstream branch
  -> workspace/vn/
  -> build/web-vn/

branch_graph.json + game_ir.json
  -> RPG downstream branch
  -> workspace/rpg/
  -> build/web-rpg/
```

The RPG branch should have its own planners, artifacts, validators, asset manifest extensions, and exporter.

The controller remains responsible for:

```text
run layout
artifact persistence
schema validation
repair routing
asset generation
manifest compilation
runtime export
browser smoke validation
final report
```

Subagents remain typed-payload authors only.

## New Run Modes

Add a target selection to the pipeline:

```text
--target web-vn
--target web-rpg
--target mixed-vn
```

Initial behavior:

```text
web-vn     existing default
web-rpg    new RPG branch
mixed-vn   existing VN plus panel adapters
```

`run_pipeline.py build` should eventually support:

```bash
python3 scripts/run_pipeline.py build \
  --run-root runs/example-rpg \
  --target web-rpg
```

For backward compatibility, omitted target should remain `web-vn`.

Do not require existing run directories to include target metadata. If a run has no target marker, treat it as `web-vn`.

## RPG Artifact Layout

Add a new canonical RPG workspace:

```text
workspace/rpg/rpg-campaign.json
workspace/rpg/world-map.json
workspace/rpg/maps/*.map.json
workspace/rpg/actors.json
workspace/rpg/classes.json
workspace/rpg/items.json
workspace/rpg/equipment.json
workspace/rpg/skills.json
workspace/rpg/enemies.json
workspace/rpg/encounter-tables.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/events.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
workspace/rpg/progression-rules.json
workspace/rpg/rpg-manifest.json
```

Add reports:

```text
reports/rpg-validation.json
reports/rpg-balance-report.json
reports/rpg-coverage.json
reports/rpg-playtest-report.json
```

Add export:

```text
build/web-rpg/index.html
build/web-rpg/runtime.js
build/web-rpg/game-data.js
build/web-rpg/assets/
```

## RPG Campaign Manifest

`rpg-campaign.json` is the controller-facing overview.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGCampaignPlanner",
    "notes": []
  },
  "campaign_id": "rpg.example",
  "title": "Example RPG",
  "source_design": {
    "branch_graph": "workspace/design_layer/branch_graph.json",
    "game_ir": "workspace/design_layer/game_ir.json"
  },
  "target_runtime": "web-rpg",
  "start": {
    "map_id": "map.village",
    "spawn_id": "spawn.start"
  },
  "primary_loop": "talk_to_npc -> explore -> battle -> collect_reward -> upgrade -> unlock_next_area",
  "required_files": [
    "workspace/rpg/world-map.json",
    "workspace/rpg/actors.json",
    "workspace/rpg/quests.json"
  ],
  "source_trace": {
    "node_ids": [],
    "game_ir_ids": []
  }
}
```

This file should not duplicate all RPG data. It names the campaign, target runtime, start point, loop, and required artifact set.

## World Map Contract

`world-map.json` describes global regions and map connections.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGWorldDesigner"
  },
  "world_id": "world.example",
  "maps": [
    {
      "map_id": "map.village",
      "title": "Village",
      "file": "workspace/rpg/maps/map.village.map.json",
      "role": "hub",
      "unlocked_at_start": true
    }
  ],
  "connections": [
    {
      "from_map_id": "map.village",
      "to_map_id": "map.field",
      "gate_id": "gate.village_to_field",
      "condition": {"quest_id": "quest.first", "status": "accepted"}
    }
  ]
}
```

## Map Contract

Each `maps/*.map.json` should be grid-based and runtime-neutral.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGMapWriter"
  },
  "map_id": "map.village",
  "title": "Village",
  "size": {"width": 24, "height": 18},
  "tile_size": 32,
  "tileset_refs": ["tileset.village"],
  "layers": [
    {
      "id": "ground",
      "type": "tile",
      "grid": [[1, 1, 1]]
    },
    {
      "id": "collision",
      "type": "collision",
      "grid": [[0, 1, 0]]
    }
  ],
  "spawns": [
    {"id": "spawn.start", "x": 4, "y": 8, "facing": "south"}
  ],
  "npcs": [
    {
      "npc_id": "npc.elder",
      "actor_ref": "actor.elder",
      "x": 8,
      "y": 8,
      "dialogue_id": "dialogue.elder_intro"
    }
  ],
  "interactables": [
    {
      "id": "rest.bed",
      "type": "rest_point",
      "x": 3,
      "y": 5,
      "rest_point_id": "rest.home_bed"
    }
  ],
  "exits": [
    {
      "id": "exit.to_field",
      "x": 23,
      "y": 9,
      "target_map_id": "map.field",
      "target_spawn_id": "spawn.from_village"
    }
  ],
  "encounters": {
    "mode": "fixed",
    "table_id": "encounter.field_early"
  },
  "required_assets": ["tileset.village", "sprite.hero", "sprite.npc.elder"]
}
```

The first implementation can use generated tile grids rather than external Tiled `.tmx` files. Later versions can add Tiled import/export.

## Actor And Party Contract

`actors.json` defines player characters and important NPC actors.

Shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "RPGSystemDesigner"},
  "party": {
    "initial_actor_ids": ["actor.hero"],
    "max_size": 4
  },
  "actors": [
    {
      "id": "actor.hero",
      "name": "Hero",
      "kind": "player",
      "class_id": "class.guardian",
      "level": 1,
      "base_stats": {
        "max_hp": 30,
        "max_mp": 8,
        "attack": 6,
        "defense": 3,
        "speed": 4
      },
      "equipment_slots": ["weapon", "armor", "accessory"],
      "initial_equipment": {
        "weapon": "equip.wood_sword"
      },
      "initial_inventory": [
        {"item_id": "item.herb", "quantity": 2}
      ],
      "sprite_ref": "sprite.hero",
      "portrait_ref": "portrait.hero.neutral"
    }
  ]
}
```

## Items, Equipment, And Skills

Add three separate files because they have different validation rules.

`items.json`:

```json
{
  "items": [
    {
      "id": "item.herb",
      "name": "Herb",
      "kind": "consumable",
      "effects": [{"target": "ally", "stat": "hp", "operation": "restore", "value": 12}],
      "usable_in": ["battle", "field"],
      "price": 10,
      "icon_ref": "icon.item.herb"
    }
  ]
}
```

`equipment.json`:

```json
{
  "equipment": [
    {
      "id": "equip.wood_sword",
      "name": "Wood Sword",
      "slot": "weapon",
      "stat_modifiers": {"attack": 2},
      "price": 30,
      "icon_ref": "icon.equip.wood_sword"
    }
  ]
}
```

`skills.json`:

```json
{
  "skills": [
    {
      "id": "skill.power_strike",
      "name": "Power Strike",
      "cost": {"mp": 3},
      "targeting": "single_enemy",
      "effects": [{"kind": "damage", "formula": "attack * 1.5"}],
      "cooldown": 0,
      "usage_limit": null,
      "icon_ref": "icon.skill.power_strike"
    }
  ]
}
```

Keep formulas deliberately small in v1. The validator should accept only a small expression grammar or named built-in formulas.

## Enemy And Encounter Contracts

`enemies.json`:

```json
{
  "enemies": [
    {
      "id": "enemy.slime",
      "name": "Slime",
      "level": 1,
      "stats": {
        "max_hp": 14,
        "attack": 4,
        "defense": 1,
        "speed": 2
      },
      "actions": [
        {"id": "attack", "weight": 1.0}
      ],
      "rewards": {
        "xp": 4,
        "gold": 3,
        "drops": [{"item_id": "item.herb", "chance": 0.15, "quantity": 1}]
      },
      "sprite_ref": "enemy.slime"
    }
  ]
}
```

`encounter-tables.json`:

```json
{
  "tables": [
    {
      "id": "encounter.field_early",
      "encounters": [
        {
          "id": "encounter.slime_pair",
          "enemy_party": [{"enemy_id": "enemy.slime", "count": 2}],
          "weight": 1.0
        }
      ],
      "trigger": {
        "type": "fixed_tile",
        "event_id": "event.first_battle"
      }
    }
  ]
}
```

First version should prefer fixed encounters and explicit event triggers. Random encounters can come later.

## Quest Contract

`quests.json` owns RPG progression.

Shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "RPGQuestDesigner"},
  "quests": [
    {
      "id": "quest.first_monster",
      "title": "Clear the Field",
      "source_node_ids": ["node.first_task"],
      "status_at_start": "locked",
      "steps": [
        {
          "id": "step.accept",
          "kind": "talk_to_npc",
          "npc_id": "npc.elder",
          "dialogue_id": "dialogue.elder_intro",
          "effects": [{"quest_id": "quest.first_monster", "operation": "set_status", "value": "active"}]
        },
        {
          "id": "step.defeat",
          "kind": "defeat_enemies",
          "enemy_ids": ["enemy.slime"],
          "count": 2
        },
        {
          "id": "step.return",
          "kind": "talk_to_npc",
          "npc_id": "npc.elder",
          "dialogue_id": "dialogue.elder_complete",
          "effects": [
            {"quest_id": "quest.first_monster", "operation": "set_status", "value": "completed"},
            {"item_id": "equip.wood_sword", "operation": "add", "quantity": 1}
          ]
        }
      ],
      "rewards": {
        "xp": 20,
        "gold": 15,
        "items": [{"item_id": "item.herb", "quantity": 1}]
      }
    }
  ]
}
```

Quest steps must reference real NPCs, maps, enemies, dialogues, and items.

## Dialogue Events

`npc-dialogue.json` should be RPG-event dialogue, not full VN Yarn.

Shape:

```json
{
  "dialogues": [
    {
      "id": "dialogue.elder_intro",
      "speaker_actor_id": "actor.elder",
      "lines": [
        {"speaker": "Elder", "text": "The field is unsafe."}
      ],
      "choices": [
        {
          "label": "I will help.",
          "effects": [{"quest_id": "quest.first_monster", "operation": "set_status", "value": "active"}]
        }
      ]
    }
  ]
}
```

The RPG runtime can render this with a simple dialogue box and optional choice menu. Do not require Yarn in v1.

Later, if richer dialogue is needed, add an optional Yarn/Ink bridge, but keep quest effects in typed event payloads.

## Runtime Events

`events.json` is the glue layer between map interactions and system effects.

Shape:

```json
{
  "events": [
    {
      "id": "event.first_battle",
      "trigger": {"kind": "interact", "map_id": "map.field", "x": 12, "y": 7},
      "actions": [
        {"kind": "start_battle", "encounter_id": "encounter.slime_pair"},
        {"kind": "set_flag", "flag_id": "flag.first_battle_seen", "value": true}
      ],
      "repeat": false
    }
  ]
}
```

Allowed action kinds in v1:

```text
show_dialogue
start_battle
give_item
remove_item
give_gold
give_xp
set_flag
set_quest_status
unlock_map
transfer_player
rest_party
open_shop
```

## Shops And Rest Points

`shops.json`:

```json
{
  "shops": [
    {
      "id": "shop.village",
      "inventory": [
        {"item_id": "item.herb", "price": 10},
        {"equipment_id": "equip.wood_sword", "price": 30}
      ]
    }
  ]
}
```

`rest-points.json`:

```json
{
  "rest_points": [
    {
      "id": "rest.inn",
      "cost_gold": 5,
      "effects": [
        {"target": "party", "stat": "hp", "operation": "restore_full"},
        {"target": "party", "stat": "mp", "operation": "restore_full"},
        {"target": "skills", "operation": "reset_daily_uses"}
      ]
    }
  ]
}
```

## Progression Rules

`progression-rules.json` maps RPG state back to design-layer intent.

Shape:

```json
{
  "rules": [
    {
      "id": "rule.unlock_field",
      "when": [
        {"quest_id": "quest.first_monster", "status": "active"}
      ],
      "effects": [
        {"kind": "unlock_map", "map_id": "map.field"}
      ],
      "source_game_ir_rule_ids": ["rule.first_task"]
    }
  ]
}
```

This keeps the RPG branch traceable to `game_ir.json` without forcing `game_ir.json` to become the RPG runtime database.

## RPG Manifest

The controller compiles all RPG artifacts into `workspace/rpg/rpg-manifest.json`.

Shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
  "source_files": {
    "campaign": "workspace/rpg/rpg-campaign.json",
    "world": "workspace/rpg/world-map.json",
    "actors": "workspace/rpg/actors.json",
    "quests": "workspace/rpg/quests.json"
  },
  "runtime_support": {
    "web_rpg": true,
    "unity": false
  },
  "coverage": {
    "maps": 2,
    "quests": 1,
    "fixed_encounters": 1,
    "shops": 0,
    "rest_points": 1
  }
}
```

## Subagent Layout

Keep the design-layer agents unchanged.

Add RPG role cards under:

```text
references/subagents/post-design/rpg/
```

Initial role cards:

```text
RPGCampaignPlanner.md
RPGWorldDesigner.md
RPGMapWriter.md
RPGQuestDesigner.md
RPGSystemDesigner.md
RPGEncounterDesigner.md
RPGDialogueEventWriter.md
RPGProgressionWriter.md
RPGAssetDirector.md
RPGBalanceReviewer.md
RPGPlaytestReviewer.md
```

### RPGCampaignPlanner

Input:

```text
branch_graph.json
game_ir.json
target RPG scope
run policy
optional repair ticket
```

Output:

```text
workspace/rpg/rpg-campaign.json
```

Responsibility:

```text
choose maps
choose primary loop
choose minimum RPG systems
map source story nodes to RPG quests and regions
```

### RPGWorldDesigner

Output:

```text
workspace/rpg/world-map.json
```

Responsibility:

```text
define region list
define map roles
define map connectivity
define unlock order
```

### RPGMapWriter

Output:

```text
workspace/rpg/maps/<map-id>.map.json
```

Responsibility:

```text
author tile grid
collision grid
spawns
NPC placements
interactables
exits
encounter trigger zones
required tileset and sprite assets
```

### RPGQuestDesigner

Output:

```text
workspace/rpg/quests.json
```

Responsibility:

```text
turn story nodes into quest chains
define objective steps
define quest effects
define rewards
ensure quests are completable in map order
```

### RPGSystemDesigner

Output:

```text
workspace/rpg/actors.json
workspace/rpg/classes.json
workspace/rpg/items.json
workspace/rpg/equipment.json
workspace/rpg/skills.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
```

Responsibility:

```text
define stats
define actor classes
define starting inventory
define equipment
define skill costs and effects
define shop inventories
define rest behavior
```

### RPGEncounterDesigner

Output:

```text
workspace/rpg/enemies.json
workspace/rpg/encounter-tables.json
```

Responsibility:

```text
define enemies
define enemy actions
define battle rewards
define drops
define fixed encounter tables
```

### RPGDialogueEventWriter

Output:

```text
workspace/rpg/npc-dialogue.json
workspace/rpg/events.json
```

Responsibility:

```text
write NPC dialogue
bind dialogue to quest state
bind map interactions to events
emit typed event actions
```

### RPGProgressionWriter

Output:

```text
workspace/rpg/progression-rules.json
```

Responsibility:

```text
convert game_ir event rules and quest status into unlock rules
keep source traceability
prevent progression dead ends
```

### RPGAssetDirector

Output:

```text
workspace/asset-direction.json
```

Responsibility:

```text
add RPG-specific asset directions
tilesets
character sprites
NPC sprites
enemy sprites
item icons
skill icons
battle backgrounds
UI frames
portraits if dialogue uses busts
```

### RPGBalanceReviewer

Output:

```text
review findings
```

Responsibility:

```text
simulate early battles
check time-to-kill
check reward economy
check item prices
check rest cost
check first quest difficulty
```

### RPGPlaytestReviewer

Output:

```text
review findings
```

Responsibility:

```text
inspect exported playable
verify movement
verify collision
verify NPC dialogue
verify first battle
verify quest completion
verify save/load if enabled
```

## Asset Pipeline Extensions

Extend asset ids and `kind_for_asset_id` to include:

```text
tileset.
sprite.
enemy.
icon.item.
icon.skill.
icon.equip.
battlebg.
ui.rpg.
```

Add manifest sections:

```json
{
  "tilesets": [],
  "sprites": [],
  "enemy_sprites": [],
  "item_icons": [],
  "skill_icons": [],
  "battle_backgrounds": [],
  "rpg_ui": []
}
```

For the first version, use deterministic generated placeholder assets where model-backed generation is unreliable:

```text
tilesets: local generated sprite sheet or simple colored tile atlas
character sprites: 4-direction chibi sheets, generated or deterministic fallback
enemy sprites: single battle sprite
icons: deterministic icon tiles
```

Model-backed image generation can be used for:

```text
portraits
battle backgrounds
enemy illustrations
tileset concept art
```

But runtime tilemaps need consistent sprite-sheet dimensions, so the exporter must be able to generate normalized fallback sheets.

## Web RPG Runtime

Add a new template:

```text
assets/web-rpg-template/
  index.html
  runtime.js
  style.css
```

Recommended runtime: Phaser 3.

Reasons:

```text
tilemap rendering
sprite movement
collision
camera follow
scene transitions
keyboard controls
pointer controls
portable static web build
```

Avoid pulling Phaser from CDN if offline playability is required. Vendor a fixed minified Phaser build under:

```text
assets/web-rpg-template/vendor/phaser.min.js
```

First runtime scenes:

```text
BootScene
PreloadScene
MapScene
DialogueScene or dialogue overlay
BattleScene
MenuScene
ShopScene
GameOverScene
```

First controls:

```text
Arrow keys / WASD: move
Enter / Space: interact / confirm
Esc: menu
Mouse/touch: menu and battle buttons
```

Runtime systems:

```text
RPGStateStore
QuestLog
Inventory
Equipment
BattleResolver
MapEventRunner
SaveSystem
```

Save format:

```json
{
  "schema_version": "0.1.0",
  "current_map_id": "map.village",
  "player": {"x": 4, "y": 8, "facing": "south"},
  "party": [],
  "inventory": [],
  "equipment": {},
  "quest_status": {},
  "flags": {},
  "defeated_encounters": []
}
```

Use `localStorage` in v1.

## Web RPG Exporter

Add:

```text
scripts/export_web_rpg.py
```

Responsibilities:

```text
validate required RPG manifest exists
copy web-rpg-template
copy generated assets
compile game-data.js
include RPG data and asset lookup
write export report section
```

`game-data.js` shape:

```js
window.RPG_GAME_DATA = {
  metadata: {},
  campaign: {},
  world: {},
  maps: {},
  actors: {},
  classes: {},
  items: {},
  equipment: {},
  skills: {},
  enemies: {},
  encounters: {},
  quests: {},
  dialogues: {},
  events: {},
  shops: {},
  restPoints: {},
  progressionRules: {},
  assets: {}
};
```

Do not reuse `story-data.js`; keep the VN and RPG runtime payloads distinct.

## Validation

Add:

```text
scripts/validate_rpg.py
```

Validation should fail on:

```text
missing required RPG files
invalid JSON
duplicate ids
map size mismatch
invalid tile grid dimensions
spawn outside bounds
NPC outside bounds
NPC placed on collision tile
exit target map missing
exit target spawn missing
quest references missing NPC/dialogue/enemy/item/map
event references missing quest/dialogue/encounter/shop/rest point
enemy drop item missing
equipment slot missing
skill formula unsupported
shop item/equipment missing
rest point effect unsupported
required asset refs missing from asset manifest
```

Warnings should cover:

```text
map has no NPCs
map has no exits and is not terminal/special
quest has no reward
enemy reward economy suspicious
background/tileset size too small
too many random encounters in early map
```

## Balance Simulation

Add:

```text
scripts/simulate_rpg_balance.py
```

The first simulator should run deterministic battles:

```text
starting party vs each required early encounter
party with quest reward equipment vs next encounter
item use allowed
basic skill use allowed
```

Report:

```json
{
  "status": "pass",
  "encounters": [
    {
      "encounter_id": "encounter.slime_pair",
      "win_rate": 1.0,
      "average_turns": 4,
      "lowest_party_hp_percent": 0.35,
      "notes": []
    }
  ],
  "economy": {
    "gold_to_first_weapon": 2,
    "rest_affordability": "ok"
  }
}
```

Fail thresholds for MVP:

```text
mandatory encounter win rate below 0.8
average first battle longer than 8 turns
starter enemy can one-shot the hero
first weapon requires more than 5 standard battles
rest cost exceeds average reward from 4 standard battles
```

## Controller Workflow

Add RPG target flow to `run_pipeline.py`.

High-level build:

```text
validate core design artifacts
project shared state
resolve target, defaulting missing target to web-vn
if target == web-vn or target == mixed-vn:
  existing VN flow
if target == web-rpg:
  validate RPG artifacts
  compile rpg-manifest.json
  plan assets including RPG assets
  generate assets
  validate assets
  simulate balance
  export web-rpg
  write final report
```

Initialization should record target in run metadata:

```json
{
  "target": "web-rpg",
  "pipeline": "rpg"
}
```

This metadata is optional for old runs. The controller must not fail when it is missing.

## Repair Routing

Extend `references/repair-routing.md`:

```text
invalid campaign overview -> RPGCampaignPlanner
invalid world connection -> RPGWorldDesigner
invalid map grid/collision/spawn -> RPGMapWriter
invalid quest reference or impossible quest -> RPGQuestDesigner
invalid actor/item/skill/equipment -> RPGSystemDesigner
invalid enemy/drop/encounter -> RPGEncounterDesigner
invalid dialogue/event action -> RPGDialogueEventWriter
invalid progression unlock -> RPGProgressionWriter
missing RPG asset direction -> RPGAssetDirector
bad battle balance -> RPGBalanceReviewer
runtime export failure -> controller/runtime adapter bug
```

## Documentation Updates

Update:

```text
SKILL.md
references/artifact-contracts.md
references/subagents/README.md
references/repair-routing.md
README.md
```

Add:

```text
references/subagents/post-design/rpg/*.md
assets/web-rpg-template/README.md
references/rpg-artifact-contracts.md
```

Consider putting RPG contracts in a separate `references/rpg-artifact-contracts.md` instead of appending everything to `artifact-contracts.md`, because RPG contracts are much larger than VN gameplay panel contracts.

## MVP Scope

The first playable MVP should include:

```text
1 hub village map
1 field map
1 player actor
1 NPC quest giver
1 fixed encounter
2 enemy types
1 consumable healing item
1 weapon upgrade
1 rest point
1 quest chain
1 reward handoff
1 save/load slot
```

The minimum loop:

```text
spawn in village
talk to NPC
accept quest
walk to field
trigger fixed battle
win reward
return to NPC
complete quest
receive weapon/gold
sleep to recover
unlock next route or end demo
```

Success criteria:

```text
browser opens build/web-rpg/index.html
player can move on a tile map
collision blocks walls
NPC dialogue opens
quest state changes
battle starts and ends
inventory receives reward
rest point restores party
save/load works
final report succeeds
```

## Implementation Phases

### Phase 1: Contracts And Docs

Add RPG contract docs, subagent role cards, repair routing, and skill workflow notes.

No runtime implementation yet.

Verification:

```text
rg old paths
markdown review
git diff --check
```

### Phase 2: RPG Validation Skeleton

Add RPG paths to run layout.

Implement:

```text
scripts/validate_rpg.py
scripts/compile_rpg_manifest.py
```

Accept hand-authored MVP artifacts and produce:

```text
workspace/rpg/rpg-manifest.json
reports/rpg-validation.json
reports/rpg-coverage.json
```

Verification:

```text
python3 -m py_compile scripts/*.py
hand-authored fixture run validates
invalid references fail clearly
```

### Phase 3: Asset Manifest Extensions

Extend asset planning and generation for RPG kinds.

Implement deterministic fallback sheets for:

```text
tileset.*
sprite.*
icon.*
enemy.*
```

Verification:

```text
asset-manifest includes RPG assets
validate_assets accepts generated RPG files
export can copy assets into build/web-rpg/assets
```

### Phase 4: Web RPG Runtime MVP

Create `assets/web-rpg-template/`.

Implement:

```text
MapScene
Dialogue overlay
BattleScene
QuestLog
Inventory
Rest point
SaveSystem
```

Use Phaser 3 or a small canvas runtime. Phaser is preferred unless repository constraints require zero third-party runtime.

Verification:

```text
node --check assets/web-rpg-template/runtime.js
browser smoke: movement, interaction, battle, quest completion
```

### Phase 5: Exporter Integration

Add:

```text
scripts/export_web_rpg.py
run_pipeline.py --target web-rpg
write_report.py RPG fields
```

Verification:

```text
python3 scripts/run_pipeline.py build --run-root runs/rpg-demo --target web-rpg
reports/final-report.json status succeeded
build/web-rpg/index.html opens
```

### Phase 6: Agent Integration

Add RPG post-design role cards and update controller prompts.

The controller should spawn RPG workers only when target is `web-rpg`.

Verification:

```text
generate one RPG run from prompt
validate artifacts
export playable
browser smoke
```

### Phase 7: Balance And Playtest Automation

Add deterministic battle simulation and browser smoke scripts.

Verification:

```text
reports/rpg-balance-report.json pass
reports/rpg-playtest-report.json pass or actionable findings
```

## Data Ownership Boundaries

`branch_graph.json` owns:

```text
high-level narrative topology
major story beats
terminal/convergence intent
player-facing chapter labels
```

`game_ir.json` owns:

```text
semantic state
entities
world rules
source-traceable progression meaning
durable narrative bible
```

`workspace/rpg/*.json` owns:

```text
maps
tile collision
party stats
items
equipment
skills
enemies
quests
dialogue events
shops
rest points
runtime progression
```

`asset-direction.json` owns:

```text
visual intent
asset ids
provider hints
style pack
```

Runtime template owns:

```text
input handling
rendering
collision execution
battle UI
save/load implementation
audio playback
```

Subagents own only typed payload drafts for their assigned artifact.

## Open Design Questions

These can be deferred until implementation:

```text
Use Phaser 3 vendored runtime or hand-written canvas runtime?
Support random encounters in v1, or fixed encounters only?
Support grid pathfinding for NPCs in v1, or static NPCs only?
Support multi-member party in MVP, or single hero first?
Support Yarn dialogue bridge, or typed RPG dialogue only?
Support Tiled import/export, or generated JSON maps only?
```

Recommended MVP answers:

```text
Phaser 3 vendored runtime
fixed encounters only
static NPCs only
single hero first
typed RPG dialogue only
generated JSON maps only
```

## Residual Risks

Tile and sprite assets are harder than VN backgrounds because runtime dimensions must be consistent. Use deterministic fallback sprite sheets before relying on model image generation.

RPG balance can fail silently if only schema validation exists. Add battle simulation before claiming a run is playable.

Quest/event references can become complex quickly. Keep v1 event actions small and typed.

If RPG runtime is implemented inside the VN template, it will become difficult to maintain. Keep `web-rpg-template` separate.

Unity export should not claim RPG support until a real Unity RPG runtime template exists.

## Definition Of Done

The RPG branch is usable when:

```text
SKILL.md documents target web-rpg
RPG role cards exist under references/subagents/post-design/rpg/
RPG artifact contracts are documented
validate_rpg.py catches broken maps, quests, events, and references
compile_rpg_manifest.py produces workspace/rpg/rpg-manifest.json
plan_assets.py supports RPG asset kinds
export_web_rpg.py writes build/web-rpg/
run_pipeline.py can build --target web-rpg
final-report.json includes RPG validation, balance, and export paths
browser smoke confirms movement, dialogue, battle, quest completion, rest, and save/load
```
