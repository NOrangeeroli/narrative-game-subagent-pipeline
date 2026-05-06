# Web RPG Camera, Avatar, and Feedback Effects Plan

## Goal

Upgrade the `web-rpg` runtime from a static grid prototype into a more legible 2D RPG scene viewer while preserving the existing RPG artifact contracts and VN pipeline.

The first execution pass should improve the feel of existing exported games without requiring new mandatory schema fields.

## Compatibility Requirements

- Do not change the default `web-vn` build path.
- Do not make new RPG artifact fields required.
- Existing `workspace/rpg/*.json` runs must still build.
- Existing generated asset sections remain valid.
- If an asset is missing, the runtime must fall back to symbolic markers.

## Execution Steps

1. Add a camera viewport and world layer to `assets/web-rpg-template`.
   - Treat `.map` as the viewport.
   - Create a `.map-world` layer sized by `map.width`, `map.height`, and a fixed tile size.
   - Clamp camera movement at world edges.
   - Center the camera on the player when the world is larger than the viewport.

2. Replace the `@` player marker with an avatar.
   - Use the current actor's `sprite_asset_id` when available.
   - Fall back to `sprite.<actor-slug>` or a symbolic avatar when no sprite exists.
   - Track facing direction from movement input.
   - Add walking/bobbing animation on movement.

3. Render event sprites instead of only icon markers.
   - NPC events use `event.sprite_asset_id` or `sprite.<event-id-suffix>` when available.
   - Battle events use the referenced enemy sprite.
   - Pickup events use item icons.
   - Rest, quest, shop, and transfer events keep clear symbolic fallbacks.
   - Add pulse/highlight styling for nearby interactables.

4. Add interaction feedback.
   - Show a near-player interaction hint with the event name and input.
   - Add floating text for pickups, rest, quest updates, battle rewards, and completion.
   - Add quick map flash/fade feedback for transfer and important interactions.

5. Add dialogue and battle polish.
   - Dialogue box displays the speaker/event portrait when a matching sprite exists.
   - Battle attacks shake or flash the enemy visual.
   - Damage numbers float over the battle panel.
   - Victory uses a visible reward/completion feedback effect.

6. Re-export the existing `runs/yu-gong-rpg` playable using `--skip-assets`.
   - This updates runtime files without regenerating assets.
   - Keep `runs/` ignored and out of commits.

7. Validate.
   - `node --check assets/web-rpg-template/runtime.js`
   - `python3 -m py_compile scripts/*.py`
   - `python3 scripts/run_pipeline.py build --target web-rpg --run-root runs/yu-gong-rpg --skip-assets`
   - `node --check runs/yu-gong-rpg/build/web-rpg/runtime.js`
   - Confirm final report status remains `succeeded`.

## Later Work

- Add true multi-frame walking spritesheets to `asset-manifest.json`.
- Add generated character portraits distinct from map sprites.
- Add object layer depth sorting and occlusion.
- Add audio cues for interact, battle hit, quest complete, and transfer.
- Add directional collision-aware animation queues instead of one-tile immediate movement.
