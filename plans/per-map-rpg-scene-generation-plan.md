# Per-Map RPG Scene Generation Plan

## Goal

Move the Web RPG scene pipeline closer to `rpg_map_designer` by making every RPG map compile into an independent scene package with its own scene spec, grids, asset request, and map-local prop assets.

## Reference

- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/SKILL.md`
- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/references/scene_spec_schema.md`
- `/Users/chenyamei/CUHK/intern/fitx/proj/narrative/rpg_map_designer/skills/rpg-map-designer/scripts/build_scene.py`

## Executed Changes

1. Add per-map scene packages under `workspace/rpg/scenes/<map-slug>/`.
2. Emit `scene-spec.json` in the generic `rpg-map-designer` schema shape.
3. Emit `assets-request.json` per map, with only that map's terrain tiles, scene props, and sprites.
4. Emit `floor_layer.txt`, `barrier_layer.txt`, `collision_layer.txt`, and `interaction_layer.txt` grids per map by rebuilding them from `scene-spec.json`, matching `rpg_map_designer/scripts/build_scene.py`.
5. Validate scene packages for bounds, spawn passability, region reachability, and interactive prop reachability.
6. Localize scene prop assets as `sceneprop.<map-slug>.<prop>` and scene terrain as `tile.<map-slug>.<terrain>` so each package owns its art namespace.
7. Include the scene package report in final reports as `reports/rpg-scene-packages.json`.

## Validation

```bash
python3 -m py_compile scripts/*.py
python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/alice-wonderland-rpg
python3 scripts/validate_assets.py --run-root runs/alice-wonderland-rpg
node --check assets/web-rpg-template/runtime.js
node --check runs/alice-wonderland-rpg/build/web-rpg/runtime.js
```

`runs/alice-wonderland-rpg/reports/rpg-scene-packages.json` currently reports `status: pass` for 5 map packages.

## Remaining Improvement

The next quality jump is to generate map-local prop art with a remote image backend, then screenshot-review each `workspace/rpg/scenes/<map-slug>/` package before the full web export.
