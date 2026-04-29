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
| bad Yarn title, invalid command, missing outcome, changed state refs | affected `NodeDialogueWriter` |
| invalid battle unit, weak verb coverage, missing victory path | `BattleRealizationWriter` |
| invalid interaction unit, unreachable completion, broken hotspot gate | `InteractionRealizationWriter` |
| invalid puzzle unit, missing solution, no fail-forward or hints | `PuzzleRealizationWriter` |
| invalid exploration unit, broken local exit, unreachable planned outcome | `ExplorationRealizationWriter` |
| missing asset id, wrong prefix, bad trace | `AssetDirector` |
| gameplay adapter runtime failure | controller/runtime adapter bug first |
| Web export failure | controller/tool bug first |
| Unity export failure | controller/template bug first |
| V2 missing or invalid source fact, character, event, theme, or world rule reference | `SourceFactExtractor` |
| V2 adaptation references missing facts, processes, endings, or forbidden changes | `AdaptationPolicyDesigner` |
| V2 state type, initial value, permission, or invariant failure | `StateModelDesigner` |
| V2 macro node, macro edge, missing contract, or contract exit mismatch | `MacroGraphDesigner` then `MacroContractWriter`, based on failed path |
| V2 expansion depth policy invalid | `MeshExpansionPlanner` |
| V2 subgraph parent/depth mismatch | `MeshLayerDesigner` |
| V2 subgraph violates root macro contract | `MeshLayerDesigner` |
| V2 route merge references missing mesh node or exit | `MacroGraphDesigner` or `MeshLayerDesigner`, based on referenced id |
| V2 simulation dead end, unreachable node, pacing budget, or theme drift warning | `DesignV2CompilerReviewer` triages first, then routes to the artifact owner |

## Repair Ticket Shape

```json
{
  "ticket_id": "repair.stage.1",
  "issue_ids": ["issue.stage.1"],
  "owners": ["NodeDialogueWriter"],
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
