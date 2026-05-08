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
- Optional `layers.objects` and `layers.overlay` grids for rendered map props and foreground cover.
- Prefer optional `map_design` for authored layouts: terrain rectangles, paths, houses, trees, gardens, props, NPCs, and player spawn. The compiler expands this into layers, events, canvas scene props, and asset refs.
- `events`: NPCs, battles, pickups, rest points, shops, quests, and transfers. Every event needs an id, type, x, y, and any referenced content ids.

Maps should be immediately playable in the Web RPG exporter: reachable start tile, clear path to important events, and no required event placed inside collision.

Use `map_design` when the scene has spatial structure:

- Default to a compact `40 x 30` outdoor map unless the controller asks for another size.
- Include exactly one `player_spawn` for the map when using `map_design`.
- Connect destinations with path rectangles or horizontal/vertical path lines.
- Put doors, bridges, NPCs, chests, rest points, and quest hooks on or next to reachable tiles.
- Use coherent landmarks instead of random scatter: at least one readable path loop, landmark, NPC, and interaction for vague prompts.
- Supported props are `fence`, `barrel`, `crate`, `chest`, `flower`, `rock`, `tree`, `bridge`, `house_small`, and `house_big`; supported NPC sprite kinds are `npc1` and `npc2`.
- Add `interaction`, `lines`, `item_id`, `event_id`, `layer`, `w`, `h`, or `render_scale` to map props when the scene needs object inspection, pickups, foreground cover, or non-1x1 art placement. The compiler preserves these into runtime `scene.props`.
- The compiler will add `map.<map-slug>`, `tileset.<map-slug>`, per-ground `tile.<map-slug>.<terrain>`, `mapprop.*`, and `sprite.*` asset refs from `map_design`. The playable web runtime uses the per-ground `tile.*` assets for block-stitched terrain; add explicit `map_asset_id`, `tileset_asset_id`, or `sprite_asset_id` only when you need stable fallback or custom art ids.
- During compilation, every authored map becomes an independent `workspace/rpg/scenes/<map-slug>/` package with an `rpg-map-designer`-compatible `scene-spec.json`, `assets-request.json`, and floor/barrier/collision/interaction grids. Treat these packages as the scene-planning surface: each map should have its own terrain identity, prop list, interactions, and reachable scene structure rather than relying on one shared global map image.

## Output Rules

Return JSON only. Use stable ids and keep referenced ids aligned with `RPGContentWriter` outputs.
