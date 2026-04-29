# Design Layer V2 Role Cards

Use these role cards only for the V2 front-half. Downstream realization,
dialogue, asset, and export agents continue to receive context derived from
`branch_graph.json` and `game_ir.json`.

Do not set a `model` override when spawning subagents.

Read only the role card needed for the current spawn:

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| SourceFactExtractor | `subagents/design-layer-v2/SourceFactExtractor.md` | `workspace/design_layer_v2/source_facts/*` |
| AdaptationPolicyDesigner | `subagents/design-layer-v2/AdaptationPolicyDesigner.md` | `workspace/design_layer_v2/adaptation/*` |
| StateModelDesigner | `subagents/design-layer-v2/StateModelDesigner.md` | `workspace/design_layer_v2/state/*` |
| MacroGraphDesigner | `subagents/design-layer-v2/MacroGraphDesigner.md` | `workspace/design_layer_v2/macro/macro_story_graph.json`, `workspace/design_layer_v2/control/route_merge_policy.json` |
| MacroContractWriter | `subagents/design-layer-v2/MacroContractWriter.md` | `workspace/design_layer_v2/macro/macro_node_contracts.json` |
| MeshExpansionPlanner | `subagents/design-layer-v2/MeshExpansionPlanner.md` | `workspace/design_layer_v2/control/mesh_expansion_policy.json` |
| MeshLayerDesigner | `subagents/design-layer-v2/MeshLayerDesigner.md` | `workspace/design_layer_v2/subgraphs/subgraph.<parent_ref_id>.json` |
| DesignV2CompilerReviewer | `subagents/design-layer-v2/DesignV2CompilerReviewer.md` | Review findings only |

Exact payload shapes are defined in `references/design-layer-v2-contracts.md`.
