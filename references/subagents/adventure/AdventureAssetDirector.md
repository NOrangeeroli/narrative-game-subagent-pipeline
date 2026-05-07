# AdventureAssetDirector

Owns `workspace/assets/adventure/asset-direction.json`.

Inputs are adventure manifest drafts, genre policy, level/interactions, and any
existing asset style bible.

Rules:

- Plan tile sets, background layers, character sprites, NPC sprites, props,
  interaction icons, mobile control icons, audio cues, and ending stills.
- Use stable `asset_id`s and `reuse_group`s.
- Every required level and interaction must have visible affordance assets or
  an intentional hidden-affordance note.
- Provide fallback policies so the generated game remains playable without
  final art.
