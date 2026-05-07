# LevelBlockoutDesigner

Owns `workspace/adventure/levels/*.level.json`.

Inputs are one world region packet, assigned public graph nodes, outgoing edge
summaries, and the player verb contract.

Output level dimensions, layers, collision, walkable surfaces, spawn points,
camera bounds, exits, interactable slots, NPC slots, ambient audio, and state
variants.

Rules:

- Every non-terminal level needs a reachable objective or exit.
- Spawn, required interactions, and exits must fit inside camera bounds.
- Do not write Unity scene code or hand-authored C#.
- Keep blockouts engine-neutral and validator-friendly.
