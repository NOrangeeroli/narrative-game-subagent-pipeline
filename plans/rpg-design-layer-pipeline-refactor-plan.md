# Narrative-First RPG Overlay Refactor Plan

## Goal

Refactor the RPG pipeline so RPG systems are added on top of the accepted V3
narrative design instead of replacing, reshaping, or reinterpreting it.

The target execution shape is:

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
  -> existing workspace/rpg/* outputs
```

The V3 designer remains the authority for fine-grained networked narrative.
RPG planning is a sidecar overlay that adds maps, quests, combat, equipment,
and progression as playable expression of the existing story.

## Non-Negotiable Design Rules

- `workspace/design_layer/branch_graph.json` and
  `workspace/design_layer/game_ir.json` remain the public narrative authority.
- RPG design must not create, delete, or rewrite public narrative nodes, edges,
  edge conditions, edge effects, endings, or canonical story states.
- `RPGSystemPlanner` must not read a huge compiled public graph. It reads V3
  story levels, facts, adaptation policy, and the user prompt.
- Complete public graph scanning is controller-owned deterministic work done by
  `prepare_rpg_postdesign_slices.py`, not LLM reading.
- RPG postdesign agents should read bounded slice packets, not the full graph,
  unless a controller repair ticket explicitly needs broader context.
- Web RPG runtime and existing `workspace/rpg/*` output files remain stable.
- Old RPG runs without `workspace/design_layer_rpg/` remain build-compatible;
  trace checks begin as warnings.

## Why This Shape

The previous RPG flow was purely postdesign:

```text
V3 design layer
  -> compile_design_v3
  -> branch_graph.json + game_ir.json
  -> RPGCampaignPlanner / RPGMapBuilder / RPGContentWriter
```

That makes RPG agents infer map, quest, combat, equipment, and progression
structure from a large fine-grained graph. For large V3 runs, fine graph nodes
are often state variants rather than RPG maps or quest beats. This can make the
runtime validate while the RPG structure feels like a shallow shell.

The overlay flow solves this by designing RPG structure from story hierarchy
while the story is still readable as story units, then deterministically binding
those RPG intents to the frozen public graph after `compile-design`.

## Layer Responsibilities

### V3 Story And Graph Design

V3 owns:

- source-grounded story extraction;
- canonical facts and adaptation policy;
- fine-grained networked graph topology;
- public edge conditions and effects;
- ending families and variants;
- public state variables and event rules.

V3 may receive RPG overlay notes only as optional read-only context. The default
mode is narrative-first: RPG planning does not constrain or rewrite the graph.

### RPG Overlay Design Layer

The RPG overlay design layer owns RPG intent, not concrete runtime content.

It writes:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
workspace/design_layer_rpg/rpg-overlay-review.json
reports/rpg-overlay-validation.json
```

It decides:

- story slices suitable for RPG realization;
- region and map intents;
- questline intents and story beat obligations;
- combat intents and their narrative functions;
- equipment and ability gate intents;
- progression axes that express existing story pressure;
- which RPG postdesign slice owns each intent;
- forbidden changes that protect the V3 narrative.

It must not write:

- public narrative graph changes;
- concrete map layouts;
- NPC dialogue lines;
- enemy stats;
- item, equipment, or shop rows;
- XP curves or numeric tuning;
- runtime manifest fields;
- asset prompts.

### Deterministic Binding Layer

After `compile-design`, the controller freezes public narrative artifacts and
binds RPG overlay intents to public graph ids.

It writes:

```text
workspace/design_layer_rpg/narrative-freeze.json
workspace/design_layer_rpg/rpg-postdesign-slices.json
workspace/controller-packets/postdesign/rpg/*.json
```

Binding priority:

1. `story_unit_ids`
2. `source_derivation.base_story_unit_ids`
3. public node `story_unit_ids`
4. public edge state reads/writes
5. title, location, or fact id fallback
6. unresolved repair notes

The binder may scan the complete graph because it is deterministic code. It
must output bounded packets for LLM postdesign workers.

### RPG Postdesign Layer

RPG postdesign owns concrete runtime content and keeps writing the existing
files:

```text
workspace/rpg/rpg-campaign.json
workspace/rpg/world-map.json
workspace/rpg/maps/*.map.json
workspace/rpg/actors.json
workspace/rpg/enemies.json
workspace/rpg/items.json
workspace/rpg/equipment.json
workspace/rpg/skills.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/encounter-tables.json
workspace/rpg/shops.json
workspace/rpg/rest-points.json
workspace/rpg/progression-rules.json
workspace/rpg/rpg-manifest.json
```

Each concrete map, quest, event, battle, equipment gate, or progression rule
should preserve trace to:

- `slice_id`
- RPG overlay intent ids
- `story_unit_ids`
- `public_node_ids`
- `public_edge_ids`
- existing state ids where applicable

If a postdesign agent finds it needs new story-critical state or a new major
branch, it must return an upstream repair note instead of inventing it inside
RPG runtime artifacts.

## RPG Overlay Plan Schema

Canonical path:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
```

Expected top-level shape:

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

Each `story_slices[]` entry should include:

```json
{
  "id": "slice.arc01.forest_threshold",
  "title": "Forest Threshold",
  "source_story_unit_ids": [],
  "criticality": "critical",
  "required_story_beats": [],
  "character_arc_beats": [],
  "emotional_turns": [],
  "canon_constraints": [],
  "forbidden_changes": [],
  "map_intent_ids": [],
  "questline_intent_ids": [],
  "combat_intent_ids": [],
  "equipment_intent_ids": [],
  "progression_axis_ids": [],
  "postdesign_allowed_outputs": []
}
```

Each RPG intent must include:

- stable `id`;
- `story_slice_ids` or `source_story_unit_ids`;
- `narrative_function`, such as `reveal`, `relationship_shift`,
  `moral_choice`, `loss`, `setup`, `payoff`, `ending_pressure`, `access`,
  `trial`, `recovery`, or `atmosphere`;
- `story_obligations`;
- `forbidden_changes`;
- optional existing state references, but no new public graph mutations.

## Narrative Freeze

Canonical path:

```text
workspace/design_layer_rpg/narrative-freeze.json
```

It records hashes and public ids for:

- `branch_graph.json`;
- `game_ir.json`;
- public node ids;
- public edge ids;
- public state ids;
- ending ids;
- story-unit-to-public-node index.

RPG stages can verify that public narrative files were not modified after the
freeze.

## Postdesign Slice Packet Schema

Canonical aggregate path:

```text
workspace/design_layer_rpg/rpg-postdesign-slices.json
```

Per-worker packet path:

```text
workspace/controller-packets/postdesign/rpg/<slice-id>.json
```

Expected packet shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "prepare_rpg_postdesign_slices.py"
  },
  "slice_id": "slice.arc01.forest_threshold",
  "source_story_unit_ids": [],
  "public_node_ids": [],
  "public_edge_ids": [],
  "existing_state_ids": [],
  "required_story_beats": [],
  "forbidden_changes": [],
  "allowed_outputs": [],
  "map_intents": [],
  "questline_intents": [],
  "combat_intents": [],
  "equipment_intents": [],
  "progression_axes": [],
  "public_node_summaries": [],
  "public_edge_summaries": [],
  "repair_notes": []
}
```

## Script Work

### Layout And Paths

Update `scripts/pipeline_lib.py`:

- add `workspace/design_layer_rpg/`;
- add `workspace/controller-packets/design-layer-rpg/`;
- add `workspace/controller-packets/postdesign/rpg/`;
- add path keys for overlay plan, review, freeze, postdesign slices, and report.

### Controller CLI

Update `scripts/run_pipeline.py`:

- adjust `init --target web-rpg --design-layer v3` TODOs to include the
  overlay stages;
- add `validate-rpg-overlay`;
- add `freeze-narrative`;
- add `prepare-rpg-postdesign-slices`.

Expected command sequence:

```bash
python3 scripts/run_pipeline.py compile-design --design-layer v3 --run-root <run>
python3 scripts/run_pipeline.py validate-rpg-overlay --run-root <run>
python3 scripts/run_pipeline.py freeze-narrative --run-root <run>
python3 scripts/run_pipeline.py prepare-rpg-postdesign-slices --run-root <run>
python3 scripts/run_pipeline.py build --target web-rpg --run-root <run>
```

### Validator

Add `scripts/validate_rpg_overlay.py`.

Checks:

- overlay plan exists and is JSON object;
- every story slice references existing V3 story units;
- critical story slices have required story beats or obligations;
- every RPG intent references a slice or story unit;
- every RPG intent declares a narrative function;
- concrete runtime rows are absent from overlay files;
- optional post-compile graph checks can verify slice/node ratio and coverage;
- write `reports/rpg-overlay-validation.json`.

### Freeze

Add `scripts/freeze_narrative.py`.

Checks:

- public `branch_graph.json` exists;
- public `game_ir.json` exists;
- output stable canonical JSON hashes and id indexes.

### Binder

Add `scripts/prepare_rpg_postdesign_slices.py`.

Checks:

- overlay plan exists;
- public graph exists;
- optional narrative freeze hashes still match;
- slice bindings are deterministic;
- unresolved story or graph bindings become repair notes;
- write aggregate slices and per-slice packets.

### Build-Time Trace Checks

Update `scripts/compile_rpg_manifest.py` and `scripts/validate_rpg.py`:

- if `rpg-postdesign-slices.json` is absent, warn only;
- if present, warn when RPG artifacts lack trace to slice ids or public node
  ids;
- warn if frozen public narrative hashes no longer match;
- do not fail old runs yet.

## Contract And Role Work

Rewrite:

- `references/design-layer-rpg-contracts.md`;
- `references/design-layer-rpg-prompts.md`.

Replace copied V3 cards under `references/subagents/design-layer-rpg/` with:

- `RPGSystemPlanner.md`;
- `RPGDesignReviewer.md`.

Update RPG postdesign role cards:

- `RPGCampaignPlanner.md`;
- `RPGMapBuilder.md`;
- `RPGContentWriter.md`;
- `RPGBalanceReviewer.md`.

Update `references/subagents/README.md` with a distinct RPG Overlay Design
section.

## Regression Tests

Add:

```text
tests/run_rpg_overlay_regression.py
```

Test cases:

- minimal V3 story hierarchy validates with an RPG overlay plan;
- `freeze_narrative.py` writes stable graph and IR hashes;
- deterministic binder maps story-unit based slices to public nodes and edges;
- large-ish public graph becomes fewer RPG postdesign packets than graph nodes;
- RPG build path remains compatible when overlay files are absent;
- VN build ignores `workspace/design_layer_rpg/`.

## Success Criteria

- V3 still owns the complete networked plot.
- RPG planning happens from story hierarchy, not from a huge public graph.
- RPG systems are additive and traceable to existing story units/nodes/edges.
- Postdesign workers receive bounded slice packets.
- Public narrative artifacts remain frozen during RPG stages.
- Existing Web RPG runtime and `workspace/rpg/*` contracts remain stable.
