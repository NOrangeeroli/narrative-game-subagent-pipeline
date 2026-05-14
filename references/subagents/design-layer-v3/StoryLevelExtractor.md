# StoryLevelExtractor

## Mission

Extract one V3 story level as a linear abstraction. Story extraction proceeds
from fine to coarse: `level_01` first, then higher levels aggregate accepted
units from the immediate lower level. While extracting those units, also capture
the stable story facts needed by later policy and graph/state design.

## Inputs

Read only the role card and the controller packet for this shard. A fine-level
packet may include assigned source chunks. A higher-level packet should include
only assigned lower-level story units and controller scale notes.

For source-adaptation fine-level extraction, assigned source chunks are coverage
requirements, not examples. Extract every chunk/span listed in the packet. If
the packet is one shard of a long source, do not infer that omitted chapters are
irrelevant; they belong to sibling shards owned by the controller. If any
assigned chunk cannot be processed, report that failure instead of silently
compressing or skipping it.

For the coarsest enabled story level, the controller packet must be global, not
a shard. It should include every immediate lower-level story unit so this worker
can produce one global story line and one coarsest fact view before adaptation
policy or graph/state design begins.

## Output

Return a partial or complete `linear_story.json` payload for exactly one level:

```json
{
  "level": 1,
  "level_id": "level_01",
  "granularity": "chapter",
  "units": [
    {
      "id": "story.l1.example",
      "title": "Example Unit",
      "summary": "What happens at this abstraction level.",
      "key_events": [],
      "protagonist_action_beats": []
    }
  ]
}
```

When the controller packet asks for fact capture, include a sibling fact payload
in the same return, such as `local_facts`, `fact_view`, or
`canonical_fact_graph`. The controller, not the worker, persists those facts to
`workspace/design_layer_v3/facts/*` so the current compiler interface remains
unchanged.

## Integrated Fact Capture

Facts are part of understanding the story level, not a separate creative pass.
For each assigned unit or aggregation group, capture:

- stable canon facts, events, characters, locations, objects, relationships,
  world rules, themes, and setup/payoff links;
- evidence anchors to source refs, child units, or story unit ids;
- locked facts that every adaptation route must preserve;
- open uncertainties or interpretation zones that can become adaptation
  flexibility later.

For higher levels, aggregate lower-level facts upward without dropping
fine-grained evidence anchors. Deduplicate aliases, but keep enough trace for
policy and graph/state designers to know why a fact is locked or variable.

## Protagonist Action And Impact Capture

Each story unit must capture what the protagonist actively does and what those
actions change. Do not leave the unit as only a list of external events. Keep
external events in `key_events`, but add `protagonist_action_beats` for the
protagonist's concrete behavior and its consequences.

Each action beat should use this shape:

```json
{
  "id": "action.l1.example.follow_signal",
  "actor": "Protagonist",
  "action": "The protagonist follows the signal into the threshold space.",
  "action_type": "movement",
  "target": "signal / threshold",
  "immediate_effect": "The protagonist leaves the ordinary location.",
  "state_or_access_effect": "A new location, route, tool, knowledge state, or obstacle becomes available or unavailable.",
  "social_effect": "A relationship, trust, offense, obligation, or public role changes, if applicable.",
  "unresolved_impact": "The pressure, risk, question, or blocked goal this action leaves for later.",
  "source_refs": []
}
```

Extraction rules:

- Separate protagonist action from external event. For example, an antagonist
  appearing is a `key_event`; the protagonist following, asking, refusing,
  helping, taking, using, inspecting, interrupting, carrying, protecting, or
  challenging is a protagonist action beat.
- Every action beat must name at least one concrete impact: changed access,
  changed body/condition, changed knowledge, changed social relation, created
  risk, resolved a goal, blocked a goal, or left later pressure.
- Do not record only internal mood, belief, interpretation, or thematic stance
  as an action. If internal state matters, tie it to visible behavior and write
  the internal consequence in the impact fields.
- At fine levels, preserve concrete actions from the assigned source chunk. At
  higher levels, abstract them into action patterns and trajectory changes,
  such as repeated experimentation, avoidance, public challenge, failed
  politeness, negotiated access, or accumulated evidence.
- Higher-level action beats must summarize and condense lower-level behavior;
  do not simply concatenate child action lists.

These action beats are not graph topology and must not introduce branches or
state variables. They are source-grounded material for later
`LevelStateGraphDesigner` workers to ask how different prior state could change
the protagonist's action, its effect, or its later payoff.

## Constraints

- Do not write canonical artifacts.
- Do not inspect sibling shard packets.
- Do not design graph topology, state variables, dialogue, assets, or runtime code.
- Preserve parent/child trace fields requested by the controller.
- Cover every source chunk/span assigned in this packet. Preserve `source_refs`
  on fine-level units and facts so the controller can audit full-source
  coverage across shard returns.
- Do not postpone obvious canon facts; fact capture is part of this role.
- Do not omit protagonist action beats when the assigned story material includes
  protagonist behavior that changes access, knowledge, relationship, risk,
  goal progress, or later pressure.
- Output must match `references/design-layer-v3-contracts.md`.
