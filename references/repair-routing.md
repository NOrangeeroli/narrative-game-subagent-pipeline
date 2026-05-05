# Repair Routing

Route failures to the smallest owner. The controller creates the repair ticket and gives it to exactly the agent that can fix the artifact.

## Owner Table

| Failure | Owner |
| --- | --- |
| malformed or backend-specific requirements | `PromptAnalyst` |
| missing event anchors or synopsis traceability | `LinearSynopsisDesigner` |
| duplicate node ids, broken edge refs, missing terminals | `BranchGraphDesigner` |
| missing state variable, stale graph refs, missing edge semantics | `BaseGameIRDesigner` |
| topology and semantics both need coordinated change | `BranchGraphDesigner` then `BaseGameIRDesigner`, or a paired planning pass |
| missing realization plan, wrong exit binding, unsupported playable kind | `NodeRealizationPlanner` |
| bad Yarn title, invalid command, missing outcome, changed state refs | affected `NodeSceneWriter` (`NodeDialogueWriter` only as legacy alias) |
| missing basic VN staging such as background, character presence, BGM, or SFX commands | affected `NodeSceneWriter` |
| line voice cannot attach because line text, speaker, or line index is missing/mismatched | affected `NodeSceneWriter` manifest `line_performance`, then `AssetDirector` if direction consolidation dropped it |
| invalid battle unit, weak verb coverage, missing victory path | `BattleRealizationWriter` |
| invalid interaction unit, unreachable completion, broken hotspot gate | `InteractionRealizationWriter` |
| invalid puzzle unit, missing solution, no fail-forward or hints | `PuzzleRealizationWriter` |
| invalid exploration unit, broken local exit, unreachable planned outcome | `ExplorationRealizationWriter` |
| missing asset id, wrong prefix, bad trace | `AssetDirector` |
| weak portrait staging or missing expression use for available portraits | affected `NodeSceneWriter` |
| gameplay adapter runtime failure | controller/runtime adapter bug first |
| Web export failure | controller/tool bug first |
| Unity export failure | controller/template bug first |
| V2 invalid input mode or source kind | `InputProfiler` |
| V2 missing/invalid source segment, source beat, or coverage row | `SourceSegmenter` |
| V2 full-novel source segmented only at chapter/section level, causing lost scene/dialogue/action/reveal beats | `SourceSegmenter`, then `MeshExpansionPlanner` if deeper mesh budget is also needed |
| V2 missing or invalid source fact, character, event, theme, or world rule reference | `SourceFactExtractor` |
| V2 adaptation references missing facts, processes, endings, or forbidden changes | `AdaptationPolicyDesigner` |
| V2 must-cover segment not covered, segment distribution violation, or source-adaptation choice without a source segment | `MacroGraphDesigner`, `MacroContractWriter`, or `MeshLayerDesigner`, based on failed path |
| V2 required source segment has no viable playable node target | `MeshLayerDesigner` for the affected parent; controller updates routing/target evidence after accepting the repaired subgraph |
| V2 state type, initial value, permission, or invariant failure | `StateModelDesigner` |
| V2 macro node, macro edge, missing contract, or contract exit mismatch | `MacroGraphDesigner` then `MacroContractWriter`, based on failed path |
| V2 expansion depth policy invalid, too shallow for dense novel parents, or uniformly inflates unrelated routes | `MeshExpansionPlanner` |
| V2 subgraph parent/depth mismatch | `MeshLayerDesigner` |
| V2 subgraph violates root macro contract | `MeshLayerDesigner` |
| V2 lower-depth subgraph collapses a dense novel parent into one chapter-scale playable node | `MeshLayerDesigner` for that parent, possibly after `MeshExpansionPlanner` raises the parent depth budget |
| V2 subgraph titles, summaries, or choice labels expose internal source labels such as `source detail`, `source_dialogue`, coverage ids, or `原文细节` | `MeshLayerDesigner` |
| V2 macro or mesh progression front-loads lore, lacks reader orientation, skips active question/tension, or jumps without a hook | `MacroGraphDesigner`, `MacroContractWriter`, or `MeshLayerDesigner`, based on failed path |
| V2 route merge references missing mesh node or exit | `MacroGraphDesigner` or `MeshLayerDesigner`, based on referenced id |
| V2 simulation dead end, unreachable node, pacing budget, or theme drift warning | `DesignV2CompilerReviewer` triages first, then routes to the artifact owner |
| Runtime Yarn exposes internal source labels such as `source detail`, `source_dialogue`, `must_keep`, coverage ids, or `原文细节` | affected `NodeSceneWriter` |
| Runtime-visible choice button has no SceneWriter-authored Yarn `->` label, uses a generic label, or falls back to designer/plan text | affected `NodeSceneWriter`; if the edge is not in the realization plan, repair V3 compile/export first |
| Runtime Yarn replaces character interaction or concrete scene action with generic summary, visible placeholders, or table-like prose | affected `NodeSceneWriter` |
| Runtime Yarn reads like mechanical excerpt stitching, lacks viewpoint orientation, active tension, emotional turn, or transition hook | affected `NodeSceneWriter`, or `NodeRealizationPlanner` if continuity summaries are too thin |

## Repair Ticket Shape

```json
{
  "ticket_id": "repair.stage.1",
  "issue_ids": ["issue.stage.1"],
  "owners": ["NodeSceneWriter"],
  "artifact_scope": "yarn_fragment",
  "repair_order": ["yarn_fragment"],
  "instructions": [
    "Previous output failed validation: complete_activity needs outcome arg.",
    "Return corrected payload only. Preserve upstream ids and schema_version 0.1.0."
  ],
  "source_report_path": "reports/validation-report.json",
  "retry_count": 1
}
```

## Rules

- Do not ask for broad rewrites when a local repair can fix the issue.
- Include the failed payload, validation findings, upstream artifacts, and exact expected contract.
- Preserve stable ids unless the finding specifically says an id is invalid.
- After repair, rerun validation before continuing.
- Stop after the retry budget and report the preserved run directory instead of overwriting evidence.
