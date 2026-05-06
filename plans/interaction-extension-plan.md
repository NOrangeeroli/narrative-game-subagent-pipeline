# Interaction Extension Plan

## Goal

Extend the current Web VN experience from slide-style dialogue plus choice buttons into a more immersive narrative-adventure loop:

```text
read scene context -> inspect places and objects -> collect or use evidence -> unlock dialogue/routes -> carry state forward
```

The first implementation should stay declarative. Subagents write typed JSON gameplay units; the controller, validators, exporters, and Web runtime own execution.

## Target Experience

Players should feel like they are acting inside a scene rather than choosing from a menu appended to a scene. The strongest near-term target is investigation-style interaction:

```text
Look around -> notice details -> take/use/present an item -> reveal a new option -> choose an outcome
```

The player should make repeated decisions about where to look, what to use, who to question, and when to leave. The reward chain is not only a new branch; it is the feeling that previous observation created a later opportunity.

## Non-Goals

- Do not add free-walk tile movement, physics, real-time collision, or character-controller logic in this phase.
- Do not let subagents write arbitrary JavaScript, CSS, C#, Yarn runtime code, or generated assets.
- Do not move topology ownership out of `branch_graph.json`.
- Do not move persistent state ownership out of `game_ir.json` and projected shared state.
- Do not require Unity parity before the Web VN version is proven.

## Current Baseline

The current gameplay layer already supports:

```text
battle.choice_duel
interaction.inspect_scene
puzzle.sequence_lock
exploration.room_nav
```

`interaction.inspect_scene` is currently a button grid over a prompt/log model:

```json
{
  "prompt": "Inspect the area.",
  "hotspots": [
    {"id": "map", "label": "Map", "reveal_text": "A route is marked.", "required_for_completion": true}
  ],
  "completion": {"required_hotspots": ["map"], "outcome_id": "complete", "label": "Move on"}
}
```

This is a good first adapter, but it still feels close to a choice menu. The extension should keep this shape valid while adding richer verbs and scene-state progression.

## Design Model

### Core Verbs

Implement these in order:

```text
inspect
collect
use
present
move
wait
```

`inspect` and `collect` belong in the first slice. `use` and `present` make discoveries matter downstream. `move` and `wait` can build on `exploration.room_nav` once interaction scenes are stable.

### Resources And State

Use two layers of state:

```text
local scene state: visited hotspots, revealed hotspots, local inventory, selected item, local log
persistent game state: game_ir-declared variables written through state_writes
```

Local state should reset when the node is re-entered unless the branch graph routes back to the same node and the runtime session remains active. Persistent consequences must go through existing state writes.

### Tension

Add tension through readable constraints, not hidden failure:

```text
locked hotspot requires another discovery
an item can be used in multiple places but only one use advances the scene
optional evidence improves a later branch but is not required to finish
time/wait costs appear only in the later exploration slice
```

Avoid hard dead ends. Every interaction node needs at least one reachable completion outcome.

## Phase 1: Backward-Compatible Interaction Contract

Update `references/artifact-contracts.md` and `references/subagents/post-design/InteractionRealizationWriter.md`.

Keep `interaction.inspect_scene` as the adapter id. Extend its `runtime_spec` with optional fields:

```json
{
  "prompt": "Inspect the area.",
  "scene": {
    "background_asset_id": "bg.library_night",
    "layout": "overlay",
    "fallback_layout": "grid"
  },
  "hotspots": [
    {
      "id": "desk",
      "label": "Desk",
      "kind": "object",
      "initially_visible": true,
      "verbs": ["inspect", "collect"],
      "reveal_text": "A torn page is hidden under the blotter.",
      "collects": ["item.torn_page"],
      "reveals_hotspots": ["locked_drawer"],
      "state_writes": []
    },
    {
      "id": "locked_drawer",
      "label": "Locked drawer",
      "kind": "container",
      "initially_visible": false,
      "requires_items": ["item.small_key"],
      "blocked_text": "The drawer will not open without a key.",
      "use_results": [
        {
          "item_id": "item.small_key",
          "text": "The key turns and the drawer opens.",
          "reveals_hotspots": ["photo"],
          "state_writes": []
        }
      ]
    }
  ],
  "items": [
    {"id": "item.torn_page", "label": "Torn page", "description": "Part of a route map."}
  ],
  "completion": {
    "required_hotspots": ["desk"],
    "required_items": ["item.torn_page"],
    "outcome_id": "complete",
    "label": "Leave with the page"
  }
}
```

Rules:

- Existing minimal `hotspots[].reveal_text` content must continue to work.
- `items` are local interaction inventory entries, not persistent state variables.
- `collects`, `requires_items`, `reveals_hotspots`, and `use_results[].item_id` must reference ids declared in the same `runtime_spec`.
- Persistent consequences still use `state_writes`.
- Completion may require hotspots, items, or persistent state reads, but it must remain reachable.

## Phase 2: Validation

Update `scripts/pipeline_lib.py` gameplay validation for `interaction.inspect_scene`.

Add checks:

```text
hotspot ids are unique
item ids are unique
completion.required_hotspots reference known hotspots
completion.required_items reference known items
hotspot.requires references known hotspots
hotspot.requires_items reference known items
hotspot.reveals_hotspots reference known hotspots
hotspot.collects reference known items
use_results item ids reference known items
use_results reveals reference known hotspots
required completion dependencies are reachable from initially visible hotspots
state_writes still reference declared shared-state variables
```

Write validation failures to the existing `reports/gameplay-validation.json`. Add warnings, not errors, for optional hotspots that can never be revealed.

## Phase 3: Web Runtime Upgrade

Update `assets/web-vn-template/runtime.js` and `assets/web-vn-template/style.css`.

The runtime should keep the current button-grid fallback, then add richer behavior:

```text
scene background panel when scene.background_asset_id resolves
visible hotspot list derived from initially_visible plus revealed_hotspots
local inventory strip
select item -> use on compatible hotspot
inspect/collect/use feedback log
newly revealed hotspot feedback
completion button only when requirements pass
keyboard-safe and mobile-safe fallback layout
```

Runtime session state for one interaction node:

```json
{
  "visited": [],
  "revealed": [],
  "items": [],
  "selectedItemId": null,
  "log": []
}
```

Implementation constraints:

- Use arrays or sets internally, but exported story data stays JSON-only.
- Do not mutate `story` data structures directly.
- Reuse `applyWrites` and `completeActivity`.
- If a background asset is missing, render the same gameplay without a background.
- Do not require pixel-perfect hotspot coordinates in the first pass. Overlay coordinates can be a later optional field.

## Phase 4: Asset Binding

Update `scripts/plan_assets.py`, `scripts/generate_assets.py`, and `references/artifact-contracts.md` only as needed.

Required asset handling:

```text
scene.background_asset_id -> existing background/cg asset lookup
hotspot.asset_id -> prop/hotspot/icon asset
items[].asset_id -> prop/icon asset
use_results[].sfx_asset_id -> optional sfx asset
```

The first pass can render without custom hotspot art if only labels exist. Asset planning should include new `required_assets` ids when the interaction unit references them.

## Phase 5: Subagent Prompt Updates

Update `InteractionRealizationWriter.md` so the writer can design richer scenes without inventing implementation details.

Prompt requirements:

```text
choose 2-5 meaningful hotspots
mark at least one hotspot as optional when the node can support it
use collect/use only when the collected item changes a later action
include blocked_text for any gate
avoid requiring an item that cannot be collected in the same unit unless the realization plan explicitly declares it as a required state/read
preserve exit_bindings exactly
do not add persistent state variables
```

Update `NodeRealizationPlanner` guidance only if needed:

```text
select interaction when the source node is about inspecting, searching, questioning, handling objects, or uncovering evidence
select exploration when the main decision is where to go across multiple areas
select puzzle when the main decision is solving a formal rule/input challenge
```

## Phase 6: Optional Evidence Presentation

After Phase 1-5 pass, add evidence presentation inside `interaction.inspect_scene` before introducing a new adapter id.

Extend `runtime_spec` with optional `present_targets`:

```json
{
  "present_targets": [
    {
      "id": "char.mira",
      "label": "Mira",
      "accepted_items": [
        {
          "item_id": "item.torn_page",
          "text": "Mira recognizes the route and admits she hid the rest.",
          "outcome_id": "confront_mira",
          "state_writes": []
        }
      ],
      "default_text": "That does not mean anything to Mira."
    }
  ]
}
```

This supports Ace Attorney-style evidence moments without requiring a separate dialogue engine. If this grows too large, split it later into `interaction.present_evidence`.

## Phase 7: Local Hub And Time Pressure

Build this after interaction scenes feel good.

Extend `exploration.room_nav` rather than creating a new navigation system:

```text
area interactions can open embedded interaction scenes
exits can have time_cost
completion can depend on visited areas, discoveries, items, or state
optional deadline creates a fail-forward outcome
NPC presence can be described declaratively per area
```

Possible fields:

```json
{
  "clock": {"start": 0, "deadline": 4, "unit": "turn"},
  "areas": [
    {
      "id": "library",
      "label": "Library",
      "time_cost": 1,
      "npc_presence": [{"character_id": "char.mira", "condition": "before_deadline"}],
      "interactions": [{"interaction_id": "desk_search", "label": "Search the desk"}]
    }
  ],
  "timeout_outcome_id": "too_late"
}
```

Keep this as a second milestone. The first milestone should not block on clock UI.

## Phase 8: Prototype Fixture

Add a small committed fixture or script-generated smoke run that contains:

```text
one VN intro node
one interaction.inspect_scene node with:
  background
  3 hotspots
  1 hidden hotspot
  1 collectable item
  1 use-result gate
  1 optional discovery
one outcome that requires the item
one VN ending node
```

Suggested path:

```text
examples/interaction-extension-fixture/
```

If this repo avoids checked-in examples, add a script instead:

```text
scripts/create_interaction_fixture.py --run-root runs/interaction-extension-smoke
```

## Phase 9: Verification

Run these checks after implementation:

```text
python3 -m compileall scripts
node --check assets/web-vn-template/runtime.js
python3 scripts/validate_gameplay.py --run-root <fixture-run-root>
python3 scripts/plan_assets.py --run-root <fixture-run-root>
python3 scripts/export_web_vn.py --run-root <fixture-run-root>
```

Then browser-check the exported Web VN:

```text
open build/web-vn/index.html
```

Manual acceptance script:

```text
start intro
enter interaction node
inspect visible hotspot
collect item
try locked hotspot before using item and see blocked feedback
select item
use item on locked hotspot
hidden hotspot appears
completion button appears only after requirements pass
complete node and reach expected ending
```

## Implementation Order

1. Update contracts and writer prompt.
2. Add validator support for extended interaction fields.
3. Upgrade Web runtime local interaction session.
4. Add CSS for scene panel, inventory strip, visible/hidden/disabled states.
5. Wire optional asset ids into asset planning.
6. Add fixture generator or checked-in fixture.
7. Run syntax checks and fixture smoke validation.
8. Update `SKILL.md` with the new interaction capabilities.

## Acceptance Criteria

The branch is ready when:

```text
old minimal interaction.inspect_scene units still render
new collect/use/reveal interaction units validate
invalid missing references fail validation before export
Web runtime can complete the fixture without console syntax errors
story-data.js remains declarative JSON data, not executable scripts
state writes still go through completeActivity/applyWrites
documentation tells subagents exactly which interaction fields they may emit
```

## Risks

The main risk is turning one adapter into a hidden general-purpose engine. Keep the first version narrow: inspect, collect, use, reveal, complete. Add evidence presentation and time pressure only after that loop is playable and validated.

The second risk is fake freedom. If every hotspot only prints flavor text, the extension will still feel like a menu. Each interaction node should include at least one action that changes available information, inventory, state, or exit options.
