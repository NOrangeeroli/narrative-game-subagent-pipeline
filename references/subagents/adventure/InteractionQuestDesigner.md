# InteractionQuestDesigner

Owns `workspace/adventure/interactions/*.interaction.json`,
`workspace/adventure/quests/*.quest.json`, and
`workspace/adventure/dialogue/*.dialogue.json`.

Inputs are level packets, assigned graph nodes/edges, and state read/write
packets.

Rules:

- Every public branch graph edge must be completed by an interaction, quest
  step, dialogue decision, or explicit automatic trigger.
- State writes must come from public branch graph edges or game IR rules.
- Player-facing action labels must describe external action.
- Each spatial interaction should declare a concrete `target_kind` such as
  `item`, `npc`, `door`, `sound`, `garden`, or `prop`, plus a position inside
  the level walk area.
- Dialogue may support choices, but the genre should primarily branch through
  spatial play.
