# RPG Boundary Contracts

Web RPG maps use pixel-native collision shapes derived from a walkable-area
mask. The mask is positive gameplay space: **cyan/walkable pixels mean the
player may stand there**. Everything outside the accepted walkable mask is
treated as blocked boundary space after vectorization.

Do not generate boundaries by guessing blocked objects first. For final-quality
Sprite Forge maps, generate and validate the walkable mask first, then invert it
to produce blocked `collision_shapes`.

Background generation has a strict dependency order: generate and accept the
still `map_asset` first, derive and validate boundaries from that exact still
image second, then generate dynamic `bgv.<map_asset_id>.loop` media third. The
still map is the fallback visual only. Static and dynamic backgrounds for a map
must share the same `collision_shapes`, event coordinates, start positions,
transfer targets, and walkable hints. Dynamic I2V output must preserve the still
map's camera, scale, roads, bridges, exits, and blocked terrain so the accepted
boundary data remains valid.

## File Location

Boundary files live under:

```text
workspace/rpg/boundaries/<map>.boundaries.json
```

Each map references the file with `boundary_file` or `boundaries_file`.

## Shape Schema

Top-level fields:

- `map_id`: Must match the RPG map id.
- `coordinate_system`: Must be `pixels`; gameplay coordinates match the
  generated background image pixels.
- `description`: Short human-readable physical interpretation.
- `collision_shapes`: Array of `polygon` or `rect` shapes.
- `walkable_hint`: Optional `{ "x": number, "y": number }` used for validation.
- `walkable_mask_ref`: Optional QA sidecar path to the accepted extracted
  walkable mask PNG. This is not runtime art unless the runtime explicitly
  supports masks.
- `boundary_source`: Optional object describing how the boundary was created,
  such as `{"type": "walkable_mask_inversion", "mask_ref": "...",
  "vectorizer": "...", "simplification": 2.5}`.

Polygon shape:

```json
{
  "id": "west_river",
  "type": "polygon",
  "points": [[0, 126], [118, 162], [86, 630], [0, 720]]
}
```

Rect shape:

```json
{
  "id": "north_house",
  "type": "rect",
  "x": 360,
  "y": 140,
  "w": 220,
  "h": 150
}
```

Coordinates are direct image pixels. A `1280x720` map has `x` in
`[0, 1280]` and `y` in `[0, 720]`. Use pixel coordinates for events, start
positions, transfer targets, walkable hints, and collision shapes. Do not author
a `1280 x 720` collision grid; use vector `collision_shapes` and trigger/event
points instead.

## Walkable Mask Workflow

Use this workflow for final-quality map boundaries:

1. Define a required walk graph before final map generation: starts, hubs,
   bridges, stairs, platforms, exits, NPC/event points, and required route
   edges. These points and edges must be reachable in one connected network.
2. Generate the Sprite Forge still map from that walk graph. Require broad,
   readable, connected traversal surfaces; clear bridge/stair overlap; and no
   props on required routes. Do not decide walkability by material name alone:
   flower beds, petals, clover, shallow water, lily pads, grass, moss, and leaf
   surfaces may be walkable when the route design says they are.
3. Treat the accepted still background as a visual QA checkpoint before
   boundary generation. Identify route surfaces that are easy to miss or
   misread, such as flower interiors behind rims, petal ledges, moss or clover
   platforms, shallow-water paths, lily pads, partly hidden stairs, bridges
   under foreground grass, edge exits, and route surfaces covered by shadow or
   perspective overlap. Also identify tempting blocked areas such as deep
   water, dense foliage, rocks, props, flower walls, frame space, and decorative
   foreground cover. This informs the boundary prompt but does not create a
   separate pre-QA artifact.
4. After the still background is accepted, use image generation/editing
   directly on that image to create a same-aspect walkable path boundary mask.
   The prompt should ask the model to mark the actual visible player-walkable
   paths and traversal surfaces in bright cyan at about 50% opacity. It must
   explicitly name the walk graph, the easy-to-miss walkable surfaces, and the
   tempting blocked surfaces to avoid. Do not require a separate pre-QA prompt
   artifact, and do not make exact coordinates the imagegen source of truth.
5. The mask must mark only actual player-walkable regions. It must keep
   required routes continuous, including walkable flower/grass/leaf/water
   surfaces when they are part of the route, and it must bridge through/under
   non-blocking visual occluders. It must not mark blocked regions directly.
5. Extract cyan locally into a binary walkable mask. Denoise, close small gaps,
   remove small islands, and keep the main connected route network.
6. Enforce graph connectivity. If a bridge, stair, platform, exit, or required
   route point is disconnected, repair it with a corridor following the intended
   visible traversal surface. Repairs may cross flowers, grass, clover, shallow
   water, lily pads, petals, moss, leaves, shadows, decorative overlays, or
   foreground perspective cover when those surfaces are intended walkable routes
   or non-blocking occluders; avoid spilling into props, walls, deep water,
   cliffs, furniture, posts, fences, or other truly blocked scenery.
7. Convert boundaries by inversion: `blocked_mask = not walkable_mask`. Extract
   contours from `blocked_mask`, simplify them, and write the result to
   `collision_shapes`.
8. Export two QA previews:
   - walkable preview: background plus cyan walkable mask
   - boundary preview: background plus red blocked/collision shapes

## Authoring Rules

- Prefer mask-first extraction over hand-authored blocker polygons.
- Keep the accepted walkable mask as a QA artifact beside the map.
- Do not block start positions, entry point starts, NPCs, event points, or
  `walkable_hint`.
- Leave bridges and visible roads open even when nearby water or cliffs are
  blocked.
- Bridges and stairs are strong constraints: their walkable mask must overlap
  adjacent roads at both ends.
- Block the outside visual frame so players cannot walk into map edges.
- Keep collision stable across dynamic GIF/video backgrounds.
- Keep `width` and `height` equal to the accepted map image dimensions whenever
  possible, such as `1280 x 720` for 16:9 Web RPG maps.

## Validation

Run after compiling the RPG manifest:

```bash
python3 scripts/validate_boundaries.py --run-root <run>
```

The validator checks shape support, key point bounds, whether key points are
inside collision, and whether key points are reachable from the map's
`walkable_hint` or first known start point.

For walkable-mask generated boundaries, also validate the mask before
vectorization: every start, transfer, bridge center, stair center, platform,
NPC, battle/event point, and required route node must be inside the same
walkable connected component.
