# V3 Post-Design Boundary Overlay

Use this overlay only as a Design Layer V3 adapter when spawning shared
post-design agents. Generic networked VN realization rules, terminal ending
variants, source-adaptation writing order, and player-visible choice-label
requirements live in `post-design/NodeRealizationPlanner.md` and
`post-design/NodeSceneWriter.md`.

This overlay only defines how V3 design artifacts should be interpreted by
post-design agents.

## V3 Runtime Boundary

- Realize only the compiled public `branch_graph.json`. In V3, that public
  graph is exported from the finest enabled design level, normally L1.
- Treat public `branch_graph.edges[*].conditions` and
  `branch_graph.edges[*].effects` as the runtime transition semantics. Do not
  reopen private V3 `design_levels/*/story_graph.json` files to recover edge
  state.
- Do not directly realize L2/L3 `story_graph` nodes or edges as runtime scenes,
  exit bindings, Yarn choices, or button labels unless they have been compiled
  into public finest-level graph nodes and edges.
- Treat L2/L3 graph ids, parent graph ids, `parent_state_settlements`,
  `source_rule_ids`, source anchor ids, and designer edge labels as trace or
  authoring context. They may explain why a public node reads/writes state, but
  they are not player-facing text.
- If a V3 trace implies route memory or a parent-level payoff, the controller
  should pass the relevant settlement, contract, or fact excerpt as context so
  the shared post-design role card can realize it on public graph nodes.
- If the public graph lacks the node, edge, state variable, or settlement needed
  to make a V3 trace playable, request V3 design/compile repair instead of
  inventing topology in post-design.

## NodeRealizationPlanner V3 Addendum

When planning from V3 artifacts:

- map realization plans only from public graph nodes;
- cover only public graph outgoing edges in `exit_bindings`;
- use V3 parent settlements and higher-level contracts to explain downstream
  payoff, not to add hidden runtime edges;
- preserve V3 trace ids in `source_trace` or implementation notes when useful
  for review, but keep them out of player-facing runtime structure.

## NodeSceneWriter V3 Addendum

When writing from V3 artifacts:

- write scenes only for public graph nodes selected by the controller;
- do not copy L1/L2/L3 designer labels, source labels, coverage labels, or
  parent settlement wording into Yarn text;
- use the shared `NodeSceneWriter` rules to author all visible `->` labels in
  the target language;
- if a public edge cannot be labeled from the scene's own visible choice
  structure, request controller repair instead of using V3 designer labels as
  fallback button text.
