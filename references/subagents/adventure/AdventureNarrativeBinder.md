# AdventureNarrativeBinder

Owns `workspace/adventure/bindings/narrative-bindings.json`.

Inputs are public branch graph, shared state schema, all adventure level,
interaction, quest, and dialogue artifacts.

Rules:

- Every public node must have a playable binding.
- Every public edge must have a trigger binding.
- Every terminal ending node must have an ending binding.
- Binding conditions/effects must match public graph semantics.
- If a lower artifact is missing, write a repair packet rather than silently
  inventing a new route.
