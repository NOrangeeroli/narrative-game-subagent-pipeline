# Subagent Role Cards

Use this index to pick the exact role card and prompt template for a subagent
spawn. Read only the role card needed for the current spawn, then pass only the
minimum upstream artifacts listed there.

Do not set a `model` override when spawning subagents.

## Clean-Context Dispatch Rules

The controller owns global workflow context and run navigation. Every subagent
spawn must be clean-context: subagents receive a compact controller packet and a
role card, not an open-ended instruction to inspect the run directory.

- Controller may read contracts, validation scripts, source extraction files, and all accepted artifacts.
- Normal authoring subagents read only their exact role card plus the packet prepared for that spawn.
- Store reusable dispatch packets under `workspace/controller-packets/`. Each packet should list included upstream artifact paths and source slices.
- For long source adaptations, pass source material as assigned slices from `inputs/source_material/chunks/` or summaries derived from accepted story extraction artifacts, not as the full extracted text unless the role card explicitly requires whole-source profiling.
- Use the separate controller-facing prompt template file named in this index for
  every spawn. Do not put prompt templates inside role cards, and do not dispatch
  a subagent with only a loose natural-language task.
- Every controller packet must include a machine-readable scope declaration:
  role, level, `shard_id`, `global`, assigned source chunk ids or story unit ids,
  parent story/graph ids when applicable, allowed input paths, and forbidden
  input path patterns. Non-coarsest packets must point to controller-made slices
  or embed selected excerpts; they must not point workers at full same-level,
  full lower-level, or sibling-shard artifacts.
- `linear_story.json` is the merged controller-owned artifact for validation and
  compile. For long levels, deterministically project shard-sized
  `story_levels/level_<NN>/slices/*.json` files from canonical artifacts and use
  those as subagent inputs. Slice files are reproducible controller projections,
  not creative outputs and not accepted canonical artifacts. A shard worker
  should never need to open a long full-level `linear_story.json`.

When V3 `StoryLevelExtractor` is sharded for a source adaptation, the controller
must cover the whole `inputs/source_material/source_index.json` inventory across
fine-level shard packets. A shard receives only its assigned chunks, but the
shard set as a whole must include every chapter/chunk/span. The controller waits
for all shard returns, stores raw returns under
`workspace/design_layer_v3/story_levels/level_01/shard_returns/`, audits
coverage, and only then writes canonical `level_01/linear_story.json` and
`facts/level_01/local_facts.json`.

## Design Layer V1

These agents produce the direct V1 design module. They may depend on earlier design-layer outputs, but downstream agents should receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.

| Agent | Role Card | Prompt Template | Canonical Output |
| --- | --- | --- | --- |
| PromptAnalyst | `design-layer/PromptAnalyst.md` | `../design-layer-prompts.md#promptanalyst-template` | `workspace/design_layer/user_requirements.json` |
| LinearSynopsisDesigner | `design-layer/LinearSynopsisDesigner.md` | `../design-layer-prompts.md#linearsynopsisdesigner-template` | `workspace/design_layer/chapter_linear_synopsis.json` |
| BranchGraphDesigner | `design-layer/BranchGraphDesigner.md` | `../design-layer-prompts.md#branchgraphdesigner-template` | `workspace/design_layer/branch_graph.json` |
| BaseGameIRDesigner | `design-layer/BaseGameIRDesigner.md` | `../design-layer-prompts.md#basegameirdesigner-template` | `workspace/design_layer/game_ir.json` |

For V1, `branch_graph.edges[*].conditions` and
`branch_graph.edges[*].effects` are the public runtime transition interface.
`BranchGraphDesigner` writes edge-local gates/effects directly on the graph;
`BaseGameIRDesigner` declares the referenced state variables and mirrors
non-trivial edge semantics in `game_ir.event_rules`.

## Design Layer V3

V3 is the hierarchical source-adaptation design module. It uses hierarchical
story abstraction and hierarchical graph/state design, then compiles into the
same public runtime interface as V1: `workspace/design_layer/branch_graph.json`
and `workspace/design_layer/game_ir.json`.
The public/runtime `branch_graph.json` is exported from the finest enabled
design level only, normally `level_01`. Higher-level `story_graph` outputs are
design/context artifacts for state settlement, parent contracts, trace, and
semantic validation; they must not create runtime-visible nodes, edges, or
choice labels. Higher-level state variables and `parent_state_settlements` may
still contribute to `game_ir.json`.

Story extraction runs fine-to-coarse and captures stable facts as part of the
same pass. Graph/state design runs coarse-to-fine and is state-first: each level
first defines the state it owns, then derives state-dependent routes, choices,
effects, contracts, and parent settlements.
For branch-permitted runs, `LevelStateGraphDesigner` task packets must require
visible network topology rather than a simple story-unit sequence: different
node orders or access, state gates, optional/revisit/delayed routes, convergence
with route memory, and downstream contracts that read prior route state.
Use the V3 controller-facing templates in
`references/design-layer-v3-prompts.md` for each level/shard worker.
For long novel/VN adaptations, enable three levels by default: L1 source
scene/chapter chunks, L2 arc packets, and L3 global story/design. Non-coarsest
story extraction levels use parallel clean-context workers by default and each
worker receives only its assigned immediate-child slice. The coarsest enabled
story level must be one global `StoryLevelExtractor` packet that sees every
immediate child story unit summary and produces the global story line/fact view,
but it must not receive full source text, all L1 detail, or lower-level design
artifacts. For graph/state design, the coarsest enabled level is also global:
the controller must spawn exactly one clean-context `LevelStateGraphDesigner`
with all coarsest story units so the global graph, global state model,
route-family consistency, and ending-resolution state are designed coherently.
Every non-coarsest graph/state level must be sharded by immediate parent packet.
The controller stores raw returns under that level's `shard_returns/` and
performs the deterministic merge into canonical artifacts.

Minimum V3 input packets:

| Agent | Minimum Packet Contents |
| --- | --- |
| StoryLevelExtractor | One story level id, scope declaration, assigned source chunks for the finest level or assigned immediate lower-level story-unit slice for higher levels, granularity and scale notes, plus fact-capture requirements. For source-adaptation `level_01`, all shard packets together must cover every chunk/span in `inputs/source_material/source_index.json`; representative chapters are not sufficient. For non-coarsest higher levels, do not pass the full lower-level `linear_story.json`; pass only the assigned child-unit slice. For the coarsest enabled story level, use exactly one global packet containing all immediate lower-level story unit summaries. |
| AdaptationPolicyDesigner | Coarsest enabled `linear_story.json`, `facts/canonical_fact_graph.json`, user adaptation brief, and global constraints. |
| LevelStateGraphDesigner | Coarsest level: one global packet containing all coarsest same-level story units, same-level fact view, global adaptation policy direction, and no parent context. Non-coarsest levels: one parent packet with immediate parent graph/state/contracts slice, assigned same-level story-unit slice, same-level fact/policy slice, and any controller-selected relevant excerpts. Do not pass all same-level story units or all parent graph/state artifacts to a non-coarsest worker. |
| DesignV3CompilerReviewer | V3 validation reports, compile report, assembled public artifacts, and only contract excerpts needed to explain failures. |

| Agent | Role Card | Prompt Template | Canonical Output |
| --- | --- | --- | --- |
| StoryLevelExtractor | `design-layer-v3/StoryLevelExtractor.md` | `../design-layer-v3-prompts.md#storylevelextractor-spawn-prompt-template` | `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`, plus controller-merged `facts/*` payloads |
| AdaptationPolicyDesigner | `design-layer-v3/AdaptationPolicyDesigner.md` | `../design-layer-v3-prompts.md#adaptationpolicydesigner-spawn-prompt-template` | `workspace/design_layer_v3/adaptation/global_policy.json` |
| LevelStateGraphDesigner | `design-layer-v3/LevelStateGraphDesigner.md` | `../design-layer-v3-prompts.md#levelstategraphdesigner-spawn-prompt-template` | `workspace/design_layer_v3/design_levels/level_<NN>/*` |
| DesignV3CompilerReviewer | `design-layer-v3/DesignV3CompilerReviewer.md` | `../design-layer-v3-prompts.md#designv3compilerreviewer-spawn-prompt-template` | Review findings only |

Every non-coarsest `LevelStateGraphDesigner` output must include
`parent_state_settlements.json`, declaring how this level's local state
settlement affects the immediate parent level's state. `effects_on_parent_state`
must not skip levels.

## Post Design

These agents run after the design layer. They should not reopen requirements or synopsis by default; use the durable downstream context in `game_ir.design_brief`, the graph topology in `branch_graph.json`, and controller-provided slices.
For networked outputs, `NodeRealizationPlanner` must preserve visible branch
structure in the realization plan: choice placement, state-gated beat changes,
route-memory payoff, and entry variants for nodes reached from different routes.
`NodeSceneWriter` owns runtime-visible Yarn `->` choice labels and terminal
variant prose. For V3 runs, pass
`design-layer-v3/V3PostDesignNetworkedVNOverlay.md` only to preserve the
finest-level public graph boundary and treat L2/L3 artifacts as trace context.
Use `references/post-design-prompts.md` for controller-facing dispatch
templates. For large source-adaptation VN runs, the controller may batch
multiple `vn_yarn` or `cutscene_yarn` plans into a chapter/source-chunk shard
packet, provided every assigned graph node still writes its own separate Yarn
fragment pair and the worker receives only the source chunk named in that
packet.
After V3 `NodeSceneWriter` fragments are accepted, the controller should run
`scripts/run_pipeline.py check-v3-scene-choice-labels --run-root <run-root>`.
This check confirms that every runtime-visible choice button is backed by a
SceneWriter-authored Yarn `->` label instead of a designer or plan fallback
label.

| Agent | Role Card | Prompt Template | Canonical Output |
| --- | --- | --- | --- |
| NodeRealizationPlanner | `post-design/NodeRealizationPlanner.md` | `../post-design-prompts.md#noderealizationplanner-full-run-template` | `workspace/realization/node-realization-plans.json` |
| NodeSceneWriter | `post-design/NodeSceneWriter.md` | `../post-design-prompts.md#nodescenewriter-single-node-template` or `../post-design-prompts.md#nodescenewriter-chapter-shard-template` | `workspace/vn/fragments/<node-id>.yarn` and `.manifest.json` |
| NodeDialogueWriter | `post-design/NodeDialogueWriter.md` | `../post-design-prompts.md#nodedialoguewriter-legacy-alias-template` | Legacy alias for `NodeSceneWriter` |
| BattleRealizationWriter | `post-design/BattleRealizationWriter.md` | `../post-design-prompts.md#gameplay-realization-writer-templates` | `workspace/realization/battles/<node-id>.battle.json` |
| InteractionRealizationWriter | `post-design/InteractionRealizationWriter.md` | `../post-design-prompts.md#gameplay-realization-writer-templates` | `workspace/realization/interactions/<node-id>.interaction.json` |
| PuzzleRealizationWriter | `post-design/PuzzleRealizationWriter.md` | `../post-design-prompts.md#gameplay-realization-writer-templates` | `workspace/realization/puzzles/<node-id>.puzzle.json` |
| ExplorationRealizationWriter | `post-design/ExplorationRealizationWriter.md` | `../post-design-prompts.md#gameplay-realization-writer-templates` | `workspace/realization/explorations/<node-id>.exploration.json` |
| AssetDirector | `post-design/AssetDirector.md` | `../post-design-prompts.md#assetdirector-template` | `workspace/asset-direction.json` |
| ReviewSubagent | `post-design/ReviewSubagent.md` | `../post-design-prompts.md#reviewsubagent-template` | Review findings only |
