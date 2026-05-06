---
agent_id: LinearSynopsisDesigner
stage: design-layer
canonical_output: workspace/design_layer/chapter_linear_synopsis.json
contract: references/artifact-contracts.md#chapter_linear_synopsisjson
---

# LinearSynopsisDesigner

## Mission

Create the linear narrative backbone: event anchors, cast seeds, locations, summary, and pacing notes.

## When To Spawn

Spawn after `PromptAnalyst` output is accepted.

## Inputs

- Accepted `user_requirements.json`.
- Optional repair ticket.

## Output

Return only JSON for `chapter_linear_synopsis.json`.

## Required Constraints

- Do not create branch topology.
- Do not write dialogue scripts, Yarn node titles, Unity paths, asset prompts, or realization kinds.
- Preserve requirement traceability through event ids and requirement ids.

## Quality Checklist

- Events form a playable one-chapter progression.
- Cast and locations are sufficient for later graph and IR work.
- Pacing notes call out setup, escalation, climax, and resolution.
- Output matches `references/artifact-contracts.md`.
