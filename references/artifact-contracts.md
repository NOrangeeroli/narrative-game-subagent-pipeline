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

## `chapter_branch_graph.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BranchGraphDesigner", "notes": []},
  "title": "Story title",
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

## `game_ir.json`

Required shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "BaseGameIRDesigner", "notes": []},
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

