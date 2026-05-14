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

## RPG Overlay Design

These agents are used by the unified RPG design layer. They add RPG system
intent from V3 story hierarchy without rewriting the narrative graph.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| RPGSystemPlanner | `design-layer-rpg/RPGSystemPlanner.md` | `workspace/design_layer_rpg/rpg-overlay-plan.json` |
| RPGDesignReviewer | `design-layer-rpg/RPGDesignReviewer.md` | `workspace/design_layer_rpg/rpg-overlay-review.json` |

## RPG Post Design

These agents are used for RPG realization and must not change the design-layer files. In narrative-first overlay runs, they should prefer assigned packets under `workspace/controller-packets/postdesign/rpg/*.json` instead of reading the full public graph.

| Agent | Role Card | Canonical Output |
| --- | --- | --- |
| RPGCampaignPlanner | `post-design/rpg/RPGCampaignPlanner.md` | `workspace/rpg/rpg-campaign.json`, `workspace/rpg/world-map.json` |
| RPGMapBuilder | `post-design/rpg/RPGMapBuilder.md` | `workspace/rpg/maps/*.map.json` |
| RPGContentWriter | `post-design/rpg/RPGContentWriter.md` | `workspace/rpg/actors.json`, `enemies.json`, `items.json`, `skills.json`, `quests.json`, `npc-dialogue.json` |
| RPGSceneScriptWriter | `post-design/rpg/RPGSceneScriptWriter.md` | `workspace/rpg/scene-scripts.json` |
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
