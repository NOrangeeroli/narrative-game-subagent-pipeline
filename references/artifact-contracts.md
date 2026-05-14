# Base Design Artifact Contracts

Use JSON for canonical artifacts. These contracts define the narrative design
surface consumed by the RPG overlay and RPG post-design stages. They are
runtime-neutral and must not include implementation code, asset prompts, engine
paths, or post-design payloads.

## `user_requirements.json`

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

## `chapter_linear_synopsis.json`

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

Do not include branches, scene scripts, runtime implementation details, or asset
prompts.

## `branch_graph.json`

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
      "body": "Optional prose used as context for RPG post-design",
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

Allowed `condition_type`: `unconditional`, `player_choice`, `state_gate`,
`outcome`, `terminal_resolution`.

Branch graph owns topology, source anchoring, and player-facing choice labels.
Executable state semantics belong in `game_ir.json`.

## `game_ir.json`

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

Allowed state variable `type`: `boolean`, `integer`, `number`, `string`,
`enum`.

Allowed effect `operation`: `set`, `increment`, `decrement`, `append`,
`remove`.

`game_ir.json` owns state variables, conditions, effects, progression rules,
and semantic continuity constraints. RPG overlay and post-design may realize
these semantics, but must not silently rewrite them.
