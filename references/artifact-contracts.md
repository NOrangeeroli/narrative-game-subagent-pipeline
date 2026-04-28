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
      "condition_type": "unconditional"
    }
  ]
}
```

Allowed `node_type`: `start`, `scene`, `choice`, `convergence`, `terminal`.

Allowed `condition_type`: `unconditional`, `player_choice`, `state_gate`, `outcome`, `terminal_resolution`.

Branch graph owns topology and player-facing labels, not executable state semantics.
It must not contain Yarn text, Unity paths, image-generation prompts, or persistent state effects.

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

Game IR owns conditions, effects, state variables, and progression. It must stay mode-neutral.

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
      "required_assets": ["bg.intro"],
      "continuity_summary": "What this unit must preserve",
      "implementation_notes": [],
      "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []}
    }
  ]
}
```

Allowed `realization_kind`: `vn_yarn`, `cutscene_yarn`, `battle`, `interaction`, `puzzle`, `exploration`, `external_stub`.

In v1, only `vn_yarn` and `cutscene_yarn` become playable content. Other kinds become not-implemented stubs.

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
Speaker: Line text.
<<complete_activity outcome="continue">>
===
```

Manifest shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "NodeDialogueWriter", "notes": []},
  "source_node_id": "node.intro",
  "realization_unit_id": "realization.node_intro",
  "yarn_node_title": "Node_Intro",
  "local_asset_refs": ["bg.intro"],
  "command_refs": [{"command": "complete_activity", "args": {"outcome": "continue"}}],
  "exit_bindings": [{"outcome_id": "continue", "edge_id": "edge.intro_to_choice"}],
  "state_reads": [],
  "state_writes": [],
  "continuity_summary": "...",
  "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []}
}
```

Use `complete_activity` for controller-owned outcomes. Do not invent topology or persistent state.

## `asset-direction.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AssetDirector", "notes": []},
  "style_pack": {"summary": "...", "palette": [], "lighting": "", "rendering": ""},
  "asset_directions": [
    {
      "asset_id": "bg.intro",
      "kind": "background",
      "description": "What should be shown",
      "source_trace": {"requirement_ids": [], "event_ids": [], "node_ids": ["node.intro"], "edge_ids": [], "game_ir_ids": []},
      "provider_hints": []
    }
  ]
}
```

Allowed `kind`: `background`, `cg`, `portrait`, `bgm`, `sfx`, `ui`.

Do not include generated image bytes, provider URLs, API calls, or Unity import paths.

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
  "audio": [],
  "version": "v1"
}
```

Every runtime-facing visual asset must have a stable `asset_id` and a `file_ref` under `workspace/generated-assets/`. Asset IDs do not encode engine paths. Generated files, prompt snapshots, and model/provider metadata belong in `workspace/generated-assets/` and `reports/asset-generation-report.json`, not in `asset-direction.json`.

Supported generation providers:

- `local-svg`: deterministic offline fallback for immediate playable exports.
- `mock`: tiny placeholder PNGs for pipeline tests.
- `gemini`: model-backed image generation using `GEMINI_API_KEY`.
- `openai-ppioImage`: PPIO image generation using `IMAGE_API_KEY`, `IMAGE_MODEL`, optional `IMAGE_BASE_URL`, `IMAGE_RESPONSE_TYPE`, `IMAGE_EXTRA_PARAMS`, and `IMAGE_REWRITE_RULES`.

Portrait post-processing attempts `rembg` background removal when available; `reports/asset-validation.json` must catch missing portrait transparency.
