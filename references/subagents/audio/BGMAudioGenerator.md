---
agent_id: BGMAudioGenerator
stage: asset-generation
canonical_output: reports/bgm-audio-generation-report.json
---

# BGMAudioGenerator

## Mission

Generate final-quality BGM assets for the current run. This subagent owns only
background music assets, usually `kind: "bgm"` entries from
`workspace/asset-manifest.json`.

## Inputs

- Run root.
- Resolved provider configuration from the controller.
- `workspace/asset-manifest.json`.
- `workspace/asset-direction.json`.
- Request files or controller-provided slices for BGM assets only.

## Workflow

1. Load the resolved audio provider from the active environment/config. Provider
   priority must already be frozen by the controller: shell environment,
   `<run-root>/.env`, repo `.env`, then user-provided values.
2. Select only BGM/music assets from `workspace/asset-manifest.json`.
3. For each BGM asset:
   - Use the asset description, mood, and style pack as the prompt source.
   - Generate with the resolved real audio provider, such as `minimax-ppio`.
   - Write the file to the manifest `file_ref` under
     `workspace/generated-assets/`.
   - Preserve provider request/response logs and provenance metadata.
4. Write `reports/bgm-audio-generation-report.json`.
5. Return a concise status to the controller.

## Success Contract

- Every required BGM asset exists at its manifest `file_ref`.
- The report records the requested provider and final provider for every BGM.
- No BGM asset is generated with `mock` in a final-quality run unless the user
  explicitly approved fallback.

## Guardrails

- Do not generate SFX or voice assets.
- Do not edit canonical RPG/story artifacts or runtime templates.
- Do not overwrite non-BGM files.
- Do not silently fall back to `mock` or `local-procedural` in final-quality
  runs.
