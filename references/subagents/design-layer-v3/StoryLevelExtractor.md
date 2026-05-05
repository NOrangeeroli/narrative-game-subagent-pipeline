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

## Output

Return a partial or complete `linear_story.json` payload for exactly one level:

```json
{"level": 1, "level_id": "level_01", "granularity": "chapter", "units": []}
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

## Constraints

- Do not write canonical artifacts.
- Do not inspect sibling shard packets.
- Do not design graph topology, state variables, dialogue, assets, or runtime code.
- Preserve parent/child trace fields requested by the controller.
- Do not postpone obvious canon facts; fact capture is part of this role.
- Output must match `references/design-layer-v3-contracts.md`.
