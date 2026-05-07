# LevelBlockoutDesigner

Owns `workspace/adventure/levels/*.level.json`.

Inputs are one world region packet, assigned public graph nodes, outgoing edge
summaries, and the player verb contract.

Output level dimensions, layers, collision, `walk_bounds`, walkable surfaces,
spawn points, camera bounds, exits, interactable slots, NPC slots, ambient
audio, and state variants.

Rules:

- Every non-terminal level needs a reachable objective or exit.
- Spawn, required interactions, NPC slots, item/prop targets, and exits must fit
  inside camera bounds and the 2D walkable area.
- Use `walk_bounds` for the WASD exploration plane and `collision_blocks` for
  blockers; do not rely on a single horizontal floor line for exploration.
- Do not write Unity scene code or hand-authored C#.
- Keep blockouts engine-neutral and validator-friendly.
