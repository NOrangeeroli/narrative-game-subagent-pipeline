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
| ReviewSubagent | `post-design/ReviewSubagent.md` | Review findings only |

## RPG Post Design

These agents are used only for explicit `--target web-rpg` runs. They are parallel to VN realization and must not change the design-layer files.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| RPGCampaignPlanner | `post-design/rpg/RPGCampaignPlanner.md` | `workspace/rpg/rpg-campaign.json`, `workspace/rpg/world-map.json` |
| RPGMapBuilder | `post-design/rpg/RPGMapBuilder.md` | `workspace/rpg/maps/*.map.json` |
| RPGContentWriter | `post-design/rpg/RPGContentWriter.md` | `workspace/rpg/actors.json`, `enemies.json`, `items.json`, `skills.json`, `quests.json`, `npc-dialogue.json` |
| RPGBalanceReviewer | `post-design/rpg/RPGBalanceReviewer.md` | Review findings or repaired RPG balance payloads |

## Audio Asset Generation

These agents are used for final-quality audio runs. The controller resolves
provider configuration first, then runs BGM, SFX, and voice agents as separate
parallel groups when possible. They must not use `mock` fallback unless the
user explicitly approved fallback for the run.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| BGMAudioGenerator | `audio/BGMAudioGenerator.md` | `reports/bgm-audio-generation-report.json` |
| SFXAudioGenerator | `audio/SFXAudioGenerator.md` | `reports/sfx-audio-generation-report.json` |
| VoiceAudioGenerator | `audio/VoiceAudioGenerator.md` | `reports/voice-audio-generation-report.json` |

## Background Asset Generation

RPG backgrounds are a single owned workflow, not separate static, boundary, and
dynamic agents.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| RPGBackgroundGenerator | `background/RPGBackgroundGenerator.md` | `reports/rpg-background-generation-report.json`; also owns RPG boundary reports and `bgv.*` media |
| VNBackgroundGenerator | `background/VNBackgroundGenerator.md` | `reports/vn-background-generation-report.json` |
