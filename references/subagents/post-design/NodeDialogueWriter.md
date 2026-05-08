---
agent_id: NodeDialogueWriter
stage: post-design
canonical_output:
  - workspace/vn/fragments/<node-id>.yarn
  - workspace/vn/fragments/<node-id>.manifest.json
contract: references/artifact-contracts.md#yarn-fragment-pair
deprecated_by: NodeSceneWriter
---

# NodeDialogueWriter

`NodeDialogueWriter` is a legacy compatibility name. New runs should spawn
`NodeSceneWriter` instead:

```text
references/subagents/post-design/NodeSceneWriter.md
```

If an existing controller or repair ticket still asks for `NodeDialogueWriter`,
follow the `NodeSceneWriter` role card exactly. The expected output paths remain
the same:

```text
workspace/vn/fragments/<node-id>.yarn
workspace/vn/fragments/<node-id>.manifest.json
```

The role is no longer limited to dialogue. It must author the complete playable
scene: narration, dialogue, scene staging, background commands, character and
expression commands, BGM/SFX commands, and manifest `line_performance` notes for
line-attached voice generation.
