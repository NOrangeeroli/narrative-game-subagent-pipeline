# Runtime Media Contracts

This reference covers Web RPG media assets that are not ordinary still images:
BGM, SFX, TTS voice lines, runtime motion GIFs, and dynamic map backgrounds.

## Audio

Audio assets are stored under `workspace/generated-assets/audio/` and planned
in the `audio` section of `workspace/asset-manifest.json`.

Required fields:

- `asset_id`: Stable id. Use `bgm.<map>`, `voice.<scope>.<line>`, or
  `sfx.<event>` style ids.
- `kind`: One of `bgm`, `sfx`, or `voice`.
- `file_ref`: Relative output path under `workspace/generated-assets/`.
- `spec.prompt`: Music or SFX prompt.
- `spec.text`: TTS text for voice assets.

Recommended voice fields:

- `speaker`: Human-readable speaker name.
- `voice_id`: Stable logical voice id, usually `voice_profile.<speaker>`.
- `voice_design`: Optional profile with `gender`, `age`, `persona`, `timbre`,
  `style`, and `preview_text`.
- `provider_bindings.minimax-ppio`: Optional provider-specific voice id,
  emotion, speed, pitch, or volume hints.

The Web RPG exporter attaches `voice_asset_id` to NPC dialogue lines and map
event outcome lines when matching audio assets exist. Run
`scripts/audit_audio_coverage.py --run-root <run>` after export to catch
missing or unbound voice lines.

Use `--audio-fallback-provider mock` during iteration. Real provider failures
should not block deterministic layout, boundary, or runtime validation.

## BGM

Each RPG map may set `bgm_asset_id`. If omitted, the compiler assigns
`bgm.<map_id_without_map_prefix>` when that audio asset exists. Runtime BGM is
looped per map and ducked while voice lines are playing.

## Dynamic Backgrounds

Dynamic map backgrounds use asset ids shaped like:

```text
bgv.<map_asset_id>.loop
```

For example, `map.beishan_village` maps to
`bgv.map.beishan_village.loop`.

Generated files live under:

```text
workspace/generated-assets/generated/videos/
```

The exporter copies this folder to:

```text
build/web-rpg/assets/generated/videos/
```

If both `bgv.map.example.loop.mp4` and `bgv.map.example.loop.gif` exist, the
exporter skips the MP4 and binds the runtime asset id to the GIF. This improves
browser compatibility for static servers and mobile LAN previews.

For final-quality Web RPG runs, background generation means both accepted still
maps and dynamic `bgv.*` media. Generate the accepted still `map_asset` first,
run and pass the boundary workflow on that exact still image, then generate the
dynamic background from the same still. Dynamic map backgrounds should come from
PPIO Veo 3.1 Fast first/last-frame I2V by default. Use the accepted still
`map_asset` as both the first frame `image` and the final frame `last_image`,
require locked camera/no terrain drift, and prompt for a seamless continuous
loop. Still `map_asset` inputs must be full-frame 16:9 before I2V; if the
accepted source is square or another ratio, preprocess it into a 16:9 frame
with art-filled edges, not black padding. The still map remains the runtime
fallback only; static and dynamic backgrounds for the same map share one
boundary contract. Local GIF overlays are acceptable for low-tier previews or
when I2V fails, but they should not be described as final-quality dynamic
background generation.

Use:

```bash
python3 scripts/convert_runtime_videos_to_gif.py --run-root <run> --overwrite
```

## Runtime Motion

Runtime motion GIFs live under:

```text
workspace/generated-assets/generated/rpg-motion/
```

Use ids shaped like:

```text
motion.<base_asset_id>.idle
motion.<base_asset_id>.walk.down.1.idle
```

The runtime checks motion ids before falling back to the still image asset.
Keep motion assets short, looping, transparent where relevant, and small enough
for browser playback.

Final-quality player movement requires Sprite Forge walk animation, not just
`motion.<sprite>.idle`. Generate a 4x4 four-direction walk sheet or equivalent
directional frame set for the controllable actor, bind it as a runtime asset,
and set the actor's `walk_sheet_asset_id` or `walk_frame_asset_ids` so movement
uses multi-frame walking art.

## Validation

Minimum post-build media validation:

```bash
python3 scripts/validate_assets.py --run-root <run> --asset-mode final-quality
python3 scripts/audit_audio_coverage.py --run-root <run>
rg "bgv\\.map\\..*\\.gif" <run>/build/web-rpg/game-data.js
```
