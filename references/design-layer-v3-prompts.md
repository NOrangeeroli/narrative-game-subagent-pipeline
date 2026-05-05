# Design Layer V3 Role Cards

Use these role cards for the V3 front-half:

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| StoryLevelExtractor | `subagents/design-layer-v3/StoryLevelExtractor.md` | `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`, plus controller-merged `facts/*` payloads |
| AdaptationPolicyDesigner | `subagents/design-layer-v3/AdaptationPolicyDesigner.md` | `workspace/design_layer_v3/adaptation/global_policy.json` |
| LevelStateGraphDesigner | `subagents/design-layer-v3/LevelStateGraphDesigner.md` | `workspace/design_layer_v3/design_levels/level_<NN>/*` |
| DesignV3CompilerReviewer | `subagents/design-layer-v3/DesignV3CompilerReviewer.md` | Review findings only |

Story extraction runs fine-to-coarse and captures facts in the same pass.
Graph/state design runs coarse-to-fine and is state-first.
Every level supports parallel shard workers by default; the controller owns the
deterministic merge into canonical artifacts.
Only the finest enabled design level, normally L1, exports public/runtime graph
nodes and edges. L2/L3 graph outputs are higher-level design artifacts used for
parent context, result settlement, trace, and validation; their edges and labels
must not become player-visible branch choices.

For V3 post-design realization, pass
`subagents/design-layer-v3/V3PostDesignNetworkedVNOverlay.md` together with the
shared post-design role card when spawning `NodeRealizationPlanner` or
`NodeSceneWriter`. The overlay contains V3-only requirements for visible
network payoff and state-resolved terminal variants; do not put those V3
requirements into shared pipeline validators.

Exact payload shapes are defined in `references/design-layer-v3-contracts.md`.

## Controller Task Prompt

`LevelStateGraphDesigner` is shard-dependent. Use the
`Controller Packet Prompt Template` in
`subagents/design-layer-v3/LevelStateGraphDesigner.md` for each spawned shard,
filling the level id, shard id, assigned story units, parent context, fact view,
policy excerpt, relevant source/fact excerpts, branch permission, and repair
notes.

The following block is the mandatory network target inside that packet for
branch-permitted runs:

```text
This run is intended to produce a visibly networked adaptation, not a linear VN.
A graph where most nodes simply advance to the next chapter or next story unit
is unacceptable unless locked canon or this packet explicitly forbids network
structure.

Preserve source anchoring, but do not preserve strict one-to-one
story-unit/node correspondence. Each same-level story unit is a source anchor
and causal template. Create one or more graph nodes from that anchor when
different prior states would make the event happen differently, fail, delay,
repeat, transform, or be replaced by a canon-compatible consequence. This
applies to L1, L2, and L3; only the abstraction level changes.

Target graph shape for any shard with 5 or more assigned story-unit nodes:
- at least two nodes with outgoing edges to different target nodes;
- at least two source story units expanded into multiple visible graph-node
  variants when the shard has enough material to support it;
- at least one state_gate edge;
- at least one optional, revisit, skip, reorder, or delayed-return route;
- at least one convergence point where route memory remains visible downstream;
- no more than two consecutive nodes with exactly one incoming edge and one
  outgoing edge.

A branch is meaningful only if it changes node order/access, gates or revisits
material, writes state read by later contracts, or changes parent settlement.
Multiple exits to the same target are cosmetic unless downstream contracts read
the divergent state and produce different later content.

Every `player_choice` must be behavior-first. The player should choose an
observable action, speech act, movement, use of an object, refusal/compliance,
inspection, waiting, helping, interrupting, or other external conduct. Do not
make the visible choice primarily a mood, belief, interpretation, or abstract
stance. Internal psychology can be written as state effects and paid off later,
but the branch must start from something the protagonist visibly does.

Before final output, audit:
1. Can two players see a different node order?
2. Can two players skip, delay, or revisit different material?
3. Can earlier choices visibly change later node contracts or route into
   different source-anchored event variants?
4. Do player-visible choices correspond to different external actions rather
   than only different internal attitudes?
5. Does convergence preserve route memory through state reads?
6. Are there at least three distinct valid node sequences?

If not, revise the graph or record the locked-canon exception inside existing
schema fields such as node summaries and settlement reasons. Do not add
non-schema fields.
```
