# Design Layer V2 Role Cards

Use these role cards only for the V2 front-half. Downstream realization,
dialogue, asset, and export agents continue to receive context derived from
`branch_graph.json` and `game_ir.json`. For source adaptations, the controller
may also pass a deterministic per-node slice of internal source segment
summaries; do not pass the raw full source to downstream workers by default.

Do not set a `model` override when spawning subagents.

Read only the role card needed for the current spawn:

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| InputProfiler | `subagents/design-layer-v2/InputProfiler.md` | `workspace/design_layer_v2/source_intake/input_profile.json` |
| SourceSegmenter | `subagents/design-layer-v2/SourceSegmenter.md` | `workspace/design_layer_v2/source_intake/*` |
| SourceFactExtractor | `subagents/design-layer-v2/SourceFactExtractor.md` | `workspace/design_layer_v2/source_facts/*` |
| AdaptationPolicyDesigner | `subagents/design-layer-v2/AdaptationPolicyDesigner.md` | `workspace/design_layer_v2/adaptation/*` |
| StateModelDesigner | `subagents/design-layer-v2/StateModelDesigner.md` | `workspace/design_layer_v2/state/*` |
| MacroGraphDesigner | `subagents/design-layer-v2/MacroGraphDesigner.md` | `workspace/design_layer_v2/macro/macro_story_graph.json`, `workspace/design_layer_v2/control/route_merge_policy.json` |
| MacroContractWriter | `subagents/design-layer-v2/MacroContractWriter.md` | `workspace/design_layer_v2/macro/macro_node_contracts.json` |
| MeshExpansionPlanner | `subagents/design-layer-v2/MeshExpansionPlanner.md` | `workspace/design_layer_v2/control/mesh_expansion_policy.json` |
| MeshLayerDesigner | `subagents/design-layer-v2/MeshLayerDesigner.md` | `workspace/design_layer_v2/subgraphs/subgraph.<parent_ref_id>.json` |
| DesignV2CompilerReviewer | `subagents/design-layer-v2/DesignV2CompilerReviewer.md` | Review findings only |

`MeshLayerDesigner` is the single recursive graph writer for every mesh depth.
The controller spawns it once per selected parent: macro-node parents produce
depth 1 subgraphs, and expandable `subgraph_node` parents produce depth 2+
subgraphs. Do not create a separate tertiary graph writer; isolate each spawn
to the current parent packet and assigned source slices.

Exact payload shapes are defined in `references/design-layer-v2-contracts.md`.
