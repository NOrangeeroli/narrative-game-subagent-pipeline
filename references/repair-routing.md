# Repair Routing

Route failures to the smallest owner. The controller creates the repair ticket
and gives it to exactly the agent that can fix the artifact.

## Owner Table

| Failure | Owner |
| --- | --- |
| malformed or backend-specific requirements | `PromptAnalyst` |
| missing event anchors or synopsis traceability | `LinearSynopsisDesigner` |
| duplicate node ids, broken edge refs, missing terminals | `BranchGraphDesigner` |
| missing state variable, stale graph refs, missing edge semantics | `BaseGameIRDesigner` |
| topology and semantics both need coordinated change | `BranchGraphDesigner` then `BaseGameIRDesigner`, or a paired planning pass |
| invalid hierarchical story extraction, fact coverage, or source coverage | `StoryLevelExtractor` |
| invalid adaptation policy or impossible route constraints | `AdaptationPolicyDesigner` |
| invalid level graph/state contracts or parent settlements | `LevelStateGraphDesigner` |
| invalid RPG overlay binding or untraceable RPG system intent | `RPGSystemPlanner` |
| RPG overlay fidelity concern | `RPGDesignReviewer` |
| invalid RPG campaign or world map | `RPGCampaignPlanner` |
| invalid RPG map dimensions, collision, event position, spatial staging, or transfer | `RPGMapBuilder` |
| invalid RPG actors, enemies, quests, dialogue, story items, shops, rest points, or encounter tables | `RPGContentWriter` |
| invalid scene-script obligation coverage, actor blocking, beat order, or scene state effect | `RPGSceneScriptWriter` |
| failed RPG balance simulation | `RPGBalanceReviewer` |
| missing asset id, wrong prefix, missing provider hint, or bad trace | scoped asset worker or controller asset binder |
| RPG background, boundary, or dynamic media failure | `RPGBackgroundGenerator` |
| Web RPG export failure | controller/tool bug first |

## Repair Ticket Shape

```json
{
  "ticket_id": "repair.stage.1",
  "issue_ids": ["issue.stage.1"],
  "owners": ["RPGSceneScriptWriter"],
  "artifact_scope": "workspace/rpg/scene-scripts.json",
  "repair_order": ["scene_script"],
  "instructions": [
    "Previous output failed validation: scene beat must preserve node.witness outcome.",
    "Return corrected payload only. Preserve upstream ids and schema_version 0.1.0."
  ],
  "source_report_path": "reports/rpg-validation.json",
  "retry_count": 1
}
```

## Rules

- Do not ask for broad rewrites when a local repair can fix the issue.
- Include the failed payload, validation findings, upstream artifacts, and exact
  expected contract.
- Preserve stable ids unless the finding specifically says an id is invalid.
- After repair, rerun validation before continuing.
- Stop after the retry budget and report the preserved run directory instead of
  overwriting evidence.
