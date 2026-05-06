# Investigation Scene 2.0 Plan

## Goal

Make `interaction.inspect_scene` feel less like a list of buttons and more like a compact investigation scene.

The target loop is:

```text
read scene -> inspect visual areas -> spend limited focus -> collect evidence -> combine evidence -> unlock completion
```

The player should be looking at a scene, making tradeoffs, and forming a conclusion. Clicking remains the physical input, but it should no longer feel like "click every menu option."

## Experience Goal

The player should feel:

```text
I noticed something in the picture.
I chose where to spend attention.
I connected clues myself.
My conclusion changed the exit.
```

## Core Verbs

Implement this set:

```text
inspect: click a visual region in the scene.
collect: gain local evidence from a hotspot.
use: apply a selected item to a hotspot.
combine: connect two or more local evidence items into a new conclusion item.
leave: complete the scene through planned outcome bindings.
```

## Rule Changes

### 1. Visual Hotspot Overlay

Extend hotspots with normalized bounds:

```json
{
  "id": "locked_drawer",
  "label": "Locked drawer",
  "bounds": {"x": 0.58, "y": 0.56, "w": 0.24, "h": 0.14}
}
```

Runtime behavior:

```text
If scene.layout is overlay and visible hotspots have bounds, render them as absolute regions over the scene panel.
Labels are subtle by default and appear strongly on hover/focus.
If bounds are missing, fall back to the existing grid layout.
```

### 2. Action Budget

Add optional `action_budget`:

```json
{
  "id": "focus",
  "label": "Focus",
  "initial": 5,
  "inspect_cost": 1,
  "use_cost": 1,
  "wrong_use_cost": 1,
  "combine_cost": 1,
  "depleted_text": "You are out of focus."
}
```

Runtime behavior:

```text
Show focus in the interaction panel.
Spend focus on inspect/use/combine when a cost is configured.
When focus is too low, show depleted_text and block the action.
Completion remains free once requirements are met.
```

### 3. Evidence Combination

Add `evidence_combinations`:

```json
{
  "id": "deduce_recent_forgery",
  "label": "Compare ink and torn page",
  "item_ids": ["item.wet_ink", "item.torn_page"],
  "creates_items": ["evidence.recent_forgery"],
  "text": "The torn edge carries the same fresh ink as the bottle.",
  "state_writes": []
}
```

Runtime behavior:

```text
Show available combinations only when the player has all required items.
Combining can create a local evidence item, reveal hotspots, or write declared persistent state.
Combinations are one-shot by default.
Completion may require created evidence.
```

## Data Contract

Extend `interaction.inspect_scene.runtime_spec` with:

```text
scene.layout: overlay or grid
scene.show_hotspot_labels: always, hover, or hidden
hotspots[].bounds: normalized x/y/w/h
action_budget: optional focus/action budget object
evidence_combinations[]: optional local evidence combination rules
```

Backward compatibility:

```text
Existing minimal hotspot-grid interaction units remain valid.
No action budget means actions stay free.
No bounds means the runtime uses the grid.
No evidence combinations means the inventory stays as collect/use only.
```

## Validation

Add validation rules:

```text
hotspot bounds must be numeric and within 0..1
action budget initial/cost fields must be non-negative numbers
evidence combination ids are unique
combination item_ids reference declared local items
combination creates_items reference declared local items
combination reveals_hotspots reference declared hotspots
combination state_writes reference shared-state variables
completion reachability accounts for collect, use, and combine steps
```

Warnings:

```text
overlay layout with no hotspot bounds
budget is too small to reach completion
combination creates an item that is never used by completion, use, present, or another combination
```

## Runtime UI

Add:

```text
focus counter
overlay hotspot region rendering
hover/focus hotspot labels
available evidence-combination actions
new log feedback for spent focus and created conclusions
```

Do not add:

```text
tile movement
physics
free camera
custom runtime scripts in story data
```

## Fixture

Update `scripts/create_interaction_fixture.py` so the smoke run exercises:

```text
overlay hotspot bounds
locked hotspot visible before key
focus budget
collect key
use key on drawer
collect torn page
inspect wet ink
combine wet ink + torn page into evidence.recent_forgery
complete only after the deduction exists
```

## Acceptance Criteria

The implementation is ready when:

```text
old interaction units still validate and render
fixture build passes end to end
browser smoke test can complete the fixture through overlay hotspots and evidence combination
invalid references fail in gameplay validation before export
story-data.js remains declarative JSON
```
