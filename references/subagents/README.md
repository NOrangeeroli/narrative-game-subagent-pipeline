# Subagent Role Cards

Use this index to pick the exact role card for a subagent spawn. Read only the role card needed for the current spawn, then pass only the minimum upstream artifacts listed there.

Do not set a `model` override when spawning subagents.

## Design Layer

These agents produce the base design layer. They may depend on earlier design-layer outputs, but downstream agents should receive only `branch_graph.json`, `game_ir.json`, and controller-made slices unless a repair explicitly needs more context.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| PromptAnalyst | `design-layer/PromptAnalyst.md` | `workspace/design_layer/user_requirements.json` |
| LinearSynopsisDesigner | `design-layer/LinearSynopsisDesigner.md` | `workspace/design_layer/chapter_linear_synopsis.json` |
| BranchGraphDesigner | `design-layer/BranchGraphDesigner.md` | `workspace/design_layer/branch_graph.json` |
| BaseGameIRDesigner | `design-layer/BaseGameIRDesigner.md` | `workspace/design_layer/game_ir.json` |

## Design Layer V2

These agents produce internal V2 source artifacts under `workspace/design_layer_v2/`. The controller validates and compiles those artifacts into the same public runtime interface as V1: `workspace/design_layer/branch_graph.json` and `workspace/design_layer/game_ir.json`. Downstream agents must not receive raw V2 source artifacts unless a repair explicitly requires them.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| SourceFactExtractor | `design-layer-v2/SourceFactExtractor.md` | `workspace/design_layer_v2/source_facts/*` |
| AdaptationPolicyDesigner | `design-layer-v2/AdaptationPolicyDesigner.md` | `workspace/design_layer_v2/adaptation/*` |
| StateModelDesigner | `design-layer-v2/StateModelDesigner.md` | `workspace/design_layer_v2/state/*` |
| MacroGraphDesigner | `design-layer-v2/MacroGraphDesigner.md` | `workspace/design_layer_v2/macro/macro_story_graph.json`, `workspace/design_layer_v2/control/route_merge_policy.json` |
| MacroContractWriter | `design-layer-v2/MacroContractWriter.md` | `workspace/design_layer_v2/macro/macro_node_contracts.json` |
| MeshExpansionPlanner | `design-layer-v2/MeshExpansionPlanner.md` | `workspace/design_layer_v2/control/mesh_expansion_policy.json` |
| MeshLayerDesigner | `design-layer-v2/MeshLayerDesigner.md` | `workspace/design_layer_v2/subgraphs/subgraph.<parent_ref_id>.json` |
| DesignV2CompilerReviewer | `design-layer-v2/DesignV2CompilerReviewer.md` | Review findings only |

## Post Design

These agents run after the design layer. They should not reopen requirements or synopsis by default; use the durable downstream context in `game_ir.design_brief`, the graph topology in `branch_graph.json`, and controller-provided slices.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| NodeRealizationPlanner | `post-design/NodeRealizationPlanner.md` | `workspace/realization/node-realization-plans.json` |
| NodeDialogueWriter | `post-design/NodeDialogueWriter.md` | `workspace/vn/fragments/<node-id>.yarn` and `.manifest.json` |
| BattleRealizationWriter | `post-design/BattleRealizationWriter.md` | `workspace/realization/battles/<node-id>.battle.json` |
| InteractionRealizationWriter | `post-design/InteractionRealizationWriter.md` | `workspace/realization/interactions/<node-id>.interaction.json` |
| PuzzleRealizationWriter | `post-design/PuzzleRealizationWriter.md` | `workspace/realization/puzzles/<node-id>.puzzle.json` |
| ExplorationRealizationWriter | `post-design/ExplorationRealizationWriter.md` | `workspace/realization/explorations/<node-id>.exploration.json` |
| AssetDirector | `post-design/AssetDirector.md` | `workspace/asset-direction.json` |
| PresentationDirector | `post-design/PresentationDirector.md` | `workspace/presentation/presentation-plan.json` |
| ReviewSubagent | `post-design/ReviewSubagent.md` | Review findings only |
