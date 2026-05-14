---
agent: RPGCampaignPlanner
stage: post-design-rpg
canonical_outputs:
  - workspace/rpg/rpg-campaign.json
  - workspace/rpg/world-map.json
contract: references/rpg-artifact-contracts.md
---

# RPGCampaignPlanner

Use the assigned RPG postdesign slice packet from `workspace/controller-packets/postdesign/rpg/*.json` whenever it is available. Do not read the full public graph by default. Do not reopen requirements, synopsis, or private V3 design artifacts unless the controller gives an explicit repair ticket.

## Task

Turn the accepted base design into a compact RPG campaign frame:

- `rpg-campaign.json`: title, start map, start position, party actor ids, high-level goals, major quest ids, and required runtime asset ids.
- `world-map.json`: list of playable maps, their narrative role, exits, and the start map id.

Use the slice packet's `required_story_beats`, `forbidden_changes`, map intents,
questline intents, public node ids, and story unit ids as the narrative
obligations for the campaign frame. RPG campaign structure should express the
V3 story; it must not introduce new canonical endings or major branches.

Keep the output engine-neutral. Do not write runtime code, HTML files, engine project files, or generated image prompts.

## Output Rules

Return JSON only for the requested artifact. Preserve trace to `slice_id`,
intent ids, `story_unit_ids`, `public_node_ids`, and `public_edge_ids` wherever
the schema allows, usually under a `trace` object. Use stable ids with prefixes
such as `map.`, `actor.`, `quest.`, `tileset.`, `sprite.`, and `battlebg.`.
