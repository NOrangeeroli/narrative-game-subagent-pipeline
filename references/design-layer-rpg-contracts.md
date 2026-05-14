# RPG Overlay Design Contracts

RPG overlay design is a narrative-first sidecar for `--target web-rpg` V3 runs.
It adds RPG map, quest, combat, equipment, and progression intent to an accepted
V3 story hierarchy without rewriting the V3 narrative graph.

## Authority Boundary

The public narrative authority remains:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

RPG overlay artifacts are target-specific sidecars:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
workspace/design_layer_rpg/rpg-overlay-review.json
workspace/design_layer_rpg/narrative-freeze.json
workspace/design_layer_rpg/rpg-postdesign-slices.json
```

RPG overlay agents must not create, delete, or rewrite public narrative nodes,
edges, edge conditions, edge effects, state variables, or endings. If an RPG
system needs new story-critical state, return a repair note.

## Required Flow

```text
StoryLevelExtractor
  -> AdaptationPolicyDesigner
  -> RPGSystemPlanner
  -> RPGDesignReviewer
  -> LevelStateGraphDesigner
  -> compile-design
  -> freeze-narrative
  -> prepare-rpg-postdesign-slices
  -> RPG postdesign agents
```

`RPGSystemPlanner` reads story hierarchy, facts, policy, and the prompt. It
does not read the compiled public graph.

`prepare_rpg_postdesign_slices.py` is the only stage that scans the full public
graph to bind RPG overlay intent to public node and edge ids.

## `rpg-overlay-plan.json`

Path:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
```

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGSystemPlanner",
    "mode": "narrative_first_overlay"
  },
  "source_story_levels": [],
  "story_slices": [],
  "region_intents": [],
  "map_intents": [],
  "questline_intents": [],
  "combat_intents": [],
  "equipment_intents": [],
  "progression_axes": [],
  "postdesign_scope": [],
  "repair_notes": []
}
```

### Story Slices

Each story slice groups V3 story units into one RPG realization scope.

```json
{
  "id": "slice.arc01.forest_threshold",
  "title": "Forest Threshold",
  "source_story_unit_ids": ["story.l1.ch03"],
  "criticality": "critical",
  "required_story_beats": [
    "The protagonist chooses whether to cross the forbidden boundary."
  ],
  "character_arc_beats": [],
  "emotional_turns": [],
  "scene_script_obligations": [
    {
      "id": "scene.forest_threshold.opening",
      "suggested_trigger": "on_entry",
      "required_beats": [
        "The protagonist hesitates at the boundary while the guide steps ahead."
      ],
      "staging_guidance": [
        "Bind the guide to a map event, move them toward the threshold, then face the party lead for dialogue."
      ]
    }
  ],
  "canon_constraints": [],
  "forbidden_changes": [],
  "map_intent_ids": ["map_intent.forest_threshold"],
  "questline_intent_ids": ["questline.cross_boundary"],
  "combat_intent_ids": [],
  "equipment_intent_ids": [],
  "progression_axis_ids": ["progression.courage"],
  "postdesign_allowed_outputs": [
    "workspace/rpg/maps/*.map.json",
    "workspace/rpg/quests.json",
    "workspace/rpg/npc-dialogue.json",
    "workspace/rpg/scene-scripts.json"
  ]
}
```

Critical slices need concrete narrative obligations. A critical slice that only
names a location or map shell is invalid.

Use `scene_script_obligations` when a slice needs authored scene blocking:
character entrances, exits, interrupting dialogue, route-opening moments,
companion exchanges, or any beat where actor movement and dialogue must be
scheduled together. If omitted, the postdesign slice binder may derive a
conservative obligation from `required_story_beats`, `character_arc_beats`, and
`emotional_turns`.

### RPG Intents

Every map, quest, combat, equipment, and progression intent must include:

- stable `id`;
- `story_slice_ids` or `source_story_unit_ids`;
- `narrative_function`;
- `story_obligations`;
- `forbidden_changes`.

Recommended `narrative_function` values:

```text
reveal
relationship_shift
moral_choice
loss
setup
payoff
ending_pressure
access
trial
recovery
atmosphere
exploration
combat_pressure
resource_pressure
```

## Forbidden Overlay Content

The overlay design layer must not include concrete runtime rows, such as:

- enemy HP, attack, defense, speed, damage, drop tables;
- item or equipment stat rows;
- shop inventory and prices;
- NPC dialogue lines;
- XP curves or level curves;
- concrete map collision, event positions, or runtime manifest fields.

Those belong to RPG postdesign and implementation.

## Review Contract

`RPGDesignReviewer` writes:

```text
workspace/design_layer_rpg/rpg-overlay-review.json
```

The review checks:

- story slices reference existing V3 story units;
- critical story units and beats are covered;
- every RPG intent has a narrative function;
- RPG systems express the V3 story instead of inventing a replacement plot;
- concrete postdesign rows are absent;
- repair notes are explicit when RPG needs conflict with narrative authority.

## Deterministic Commands

Validate overlay:

```bash
python3 scripts/run_pipeline.py validate-rpg-overlay --run-root <run>
```

Freeze public narrative after compile:

```bash
python3 scripts/run_pipeline.py freeze-narrative --run-root <run>
```

Prepare bounded RPG postdesign packets:

```bash
python3 scripts/run_pipeline.py prepare-rpg-postdesign-slices --run-root <run>
```

## Postdesign Binding

`prepare_rpg_postdesign_slices.py` binds by:

1. `story_unit_ids`
2. `source_derivation.base_story_unit_ids`
3. public node `story_unit_ids`
4. public edge state reads/writes
5. title, location, or fact fallback
6. repair notes

Postdesign workers receive packets under:

```text
workspace/controller-packets/postdesign/rpg/*.json
```

They should preserve trace fields in `workspace/rpg/*` wherever practical:

```json
{
  "trace": {
    "slice_id": "slice.arc01.forest_threshold",
    "intent_ids": ["questline.cross_boundary"],
    "story_unit_ids": ["story.l1.ch03"],
    "public_node_ids": ["v3.l1.ch03.choice"],
    "public_edge_ids": ["edge.ch03.cross"]
  }
}
```
