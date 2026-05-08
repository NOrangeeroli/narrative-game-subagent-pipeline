# Web RPG Scene Runtime Parity Plan

## Goal

Bring this repository's `web-rpg` map feel closer to `rpg-map-designer` by moving the map layer from a DOM-grid prototype toward a scene-first canvas runtime with prop-scale rendering, facing-tile interactions, and continuous movement.

Reference baseline:

- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/scripts/build_scene.py`
- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/references/scene_spec_schema.md`
- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/outputs/alice_gothic_castle/game.html`

## Non-Goals

- Do not replace the RPG post-design artifact set.
- Do not remove quest, battle, inventory, save/load, or multi-map support.
- Do not commit or depend on `runs/`.
- Do not require Phaser or another runtime dependency in this slice.

## Execution Slice

### 1. Preserve Scene Runtime Semantics

Files:

- `scripts/compile_rpg_manifest.py`
- `references/rpg-artifact-contracts.md`
- `references/subagents/post-design/rpg/RPGMapBuilder.md`

Actions:

- Add a runtime-facing `scene` object to compiled maps when `map_design` is present.
- Preserve prop rectangles, asset ids, blocking, layer, interaction lines, item ids, render scale, and spawn tile.
- Add per-terrain `tile.<map>.<terrain>` asset ids so the web runtime can stitch real map tiles instead of depending on whole-map backgrounds or free-form atlases.
- Keep existing `layers.ground`, `layers.collision`, `layers.objects`, `layers.overlay`, and `events` output for compatibility.

Acceptance:

```bash
python3 scripts/compile_rpg_manifest.py --run-root runs/alice-wonderland-rpg
python3 - <<'PY'
import json
from pathlib import Path
m=json.loads(Path('runs/alice-wonderland-rpg/workspace/rpg/rpg-manifest.json').read_text())
assert all('scene' in game_map for game_map in m['maps'])
assert sum(len(game_map['scene'].get('props', [])) for game_map in m['maps']) > 0
PY
```

### 2. Export Asset Bounds

File:

- `scripts/export_web_rpg.py`

Actions:

- Compute transparent content bounds for copied PNG assets.
- Include bounds in `game-data.js` as `asset_bounds`.
- Fall back to full-image bounds if alpha is absent or Pillow cannot inspect the asset.

Acceptance:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/alice-wonderland-rpg --skip-assets
python3 - <<'PY'
import re, json
from pathlib import Path
raw=Path('runs/alice-wonderland-rpg/build/web-rpg/game-data.js').read_text()
payload=json.loads(re.sub(r'^window.RPG_GAME_DATA = ', '', raw).rstrip(';\n'))
assert payload.get('asset_bounds')
PY
```

### 3. Canvas Runtime Map Layer

Files:

- `assets/web-rpg-template/runtime.js`
- `assets/web-rpg-template/style.css`

Actions:

- Replace the map DOM grid renderer with a canvas scene renderer.
- Draw `layers.ground` as repeated per-terrain tile images. Fall back to `tileset.*` atlas slicing and then procedural colors only when those tile images are unavailable.
- Keep whole-map backgrounds as a last fallback for maps without layer data.
- Fall back to simple procedural tiles when a map background is missing.
- Draw scene props using content bounds, prop `w/h`, `layer`, and `render_scale`.
- Sort non-floor props, events, and player by y position.
- Keep dialogue, battle, inventory, quest, save/load, and panels.

Acceptance:

```bash
node --check assets/web-rpg-template/runtime.js
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/alice-wonderland-rpg --skip-assets
node --check runs/alice-wonderland-rpg/build/web-rpg/runtime.js
```

### 4. Movement And Facing Interaction

File:

- `assets/web-rpg-template/runtime.js`

Actions:

- Use keydown/keyup key state, not one movement per keydown.
- Move tile-to-tile with pixel interpolation in the render loop.
- Trigger transfer events after movement completes.
- Resolve interactions in this order:
  1. current-tile touch/transfer event
  2. facing-tile event
  3. facing-rect scene prop with interaction or item id
  4. current/four-neighbor event fallback

Acceptance:

Manual browser check:

- Holding WASD/arrow keys continuously moves the avatar.
- Facing an NPC or prop and pressing Space/Enter opens the right dialogue or pickup.
- Transfer tiles still change maps.

### 5. Rebuild Alice Run

Commands:

```bash
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/alice-wonderland-rpg --skip-assets
python3 scripts/validate_assets.py --run-root runs/alice-wonderland-rpg
python3 -m http.server 8787 --bind 127.0.0.1 --directory runs/alice-wonderland-rpg/build/web-rpg
```

Browser URL:

```text
http://127.0.0.1:8787/
```

## Residual Work After This Slice

- Change asset planning to generate per-scene `terrain_atlas`, `object_atlas`, and `hero/npc_sheet` requests instead of one global large manifest batch.
- Promote the per-terrain tile asset path into any future engine exporters, not only `web-rpg`.
- Add screenshot/pixel checks for canvas nonblank state.
- Promote scene-level reachability and per-region interaction checks into the RPG validator.
