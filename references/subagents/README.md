# Subagent Role Cards

Use this index to pick the exact role card for a subagent spawn. Read only the role card needed for the current spawn, then pass only the minimum upstream artifacts listed there.

Do not set a `model` override when spawning subagents.

## Clean-Context Dispatch Rules

The controller owns global workflow context and run navigation. Subagents should receive a compact controller packet, not an open-ended instruction to inspect the run directory.

- Controller may read contracts, validation scripts, source extraction files, and all accepted artifacts.
- Normal authoring subagents read only their exact role card plus the packet prepared for that spawn.
- Do not pass `references/design-layer-v2-contracts.md` to normal authoring workers by default. The controller uses it to validate and repair; `DesignV2CompilerReviewer` or targeted repair workers may receive contract excerpts when explicitly needed.
- Store reusable dispatch packets under `workspace/controller-packets/`. Each packet should list included upstream artifact paths and source slices.
- For long source adaptations, pass source material as assigned slices from `inputs/source_material/chunks/` or summaries derived from accepted source-intake artifacts, not as the full extracted text unless the role card explicitly requires whole-source profiling.

When `SourceSegmenter` is sharded for a long source, each shard still uses the same `SourceSegmenter` role card but receives only one packet under `workspace/controller-packets/source_segmenter/`. Workers return partial typed payloads only. The controller waits for all shards, saves raw returns under `workspace/controller-packets/source_segmenter_returns/`, normalizes keys such as `segment_id` to `id`, merges all accepted segments/beats/coverage rows in source order, and writes the canonical `workspace/design_layer_v2/source_intake/*` files. No shard worker may inspect sibling shard packets or write canonical artifacts.

## Design Layer

These agents produce the base design layer. They may depend on earlier design-layer outputs, but downstream agents should receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| PromptAnalyst | `design-layer/PromptAnalyst.md` | `workspace/design_layer/user_requirements.json` |
| LinearSynopsisDesigner | `design-layer/LinearSynopsisDesigner.md` | `workspace/design_layer/chapter_linear_synopsis.json` |
| BranchGraphDesigner | `design-layer/BranchGraphDesigner.md` | `workspace/design_layer/branch_graph.json` |
| BaseGameIRDesigner | `design-layer/BaseGameIRDesigner.md` | `workspace/design_layer/game_ir.json` |

## Design Layer V2

These agents produce internal V2 source artifacts under `workspace/design_layer_v2/`. The controller validates and compiles those artifacts into the same public runtime interface as V1: `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`. Downstream agents must not receive raw V2 source artifacts unless a repair explicitly requires them; for novel adaptations, the controller may pass only the current node's source segment summary slice to the scene writer.

Minimum V2 input packets:

| Agent | Minimum Packet Contents |
| --- | --- |
| InputProfiler | User prompt, source-adaptation brief, production constraints, and source overview from `inputs/source_material/source_index.json`; include `full_text.txt` only when whole-source profiling is feasible and necessary. |
| SourceSegmenter | Accepted `source_intake/input_profile.json`, source overview, assigned source chunks or chapter excerpts, target language/tone/scale notes. |
| SourceFactExtractor | Accepted `source_intake/*`, controller-assigned source chunks or segment packet, extraction constraints. |
| AdaptationPolicyDesigner | Accepted `source_intake/*`, accepted `source_facts/*`, user adaptation brief, optional repair ticket. |
| StateModelDesigner | Accepted `source_intake/*`, `source_facts/*`, and `adaptation/*`, optional repair ticket. |
| MacroGraphDesigner | Accepted `source_intake/*`, `source_facts/*`, `adaptation/*`, and `state/*`, optional repair ticket. |
| MacroContractWriter | Accepted `source_intake/*`, `source_facts/*`, `adaptation/*`, `state/*`, and `macro/macro_story_graph.json`, optional repair ticket. |
| MeshExpansionPlanner | Accepted source-intake, source-facts, adaptation, state, macro graph, and macro contracts. |
| MeshLayerDesigner | One parent packet only: parent id/type, root macro contract, assigned source segment slice, accepted macro/control artifacts, required continuity from accepted lower-depth subgraphs when applicable. |
| DesignV2CompilerReviewer | Validation reports, compile report, compiled public artifacts, and only the contract excerpts needed to explain failures. |

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| InputProfiler | `design-layer-v2/InputProfiler.md` | `workspace/design_layer_v2/source_intake/input_profile.json` |
| SourceSegmenter | `design-layer-v2/SourceSegmenter.md` | `workspace/design_layer_v2/source_intake/*` |
| SourceFactExtractor | `design-layer-v2/SourceFactExtractor.md` | `workspace/design_layer_v2/source_facts/*` |
| AdaptationPolicyDesigner | `design-layer-v2/AdaptationPolicyDesigner.md` | `workspace/design_layer_v2/adaptation/*` |
| StateModelDesigner | `design-layer-v2/StateModelDesigner.md` | `workspace/design_layer_v2/state/*` |
| MacroGraphDesigner | `design-layer-v2/MacroGraphDesigner.md` | `workspace/design_layer_v2/macro/macro_story_graph.json`, `workspace/design_layer_v2/control/route_merge_policy.json` |
| MacroContractWriter | `design-layer-v2/MacroContractWriter.md` | `workspace/design_layer_v2/macro/macro_node_contracts.json` |
| MeshExpansionPlanner | `design-layer-v2/MeshExpansionPlanner.md` | `workspace/design_layer_v2/control/mesh_expansion_policy.json` |
| MeshLayerDesigner | `design-layer-v2/MeshLayerDesigner.md` | `workspace/design_layer_v2/subgraphs/subgraph.<parent_ref_id>.json` |
| DesignV2CompilerReviewer | `design-layer-v2/DesignV2CompilerReviewer.md` | Review findings only |

`MeshLayerDesigner` is intentionally reused for all mesh depths. The
controller spawns it once for each selected parent in `mesh_expansion_policy`:
depth 1 parents are macro nodes, while depth 2+ parents are expandable
`subgraph_node` ids from accepted lower-depth subgraphs. Do not add a separate
tertiary graph writer role; pass only the current parent packet and its assigned
source slices to each worker.

## Design Layer V3

V3 replaces the V2 authoring flow with hierarchical story abstraction and
hierarchical graph/state design. It still compiles into the same public runtime
interface: `workspace/design_layer/branch_graph.json` and
`workspace/design_layer/game_ir.json`.
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
Use the `Controller Packet Prompt Template` in
`design-layer-v3/LevelStateGraphDesigner.md` for each level/shard worker.
Every story extraction level and every graph/state design level should support
parallel clean-context workers by default. The controller shards a level into
packets, stores raw returns under that level's `shard_returns/`, and performs
the deterministic merge into canonical artifacts.

Minimum V3 input packets:

| Agent | Minimum Packet Contents |
| --- | --- |
| StoryLevelExtractor | One story level id, assigned source chunks for the finest level or assigned lower-level story units for higher levels, granularity and scale notes, plus fact-capture requirements. |
| AdaptationPolicyDesigner | Coarsest enabled `linear_story.json`, `facts/canonical_fact_graph.json`, user adaptation brief, and global constraints. |
| LevelStateGraphDesigner | One parent packet: immediate parent graph/state/contracts slice, same-level story units, same-level fact view slice, global adaptation policy direction, and any controller-selected relevant excerpts. |
| DesignV3CompilerReviewer | V3 validation reports, compile report, assembled public artifacts, and only contract excerpts needed to explain failures. |

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| StoryLevelExtractor | `design-layer-v3/StoryLevelExtractor.md` | `workspace/design_layer_v3/story_levels/level_<NN>/linear_story.json`, plus controller-merged `facts/*` payloads |
| AdaptationPolicyDesigner | `design-layer-v3/AdaptationPolicyDesigner.md` | `workspace/design_layer_v3/adaptation/global_policy.json` |
| LevelStateGraphDesigner | `design-layer-v3/LevelStateGraphDesigner.md` | `workspace/design_layer_v3/design_levels/level_<NN>/*` |
| DesignV3CompilerReviewer | `design-layer-v3/DesignV3CompilerReviewer.md` | Review findings only |

Every non-coarsest `LevelStateGraphDesigner` output must include
`parent_state_settlements.json`, declaring how this level's local state
settlement affects the immediate parent level's state. `effects_on_parent_state`
must not skip levels.

## Post Design

These agents run after the design layer. They should not reopen requirements or synopsis by default; use the durable downstream context in `game_ir.design_brief`, the graph topology in `branch_graph.json`, and controller-provided slices.
For networked V3 outputs, `NodeRealizationPlanner` must preserve visible branch
structure in the realization plan: choice placement, state-gated beat changes,
route-memory payoff, and entry variants for nodes reached from different routes.
After V3 `NodeSceneWriter` fragments are accepted, the controller should run
`scripts/run_pipeline.py check-v3-scene-choice-labels --run-root <run-root>`.
This check confirms that every runtime-visible choice button is backed by a
SceneWriter-authored Yarn `->` label instead of a designer or plan fallback
label.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| NodeRealizationPlanner | `post-design/NodeRealizationPlanner.md` | `workspace/realization/node-realization-plans.json` |
| NodeSceneWriter | `post-design/NodeSceneWriter.md` | `workspace/vn/fragments/<node-id>.yarn` and `.manifest.json` |
| NodeDialogueWriter | `post-design/NodeDialogueWriter.md` | Legacy alias for `NodeSceneWriter` |
| BattleRealizationWriter | `post-design/BattleRealizationWriter.md` | `workspace/realization/battles/<node-id>.battle.json` |
| InteractionRealizationWriter | `post-design/InteractionRealizationWriter.md` | `workspace/realization/interactions/<node-id>.interaction.json` |
| PuzzleRealizationWriter | `post-design/PuzzleRealizationWriter.md` | `workspace/realization/puzzles/<node-id>.puzzle.json` |
| ExplorationRealizationWriter | `post-design/ExplorationRealizationWriter.md` | `workspace/realization/explorations/<node-id>.exploration.json` |
| AssetDirector | `post-design/AssetDirector.md` | `workspace/asset-direction.json` |
| ReviewSubagent | `post-design/ReviewSubagent.md` | Review findings only |
