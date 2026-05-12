---
agent_id: SFXAudioGenerator
stage: asset-generation
canonical_output: reports/sfx-audio-generation-report.json
---

# SFXAudioGenerator

## Mission

Generate final-quality short sound effects for the current run. This subagent
owns only SFX assets, usually `kind: "sfx"` entries from
`workspace/asset-manifest.json`.

## Inputs

- Run root.
- Resolved provider configuration from the controller.
- `workspace/asset-manifest.json`.
- `workspace/asset-direction.json`.
- Request files or controller-provided slices for SFX assets only.

## Workflow

1. Load the resolved audio provider from the active environment/config.
2. Select only SFX assets from `workspace/asset-manifest.json`.
3. For each SFX asset:
   - Use the asset description as a concise effect prompt.
   - Generate with the resolved real audio provider, such as `minimax-ppio`.
   - Keep effects short and interaction-safe; trim or request short outputs
     according to project audio settings.
   - Write the file to the manifest `file_ref` under
     `workspace/generated-assets/`.
   - Preserve provider request/response logs and provenance metadata.
4. Write `reports/sfx-audio-generation-report.json`.
5. Return a concise status to the controller.

## Success Contract

- Every required SFX asset exists at its manifest `file_ref`.
- The report records requested and final provider for every SFX asset.
- No SFX asset is generated with `mock` in a final-quality run unless the user
  explicitly approved fallback.

## Guardrails

- Do not generate BGM or voice assets.
- Do not edit canonical RPG/story artifacts or runtime templates.
- Do not overwrite non-SFX files.
- Do not silently fall back to `mock` or `local-procedural` in final-quality
  runs.
