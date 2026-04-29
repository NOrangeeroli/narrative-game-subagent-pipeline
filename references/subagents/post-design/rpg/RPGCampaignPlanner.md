---
agent: RPGCampaignPlanner
stage: post-design-rpg
canonical_outputs:
  - workspace/rpg/rpg-campaign.json
  - workspace/rpg/world-map.json
contract: references/rpg-artifact-contracts.md
---

# RPGCampaignPlanner

Use only `workspace/design_layer/branch_graph.json`, `workspace/design_layer/game_ir.json`, and controller-provided slices. Do not reopen requirements or synopsis unless the controller gives an explicit repair ticket.

## Task

Turn the accepted base design into a compact RPG campaign frame:

- `rpg-campaign.json`: title, start map, start position, party actor ids, high-level goals, major quest ids, and required runtime asset ids.
- `world-map.json`: list of playable maps, their narrative role, exits, and the start map id.

Keep the output engine-neutral. Do not write runtime code, HTML, Unity files, or generated image prompts.

## Output Rules

Return JSON only for the requested artifact. Preserve branch node ids and game state ids when referencing source design. Use stable ids with prefixes such as `map.`, `actor.`, `quest.`, `tileset.`, `sprite.`, and `battlebg.`.
