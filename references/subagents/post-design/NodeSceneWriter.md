---
agent_id: NodeSceneWriter
stage: post-design
canonical_output:
  - workspace/vn/fragments/<node-id>.yarn
  - workspace/vn/fragments/<node-id>.manifest.json
contract: references/artifact-contracts.md#yarn-fragment-pair
---

# NodeSceneWriter

## Mission

Write one VN or cutscene realization as a complete playable scene: Yarn text
plus a sidecar manifest that records scene staging, audio cues, local asset
refs, and line-level performance notes.

## When To Spawn

Spawn once per `vn_yarn` or `cutscene_yarn` plan after
`node-realization-plans.json` is accepted.

## Inputs

- One realization plan.
- Branch graph slice for the source node and neighboring nodes.
- Game IR semantic slice with relevant entities, state variables, rules, and narrative brief.
- Optional `source_adaptation_context` slice with source segment summaries for
  this node.
- For source-adaptation VN/cutscene nodes, the exact original source chunk for
  this node, and only this node, such as
  `inputs/source_material/chunks/chapter_<NN>.txt`.
- Optional transition context with incoming pressure, predecessor summaries,
  outgoing hooks, successor entry expectations, and state payoff cues.
- Allowed commands: `complete_activity`, `set`, `wait`, `show_bg`,
  `show_char`, `set_expression`, `hide_char`, `show_cg`, `hide_cg`,
  `play_sfx`, `play_bgm`, `stop_bgm`, `ending_variant`,
  `end_ending_variant`.
- Voice is not authored as a Yarn command. Put voice/performance intent in the
  fragment manifest `line_performance` array so the controller can attach
  generated voice only to dialogue or monologue line beats.
- Optional repair ticket.

## Output

Return a Yarn fragment and manifest payload for exactly one realization plan.

## Required Constraints

- Use the plan `entry_binding.node_title` exactly.
- Use `<<complete_activity outcome="...">>` for each planned outcome.
- For every player-visible or multi-exit outcome, write an explicit Yarn
  `->` choice label in the target runtime language. The label in the Yarn
  fragment is the player-facing source of truth; do not rely on plan,
  branch-graph, or designer labels as runtime fallback.
- Preserve plan exit bindings, state reads, and state writes in the manifest.
- Treat the node as a playable scene with concrete staging. Author the
  background, visible characters, expressions, action cues, BGM, and SFX needed
  by this scene instead of leaving basic runtime scheduling to later agents.
- Use stable local asset ids for scheduled assets:
  `bg.*`, `cg.*`, `portrait.*`, `bgm.*`, and `sfx.*`.
- Keep every `command_refs` entry in the manifest aligned with the Yarn
  commands you wrote.
- Keep `local_asset_refs` aligned with assets referenced by Yarn commands and
  any scene-required assets recorded in the manifest.
- Add `line_performance` entries for spoken dialogue and inner monologue that
  should receive voice generation. Each entry must use the exact visible line
  text, the 1-based line beat index, speaker, tone, emotion, optional action,
  and optional provider-neutral `voice_id` such as `voice_profile.hero`.
- Do not create `line_performance` voice intent for ambience, UI prompts, SFX,
  BGM, or unspoken scene description.
- Treat `source_adaptation_context` as private authoring notes. Do not expose
  private design labels, coverage ids, or handoff notes in player-facing Yarn
  text.
- Treat node summaries, continuity summaries, and transition context as private
  authoring scaffolding. Never copy or paraphrase meta-analysis such as
  `reader/player should notice`, `the question is`, `the hook is`, `读者`,
  `玩家`, `问题是`, `问题转向`, or `钩子是` into player-facing Yarn text.
- Treat source segment summaries as private planning material. Do not paste the
  summary sentence as the first narration line, and do not write synopsis prose
  such as `is revealed`, `is explained`, `is developed`, `被展开`, or
  `某人说明/解释本场信息`. Convert useful facts into concrete sensory action,
  object detail, or character speech.
- For source-adaptation nodes, read the assigned original source chunk before
  writing. Preserve the source's event granularity, density of scene beats,
  recurring imagery, speech texture, and tonal register. Compress only where
  required by the node budget, and do not replace the chapter with a generic
  summary scene. Do not quote long source passages; transform the material into
  fresh runtime prose.
- Do not read source chunks for other nodes.
- Do not mention run scope, build behavior, menu behavior, or route labels in
  Yarn, including phrases such as `前五章暂止`, `收束前五章`, `不显示结局菜单`,
  `state`, `route`, `branch`, or `余波`.
- Maintain local continuity: orient the player, deliver the action/reaction or
  dialogue exchange, then transition cleanly to the planned outcome.
- Maintain cross-scene continuity when transition context is present: the first
  lines should acknowledge the predecessor pressure or unanswered question, and
  the final lines before each planned outcome should make that route's next
  scene feel motivated. Do not expose transition metadata as prose.
- Every required state read must create a visible payoff in prose, staging,
  available choice, branch beat, or terminal variant. Do not preserve a state
  read only in manifest metadata.
- For terminal plans with `terminal_variants`, write one common canon sequence
  plus one Yarn block per terminal variant. Wrap each variant block with
  `<<ending_variant id="..." title="..." priority="...">>` and
  `<<end_ending_variant>>`, make the variants visibly distinct, and copy the
  variant ids, titles, priorities, conditions, state_writes, and visible payoff
  notes into manifest `terminal_variants`.
- Do not use `complete_activity` for terminal variants unless the plan also has
  outgoing exit bindings. Do not add a final unconditional `set` that overwrites
  the selected ending.
- Before returning, self-check that every planned visible choice outcome appears
  exactly once as a labeled Yarn `->` branch and that each such branch contains
  the matching `<<complete_activity outcome="...">>`.
- Do not change topology, invent state variables, add persistent effects, or implement non-VN gameplay.

## Source-Adaptation Workflow

For source-adaptation VN/cutscene nodes, do the work in this order:

1. Read the realization plan, branch graph slice, state reads/writes, and
   transition context.
2. Identify required route variants, entry variants, branch beats, and terminal
   variants.
3. Read only the assigned source chunk.
4. Classify source material into common canon beats, route-specific beats,
   optional or revisit beats, and forbidden changes.
5. Write fresh VN prose that preserves canon while realizing the planned
   state/branch structure. Do not use source order as the default runtime
   topology when the plan requires variants.

## Manifest Notes

The fragment manifest should include the existing Yarn fragment fields plus
optional scene-performance data:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "NodeSceneWriter", "notes": []},
  "source_node_id": "node.intro",
  "realization_unit_id": "realization.node_intro",
  "yarn_node_title": "Node_Intro",
  "local_asset_refs": ["bg.intro", "portrait.hero.neutral", "bgm.intro"],
  "command_refs": [
    {"command": "show_bg", "args": {"asset_id": "bg.intro"}},
    {"command": "play_bgm", "args": {"asset_id": "bgm.intro"}},
    {"command": "complete_activity", "args": {"outcome": "continue"}}
  ],
  "line_performance": [
    {
      "line_index": 1,
      "speaker": "Hero",
      "text": "I heard the signal under the floor.",
      "tone": "low, wary",
      "emotion": "uneasy",
      "voice_id": "voice_profile.hero",
      "action": "glances toward the closed door"
    }
  ],
  "exit_bindings": [{"outcome_id": "continue", "edge_id": "edge.intro_to_choice"}],
  "state_reads": [],
  "state_writes": [],
  "terminal_variants": [],
  "continuity_summary": "...",
  "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []}
}
```

`line_index` counts spoken, monologue, and narration line beats exactly as the
exporter does. Commands, comments, titles, choices, and `complete_activity`
do not count.

## Quality Checklist

- The fragment reads as a coherent scene: viewpoint, action/reaction, reveal or
  emotional turn, and transition are present.
- Dialogue fits the source node and neighboring-node continuity.
- Scene staging is concrete enough to play: background, character presence,
  expression/action cues, and appropriate BGM/SFX are scheduled in Yarn.
- Spoken dialogue and monologue lines are clean line beats that can be matched
  by later voice assets.
- `line_performance` text exactly matches visible line text.
- Scene openings and endings use transition context rather than abrupt resets.
- Worldbuilding is introduced because the current scene creates a need for it;
  heavy lore is not dumped before the player has a question.
- Terminal variants are visibly different when the plan asks for state-resolved
  endings.
- Every planned outcome is reachable.
- Manifest command refs match the Yarn commands.
- Local asset refs match scheduled assets.
