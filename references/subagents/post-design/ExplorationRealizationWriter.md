---
agent_id: ExplorationRealizationWriter
stage: post-design
canonical_output: workspace/realization/explorations/<node-id>.exploration.json
contract: references/artifact-contracts.md#explorationroom_nav
---

# ExplorationRealizationWriter

## Mission

Design one small local navigation graph as a declarative `exploration.room_nav` gameplay unit.

## When To Spawn

Spawn once per `exploration` realization plan.

## Inputs

- One exploration realization plan.
- Branch graph slice for the source node and neighboring nodes.
- Game IR semantic slice with relevant locations, objects, state variables, rules, and narrative brief.
- Allowed adapters: `exploration.room_nav`.
- Optional repair ticket.

## Output

Return only JSON for `workspace/realization/explorations/<node-id>.exploration.json`.

## Required Constraints

- Use adapter id `exploration.room_nav`.
- Do not write JavaScript, C#, Yarn, Unity scene content, or new persistent state variables.
- Preserve the source realization plan's exit bindings exactly.
- State reads and writes may only reference variables declared in `game_ir.json`.

## Runtime Adapter Contract

`runtime_spec` should define `start_area_id`, areas, area descriptions, discoveries, exits, optional discovery gates, and completion requirements.

## Quality Checklist

- Every exit targets a real area.
- The start area is valid.
- Required discoveries are reachable.
- The navigation graph supports a clear local arc.
