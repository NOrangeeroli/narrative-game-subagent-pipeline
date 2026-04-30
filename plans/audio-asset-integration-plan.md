# Audio Asset Integration Plan

## Scope

Integrate the audio demos into the existing post-design asset pipeline. The design layer stays unchanged: story semantics remain in `branch_graph` and `game_ir`, while audio intent is carried by `asset-direction.json`, `required_assets`, Yarn presentation commands, and the generated `asset-manifest.json`.

## Provider Contract

- Add `scripts/asset_audio_providers.py`.
- Support `mock` for offline tests and `minimax-ppio` for the PPIO MiniMax endpoints.
- Read API credentials from environment only:
  - `AUDIO_API_KEY` or `PPIO_API_KEY`
  - optional `AUDIO_BASE_URL`, `AUDIO_MODEL`, `AUDIO_FORMAT`
- Never copy demo fallback keys into this repo.

## Pipeline Changes

- `scripts/plan_assets.py`
  - Plan `bgm.*`, `sfx.*`, and `voice.*` assets into `manifest.audio`.
  - Use browser-friendly generated file refs under `audio/`.
- `scripts/generate_assets.py`
  - Generate audio entries after visual assets.
  - Write prompt snapshots and generation report entries just like image assets.
  - Copy provider hints when supplied.
- `scripts/validate_assets.py`
  - Validate audio files by existence and non-empty size.
- `scripts/export_web_vn.py`
  - Copy generated audio into Web VN exports.
  - Include audio entries in `story.assets`.
  - Attach optional `voice.*` assets to line beats when deterministic IDs match.
- `assets/web-vn-template/runtime.js`
  - Play `play_bgm`, `stop_bgm`, and `play_sfx` through `Audio`.
  - Play line-level `voice_asset_id` once when present.
- `scripts/run_pipeline.py`
  - Add build CLI options for audio provider/model.

## Execution Checklist

1. Add provider adapter and audio prompt/generation helpers.
2. Wire planning, generation, validation, export, and runtime playback.
3. Update CLI and short docs.
4. Run Python/JS syntax checks.
5. Run a smoke test with `mock` audio to prove manifest to export binding.
