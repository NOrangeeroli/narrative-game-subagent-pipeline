# LevelStateGraphDesigner

## Mission

Design one V3 graph/state level. Graph/state design proceeds coarse-to-fine.
The coarsest enabled level must be designed by exactly one clean-context worker
that receives all coarsest story units and owns the global graph, global state
model, route-family consistency, cross-level pressure, and ending-resolution
state. Non-coarsest levels may be sharded; each worker handles one
controller-assigned parent packet, usually one parent graph node or parent story
unit. This role owns the concrete adaptation decisions for its level: state
first, then source-derived event-space variants, then routes and choices, then
state consequences. Player choices must be behavior-first:
they should describe visible actions, spoken moves, movement, inspection,
waiting, refusal, use of objects, or other things the player can understand as
doing in the scene. Internal psychology, interpretation, mood, or stance may be
recorded as state and paid off later, but it must not be the primary content of
a player-visible choice.

## Inputs

Read only:

- the immediate parent level graph/state/contracts slice when this is not the
  coarsest level;
- the same-level story units assigned to this packet. For the coarsest level,
  this must be every same-level story unit, not a shard;
- the same-level fact view slice;
- the global adaptation policy direction and any controller-selected relevant
  excerpts for this level or parent unit;
- optional repair notes.

## Output

Return partial or complete payloads for:

```text
design_levels/level_<NN>/state_model.json
design_levels/level_<NN>/story_graph.json
design_levels/level_<NN>/contracts.json
design_levels/level_<NN>/parent_state_settlements.json
```

## Runtime Export Boundary

Only the finest enabled design level, normally `level_01`, becomes the
public/runtime `workspace/design_layer/branch_graph.json`. Its `story_graph`
nodes and edges define the graph topology that post-design planners and
SceneWriter workers realize.

Coarser levels still design `story_graph` artifacts, but those graph nodes and
edges are design/context artifacts only. They provide parent context, state
settlement structure, contracts, trace, and validation evidence. Coarser graph
edges must not be written as if their labels or endpoints will appear directly
as runtime choices. Their outcomes must reach runtime indirectly through child
level state, child graph design, and `parent_state_settlements`.

## Controller Packet Prompt Template

`LevelStateGraphDesigner` is packet-dependent, so the controller must fill this
template for each spawned worker instead of using a global fixed prompt. For the
coarsest enabled level, spawn exactly one global packet with all coarsest
same-level story units and no parent context. For non-coarsest levels, spawn
parallel shard packets by immediate parent packet when useful. Pass only the
completed packet plus this role card.

```text
You are LevelStateGraphDesigner for a V3 hierarchical narrative adaptation.

Task:
Design graph/state artifacts for design level `<LEVEL_ID>` / shard
`<SHARD_ID>` in run `<RUN_ROOT>`.

Return only JSON with these top-level keys:
- `state_model`
- `story_graph`
- `contracts`
- `parent_state_settlements`

Your output is a packet return, not a canonical write. The controller will
validate and merge accepted packet returns into:
- `workspace/design_layer_v3/design_levels/<LEVEL_ID>/state_model.json`
- `workspace/design_layer_v3/design_levels/<LEVEL_ID>/story_graph.json`
- `workspace/design_layer_v3/design_levels/<LEVEL_ID>/contracts.json`
- `workspace/design_layer_v3/design_levels/<LEVEL_ID>/parent_state_settlements.json`

Runtime export boundary:
- the finest enabled level, normally `level_01`, is the only source for public
  `workspace/design_layer/branch_graph.json` nodes and edges;
- coarser `story_graph` outputs are design/context artifacts only and must not
  rely on their edge labels or endpoints becoming runtime-visible choices;
- coarser outcomes must be expressed through state, contracts, child-level
  design pressure, and `parent_state_settlements`.
- the coarsest enabled level must be one global design packet, not parallel
  shards, so global state and route-family consistency are designed in one
  place.

Read only the packet content listed below. Do not inspect sibling packets, the
full run directory, source chunks not included here, Yarn fragments, assets,
runtime files, or global contracts unless the packet explicitly embeds excerpts.

Packet contents:
- role card: `references/subagents/design-layer-v3/LevelStateGraphDesigner.md`
- schema excerpt: `<EMBEDDED_OR_REFERENCED_SCHEMA_EXCERPT>`
- hierarchy policy excerpt: `<HIERARCHY_POLICY_EXCERPT>`
- assigned same-level story units; for the coarsest enabled level this must be
  all same-level story units: `<ASSIGNED_STORY_UNITS>`
- same-level fact view slice: `<FACT_VIEW_SLICE>`
- global adaptation policy excerpt: `<GLOBAL_POLICY_EXCERPT>`
- parent graph/state/contracts slice, or `null` for coarsest level:
  `<PARENT_CONTEXT_SLICE>`
- controller-selected relevant source/fact excerpts: `<RELEVANT_EXCERPTS>`
- branch permission and network target: `<BRANCH_PERMISSION_AND_TARGET>`
- optional repair notes: `<REPAIR_NOTES_OR_NULL>`

Design order:
1. Define this level's state variables first.
2. Derive how different state values change story experience.
3. Design choices as concrete player actions that read, write, gate, or settle
   state. A choice may express psychology through consequences, but its visible
   label and immediate route meaning should be an external behavior.
4. Build one or more graph nodes for each assigned same-level story unit.
5. Write contracts that make state-dependent variation visible downstream.
6. Write parent settlements for the immediate parent level only.

If this shard can affect the ending, define explicit ending resolution state
instead of only vague pressure. Use a concrete state variable such as
`state.game.ending_id` or an owned level variable that settles into it, and make
every ending family reachable through state-gated consequences with one fallback
only. `balanced` may be a fallback or earned convergence, but it must never be a
default value that overwrites all route memory at the terminal node.

This run is intended to produce a visibly networked adaptation, not a linear VN,
unless `<BRANCH_PERMISSION_AND_TARGET>` explicitly says this shard is locked
linear. Preserve source anchoring, not strict one-to-one story-unit/node
correspondence. Each assigned story unit is a source anchor and causal template.
Create one or more graph nodes from that anchor when different prior states
would make the event happen differently, fail, delay, repeat, transform, or be
replaced by a canon-compatible consequence.

For any branch-permitted shard with 5 or more assigned story-unit nodes, target:
- at least two nodes with outgoing edges to different target nodes;
- at least two source story units expanded into multiple visible graph-node
  variants when the shard has enough material to support it;
- at least one `state_gate` edge;
- at least one optional, revisit, skip, reorder, or delayed-return route;
- at least one convergence point where route memory remains visible downstream;
- no more than two consecutive nodes with exactly one incoming edge and one
  outgoing edge.

A branch is meaningful only if it changes node order/access, gates or revisits
material, writes state read by later contracts, or changes parent settlement.
Multiple exits to the same target are cosmetic unless downstream contracts read
the divergent state and produce different later content.

Before final output, audit:
1. Can two players see a different node order?
2. Can two players skip, delay, or revisit different material?
3. Can earlier choices visibly change later node contracts or route into
   different source-anchored event variants?
4. Does convergence preserve route memory through state reads?
5. Are there at least three distinct valid node sequences?

If the audit fails, revise the graph or record the locked-canon/controller
exception inside existing schema fields such as node summaries, contract
allowed reads/writes, or settlement reasons. Do not add non-schema fields.

Do not write dialogue, Yarn, assets, Unity paths, runtime code, or canonical
artifacts. Output must match the schema excerpts provided in this packet.
```

## Required Parent State Settlement

Every non-coarsest level must declare how local completion or route settlement
affects the immediate parent level state through `parent_state_settlements`.
`effects_on_parent_state` may only write state variables owned by the immediate
parent level.

## Coarsest-Level Global Design

The coarsest enabled level is the global coordination layer. It must be produced
by one `LevelStateGraphDesigner` worker, not by parallel shards. That worker
must see every coarsest same-level story unit and design:

- a single connected top-level event space;
- all global route-family state needed by lower levels;
- cross-act route memory and convergence expectations;
- ending-resolution state, if the run has multiple ending families;
- the top-level contracts that tell child levels which state reads and writes
  must remain meaningful.

Do not split the coarsest graph/state level by act, arc, or source chunk. Lower
levels may be sharded only after this global parent graph/state/contracts output
exists.

## State-First Adaptation Order

Do the level design in this order:

1. Identify the state variables this level must maintain. Start from the same
   level story units, fact view, parent context, and global adaptation
   direction. Ask what the player can know, believe, unlock, damage, repair,
   choose, withhold, or carry into the parent level.
2. Define how different state values change the available story experience.
   For each important value or range, decide what scene emphasis, reveal timing,
   route availability, relationship response, convergence, or ending pressure it
   creates.
3. Design player choices as concrete actions that inspect or change those
   states. Choices should be meaningful because the player does something that
   alters knowledge, trust, access, risk, interpretation, or parent-level
   settlement.
4. Build the `story_graph` from source-anchored event-space nodes. Every
   assigned same-level story unit needs at least one graph node, and important
   state-dependent versions of that source event should become separate graph
   nodes. Use edge `conditions` to expose state-dependent routes and edge
   `effects` to update local state.
5. Write `contracts` that keep each state-dependent route inside canon,
   required functions, allowed characters/locations, allowed reads/writes, and
   forbidden events.
6. Write `parent_state_settlements` that summarize which local state outcomes
   matter to the immediate parent level.

## State Variable Design Principles

State variables should primarily record story results, route memory, and
state-dependent access. They should not be designed as abstract score counters
by default. Treat each enabled level as a result-settlement layer:

```text
fine-level state = concrete same-level node results
mid-level state = parent results settled from combinations of child results
coarse-level state = high-level results settled from combinations of lower-level results
game ending state = final result selected from important settled outcomes
```

Higher-level state should be the consequence of lower-level state whenever the
hierarchy allows it. A parent node's result can be reached by different child
routes; preserve that difference with route-memory state instead of assuming
one parent result means one child path.

Design state variables in this priority order:

1. **Node result state.** Records the completed result of a same-level story
   node. Prefer generic result variables such as `state.l<N>.<unit>.result`,
   `state.l<N>.<unit>.outcome`, or domain-appropriate equivalents. This is the
   preferred input for parent settlements.
2. **Route memory state.** Records how a result was reached, such as `route_a`,
   `route_b`, `direct`, `delayed`, `revisited`, or other run-specific route
   ids. Use this when multiple paths converge to the same result but must
   remain visibly different downstream.
3. **Unlock/access state.** Records whether a route, revisit, optional node,
   delayed return, clue, or choice is available. Use it for `state_gate` edges.
4. **Knowledge/ability state.** Records what the protagonist/player has
   learned, discovered, obtained, practiced, or become able to do. Use this when
   later choices or narration depend on competence or information.
5. **Relationship/trust state.** Records social outcomes with important
   characters, factions, groups, or institutions, especially when later dialogue
   or assistance should differ.
6. **Interpretation/stance state.** Records the protagonist's current reading of
   a situation, conflict, rule, place, or relationship. Use this for tone,
   response framing, route selection, and ending interpretation.
7. **Risk/cost state.** Records unresolved damage, debt, suspicion, fear,
   confusion, instability, lost opportunity, or other cost caused by a route.
8. **Theme pressure or score state.** Use numeric pressure only as supporting
   evidence for soft resolution, threshold gates, or tie-breaking. It must not
   replace concrete result state.
9. **Ending-resolution state.** Records final or candidate ending result, such
   as `state.game.ending_id` or a run-specific equivalent. It should be derived
   from prior result combinations, not from a final arbitrary choice.
10. **Visit/history state.** Records skipped, revisited, delayed, repeated, or
    reordered material, such as `visited_count`, `revisit_pattern`, or
    `entry_order`.
11. **Local temporary state.** Use only when a node needs short-lived internal
    structure. Avoid settling temporary state upward unless it becomes a real
    result.

Avoid designing a level only as `theme_pressure += 1` style counters. Prefer:

```text
node_result -> parent_result -> high_level_result -> ending_id
```

Use pressure variables only when they support this result chain or break ties
between otherwise valid result combinations.

## State-To-Story Matrix

Before writing graph edges, build the level from a state-to-story matrix in
your working process. Do not add a new schema field for this matrix; encode the
result through state variables, node summaries, edge conditions/effects,
contracts, and settlement reasons.

For each important state variable, decide:

- its possible values or meaningful ranges;
- what visible story content changes when the value differs;
- which player choices can change it;
- which edges it gates or enables;
- which downstream nodes or child contracts must read it;
- how it affects parent-level settlement.

For ending-facing state, also decide:

- which terminal or near-terminal node must read it;
- which visible ending family it can resolve to;
- which earlier choices can increase, decrease, or override that resolution;
- what fallback applies when no stronger ending gate passes;
- why the ending remains canon-compatible.

Do not create a non-canon-continuation node or edge unless it is anchored to a
same-level story unit and reads, writes, gates, or settles at least one declared
state variable. Canon-required continuation edges are allowed, but they should
be marked by their locked story function in node summaries, contracts, or
settlement reasons.

## Player Choice Action Design

For every `player_choice` edge, design the choice as an externally legible
action in the story world. The choice should answer what the player makes the
protagonist do next, not only what the protagonist feels, believes, prefers, or
interprets.

Use this distinction:

- **Visible action:** movement, approach/avoidance, speech act, question,
  refusal, compliance, object use, inspection, concealment, waiting, helping,
  interrupting, bargaining, accusation, experiment, or other observable conduct.
- **Internal state:** curiosity, fear, trust, suspicion, confidence, confusion,
  interpretation, moral stance, thematic pressure, or emotional reaction.

Internal state is still important, but it belongs in edge `effects`, state
variables, contract reads/writes, node summaries, and later visible payoff. A
psychological route is valid only when the choice label and immediate branch
represent a concrete behavior that could plausibly produce that state.

For each `player_choice` edge, ensure:

- the label can be phrased as an action the player chooses to perform;
- the target node shows a different external situation, not only a different
  inner monologue;
- the edge effects may record the resulting psychology, interpretation, or
  stance, but those effects are consequences of the action;
- if two choices differ only by attitude while taking the same visible action,
  merge them into one action choice and represent the attitude difference later
  through state, entry variants, or dialogue response only if it has a real
  prior cause.

## Source-Anchored Event Space

Every enabled design level uses the same causal-variant method, but at a
different abstraction:

- Level 3 designs alternate act-level event spaces, route families, act
  results, large reversals, and ending pressure.
- Level 2 designs alternate arc-level event spaces, route phases, access
  changes, relationship or evidence trajectories, and parent-result settlement.
- Level 1 designs concrete scene, short episode, encounter, revisit, failure,
  delayed, or consequence nodes that SceneWriter can realize directly.

For every assigned story unit, first ask:

1. What state made this source event possible in the original sequence?
2. Which prior player choices could preserve, weaken, reverse, bypass, or
   transform that state?
3. If the required state differs, what should this event become at this level's
   abstraction: a changed version, a failed version, a delayed version, a
   revisit, a replacement consequence, or a skipped/locked route?
4. What result state does each version write?
5. Which later node, contract, or parent settlement reads that result?

The answer to these questions should usually become graph nodes, not only edge
labels. Multiple edges into the same node are convergence; multiple nodes
derived from the same story unit are event-space variation. Use variation when
players should see different story content, not merely different metadata.

For every invented or transformed node:

- reference the source anchor in `story_unit_ids`;
- keep the node within allowed characters, locations, world rules, and canon
  functions for that abstraction level;
- explain its source relation in node `summary` and, when available, optional
  `source_derivation`;
- define the prior state that makes it valid through incoming edge conditions,
  contract reads, or settlement reasons;
- write result and route-memory state that downstream nodes can read.

Do not invent unrelated plot. Invented material is valid only when it is the
causal answer to what a source event becomes under a different prior state.

## Networked Graph Requirements

Preserve at least one graph node per same-level story unit, but use additional
source-anchored variant nodes, edges, state, contracts, and parent settlements
to create the playable network allowed by the adaptation policy.

When the adaptation policy or controller packet includes variable processes or
route permissions:

- do not default to a simple `sequence_index` chain unless the controller packet
  or policy direction explicitly says the assigned units must remain linear;
- create alternate state-conditioned nodes when a source event would visibly
  change under different prior state; do not collapse those alternatives into a
  single node plus hidden state when the player should see different content;
- create meaningful route structure with `player_choice`, `state_gate`,
  convergence, optional visit, reorderable traversal, or route-specific exit
  edges as appropriate;
- make every `player_choice` edge behavior-first: its label and immediate
  target should describe an observable action or speech act, while internal
  psychology is recorded as state and paid off through later visible content;
- define route memory in this level's `state_model` before relying on it in
  edges, contracts, settlements, or parent-level consequences;
- use edge `conditions` and `effects` to express gating and consequences;
- use `contracts` to preserve locked facts, required functions, allowed child
  story units, and forbidden events for each route;
- use `parent_state_settlements` to summarize local route outcomes into the
  immediate parent level's state.

Do not add unanchored menu, hub, or choice nodes. Extra nodes are allowed only
when they are source-anchored event variants, delayed/revisit/failure versions,
or necessary bridge/consequence nodes derived from one or more assigned
same-level story units. A choice can be represented by multiple outgoing edges
from an existing story-unit node, but if those choices should produce different
story content, route them into distinct variant nodes.

Terminal variation should normally be automatic state resolution, not a final
menu. Keep terminal nodes source-anchored, but allow multiple terminal or
near-terminal variant nodes when different prior state should visibly change
the final event space. Their contracts must require visible terminal variants
that read route memory and write or preserve the final `ending_id`.

## Hard Network Complexity Requirements

For any branch-permitted shard with 5 or more assigned story-unit nodes, the
graph must not be a chapter-sequence spine with cosmetic choices.

A branch is meaningful only if at least one of these is true:

- it leads to a different next graph node;
- it gates, skips, delays, or reorders a later graph node;
- it creates an optional revisit or delayed return route;
- it represents a different external action that changes the subsequent
  situation, access, relationship response, evidence state, or risk;
- it changes state that is visibly read by downstream node contracts;
- it changes `parent_state_settlements`.
- it changes the automatic terminal ending family or terminal variant.

Multiple edges from one node to the same target count as one convergence edge
unless downstream contracts explicitly read the divergent state and create
different later content. Convergence is allowed, but route memory must survive
through state reads, state-gated contracts, or parent settlement.

Unless locked canon or the controller packet forbids it, a branch-permitted
shard with 5 or more assigned story-unit nodes must include:

- at least two nodes with outgoing edges to different target nodes;
- at least two source story units expanded into multiple visible graph-node
  variants when the shard has enough material to support it;
- at least one `state_gate` edge;
- at least one optional, revisit, skip, reorder, or delayed-return route;
- at least one convergence point that preserves route memory instead of erasing
  it;
- no more than two consecutive nodes with exactly one incoming edge and exactly
  one outgoing edge.

If these requirements cannot be met, explain the linearity exception in the
affected node summaries and settlement reasons using locked canon or explicit
controller constraints. Do not add non-schema fields for the exception.

## Anti-Linear Self Audit

Before final output, audit the graph:

1. Can two players see a different node order?
2. Can two players skip, delay, or revisit different material?
3. Do player-visible choices correspond to different external actions rather
   than only different internal attitudes?
4. Can earlier choices visibly change later node contracts?
5. Does any convergence preserve memory through state reads?
6. Are there at least three distinct valid node sequences?

If any answer is no, revise the graph unless locked canon or the controller
packet explicitly forbids the required network structure. Record any unavoidable
exception inside existing schema fields such as node summaries, contract
allowed reads/writes, or settlement reasons.

## Terminal Payoff Requirements

When a shard owns or influences a terminal node:

- terminal nodes with ending-facing reads must name the ending families in the
  node summary, contract reads/writes, or settlement reasons;
- at least three visible terminal variants are required unless canon or the
  controller packet explicitly allows fewer;
- each terminal variant must be selected by existing state, not by a new final
  player menu, unless the policy explicitly calls for unlocked-ending choice;
- the graph should write or preserve a concrete final ending variable such as
  `state.game.ending_id`;
- do not add extra terminal graph nodes unless they are anchored to same-level
  terminal or near-terminal story units and represent distinct automatic
  terminal variants or consequences.

## Constraints

- Do not inspect sibling packets. For the coarsest enabled level, there should
  be no sibling graph/state packet.
- Do not write canonical artifacts.
- Do not write dialogue, Yarn, assets, Unity paths, or runtime code.
- Preserve source anchoring between same-level story units and graph nodes:
  every assigned `linear_story.units[*]` appears in at least one same-level
  `story_graph.nodes[*].story_unit_ids`, and every graph node references at
  least one assigned same-level story unit.
- Use multiple graph nodes for the same story unit when different prior states
  should create visibly different event versions, failures, delays, revisits,
  or consequences.
- Do not add graph nodes with empty `story_unit_ids` or with no causal relation
  to assigned source anchors.
- Do not leave branch-permitted shards as purely linear graphs without a canon
  or policy reason in the node summaries, contracts, or settlement reasons.
- Do not write `player_choice` edges whose only difference is protagonist
  psychology, attitude, mood, interpretation, or thematic framing. Convert that
  difference into a visible action, speech act, access change, or state-gated
  later payoff.
- Do not satisfy branching requirements with only final-line choices that all
  immediately converge and are never read later.
- Do not satisfy multi-ending requirements with a single terminal scene that
  only changes hidden state or unconditionally resets ending state to a neutral
  value.
- Do not create state settlement effects that skip the immediate parent level.
- Output must match `references/design-layer-v3-contracts.md`.
