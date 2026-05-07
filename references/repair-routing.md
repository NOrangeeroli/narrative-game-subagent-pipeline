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
| Runtime Yarn exposes internal source labels such as `source detail`, `source_dialogue`, `must_keep`, coverage ids, or `原文细节` | affected `NodeSceneWriter` |
| Runtime-visible choice button has no SceneWriter-authored Yarn `->` label, uses a generic label, or falls back to designer/plan text | affected `NodeSceneWriter`; if the edge is not in the realization plan, repair V3 compile/export first |
| Runtime Yarn replaces character interaction or concrete scene action with generic summary, visible placeholders, or table-like prose | affected `NodeSceneWriter` |
| Runtime Yarn reads like mechanical excerpt stitching, lacks viewpoint orientation, active tension, emotional turn, or transition hook | affected `NodeSceneWriter`, or `NodeRealizationPlanner` if continuity summaries are too thin |
| missing adventure genre policy | `AdventureGenrePlanner` |
| missing world region or invalid world start level | `WorldMapDesigner` |
| missing level binding, spawn, walkable surface, camera bounds, or blocked spatial path | `LevelBlockoutDesigner` |
| missing interaction binding, invalid interaction completion, or quest step without a trigger | `InteractionQuestDesigner` |
| public graph edge has no adventure trigger binding | `AdventureNarrativeBinder` |
| adventure state gate is impossible or references undeclared state | `AdventureNarrativeBinder`, then V3 design repair if the public graph state is wrong |
| terminal ending node has no adventure ending binding or mismatched ending id | `AdventureNarrativeBinder`, then V3 ending repair if public metadata is wrong |
| missing adventure tileset, sprite, UI, audio, or ending still direction | `AdventureAssetDirector` |
| Web adventure export/runtime failure | controller/runtime template bug first |
| Unity adventure export/runtime failure | controller/runtime template bug first |

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
