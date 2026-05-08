# Design Layer V3 Controller Prompt Templates

These are controller-facing dispatch templates for clean-context V3 subagents.
Role behavior lives in the role cards under
`references/subagents/design-layer-v3/`; this file defines the spawn prompt
shape.

Use these role cards with the templates below for the V3 front-half:

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| StoryLevelExtractor | `subagents/design-layer-v3/StoryLevelExtractor.md` | `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`, plus controller-merged `facts/*` payloads |
| AdaptationPolicyDesigner | `subagents/design-layer-v3/AdaptationPolicyDesigner.md` | `workspace/design_layer_v3/adaptation/global_policy.json` |
| LevelStateGraphDesigner | `subagents/design-layer-v3/LevelStateGraphDesigner.md` | `workspace/design_layer_v3/design_levels/level_<NN>/*` |
| DesignV3CompilerReviewer | `subagents/design-layer-v3/DesignV3CompilerReviewer.md` | Review findings only |

Story extraction runs fine-to-coarse and captures facts in the same pass.
Graph/state design runs coarse-to-fine and is state-first.
For source adaptations, finest-level `StoryLevelExtractor` packets must cover
the full `inputs/source_material/source_index.json` inventory across shards.
The controller may split the source for clean-context parallelism, but it must
not send only representative chapters or proceed while any source chunk/span is
unassigned or missing from accepted shard returns.
Long source-adaptation VN runs should enable three levels by default: L1
source scene/chapter chunks, L2 arc packets, and L3 global story/design. L1 and
L2 are non-coarsest and must use scoped shard packets; L3 is the global
coordination layer. Non-coarsest workers must receive only assigned slices, not
complete same-level or complete lower-level artifacts.
The coarsest enabled `StoryLevelExtractor` pass must be exactly one global
clean-context worker. It receives every immediate lower-level story unit and
returns the global story line plus the coarsest fact view; do not split the
coarsest story line by act, arc, or source chunk. This global worker still sees
only immediate child summaries/fact view, not full source, all L1 detail, or
lower-level design artifacts.
The coarsest enabled graph/state level must be designed by exactly one
clean-context `LevelStateGraphDesigner` worker, because it owns the global
graph, global state model, route-family consistency, and ending-resolution
state. Non-coarsest graph/state levels may use parallel shard workers by
immediate parent packet; the controller owns the deterministic merge into
canonical artifacts.
Only the finest enabled design level, normally L1, exports public/runtime graph
nodes and edges, including edge `conditions` and `effects`. L2/L3 graph outputs
are higher-level design artifacts used for parent context, result settlement,
trace, and validation; their edges and labels must not become player-visible
branch choices.

For V3 post-design realization, pass
`subagents/design-layer-v3/V3PostDesignNetworkedVNOverlay.md` together with the
selected branch role card. Standard `vn` spawns `NodeRealizationPlanner` or
`NodeSceneWriter` from `subagents/post-design/vn/`. `advanced-vn` spawns
`AdvancedVNRealizationPlanner` or `AdvancedVNSceneDesigner` from
`subagents/post-design/advanced-vn/`. The branch role cards contain the generic
networked VN, terminal variant, source-adaptation, choice-label, or Scene IR
rules. The V3 overlay only explains V3-specific artifact interpretation:
finest-level public graph boundaries, higher-level trace context, and the rule
that L2/L3 designer labels must not become runtime button text.

Exact payload shapes are defined in `references/design-layer-v3-contracts.md`.

## Controller Task Prompt

`StoryLevelExtractor` is packet-dependent. For source-adaptation `level_01`,
create one or more shard packets whose assigned source chunks together cover
every entry in `inputs/source_material/source_index.json`. Each packet should
list its assigned chunk ids/paths, coverage scope, granularity, scale notes, and
fact-capture requirements. Wait for every shard return and verify complete
chunk/span coverage before writing canonical `level_01/linear_story.json`,
`facts/level_01/local_facts.json`, or any higher-level story artifact.

For the coarsest enabled story level, create exactly one global
`StoryLevelExtractor` packet. It must include all immediate lower-level story
units, the lower-level fact view or canonical fact graph, hierarchy policy
excerpt, aggregation scale notes, and fact aggregation requirements. The
coarsest story level is not parallel-sharded.

Every StoryLevelExtractor packet must include a `scope` object with role, level,
`shard_id`, `global`, assigned source chunk ids or assigned lower-level story
unit ids, allowed input paths, and forbidden input path patterns. For
non-coarsest higher-level extraction, `assigned_lower_level_unit_ids` must be a
strict slice and `allowed_input_paths` should point to a controller-made slice
file or embedded excerpts, not the full lower-level `linear_story.json`.
Controller-made slice files under `story_levels/level_<NN>/slices/` and
`facts/level_<NN>/slices/` must be deterministic projections from canonical
artifacts. They are reproducible input views, not subagent-authored artifacts and
not alternate canon.

## StoryLevelExtractor Spawn Prompt Template

```text
You are StoryLevelExtractor for a V3 hierarchical narrative adaptation.

Clean-context rule:
Read only the role card and this controller packet. Do not inspect sibling
packets, the run directory, source chunks not embedded or listed in the packet,
global contracts, runtime files, Yarn fragments, assets, or code.

Inputs:
- role card: references/subagents/design-layer-v3/StoryLevelExtractor.md
- packet: <PACKET_PATH_OR_EMBEDDED_PACKET>
- scope declaration: <SCOPE>
- level id: <LEVEL_ID>
- shard id: <SHARD_ID_OR_GLOBAL>
- assigned source chunks for finest-level extraction, or assigned immediate
  lower-level story units for higher-level aggregation: <ASSIGNED_MATERIAL>
- hierarchy policy excerpt: <HIERARCHY_POLICY_EXCERPT>
- fact capture / aggregation requirements: <FACT_REQUIREMENTS>
- output write target for raw return: <RAW_RETURN_PATH>

Coverage:
- For source-adaptation level_01, extract every assigned chunk/span. Across all
  sibling level_01 shard packets, the controller must cover every
  source_index.json entry; do not treat assigned chapters as examples.
- For the coarsest enabled story level, this packet is global, not a shard. It
  must cover every immediate lower-level story unit and produce one global story
  line / fact view.

Return only JSON with:
- linear_story
- local_facts, fact_view, or canonical_fact_graph as requested by the packet
- coverage_report or failures for assigned material

Do not write canonical artifacts. If the packet asks you to persist a raw return,
write only the raw packet return to <RAW_RETURN_PATH>.
```

## AdaptationPolicyDesigner Spawn Prompt Template

```text
You are AdaptationPolicyDesigner for a V3 hierarchical narrative adaptation.

Clean-context rule:
Read only the role card and this controller packet. Do not inspect the run
directory, source chunks, graph/state artifacts, runtime files, Yarn fragments,
assets, or code unless excerpts are embedded in this packet.

Inputs:
- role card: references/subagents/design-layer-v3/AdaptationPolicyDesigner.md
- packet: <PACKET_PATH_OR_EMBEDDED_PACKET>
- coarsest enabled linear_story excerpt or full artifact: <COARSEST_STORY>
- canonical fact graph excerpt or full artifact: <CANONICAL_FACTS>
- user adaptation brief and constraints: <ADAPTATION_BRIEF>
- source/fact evidence anchors selected by the controller: <EVIDENCE_ANCHORS>
- output write target for raw return: <RAW_RETURN_PATH>

Task:
Define global adaptation direction only: route families, tone/style, canon
locks, forbidden changes, allowed variable processes, ending families, and broad
permissions. Do not design concrete level graphs, exact state variables, edges,
choice labels, dialogue, assets, or runtime implementation.

Return only JSON shaped as adaptation/global_policy.json. Do not write canonical
artifacts unless the packet explicitly asks you to write the raw return to
<RAW_RETURN_PATH>.
```

`LevelStateGraphDesigner` is packet-dependent. For the coarsest enabled level,
spawn one global designer packet containing all same-level story units and no
parent context. For every non-coarsest level, use the separate spawn prompt
template below for each spawned shard, filling the level id, shard id, assigned
story units, parent context, fact view, policy excerpt, relevant source/fact
excerpts, branch permission, and repair notes.

Every LevelStateGraphDesigner packet must include a `scope` object with role,
level, `shard_id`, `global`, assigned same-level story unit ids, parent
story/graph ids when applicable, allowed input paths, and forbidden input path
patterns. For non-coarsest design, pass parent graph/state/contracts slices and
assigned same-level story-unit slices only. The coarsest design packet is global
but must not include lower-level story or design artifacts.
Story/fact/policy slices passed to non-coarsest designers must be deterministic
controller projections from canonical artifacts. Designers must treat them as
read-only local views and must not infer that omitted sibling material is absent
from the run.

## LevelStateGraphDesigner Spawn Prompt Template

```text
You are LevelStateGraphDesigner for a V3 hierarchical narrative adaptation.

Clean-context rule:
Read only the role card and this controller packet. Do not inspect sibling
packets, the full run directory, source chunks not embedded here, Yarn
fragments, assets, runtime files, code, or global contracts unless excerpts are
embedded in this packet.

Task:
Design graph/state artifacts for design level `<LEVEL_ID>` / shard
`<SHARD_ID>` in run `<RUN_ROOT>`.

Return only JSON with these top-level keys:
- `state_model`
- `story_graph`
- `contracts`
- `parent_state_settlements`

Your output is a packet return, not a canonical write. The controller validates
and merges accepted packet returns into `workspace/design_layer_v3/design_levels/<LEVEL_ID>/`.

Runtime export boundary:
- the finest enabled level, normally `level_01`, is the only source for public
  `workspace/design_layer/branch_graph.json` nodes and edges;
- coarser `story_graph` outputs are design/context artifacts only and must not
  rely on their edge labels or endpoints becoming runtime-visible choices;
- coarser outcomes must be expressed through state, contracts, child-level
  design pressure, and `parent_state_settlements`;
- the coarsest enabled level must be one global design packet, not parallel
  shards, so global state and route-family consistency are designed in one
  place.

Layered refinement:
- each level owns a state model. Higher levels define coarser story results,
  route functions, pressure, and contracts; lower levels refine those parent
  results with concrete event-space, local state, route memory, and visible
  consequences;
- this applies to every graph node, not only endings. Preserve the assigned
  `parent_node_id` meaning: higher level says what happened or what role the
  unit serves; lower level says how it specifically happens and which local
  route produced it;
- use local result state and route memory to distinguish child variants that
  still settle to the same parent result;
- if this packet needs to change the parent result, parent state model, or
  parent contract itself, return a repair note for the higher level instead of
  inventing a contradictory child node.

Ending ownership:
- ending ownership is the terminal case of layered refinement: higher-level
  endings are defined by higher-level state, while lower-level variants refine
  that inherited result with additional lower-level state;
- for the coarsest enabled level, design every terminal ending family node,
  unique `ending_id`, high-level state values that determine each family,
  fallback ordering, and an ending matrix covering route family, preserved
  canon, cost, unresolved pressure, and required prior state;
- for non-coarsest levels, do not invent new ending family ids. If this packet
  expands an inherited ending, keep the parent `ending_id`, add an
  `ending_variant_id` only for the local refinement, and name the lower-level
  state variables that make the variant distinct;
- if a lower-level packet needs to change the higher-level ending result
  itself, return a repair note for the higher level instead of creating a new
  `ending_id`.

Packet contents:
- role card: references/subagents/design-layer-v3/LevelStateGraphDesigner.md
- scope declaration: <SCOPE>
- schema excerpt: <EMBEDDED_OR_REFERENCED_SCHEMA_EXCERPT>
- hierarchy policy excerpt: <HIERARCHY_POLICY_EXCERPT>
- assigned same-level story units; for the coarsest enabled level this must be
  all same-level story units: <ASSIGNED_STORY_UNITS>
- same-level fact view slice: <FACT_VIEW_SLICE>
- global adaptation policy excerpt: <GLOBAL_POLICY_EXCERPT>
- parent graph/state/contracts slice, or null for coarsest level:
  <PARENT_CONTEXT_SLICE>
- controller-selected relevant source/fact excerpts: <RELEVANT_EXCERPTS>
- branch permission and network target: <BRANCH_PERMISSION_AND_TARGET>
- optional repair notes: <REPAIR_NOTES_OR_NULL>

Design order:
1. Define this level's state variables first.
2. Derive how different state values change story experience.
3. Design choices as concrete player actions that read, write, gate, or settle
   state.
4. Build one or more graph nodes for each assigned same-level story unit.
5. Write contracts that make state-dependent variation visible downstream.
6. Write parent settlements for the immediate parent level only.
7. When applicable, bind terminal nodes to declared ending families and local
   variants without changing the inherited high-level ending result.

For branch-permitted packets, include the mandatory network target block from
this file. If the packet can affect endings, define explicit ending resolution
state instead of only vague pressure.

Do not write dialogue, Yarn, assets, Unity paths, runtime code, or canonical
artifacts. Output must match the schema excerpts provided in this packet.
```

## DesignV3CompilerReviewer Spawn Prompt Template

```text
You are DesignV3CompilerReviewer for a V3 hierarchical narrative adaptation.

Clean-context rule:
Read only the role card and this controller packet. Do not inspect the run
directory or open additional artifacts. Review only the reports, assembled
artifacts, diffs, and contract excerpts embedded or listed in this packet.

Inputs:
- role card: references/subagents/design-layer-v3/DesignV3CompilerReviewer.md
- packet: <PACKET_PATH_OR_EMBEDDED_PACKET>
- validation report excerpt: <VALIDATION_REPORT>
- compile report excerpt: <COMPILE_REPORT>
- assembled public artifact excerpts, if relevant: <ASSEMBLED_ARTIFACTS>
- contract excerpts selected by controller: <CONTRACT_EXCERPTS>
- repair scope limits: <REPAIR_SCOPE>

Return findings only. Each finding must include severity, artifact path, relevant
ids, evidence from the packet, and the narrowest repair recommendation. Do not
rewrite artifacts unless the packet explicitly asks for a narrow patch
suggestion.
```

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
