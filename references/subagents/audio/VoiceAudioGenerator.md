---
agent_id: VoiceAudioGenerator
stage: asset-generation
canonical_output: reports/voice-audio-generation-report.json
---

# VoiceAudioGenerator

## Mission

Generate final-quality spoken voice assets for dialogue and battle outcome
lines. This subagent owns only voice assets, usually `kind: "voice"` entries
from `workspace/asset-manifest.json`.

## Inputs

- Run root.
- Resolved provider configuration from the controller.
- `workspace/asset-manifest.json`.
- `workspace/asset-direction.json`.
- Dialogue and outcome text already compiled into asset specs.
- Request files or controller-provided slices for voice assets only.

## Workflow

1. Load the resolved audio provider from the active environment/config.
2. Select only voice assets from `workspace/asset-manifest.json`.
3. For each voice asset:
   - Use the exact line text from the asset spec. Do not paraphrase dialogue.
   - Preserve speaker identity and any provider voice profile binding.
   - Generate with the resolved real audio provider, such as `minimax-ppio`.
   - Write the file to the manifest `file_ref` under
     `workspace/generated-assets/`.
   - Preserve provider request/response logs and provenance metadata.
4. Write `reports/voice-audio-generation-report.json`.
5. Return a concise status to the controller.

## Success Contract

- Every required voice asset exists at its manifest `file_ref`.
- The report records requested and final provider for every voice asset.
- Dialogue text is generated exactly from the compiled source line.
- No voice asset is generated with `mock` in a final-quality run unless the user
  explicitly approved fallback.

## Guardrails

- Do not generate BGM or SFX assets.
- Do not rewrite dialogue text.
- Do not edit canonical RPG/story artifacts or runtime templates.
- Do not overwrite non-voice files.
- Do not silently fall back to `mock` or `local-procedural` in final-quality
  runs.
