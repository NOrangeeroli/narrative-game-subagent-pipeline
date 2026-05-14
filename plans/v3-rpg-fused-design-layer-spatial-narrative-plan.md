# V3 RPG Fused Design Layer And Spatial Narrative Execution Plan

## Goal

Merge V3 story design and RPG overlay into one RPG-first design layer so RPG
macro architecture shapes the narrative graph before it is compiled.

This plan replaces a weak sidecar model:

```text
V3 graph is generated
  -> RPG overlay binds to the finished graph
  -> postdesign tries to make the graph feel like an RPG
```

with a fused graph-design model:

```text
V3 story extraction
  -> adaptation policy
  -> RPG narrative architecture
  -> RPG graph directives
  -> V3 graph/state design consumes RPG directives
  -> graph/RPG/spatial integration review
  -> compile-design
  -> narrative freeze
  -> bound semantic module packets
  -> module-scoped RPG postdesign
  -> Web implementation packets
  -> playable runtime export
```

The public narrative authority remains:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

The design layer must preserve source anchoring. RPG design pressure can split
source story units into playable event variants, require graph state, require
spatial gates, and impose postdesign contracts, but it must not replace the
source story with unrelated RPG progression.

## Core Design Principle

Spatial RPG adaptation is not an art pass. It is graph design.

For a critical story beat, the graph should answer:

- where the beat is playable;
- why that place matters to the story;
- what player-visible actions happen there;
- what object, NPC, movement, route, or combat pressure carries the beat;
- what state changes when the player inspects, returns, uses, waits, follows,
  refuses, fights, flees, or crosses a threshold;
- how the same place means something different after state changes.

If these answers are postponed until map postdesign, the RPG layer can only
decorate the story. If they are present during graph/state design, the graph
can become a playable spatial narrative.

## Canonical New Artifacts

Keep `rpg-overlay-plan.json` temporarily for compatibility, but add graph-facing
artifacts that make the RPG layer a first-class design input.

```text
workspace/design_layer_rpg/rpg-narrative-architecture.json
workspace/design_layer_rpg/rpg-graph-directives.json
workspace/design_layer_rpg/slices/level_<NN>/*.graph-directives.json
workspace/design_layer_rpg/module-intents.json
workspace/design_layer_rpg/rpg-graph-integration-review.json
workspace/controller-packets/postdesign/rpg/module-index.json
workspace/controller-packets/postdesign/rpg/modules/<module-id>.semantic-design-module.json
workspace/controller-packets/implementation/web-rpg/modules/<module-id>.web-implementation-packet.json
workspace/runtime/web-rpg/runtime-verb-contracts.json
```

### `rpg-narrative-architecture.json`

Purpose: define the RPG macro architecture before graph generation.

It answers how the player inhabits the story through places, route structure,
quests, story objects, NPC functions, scene blocking, combat pressure, and
progression pressure.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGSystemPlanner",
    "mode": "graph_precondition"
  },
  "campaign_arc_intents": [],
  "story_slices": [],
  "region_intents": [],
  "map_intents": [],
  "questline_intents": [],
  "story_object_intents": [],
  "npc_function_intents": [],
  "combat_intents": [],
  "progression_axes": [],
  "scene_blocking_intents": [],
  "spatial_narrative_intents": [],
  "forbidden_changes": [],
  "repair_notes": []
}
```

Rules:

- Every intent references source story units, fact ids, character ids,
  location ids, or adaptation policy permissions.
- Every intent names its narrative function.
- No concrete runtime rows: no map coordinates, collision shapes, item stats,
  enemy stats, shop rows, dialogue scripts, or asset prompts.

### `rpg-graph-directives.json`

Purpose: convert RPG macro architecture into graph-design obligations consumed
by `LevelStateGraphDesigner`.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGSystemPlanner",
    "mode": "graph_design_directives"
  },
  "level_directives": [
    {
      "level_id": "level_01",
      "story_unit_ids": ["story.l1.hall_of_doors"],
      "node_split_obligations": [],
      "state_design_directives": [],
      "edge_affordance_obligations": [],
      "spatial_progression_obligations": [],
      "story_object_obligations": [],
      "npc_function_obligations": [],
      "combat_pressure_obligations": [],
      "scene_blocking_obligations": [],
      "contract_obligations": [],
      "spatial_narrative_obligations": []
    }
  ],
  "global_state_directives": [],
  "ending_pressure_directives": [],
  "repair_notes": []
}
```

Directive categories:

- `node_split_obligations`: story units that must expand into multiple
  source-anchored graph nodes because RPG interaction should expose different
  event versions, failed versions, revisits, delayed outcomes, or consequences.
- `state_design_directives`: graph state variables required by RPG actions,
  spatial gates, story objects, NPC responses, route memory, or combat cost.
- `edge_affordance_obligations`: player-visible action types that should appear
  as graph edges, such as inspect, use object, wait, approach, avoid, follow,
  ask, trade, fight, flee, help, refuse, revisit, or cross threshold.
- `spatial_progression_obligations`: route logic that must be visible in graph
  topology, such as locked access, loopback, shortcut reveal, threshold
  crossing, return with new knowledge, route-specific entry, or transformed
  traversal.
- `story_object_obligations`: objects that must carry story state through
  pickup, inspection, use, loss, transformation, or evidence revelation.
- `npc_function_obligations`: NPC roles that must affect state, access,
  interpretation, route memory, scene timing, or spatial pressure.
- `combat_pressure_obligations`: encounters that express story pressure,
  risk, cost, pursuit, trial, or moral pressure instead of generic combat.
- `scene_blocking_obligations`: beats that require actor movement, entrance,
  exit, facing, wait, reveal, quest update, object reveal, or transfer timing.
- `contract_obligations`: downstream realization constraints that must be
  encoded in V3 contracts.
- `spatial_narrative_obligations`: graph-time requirements that explain how
  place, movement, object placement, NPC placement, and return visits carry
  story meaning.

### Directive Slice Files

The controller derives read-only slices for graph workers:

```text
workspace/design_layer_rpg/slices/level_<NN>/*.graph-directives.json
```

Slicing rules:

- Coarsest graph worker receives global directives plus all coarsest story-unit
  directives.
- Non-coarsest graph workers receive only directives for their assigned parent
  context and same-level story units.
- Slice files contain no new creative content. They are deterministic
  projections from `rpg-graph-directives.json`.

## Module-Oriented Design Output

The design layer should not only emit global design files that are hard to
parallelize. It must also emit module-oriented work units that can be assigned
to postdesign and implementation agents.

The module is a vertical playable slice, not a horizontal table slice.

Bad split:

```text
one agent writes all maps
one agent writes all items
one agent writes all NPC dialogue
one agent writes all scene scripts
```

Better split:

```text
module.alice.riverbank_chase
  owns the riverbank map slice, rabbit NPC behavior, opening chase scene,
  follow-rabbit quest step, relevant items, events, assets, and tests

module.alice.hall_of_doors
  owns the hall map slice, tiny door gate, key/bottle objects, size state,
  return route, garden threshold scene, assets, and tests
```

The final canonical RPG files may still be global:

```text
workspace/rpg/items.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/scene-scripts.json
```

but agents should author module payloads first. The controller/compiler merges
accepted module payloads into global files.

### Three-Layer Module Handoff

Module handoff has three separate layers. Do not collapse them into one file.

```text
graph-time module intent
  -> bound semantic design module
  -> Web implementation packet
```

1. `module-intents.json` is graph-time, pre-compile, and source/story based.
   It helps shape graph design and module boundaries, but it must not name
   public graph ids or Web implementation paths.
2. `semantic-design-module.json` is generated after `compile-design` and
   `freeze-narrative`. It binds module intent to public node ids, edge ids,
   state ids, RPG directives, and spatial obligations. It is engine-neutral.
3. `web-implementation-packet.json` is target-specific. It is generated from
   the semantic module plus Web RPG runtime capabilities. It may name Web paths,
   standard verbs, custom hooks, handlers, generated tests, and module registry
   entries.

This separation keeps design artifacts semantic while still producing concrete,
parallelizable implementation packets.

### `module-intents.json`

Purpose: list graph-time module candidates and boundaries before public graph
ids exist.

Path:

```text
workspace/design_layer_rpg/module-intents.json
```

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RPGSystemPlanner",
    "mode": "module_intents"
  },
  "module_intents": [
    {
      "id": "module.alice.hall_of_doors",
      "title": "Hall of Doors",
      "module_type": "spatial_story_slice",
      "source_story_unit_ids": ["story.l1.hall_of_doors"],
      "rpg_directive_ids": ["directive.hall.spatial_gate"],
      "expected_state_hooks": [
        "state.alice.size",
        "state.hall.tiny_key_collected"
      ],
      "expected_runtime_namespaces": [
        "map.hall_of_doors",
        "item.hall.*",
        "quest.hall.*",
        "scene.hall.*",
        "event.hall.*"
      ],
      "depends_on_intent_ids": ["module.alice.rabbit_hole_fall"],
      "parallel_group_hint": "arc01.group02",
      "handoff_notes": []
    }
  ],
  "shared_intents": [
    {
      "id": "shared.party",
      "owned_by": "module.core.party",
      "reader_intent_ids": ["module.alice.hall_of_doors"],
      "writer_intent_ids": []
    }
  ],
  "repair_notes": []
}
```

Rules:

- Module intents may reference story units, RPG directive ids, state hook
  names, expected namespaces, and dependency hints.
- Module intents must not reference public node ids, public edge ids, concrete
  Web paths, handler names, JS files, or runtime hook implementations.
- A module intent should be sized so one later worker can understand and
  implement it as a playable slice.

### `module-index.json`

Purpose: list all design-approved development modules, their dependency order,
parallelization groups, and ownership boundaries.

Path:

```text
workspace/controller-packets/postdesign/rpg/module-index.json
```

This file is generated after public graph compilation and narrative freeze from:

```text
module-intents.json
branch_graph.json
game_ir.json
narrative-freeze.json
rpg-graph-directives.json
```

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "ModulePacketBinder",
    "mode": "module_index"
  },
  "modules": [
    {
      "id": "module.alice.hall_of_doors",
      "title": "Hall of Doors",
      "module_type": "spatial_story_slice",
      "parallel_group": "arc01.group02",
      "depends_on": ["module.alice.rabbit_hole_fall"],
      "unlocks": ["module.alice.garden_threshold"],
      "owned_story_unit_ids": ["story.l1.hall_of_doors"],
      "owned_public_node_ids": [],
      "owned_public_edge_ids": [],
      "owned_state_ids": [
        "state.alice.size",
        "state.hall.tiny_key_collected"
      ],
      "owned_semantic_namespaces": [
        "map.hall_of_doors",
        "item.hall.*",
        "quest.hall.*",
        "scene.hall.*",
        "event.hall.*"
      ],
      "allowed_postdesign_output_paths": [
        "workspace/rpg/modules/module.alice.hall_of_doors/*.json"
      ],
      "integration_points": [
        {
          "kind": "entry",
          "from_module_id": "module.alice.rabbit_hole_fall",
          "state_contract": "state.route.entered_hall == true"
        },
        {
          "kind": "exit",
          "to_module_id": "module.alice.garden_threshold",
          "state_contract": "state.hall.garden_access_unlocked == true"
        }
      ]
    }
  ],
  "shared_resources": [
    {
      "id": "shared.party",
      "owner_module_id": "module.core.party",
      "resource_ids": ["actor.alice"],
      "initializer_module_ids": ["module.core.party"],
      "writer_module_ids": [],
      "reader_module_ids": ["module.alice.hall_of_doors"]
    }
  ]
}
```

Rules:

- A module owns a coherent playable unit: a place, quest step, scene sequence,
  encounter cluster, or route segment.
- A module may contribute to multiple RPG tables, but only inside its declared
  namespaces.
- A module packet must be small enough for one agent to understand without the
  full graph.
- Cross-module communication uses explicit state, transfer, quest, and event
  contracts, not hidden assumptions.
- Parallel groups may run concurrently only when their owned ids and output
  paths are disjoint.
- Shared resources must be explicit. A shared resource has one owner and
  separate initializer, writer, and reader permissions.

### `<module-id>.semantic-design-module.json`

Purpose: package all design-layer evidence and obligations needed by one
postdesign worker.

Path:

```text
workspace/controller-packets/postdesign/rpg/modules/<module-id>.semantic-design-module.json
```

This packet is semantic and engine-neutral. It must not include Web paths,
handler names, JavaScript file names, or DOM/runtime implementation details.

Shape:

```json
{
  "id": "module.alice.hall_of_doors",
  "title": "Hall of Doors",
  "source_story_unit_ids": ["story.l1.hall_of_doors"],
  "public_node_ids": ["node.hall.enter", "node.hall.inspect_door"],
  "public_edge_ids": ["edge.hall.inspect_key", "edge.hall.drink"],
  "rpg_directive_ids": ["directive.hall.spatial_gate"],
  "spatial_narrative_obligations": [],
  "story_object_obligations": [],
  "npc_function_obligations": [],
  "scene_blocking_obligations": [],
  "required_state_hooks": [],
  "owned_semantic_runtime_ids": {
    "maps": ["map.hall_of_doors"],
    "events": ["event.hall.tiny_door", "event.hall.bottle"],
    "items": ["item.hall.tiny_key", "item.hall.drink_me_bottle"],
    "quests": ["quest.hall.reach_garden"],
    "scene_scripts": ["scene.hall.garden_threshold"]
  },
  "runtime_verb_requirements": [
    {
      "id": "verb.hall.inspect_tiny_door",
      "standard_verb": "inspect_object",
      "required": true,
      "reads": ["state.alice.size", "state.hall.tiny_key_collected"],
      "writes": ["state.hall.tiny_door_understood"],
      "fallback_policy": "fail_if_missing"
    }
  ],
  "dependencies": [],
  "handoff_notes": []
}
```

This file is the preferred packet source for postdesign workers. It is also the
semantic source for later target-specific implementation packets.

### `<module-id>.web-implementation-packet.json`

Purpose: target-specific Web implementation handoff derived from one semantic
design module and the Web RPG runtime capability registry.

Path:

```text
workspace/controller-packets/implementation/web-rpg/modules/<module-id>.web-implementation-packet.json
```

Shape:

```json
{
  "id": "module.alice.hall_of_doors",
  "target": "web-rpg",
  "semantic_module_path": "workspace/controller-packets/postdesign/rpg/modules/module.alice.hall_of_doors.semantic-design-module.json",
  "module_path": "implementation/web-rpg/modules/module.alice.hall_of_doors",
  "allowed_output_paths": [
    "implementation/web-rpg/modules/module.alice.hall_of_doors/**",
    "tests/web-rpg/modules/module.alice.hall_of_doors/**"
  ],
  "standard_verbs": [
    "inspect_object",
    "use_item",
    "state_gate",
    "transformation",
    "route_revisit"
  ],
  "custom_hooks": [
    {
      "id": "hook.hall.inspect_tiny_door",
      "handler": "handleInspectTinyDoor",
      "trigger": "inspect_object",
      "required": true,
      "reads": ["state.alice.size", "state.hall.tiny_key_collected"],
      "writes": ["state.hall.tiny_door_understood"],
      "fallback_policy": "fail_if_missing",
      "fallback": null
    }
  ],
  "required_handlers": [
    "handleInspectTinyDoor",
    "handleDrinkMeBottle",
    "handleGardenDoorGate"
  ],
  "required_tests": [
    "test_hall_key_without_size_blocks_access",
    "test_hall_key_and_small_size_unlocks_garden_threshold"
  ]
}
```

This packet is the preferred input for Web code workers. A code worker should
be able to implement one module without touching unrelated modules or global
runtime files.

## Module-Scoped Postdesign And Implementation

Postdesign should become module-first. Role cards can still exist, but the
primary ownership unit is the design module.

Default dispatch:

```text
module.alice.hall_of_doors
  -> one module owner receives the semantic-design-module packet
  -> optional role-specific workers operate inside the module namespace
  -> controller accepts module payload
  -> compiler merges module payload into global RPG artifacts
  -> controller derives a Web implementation packet
  -> implementation worker receives the Web implementation packet
  -> implementation worker writes only the module implementation path
```

Module postdesign outputs should live under:

```text
workspace/rpg/modules/<module-id>/module-rpg-payload.json
workspace/rpg/modules/<module-id>/module-asset-needs.json
workspace/rpg/modules/<module-id>/module-test-plan.json
```

`module-rpg-payload.json` may contain contributions to many global tables, but
only for ids owned by the module:

```json
{
  "module_id": "module.alice.hall_of_doors",
  "maps": [],
  "events": [],
  "actors": [],
  "items": [],
  "quests": [],
  "npc_dialogue": [],
  "scene_scripts": [],
  "enemies": [],
  "encounter_tables": [],
  "shops": [],
  "rest_points": [],
  "progression_rules": [],
  "trace": {
    "source_story_unit_ids": [],
    "public_node_ids": [],
    "public_edge_ids": [],
    "rpg_directive_ids": []
  }
}
```

The merge step writes the existing canonical files:

```text
workspace/rpg/maps/*.map.json
workspace/rpg/items.json
workspace/rpg/quests.json
workspace/rpg/npc-dialogue.json
workspace/rpg/scene-scripts.json
workspace/rpg/events.json
workspace/rpg/rpg-manifest.json
```

Implementation workers should receive the Web implementation packet plus the
compiled module payload and write only declared module-owned paths, for example:

```text
implementation/web-rpg/modules/module.alice.hall_of_doors/**
tests/web-rpg/modules/module.alice.hall_of_doors/**
```

This keeps final game code parallelizable. It also prevents a worker from
needing to understand or edit every global table just to implement one playable
slice.

### Module Ownership Rules

- Every authored runtime id must be owned by exactly one module.
- Shared ids must be declared in `module-index.json` under a core/shared owner
  such as `module.core.party`, `module.core.ui`, or `module.core.shared_state`.
  Shared resources distinguish `owner`, `initializer`, `writer`, and `reader`
  permissions.
- Module workers may reference external state, quests, or events only through
  declared `dependencies` and `integration_points`.
- Module workers must not edit global RPG files directly.
- The controller merges accepted module payloads and rejects id collisions,
  undeclared writes, missing dependencies, or unresolved integration points.
- A module should be sized for one agent to implement final game code in one
  bounded workspace. If a module is too large, split it by playable route,
  scene sequence, or map region, not by global artifact type.

## Playable Code Extensibility Model

The Web RPG runtime should remain stable, but it must not remain a closed,
one-size-fits-all template. A fixed runtime with only movement, dialogue,
pickup, transfer, and battle will make different generated stories feel like
the same shell with different text.

Use a three-layer playable-code model:

```text
Core runtime shell
  -> standard RPG verb library
  -> module-specific hooks
```

### Core Runtime Shell

`assets/web-rpg-template/runtime.js` remains the stable shell. It owns:

- data loading from `game-data.js`;
- map rendering, camera, input, movement, collision, and transfer;
- canonical state storage for flags, inventory, quests, party, and scene state;
- dialogue, inventory, battle, rest, and scene-script scheduling;
- asset lookup, audio playback, save/load, and debug overlays;
- module loading, hook registration, and runtime API dispatch.

The shell should expose a narrow runtime API to module hooks. Hooks should not
mutate global state or DOM directly. They should request changes through API
methods such as:

```text
getState
setFlag
updateQuest
addItem
removeItem
showDialogue
runSceneScript
transfer
playSfx
registerEventHandler
completeHook
```

### Standard RPG Verb Library

Common story interactions should be declarative verbs, not custom code every
time. The verb library is part of the stable runtime contract and can be tested
once, then reused across modules.

Initial verb targets:

```text
inspect_object
inspect_inventory_item
use_item
combine_items
state_gate
threshold_transfer
route_revisit
timed_scene
follow_or_chase
hide_or_reveal_event
transformation
evidence_reveal
companion_response
conversation_branch
puzzle_gate
combat_pressure
resource_cost
memory_recall
```

Semantic modules should prefer standard verbs. A custom hook is allowed only
when the module needs behavior that cannot be expressed by the standard verb
schema.

### Module-Specific Hooks

Module hooks are the controlled escape hatch that prevents the fixed runtime
from becoming rigid.

Hook files should live only under module-owned implementation paths:

```text
implementation/web-rpg/modules/<module-id>/hooks.js
implementation/web-rpg/modules/<module-id>/module.json
tests/web-rpg/modules/<module-id>/**
```

Each custom hook must be declared in the Web implementation packet before
implementation:

```json
{
  "id": "hook.hall.drink_me_bottle",
  "module_id": "module.alice.hall_of_doors",
  "handler": "handleDrinkMeBottle",
  "trigger": "use_item",
  "required": true,
  "reads": ["state.alice.size", "inventory.item.hall.drink_me_bottle"],
  "writes": ["state.alice.size", "state.hall.size_changed"],
  "calls": ["runSceneScript", "setFlag", "removeItem"],
  "fallback_policy": "fail_if_missing",
  "fallback": null
}
```

Hook rules:

- A hook belongs to exactly one module.
- A hook can read or write only declared state, inventory, quest, event, and
  scene-script ids.
- A required hook must fail validation when missing. Fallback behavior is only
  allowed for optional hooks or explicitly degraded preview builds.
- A hook must have contract tests generated from its Web implementation packet
  and semantic design module.
- A hook must not modify core runtime files.
- A hook must not import or call another module except through declared
  integration points.

### `runtime-verb-contracts.json`

Purpose: describe standard verbs and allowed hook API for the run.

Path:

```text
workspace/runtime/web-rpg/runtime-verb-contracts.json
```

This is not a design-layer artifact. It is compiled after semantic modules and
Web implementation packets exist.

Shape:

```json
{
  "metadata": {
    "schema_version": "0.1.0",
    "generated_by": "RuntimeVerbContractCompiler"
  },
  "standard_verbs": [
    {
      "id": "transformation",
      "description": "Change player or world state and optionally run a scene script.",
      "required_fields": ["reads", "writes"],
      "allowed_runtime_calls": ["setFlag", "runSceneScript", "showDialogue"]
    }
  ],
  "module_hooks": [
    {
      "module_id": "module.alice.hall_of_doors",
      "hook_id": "hook.hall.drink_me_bottle",
      "handler": "handleDrinkMeBottle",
      "allowed_runtime_calls": ["setFlag", "removeItem", "runSceneScript"],
      "required_tests": ["test_hall_drink_changes_size_state"]
    }
  ]
}
```

The exporter should include this contract in `game-data.js` or a companion
module registry so the runtime can load only declared module code.

## Required Agent Flow

```text
StoryLevelExtractor
  -> AdaptationPolicyDesigner
  -> RPGSystemPlanner
     writes rpg-narrative-architecture.json
     writes rpg-graph-directives.json
     writes module-intents.json
  -> RPGDesignReviewer
     reviews architecture and graph directives before graph generation
  -> controller slices graph directives
  -> LevelStateGraphDesigner
     consumes graph directive slices during graph/state design
  -> RPGGraphIntegrationReviewer
     verifies graph, state, contracts, and spatial obligations
  -> compile-design
  -> freeze-narrative
  -> controller binds module-intents into module-index and semantic modules
  -> prepare-rpg-postdesign-slices
  -> module-scoped RPG postdesign workers
  -> controller builds Web implementation packets
  -> runtime verb contract compiler
  -> module-scoped implementation workers
  -> runtime shell export with module hook registry
```

## Role Changes

### RPGSystemPlanner

Current role: write a post-graph RPG overlay plan.

New role: write graph-precondition RPG architecture and graph directives.

Responsibilities:

- group source story units into RPG-sized playable slices;
- identify where space should carry story meaning;
- define required map, questline, story object, NPC, combat, progression, and
  scene-blocking intents;
- produce graph-facing obligations for node splits, state variables, edge
  affordances, spatial gates, object state, NPC functions, and contracts;
- produce module intents that can later be bound to public graph ids after
  compile/freeze;
- return repair notes when RPG playability requires source-level or
  adaptation-policy clarification.

### RPGDesignReviewer

Current role: check overlay fidelity.

New role: check whether RPG graph directives are faithful, useful, and still
design-layer appropriate.

It must reject:

- directives that invent unrelated plot;
- directives that require concrete runtime rows too early;
- critical slices with only map names and no narrative obligations;
- spatial obligations that do not name story state, route logic, object logic,
  NPC function, or return logic;
- RPG systems that cannot bind back to source story units or facts.

### LevelStateGraphDesigner

Current role: design V3 graph/state from story units, facts, parent context, and
adaptation policy.

New role: also consume graph directive slices as hard design input.

For each assigned directive, it must satisfy the directive or return a repair
note. It should encode satisfaction through existing artifacts:

- `state_model.json`: state variables for story objects, route memory, access,
  place meaning, NPC response, risk, cost, or body/world transformation;
- `story_graph.json`: source-anchored node splits, player-visible edges,
  state-gated routes, loopbacks, revisits, delayed outcomes, thresholds, and
  convergence that preserves route memory;
- `contracts.json`: postdesign requirements for maps, objects, NPCs, scene
  scripts, combat pressure, and spatial narrative obligations;
- `parent_state_settlements.json`: how local spatial or RPG results settle into
  parent-level outcomes.

### RPGGraphIntegrationReviewer

New role card to add:

```text
references/subagents/design-layer-rpg/RPGGraphIntegrationReviewer.md
```

Canonical output:

```text
workspace/design_layer_rpg/rpg-graph-integration-review.json
```

Checks:

- every critical RPG story slice maps to graph nodes or explicit repair notes;
- required node splits are present where canon allows them;
- required state variables are declared and read or written by edges,
  contracts, or parent settlements;
- required RPG affordances are visible as player actions, not hidden prose;
- story-critical objects have graph-level state hooks;
- spatial progression appears in graph topology through gates, loopbacks,
  revisits, route-specific entries, or threshold transitions;
- scene blocking obligations remain traceable to graph nodes and contracts;
- combat and progression intent are tied to narrative pressure, not generic
  system loops;
- return visits change meaning through state rather than repeating content.

## Spatial Narrative Contract

Spatial narrative obligations must be authored before postdesign. A critical
RPG slice should include the following fields in either
`rpg-narrative-architecture.json`, `rpg-graph-directives.json`, or both.

```json
{
  "where": ["location.hall_of_doors"],
  "why_here": "The hall externalizes Alice's desire, wrong scale, and delayed understanding of access.",
  "route_logic": [
    "The tiny door is visible before it is usable.",
    "The room loops back after Alice changes size.",
    "Garden access is gated by both key state and size state."
  ],
  "object_logic": [
    "The tiny key turns curiosity into a concrete access problem.",
    "The bottle changes body state and reinterprets the same room."
  ],
  "npc_placement_logic": [],
  "scene_blocking_logic": [
    "Alice should face the door before understanding the size problem.",
    "The successful return to the door should use a short scripted approach."
  ],
  "return_logic": [
    "First visit is confusion.",
    "Second visit is blocked understanding.",
    "Third visit is transformed access."
  ],
  "required_state_hooks": [
    "state.alice.size",
    "state.hall.tiny_key_collected",
    "state.hall.tiny_door_understood"
  ]
}
```

### Spatial Narrative Minimums

For every critical slice:

- `where` names one or more story places.
- `why_here` explains the place's narrative function, such as concealment,
  temptation, danger, memory, threshold, social pressure, loss, revelation,
  pursuit, disorientation, or return.
- `route_logic` explains how traversal carries story state.
- `object_logic` identifies at least one inspectable object, evidence, key,
  memory, tool, or absence that carries story meaning, unless the slice is
  explicitly non-object-based.
- `npc_placement_logic` explains how NPC location, distance, entrance, exit,
  facing, pursuit, help, obstruction, or absence expresses the beat.
- `scene_blocking_logic` identifies any beat requiring scheduled movement,
  facing, reveal, wait, transfer, or state write.
- `return_logic` says how revisiting a place changes its meaning, or explains
  why the slice is one-way.
- `required_state_hooks` names the state that makes the spatial meaning
  executable by graph and runtime.

## How Spatial Narrative Enters The Graph

Spatial narrative should affect these graph dimensions:

1. Node topology.
   - Split a story unit when the place needs multiple playable meanings:
     arrival, inspection, failed access, object discovery, transformation,
     return, consequence, or exit.
2. Edge affordances.
   - Use player-visible actions: inspect, use, wait, follow, approach, avoid,
     cross, return, ask, refuse, help, fight, flee.
3. State model.
   - Record place meaning and route memory, not only inventory or quest flags.
     Examples: `state.hall.door_understood`,
     `state.forest.shortcut_known`, `state.castle.guard_trust`,
     `state.rabbit_seen_route`.
4. Contracts.
   - Make downstream RPG realization obligations explicit:
     required map role, required object, required NPC function,
     required scene script, required battle pressure, required revisit.
5. Parent settlements.
   - Summarize spatial outcomes upward: crossed threshold, failed access,
     learned route, lost time, gained trust, escalated pursuit, changed body,
     accepted cost.

## Alice Hall Example

The hall of doors should not compile to one generic graph node. It should become
a spatial puzzle expressed through graph structure:

```json
{
  "story_unit_id": "story.l1.hall_of_doors",
  "node_split_obligations": [
    {
      "reason": "The scene is a spatial puzzle about desire, size, access, and delayed understanding.",
      "required_variants": [
        "enter_hall_and_notice_many_doors",
        "inspect_tiny_door_without_key",
        "find_key_but_wrong_size",
        "drink_to_change_size",
        "return_to_tiny_door_with_access_state",
        "reach_garden_threshold"
      ]
    }
  ],
  "state_design_directives": [
    "state.alice.size",
    "state.hall.tiny_key_seen",
    "state.hall.tiny_key_collected",
    "state.hall.tiny_door_understood",
    "state.hall.garden_desire_awakened"
  ],
  "edge_affordance_obligations": [
    "inspect_object",
    "use_item",
    "drink",
    "return_to_locked_access",
    "state_gate"
  ],
  "story_object_obligations": [
    "tiny key must be inspectable and must write evidence/access state",
    "drink me bottle must transform access state and trigger consequence"
  ],
  "spatial_progression_obligations": [
    "same room should mean different things before and after size change",
    "door access should be a spatial gate, not only dialogue exposition"
  ],
  "spatial_narrative_obligations": [
    {
      "where": ["location.hall_of_doors"],
      "why_here": "The room turns Alice's curiosity into a visible access problem.",
      "route_logic": [
        "The tiny door is discoverable before Alice can use it.",
        "The key and size states must both be true before garden access."
      ],
      "object_logic": [
        "The tiny key is evidence of a solvable door, not just inventory.",
        "The bottle changes Alice's body state and redefines the same map."
      ],
      "return_logic": [
        "Returning after the size change must unlock a different graph route."
      ],
      "required_state_hooks": [
        "state.alice.size",
        "state.hall.tiny_key_collected",
        "state.hall.tiny_door_understood"
      ]
    }
  ]
}
```

## Validation Gates

Add deterministic validation in stages.

### Gate 1: RPG Graph Directive Validation

Command target:

```text
python3 scripts/run_pipeline.py validate-rpg-overlay --run-root <run>
```

Extend validation to check:

- every directive references existing story units or facts;
- every critical slice has narrative obligations, not only locations;
- every spatial narrative obligation has `where`, `why_here`, `route_logic`,
  and `required_state_hooks`;
- no concrete runtime rows appear in graph directives;
- repair notes are explicit when obligations cannot be authored safely.

### Gate 2: Graph Integration Validation

Add or extend a command:

```text
python3 scripts/run_pipeline.py validate-rpg-graph-integration --run-root <run>
```

Check:

- directive story units appear in graph nodes;
- required node splits exist or have accepted repair notes;
- required state hooks exist in state models;
- required edge affordances appear in graph edges or contracts;
- required spatial progression appears as gates, loopbacks, revisits,
  route-specific entries, or threshold transitions;
- story-object obligations have state reads/writes;
- scene-blocking obligations appear in graph contracts and postdesign packets.

### Gate 3: Postdesign Slice Validation

Extend:

```text
python3 scripts/run_pipeline.py prepare-rpg-postdesign-slices --run-root <run>
```

Check each packet carries:

- source story unit ids;
- public node ids and edge ids;
- semantic module ids and packet paths;
- RPG directive ids;
- spatial narrative obligations;
- required state hooks;
- scene script obligations;
- allowed output paths.

### Gate 4: Module Boundary Validation

Add validation after module packet generation and before postdesign dispatch:

```text
python3 scripts/run_pipeline.py validate-rpg-modules --run-root <run>
```

Check:

- every critical graph node belongs to exactly one module or has an explicit
  shared integration contract;
- every module has owned story units, owned semantic namespaces, allowed
  postdesign output paths, dependencies, and integration points;
- module dependencies are acyclic or explicitly marked as runtime loops;
- parallel groups have disjoint owned ids and output paths;
- module packets include all spatial, object, NPC, scene, state, and test
  obligations needed to implement the module without reading the full graph;
- module size stays within a bounded packet budget, with large modules split by
  playable route, scene sequence, or map region.

### Gate 5: Module Payload Merge Validation

Run after module-scoped postdesign workers return payloads.

Check:

- every module payload writes only ids and paths declared in its module
  contract;
- no two module payloads define the same runtime id unless one is the declared
  owner and the other is a reader;
- cross-module transfers, quest dependencies, state reads, and scene-script
  calls target declared integration points;
- every accepted module payload can merge into global canonical RPG files
  without losing trace to source story units, graph ids, and RPG directives.

### Gate 6: Runtime Verb And Hook Validation

Run before export and before module implementation is accepted:

```text
python3 scripts/run_pipeline.py validate-runtime-verbs --run-root <run>
```

Check:

- every non-standard verb used by a module has a declared custom hook;
- every custom hook belongs to exactly one module;
- every hook reads and writes only declared module or integration-point state;
- every required hook fails validation when missing;
- every optional hook declares fallback behavior;
- every hook uses only allowed runtime API calls;
- every hook has generated or authored contract tests;
- no module implementation edits core runtime files directly;
- module hook registry can be loaded by the Web RPG shell without name
  collisions.

### Gate 7: RPG Runtime Coverage

Extend RPG coverage to check:

- story-critical items have `story_role`, `inspect_lines`, and stateful
  `on_pickup` or `on_inspect`;
- maps contain events or scripts that realize required spatial obligations;
- NPCs tied to critical obligations have placement, dialogue, scene script, or
  state effect coverage;
- scene scripts realize required movement, facing, reveal, wait, transfer, or
  state write beats;
- revisits or return routes consume state rather than repeating the same
  content.
- compiled runtime data preserves module ids for coverage reports and repair
  routing.
- compiled runtime data preserves hook ids, standard verb ids, and fallback
  metadata for coverage reports and repair routing.

## Implementation Phases

### Phase 1: Contract Documentation

Files:

```text
references/design-layer-rpg-contracts.md
references/design-layer-v3-contracts.md
references/subagents/design-layer-rpg/RPGSystemPlanner.md
references/subagents/design-layer-rpg/RPGDesignReviewer.md
references/subagents/design-layer-v3/LevelStateGraphDesigner.md
references/subagents/README.md
```

Tasks:

1. Add `rpg-narrative-architecture.json` and `rpg-graph-directives.json`
   schemas.
2. Add `module-intents.json`, `module-index.json`, and
   `<module-id>.semantic-design-module.json` schemas.
3. Add `<module-id>.web-implementation-packet.json` as a separate
   target-specific implementation packet schema.
4. Define spatial narrative obligation fields.
5. Define module ownership, dependency, namespace, shared/core permissions, and
   integration-point rules.
6. Update RPGSystemPlanner responsibilities from sidecar overlay to
   graph-precondition architecture.
7. Update RPGDesignReviewer to review graph directives before graph design.
8. Update LevelStateGraphDesigner inputs and responsibilities.
9. Add `RPGGraphIntegrationReviewer` to the role index.

Done when:

- docs name the new artifacts;
- role cards explain the new data flow;
- no role implies RPG overlay is only post-graph binding.
- postdesign is described as module-first, not global-file-first.
- semantic design modules do not contain Web paths, handler names, or runtime
  implementation details.

### Phase 2: Controller And Layout

Files:

```text
scripts/pipeline_lib.py
scripts/run_pipeline.py
scripts/design_v3_lib.py
```

Tasks:

1. Add canonical paths for architecture, graph directives, directive slices,
   module intents, semantic modules, Web implementation packets, module
   payloads, runtime verb contracts, and graph integration review.
2. Ensure run initialization creates the needed directories.
3. Add controller helper logic to derive graph directive slices.
4. Add controller helper logic to bind module intents into semantic modules
   only after `compile-design` and `freeze-narrative`.
5. Add controller helper logic to derive Web implementation packets from
   semantic modules and Web runtime capabilities.
6. Add a merge step that compiles accepted module payloads into global RPG
   files.
7. Add `validate-rpg-graph-integration`, `validate-rpg-modules`, and
   `validate-runtime-verbs` command hooks.

Done when:

- paths exist in run layout;
- command help exposes graph integration validation;
- command help exposes module validation;
- command help exposes runtime verb validation;
- existing RPG-only builds still work when new artifacts are absent, initially
  as warnings.

### Phase 3: Validation

Files:

```text
scripts/validate_rpg_overlay.py
scripts/design_v3_validate.py
scripts/prepare_rpg_postdesign_slices.py
```

Tasks:

1. Validate directive references against story units and facts.
2. Validate spatial narrative minimum fields.
3. Validate forbidden concrete runtime fields.
4. Validate graph coverage after LevelStateGraphDesigner output.
5. Validate module ownership, namespace disjointness, dependencies, and
   integration points.
6. Validate that semantic modules are generated after public graph ids exist.
7. Ensure postdesign slices carry directive ids, module ids, and spatial
   obligations.
8. Validate module payload merge before writing global RPG artifacts.
9. Validate Web implementation packets separately from semantic modules.

Done when:

- invalid directives fail with actionable messages;
- graph misses produce repair routing instead of silent pass;
- postdesign packet output includes directive trace.
- module collisions, undeclared writes, and missing integration points fail
  before build.
- implementation-specific fields in semantic modules fail validation.

### Phase 4: Role Cards And Reviewer

Files:

```text
references/subagents/design-layer-rpg/RPGGraphIntegrationReviewer.md
references/subagents/design-layer-rpg/RPGSystemPlanner.md
references/subagents/design-layer-rpg/RPGDesignReviewer.md
references/subagents/design-layer-v3/LevelStateGraphDesigner.md
```

Tasks:

1. Add the new reviewer role card.
2. Specify its required inputs and output JSON.
3. Update planner/reviewer/designer constraints.
4. Add repair-note conventions for unsatisfied graph directives.
5. Update RPG postdesign role cards so workers consume semantic design modules
   and write module payloads, not global canonical files.
6. Add Web implementation packet instructions for target-specific code workers.

Done when:

- each agent has one clear owner boundary;
- graph directives are hard input for graph design;
- concrete runtime content remains postdesign-owned.
- postdesign ownership is module-scoped and parallel-safe.
- implementation ownership is target-specific and packet-scoped.

### Phase 5: Regression Fixtures

Files:

```text
tests/
scripts/create_alice_wonderland_rpg_artifacts.py
```

Tasks:

1. Add a fixture where a critical story unit must split into multiple spatial
   graph nodes.
2. Add an Alice hall-of-doors fixture for key, size, door, return, and garden
   threshold states.
3. Add a fixture where an NPC entrance/exit obligation must survive into scene
   script packets.
4. Add a fixture where a story-critical object must be inspectable and consumed
   by a later graph or runtime gate.
5. Add a fixture with two parallel modules that write different maps, items,
   quests, scenes, and tests without id collisions.
6. Add a fixture that deliberately writes an undeclared cross-module id and
   confirm module validation rejects it.

Done when:

- regression fails if graph output collapses spatial obligations into one node;
- regression fails if story objects are pickup-only counters;
- regression fails if scene-blocking obligations disappear before postdesign.
- regression fails if module workers need to edit global files directly or
  collide on owned runtime ids.

### Phase 6: Runtime Extensibility And Coverage

Files:

```text
scripts/validate_rpg.py
scripts/compile_rpg_manifest.py
scripts/export_web_rpg.py
scripts/validate_runtime_verbs.py
assets/web-rpg-template/runtime.js
```

Tasks:

1. Extend RPG validation to verify story-object fields and stateful outcomes.
2. Ensure compiled manifest carries required scene scripts, item inspection
   data, and event conditions.
3. Check Web RPG runtime can expose inspectable item text and consume item
   `on_inspect` or `on_pickup` state.
4. Add coverage warnings when map events do not realize required spatial
   obligations.
5. Preserve `module_id` in manifest entries and coverage reports so failed
   runtime checks route back to the responsible module.
6. Add a runtime hook registry loaded by the core Web RPG shell.
7. Add a standard verb dispatcher for reusable interactions such as
   `inspect_object`, `use_item`, `state_gate`, `threshold_transfer`,
   `route_revisit`, `transformation`, and `puzzle_gate`.
8. Add a module hook API that limits hooks to declared state, inventory,
   quests, events, scene scripts, and runtime calls.
9. Add `validate-runtime-verbs` to reject undeclared hooks, unsupported verbs,
   missing required hooks, optional hooks without fallbacks, missing tests, and
   direct core-runtime edits.
10. Export module hook registry and runtime verb contracts into `build/web-rpg/`
    alongside `game-data.js`.

Done when:

- graph-level spatial obligations are visible in runtime data;
- item inspection can advance story state;
- scene scripts can realize actor blocking tied to graph obligations.
- runtime failures can be routed to one module owner instead of a global file
  owner.
- generated games can vary module-level interaction behavior without forking
  the core runtime shell.
- standard verbs cover common story interactions while custom hooks cover only
  module-specific exceptions.

## Repair Routing

Use smallest-scope repair.

- Missing or ungrounded RPG architecture: route to `RPGSystemPlanner`.
- RPG directives faithful but too vague: route to `RPGSystemPlanner`.
- Directives include concrete runtime rows: route to `RPGDesignReviewer`.
- Graph ignores directives: route to `LevelStateGraphDesigner`.
- Graph cannot satisfy a directive because parent state is missing: route to the
  parent-level `LevelStateGraphDesigner`.
- Directive binds poorly to public graph after compile: route to deterministic
  binder or graph integration review.
- Postdesign packet lacks obligations: route to
  `prepare_rpg_postdesign_slices.py`.
- Module ownership is missing, too broad, or collides with another module:
  route to module packet generation or `RPGSystemPlanner`, depending on whether
  the issue is deterministic binding or design scope.
- Module payload writes undeclared ids or global files directly: route to the
  responsible module postdesign worker.
- Cross-module dependency is undeclared or broken: route to module index repair
  before runtime implementation.
- Unsupported standard verb or missing custom hook: route to the semantic
  module if the interaction requirement is wrong, to the Web implementation
  packet if the hook declaration is missing, or to the module implementation
  worker if the hook was declared but not implemented.
- Hook reads or writes undeclared state: route to semantic module repair when
  the state should be authorized, otherwise route to the Web implementation
  packet or module implementation worker to remove the illegal access.
- Hook requires core runtime changes: route to runtime architecture review
  before allowing any shell change.
- Runtime item, event, or scene script fails to realize accepted obligations:
  route to the relevant RPG postdesign role.

## Non-Goals

- Do not move concrete map layout, collision, event coordinates, item rows,
  stats, shop prices, or dialogue lines into the design layer.
- Do not let RPG directives invent unrelated plot.
- Do not bypass source anchoring. Every graph node still references source story
  units or explicit source-derived bridge/consequence logic.
- Do not make spatial narrative a purely visual asset problem. The graph must
  encode the state and route logic that make a place narratively meaningful.
- Do not make every NPC line a scene script. Only movement, timing, entrance,
  exit, facing, reveal, quest update, transfer, or stateful staging requires
  scene blocking.
- Do not let module workers freely fork or patch the core Web RPG runtime.
  Runtime variation should use standard verbs and declared module hooks first.
- Do not create custom hooks for behavior that the standard verb library can
  express cleanly.
