# V3 Post-Design Networked VN Overlay

Use this overlay only for Design Layer V3 runs that need visibly networked VN
realization and state-resolved endings. It supplements the shared
`post-design/NodeRealizationPlanner.md` and `post-design/NodeSceneWriter.md`
role cards without changing their global contract.

## NodeRealizationPlanner Overlay

For every branch node:

- plan the player-facing branch as visible scene structure, not only as a
  final-line choice;
- state exactly which beat changes under which state value;
- if multiple exits converge to the same target, name the downstream node or
  later scene that must read the divergent state;
- if the graph cannot make a convergent edge meaningful, request repair instead
  of treating it as a branch.

For every multi-incoming node:

- name the incoming route state expected;
- describe the alternate opening beat or line emphasis;
- name the prior choice being acknowledged;
- name the state variable that preserves that memory.

For terminal VN/cutscene nodes that read ending, route-family, waking-tone, or
final pressure state, add a `terminal_variants` array to the plan. Each variant
uses this shape:

```json
{
  "id": "ending.logic_reclaimed",
  "title": "Logic Reclaimed",
  "priority": 40,
  "conditions": [{"state_variable_id": "state.game.ending_id", "operator": "==", "value": "ending.logic_reclaimed"}],
  "state_writes": [{"state_variable_id": "state.game.ending_id", "operation": "set", "value": "ending.logic_reclaimed"}],
  "visible_payoff": "What concrete lines, images, testimony emphasis, or waking-frame details must differ.",
  "canon_locked_beats": ["Fixed events that must still occur."],
  "variant_beats": ["Specific beat-level instructions for this ending."]
}
```

Rules:

- Use automatic state resolution; do not turn endings into a final visible menu
  unless the graph/policy explicitly asks for it.
- Include at least three terminal variants when the design exposes three or
  more ending families, plus one unconditional fallback only when needed.
- `balanced` may be the fallback or an earned variant, but do not plan an
  unconditional final write that erases stronger route outcomes.
- For canon-locked finales, separate `canon_locked_beats` from
  `variant_beats`: preserve fixed final events while changing testimony,
  defiance, reflection, final title, or postgame summary.
- Every required state read that contributes to ending resolution must appear in
  at least one variant condition or visible payoff note.

## NodeSceneWriter Overlay

Allowed extra V3 terminal commands:

```text
ending_variant
end_ending_variant
```

For source-adaptation nodes, do the work in this order:

1. Read the realization plan, branch graph slice, state reads/writes, and this
   overlay.
2. Identify required route variants, entry variants, branch beats, and terminal
   variants.
3. Read only the assigned source chunk.
4. Classify source material into common canon beats, route-specific beats,
   optional/revisit beats, and forbidden changes.
5. Write fresh VN prose that preserves canon while realizing the state/branch
   structure. Do not use source order as the default runtime topology when the
   plan requires variants.

For every V3 player-visible choice:

- write the visible label in the Yarn `->` branch, in the run's target language;
- cover every planned visible outcome exactly once with a labeled `->` branch
  and a matching `<<complete_activity outcome="...">>` command;
- phrase the visible label as an external behavior, speech act, movement,
  inspection, refusal/compliance, object use, waiting, helping, interruption,
  or other observable conduct. Do not surface the choice mainly as an internal
  mood, belief, interpretation, or abstract stance;
- when design context describes a psychological route, realize it through the
  action that expresses or causes that state, then preserve the psychological
  consequence through state reads/writes and later visible payoff;
- do not depend on L1/L2/L3 designer edge labels, plan labels, or branch-graph
  labels to supply player-facing button text;
- single automatic route exits may use direct `complete_activity`, but any
  exit that can render as a button must have a SceneWriter-authored Yarn label;
- if the provided plan/graph contains a runtime-visible edge that cannot be
  labeled from the scene's own choice structure, request controller repair
  instead of silently using fallback labels.

For terminal plans with `terminal_variants`:

- write one common canon sequence plus one Yarn block per terminal variant;
- wrap each variant block with
  `<<ending_variant id="..." title="..." priority="...">>` and
  `<<end_ending_variant>>`;
- make each variant visibly distinct through testimony emphasis, Alice's final
  stance, waking narration, sister reflection, ending title, or postgame
  summary;
- copy the variant ids, titles, priorities, conditions, state_writes, and
  visible payoff notes into manifest `terminal_variants`;
- do not use `complete_activity` for terminal variants unless the plan also has
  outgoing exit bindings;
- do not add a final unconditional `set` that overwrites the selected ending.

Every required state read must create a visible payoff in prose, staging,
available choice, branch beat, or terminal variant. Do not preserve a state read
only in manifest metadata.
