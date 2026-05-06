# Artifact Contracts

Use JSON for canonical artifacts. Subagents may draft in Markdown during reasoning, but accepted output must be JSON or Yarn text matching these contracts.

## `user_requirements.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "PromptAnalyst", "notes": []},
  "prompt": "original prompt",
  "target_experience": "short description",
  "requirements": [{"id": "req.core", "priority": "must", "text": "...", "source_phrase": "..."}],
  "creative_constraints": {"genre": "", "tone": "", "themes": [], "motifs": [], "prohibited_content": []},
  "production_constraints": {"target_language": "en", "approximate_node_count": 6, "desired_endings": 2, "asset_budget_level": "low", "notes": []},
  "assumptions": [],
  "unknowns": []
}
```

Must not contain backend implementation details.

## `chapter_linear_synopsis.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "LinearSynopsisDesigner", "notes": []},
  "title": "Story title",
  "summary": "linear chapter summary",
  "events": [{"id": "event.intro", "summary": "...", "purpose": "...", "requirement_ids": ["req.core"]}],
  "cast": [{"id": "char.hero", "name": "Hero", "role": "..."}],
  "locations": [{"id": "loc.hall", "name": "Hall", "description": "..."}],
  "pacing_notes": []
}
```

Do not include branches, dialogue scripts, Yarn titles, Unity paths, or asset prompts.

## `branch_graph.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BranchGraphDesigner", "notes": []},
  "title": "Story title",
  "graph_scope": "full_game",
  "clusters": [],
  "source_outline_ids": ["event.intro"],
  "start_node_id": "node.intro",
  "nodes": [
    {
      "id": "node.intro",
      "node_type": "start",
      "title": "Intro",
      "summary": "What happens here",
      "body": "Optional prose used by exporters when no Yarn fragment exists",
      "is_terminal": false,
      "source_event_ids": ["event.intro"]
    }
  ],
  "edges": [
    {
      "id": "edge.intro_to_choice",
      "from": "node.intro",
      "to": "node.choice",
      "label": "Continue",
      "condition_type": "player_choice",
      "conditions": [],
      "effects": [
        {"state_variable_id": "state.trust", "operation": "increment", "value": 1, "description": "Trust increases after this visible action."}
      ]
    }
  ]
}
```

Allowed `node_type`: `start`, `scene`, `choice`, `convergence`, `terminal`.

Allowed `condition_type`: `unconditional`, `player_choice`, `state_gate`, `outcome`, `terminal_resolution`.

Branch graph owns public runtime topology plus edge-local transition semantics:
`conditions` gate edge availability and `effects` apply when that edge is
chosen or resolved. State variables referenced by edge `conditions` and
`effects` must be declared in `game_ir.json`, and non-trivial edge semantics
should be mirrored by `game_ir.event_rules` for auditability. For VN/cutscene
realization, final runtime button text is authored in SceneWriter Yarn `->`
labels. Branch graph labels are planning/debug fallback data, not the
authoritative runtime prose. It must not contain Yarn text, Unity paths, image
generation prompts, or realization details.

## `game_ir.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BaseGameIRDesigner", "notes": []},
  "design_brief": {
    "target_experience": "...",
    "tone": "...",
    "themes": [],
    "must_keep_constraints": [],
    "production_constraints": {},
    "narrative_bible": {
      "cast": [],
      "locations": [],
      "timeline": [],
      "continuity_rules": []
    }
  },
  "world": {"summary": "..."},
  "entities": [{"id": "char.hero", "kind": "character", "name": "Hero", "description": "..."}],
  "global_state_variables": [
    {"id": "state.trust", "type": "integer", "initial_value": 0, "description": "Trust score"}
  ],
  "progression_stages": [{"id": "stage.beginning", "description": "..."}],
  "event_rules": [
    {
      "id": "rule.choice_effect",
      "source_edge_id": "edge.intro_to_choice",
      "conditions": [],
      "effects": [{"state_variable_id": "state.trust", "operation": "increment", "value": 1, "description": "..."}]
    }
  ]
}
```

Allowed state variable `type`: `boolean`, `integer`, `number`, `string`, `enum`.

Allowed effect `operation`: `set`, `increment`, `decrement`, `append`, `remove`.

Game IR owns the formal state model, progression stages, durable world
semantics, and audit rules for edge/node effects. Public runtime transition
conditions/effects live on `branch_graph.edges[*]` so all design layers compile
to the same interface; corresponding `event_rules` should preserve the same
edge ids and state operations for validation and downstream reasoning. Game IR
must stay mode-neutral.

## `node-realization-plans.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "NodeRealizationPlanner", "notes": []},
  "plans": [
    {
      "source_node_id": "node.intro",
      "realization_kind": "vn_yarn",
      "unit_id": "realization.node_intro",
      "entry_binding": {"type": "yarn_node", "node_title": "Node_Intro"},
      "exit_bindings": [{"outcome_id": "continue", "edge_id": "edge.intro_to_choice"}],
      "required_state_reads": [],
      "state_writes": [],
      "terminal_variants": [],
      "required_assets": ["bg.intro"],
      "continuity_summary": "What this unit must preserve",
      "implementation_notes": [],
      "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []}
    }
  ]
}
```

Allowed `realization_kind`: `vn_yarn`, `cutscene_yarn`, `battle`, `interaction`, `puzzle`, `exploration`, `external_stub`.

`vn_yarn` and `cutscene_yarn` use Yarn fragment pairs. `battle`, `interaction`, `puzzle`, and `exploration` use typed gameplay unit JSON files and registered runtime adapters. `external_stub` remains a not-implemented stub.

Optional `terminal_variants` entries are used by terminal VN/cutscene plans that
resolve endings from state:

```json
{
  "id": "ending.resolved",
  "title": "Resolved",
  "priority": 40,
  "conditions": [{"state_variable_id": "state.game.ending_id", "operator": "==", "value": "ending.resolved"}],
  "state_writes": [{"state_variable_id": "state.game.ending_id", "operation": "set", "value": "ending.resolved"}],
  "visible_payoff": "What must visibly differ in this ending.",
  "canon_locked_beats": [],
  "variant_beats": []
}
```

## Yarn Fragment Pair

For every VN/cutscene plan, write:

```text
workspace/vn/fragments/<node-id>.yarn
workspace/vn/fragments/<node-id>.manifest.json
```

Yarn fragment requirements:

```text
title: StableNodeTitle
---
// source_node: node.id
<<show_bg asset_id="bg.intro">>
<<show_char character_id="char.hero" asset_id="portrait.hero.neutral">>
Speaker: Line text.
<<set_expression character_id="char.hero" expression_asset_id="portrait.hero.concerned">>
<<complete_activity outcome="continue">>
===
```

Allowed VN commands are `complete_activity`, `set`, `wait`, `show_bg`,
`show_char`, `set_expression`, `hide_char`, `show_cg`, `hide_cg`, `play_bgm`,
`stop_bgm`, `play_sfx`, `ending_variant`, and `end_ending_variant`.
`NodeSceneWriter` should author the background, character, expression, BGM, and
SFX scheduling that is materially needed by the scene. Later asset planning may
consolidate ids and prompts, but it should not be the first place where basic
scene scheduling appears.

Manifest shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "NodeSceneWriter", "notes": []},
  "source_node_id": "node.intro",
  "realization_unit_id": "realization.node_intro",
  "yarn_node_title": "Node_Intro",
  "local_asset_refs": ["bg.intro", "portrait.hero.neutral", "portrait.hero.concerned"],
  "command_refs": [
    {"command": "show_bg", "args": {"asset_id": "bg.intro"}},
    {"command": "show_char", "args": {"character_id": "char.hero", "asset_id": "portrait.hero.neutral"}},
    {"command": "set_expression", "args": {"character_id": "char.hero", "expression_asset_id": "portrait.hero.concerned"}},
    {"command": "complete_activity", "args": {"outcome": "continue"}}
  ],
  "line_performance": [
    {
      "line_index": 1,
      "speaker": "Speaker",
      "text": "Line text.",
      "tone": "quiet, wary",
      "emotion": "concerned",
      "voice_id": "voice_profile.hero",
      "action": "glances toward the door"
    }
  ],
  "exit_bindings": [{"outcome_id": "continue", "edge_id": "edge.intro_to_choice"}],
  "state_reads": [],
  "state_writes": [],
  "terminal_variants": [],
  "continuity_summary": "...",
  "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []}
}
```

Use `complete_activity` for controller-owned outcomes. Do not invent topology or persistent state.
For multi-exit or player-visible exits, the Yarn fragment must include an
explicit `->` branch label for each planned outcome. Runtime button text should
come from these SceneWriter-authored Yarn labels; graph, plan, and designer
labels are fallback/debug data, not the authoritative player-facing text.
Runtime-facing Yarn text must not expose internal source-adaptation labels such
as `source detail`, `source_dialogue`, `must_keep`, coverage ids, or
`原文细节`; those belong only in controller context and repair evidence.
VN/cutscene prose should read as a scene, not a source table: it needs a clear
viewpoint or orientation, an active question or tension, a reveal or emotional
turn, and a motivated transition to the planned outcome.

For terminal VN/cutscene plans with `terminal_variants`, each variant should be
represented by a Yarn block wrapped in `<<ending_variant id="..."
title="..." priority="...">>` and `<<end_ending_variant>>`. The fragment
manifest should copy variant ids, titles, priorities, conditions, state_writes,
and visible payoff notes into `terminal_variants`. Terminal variants should
resolve automatically from state; do not add a final visible ending menu or an
unconditional final state write unless the plan explicitly requires it.

`line_performance` is optional but recommended for voiced VN lines. It is
internal generation/staging metadata, not player-facing prose. `line_index`
is 1-based and counts spoken, monologue, and narration line beats exactly as
the exporter counts them; commands, comments, titles, choices, and
`complete_activity` do not count. A voice-generating line entry must use text
that exactly matches the visible dialogue or monologue beat. Do not add voice
intent for ambience, UI prompts, SFX, BGM, or unspoken scene description.
`generated_by: NodeDialogueWriter` remains accepted as a legacy alias during
the migration, but new fragments should use `NodeSceneWriter`.

## Gameplay Realization Units

For non-VN playable plans, write exactly one unit artifact:

```text
workspace/realization/battles/<node-id>.battle.json
workspace/realization/interactions/<node-id>.interaction.json
workspace/realization/puzzles/<node-id>.puzzle.json
workspace/realization/explorations/<node-id>.exploration.json
```

Shared shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BattleRealizationWriter", "notes": []},
  "source_node_id": "node.example",
  "realization_unit_id": "realization.node_example",
  "realization_kind": "battle",
  "adapter_id": "battle.choice_duel",
  "entry_text": "Short player-facing setup text.",
  "exit_bindings": [{"outcome_id": "victory", "edge_id": "edge.example_to_next", "label": "Continue", "state_writes": []}],
  "required_state_reads": [],
  "state_writes": [],
  "required_assets": ["bg.example", "ui.example"],
  "runtime_spec": {},
  "fail_forward": {"enabled": true, "outcome_id": "partial_success", "summary": "..."},
  "continuity_summary": "...",
  "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.example"], "edge_ids": [], "game_ir_ids": []}
}
```

Allowed first adapters:

```text
battle.choice_duel
interaction.inspect_scene
puzzle.sequence_lock
exploration.room_nav
```

Gameplay units must preserve plan topology. Their `exit_bindings` must cover the realization plan exits exactly once, and all persistent state reads/writes must reference variables declared in `game_ir.json`.

### `battle.choice_duel`

`runtime_spec` should include:

```json
{
  "prompt": "Choose a tactic.",
  "player": {"label": "Player", "stats": [{"id": "focus", "label": "Focus", "initial": 3}]},
  "opponent": {"label": "Rival", "stats": [{"id": "resolve", "label": "Resolve", "initial": 3}]},
  "player_actions": [
    {"id": "observe", "label": "Observe", "feedback": "...", "effects": [{"side": "opponent", "stat_id": "resolve", "operation": "decrement", "value": 1}]}
  ],
  "enemy_pattern": [{"id": "press", "feedback": "...", "effects": [{"side": "player", "stat_id": "focus", "operation": "decrement", "value": 1}]}],
  "win_conditions": [{"side": "opponent", "stat_id": "resolve", "operator": "less_than_or_equal", "value": 0, "outcome_id": "victory"}],
  "lose_conditions": [{"side": "player", "stat_id": "focus", "operator": "less_than_or_equal", "value": 0, "outcome_id": "defeat"}],
  "max_rounds": 4
}
```

### `interaction.inspect_scene`

`runtime_spec` should include:

```json
{
  "prompt": "Inspect the area.",
  "hotspots": [
    {"id": "map", "label": "Map", "reveal_text": "A route is marked.", "required_for_completion": true}
  ],
  "completion": {"required_hotspots": ["map"], "outcome_id": "complete", "label": "Move on"}
}
```

### `puzzle.sequence_lock`

`runtime_spec` should include:

```json
{
  "prompt": "Enter the sequence.",
  "clues": ["The mural shows dawn before flame."],
  "options": [{"id": "dawn", "label": "Dawn"}, {"id": "flame", "label": "Flame"}],
  "solution": ["dawn", "flame"],
  "hints": ["Start with the first mural symbol."],
  "max_attempts": 3,
  "solved_outcome_id": "solved",
  "failed_outcome_id": "partial_success"
}
```

### `exploration.room_nav`

`runtime_spec` should include:

```json
{
  "start_area_id": "gate",
  "areas": [
    {
      "id": "gate",
      "label": "Gate",
      "description": "A narrow gate opens into the path.",
      "discoveries": [{"id": "marker", "label": "Trail marker", "text": "It points east."}],
      "exits": [{"label": "Go east", "target_area_id": "trail"}]
    },
    {"id": "trail", "label": "Trail", "description": "The trail reaches the campsite.", "discoveries": [], "exits": []}
  ],
  "completion": {"required_areas": ["trail"], "required_discoveries": ["marker"], "outcome_id": "complete"}
}
```

## `gameplay-manifest.json`

Controller-authored lookup table:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
  "source_plan_path": "workspace/realization/node-realization-plans.json",
  "units": [
    {
      "source_node_id": "node.example",
      "realization_unit_id": "realization.node_example",
      "realization_kind": "battle",
      "adapter_id": "battle.choice_duel",
      "artifact_path": "workspace/realization/battles/node.example.battle.json",
      "status": "implemented"
    }
  ],
  "adapter_support": {"battle.choice_duel": {"web_vn": true, "unity": false}}
}
```

## `asset-direction.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AssetDirector", "notes": []},
  "style_pack": {"summary": "...", "palette": [], "lighting": "", "rendering": ""},
  "voice_profiles": {
    "voice_profile.hero": {
      "gender": "female",
      "age": "young adult",
      "prompt": "Create a natural voice for the hero..."
    }
  },
  "asset_directions": [
    {
      "asset_id": "bg.intro",
      "kind": "background",
      "description": "What should be shown",
      "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []},
      "provider_hints": [],
      "provider_bindings": {}
    }
  ]
}
```

Allowed `kind`: `background`, `cg`, `portrait`, `bgm`, `sfx`, `voice`, `ui`, `enemy`, `prop`, `hotspot`, `symbol`, `effect`, `icon`, `map`.

Do not include generated image bytes, provider URLs, API calls, or Unity import paths.

`asset-direction.json` is a consolidation and prompt-direction artifact. It
should incorporate accepted scene asset intents from Yarn commands,
fragment-manifest `local_asset_refs`, and `line_performance` instead of
inventing unrelated runtime staging after the scene has been written. The
controller may deterministically derive missing asset directions from accepted
scene scripts so scheduled assets are not lost during build.

Asset kind rules:

- `voice.*` is restricted to dialogue and monologue line beats. A voice direction must include only the exact words to be spoken in `text` or `line_text`; do not include speaker labels or action narration in TTS text. If the original visible line includes a speaker/action prefix, preserve that source form separately as `source_line_text`. Include `speaker`, `line_index`, and `source_trace.node_ids` when available. Do not use `voice.*` for ambience, UI sounds, scene setting text that is not spoken/inner monologue, SFX, or BGM.
- `voice_profiles` is optional but recommended for provider-backed TTS. It maps project-local ids such as `voice_profile.hero` to provider-neutral recurring-character constraints (`gender`, `age`, `persona`, `timbre`, `style`, `prompt`). Voice assets may reference these ids with `voice_id`; provider adapters must not hard-code project-specific profile names. AssetDirector must verify `gender` and `age` from story evidence rather than inferring them from names, aliases, historical-name jokes, or homophones.
- `provider_bindings` is optional provider-specific direction. It must preserve the provider-neutral fields rather than replacing them. For `minimax-ppio` voice generation, keep the original authored emotion in `emotion`, keep delivery nuance in `tone` when available, put the provider enum mapped from the combined emotion/tone intent in `provider_bindings.minimax-ppio.voice_emotion`, and bind the line to `provider_bindings.minimax-ppio.voice_profile_id` or `voice_id` when a `voice_profile.*` should be used.
- `bgm.*` describes instrumental background music only. It should specify scene mood and loop-friendly direction, not lyrics or spoken content unless the project explicitly wants a song cue. The controller plans BGM files as mp3 by default and MiniMax-backed generation uses the music endpoint.
- `portrait.<character>.<emotion>` describes one visible expression/state for a character. Use stable character ids and explicit emotion suffixes such as `neutral`, `alert`, `sad`, `soft`, or `resolved`; the controller groups them into `expression_asset_ids` and generates one transparent sprite per expression. Portrait descriptions should include mandatory visible identity anchors such as gender presentation, age impression, silhouette, profession/costume, and details that override misleading names or nicknames.

## `asset-manifest.json`

Controller-authored production plan and runtime lookup table, following the `unity-vn-studio` split between visual direction and generated files.

Required shape:

```json
{
  "project_id": "vn.project.sample",
  "style_bible": {"palette": [], "rendering_mode": "...", "lighting_mood": "..."},
  "characters": [
    {
      "id": "char.hero",
      "display_name": "Hero",
      "canon_ref_asset_id": "charref.hero.core",
      "canon_ref_file_ref": "generated/charrefs/charref.hero.core.png",
      "base_portrait_asset_id": "portrait.hero",
      "expression_asset_ids": ["portrait.hero"],
      "portrait_assets": [
        {
          "asset_id": "portrait.hero",
          "emotion": "neutral",
          "file_ref": "generated/portraits/portrait.hero.png",
          "source_file_ref": "generated/portraits/source/portrait.hero.png"
        }
      ],
      "costume_rules": "",
      "color_anchors": []
    }
  ],
  "backgrounds": [
    {
      "asset_id": "bg.intro",
      "scene_id": "node.intro",
      "location_tag": "intro",
      "time_of_day": "default",
      "spec": {},
      "file_ref": "generated/backgrounds/bg.intro.png"
    }
  ],
  "cgs": [],
  "ui": [],
  "audio": [
    {
      "asset_id": "bgm.intro",
      "kind": "bgm",
      "mood": "quiet anticipation",
      "spec": {},
      "file_ref": "audio/bgm.intro.mp3"
    },
    {
      "asset_id": "voice.node_intro.1",
      "kind": "voice",
      "mood": "quiet resolve",
      "spec": {
        "text": "I will keep walking until the signal answers.",
        "speaker": "Hero",
        "line_index": 1,
        "emotion": "quiet resolve",
        "voice_id": "voice_profile.hero",
        "provider_bindings": {
          "minimax-ppio": {
            "voice_profile_id": "voice_profile.hero",
            "voice_emotion": "calm"
          }
        },
        "source_trace": {"node_ids": ["node.intro"]}
      },
      "file_ref": "audio/voice.node_intro.1.wav"
    }
  ],
  "voice_profiles": {
    "voice_profile.hero": {"gender": "female", "prompt": "Create a natural voice for the hero..."}
  },
  "version": "v1"
}
```

Every runtime-facing visual asset must have a stable `asset_id` and a `file_ref` under `workspace/generated-assets/`. Asset IDs do not encode engine paths. Generated files, prompt snapshots, and model/provider metadata belong in `workspace/generated-assets/` and `reports/asset-generation-report.json`, not in `asset-direction.json`.

Supported generation providers:

- `local-svg`: deterministic offline fallback for immediate playable exports.
- `mock`: tiny placeholder PNGs for pipeline tests.
- `gemini`: required model-backed provider for production/runtime image generation in this workflow, using `GEMINI_API_KEY`.
- `openai-ppioImage`: PPIO image generation using `IMAGE_API_KEY`, `IMAGE_MODEL`, optional `IMAGE_BASE_URL`, `IMAGE_RESPONSE_TYPE`, `IMAGE_EXTRA_PARAMS`, and `IMAGE_REWRITE_RULES`. Keep this provider for explicit experiments only; do not use it as a fallback for final/runtime images unless the user asks for that provider.

Supported audio providers:

- `mock`: deterministic local WAV placeholders for pipeline tests.
- `minimax-ppio`: PPIO MiniMax music and speech generation using `AUDIO_API_KEY` or `PPIO_API_KEY`, optional `AUDIO_BASE_URL`, `AUDIO_MODEL`, `AUDIO_BGM_FORMAT`/`AUDIO_MUSIC_FORMAT`, `AUDIO_FORMAT`, and audio-specific extra parameter environment variables. BGM defaults to mp3; SFX and voice default to wav.
  - Requests to `https://api.ppio.com/v3/minimax-music` bypass system proxies by default. Set `AUDIO_NO_PROXY=1` to disable proxies for every audio request, or `PPIO_MINIMAX_MUSIC_NO_PROXY=0` only when a run intentionally needs proxy routing for that endpoint.

Portrait generation details:

- The deterministic planner turns every `portrait.<character>.<emotion>` direction into `characters[].portrait_assets[]`.
- When a `voice_profile` matches a character display name, the planner carries its provider-neutral `gender`, `age`, `persona`, and `prompt` into `characters[].character_profile` so image prompts can preserve identity constraints.
- `generate_assets.py` orders each character's portraits so neutral/base is generated first when present.
- Gemini generation passes the base portrait as a reference image for later expressions, asks for a waist-up or three-quarter VN sprite with readable face/body language, and then runs transparent cutout post-processing.
- Portrait post-processing attempts `rembg` background removal when available; `reports/asset-validation.json` must catch missing portrait transparency.

Audio generation details:

- BGM prompts are instrumental, dialogue-safe, and loop-friendly. `minimax-ppio` uses MiniMax music generation and downloads the returned audio URL.
- SFX assets are one-shot cues, not loops or ambience beds. The audio generator trims WAV SFX to a short maximum duration and asset validation fails SFX that remain too long.
- Voice prompts are the exact dialogue or monologue text. `minimax-ppio` uses MiniMax TTS and downloads the returned audio URL. Voice assets are bound to line beats by `export_web_vn.py`; they are not Yarn commands.
