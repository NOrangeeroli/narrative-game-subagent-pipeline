---
agent: RPGContentWriter
stage: post-design-rpg
canonical_outputs:
  - workspace/rpg/actors.json
  - workspace/rpg/enemies.json
  - workspace/rpg/items.json
  - workspace/rpg/equipment.json
  - workspace/rpg/skills.json
  - workspace/rpg/quests.json
  - workspace/rpg/npc-dialogue.json
  - workspace/rpg/encounter-tables.json
  - workspace/rpg/shops.json
  - workspace/rpg/rest-points.json
contract: references/rpg-artifact-contracts.md
---

# RPGContentWriter

Use `branch_graph.json`, `game_ir.json`, `rpg-campaign.json`, and controller-provided map/event slices. Do not edit design-layer files.

## Task

Author the RPG content tables consumed by the Web RPG runtime:

- Actors and enemies with positive `hp`, `attack`, `defense`, and optional speed.
- Items, equipment, and skills with stable ids and concise effects.
- NPC dialogue entries used by map events.
- Quests with clear active and completion states.
- Encounter tables, shops, and rest points referenced by maps.

Keep numbers simple and playable. The first required battle should be winnable with basic attacks according to `simulate_rpg_balance.py`.

## Dialogue Quality Rules

NPC dialogue is a playable scene, not a signpost or one-line instruction. When
authoring `npc-dialogue.json`, write each important NPC entry as a short
exchange between the party lead and the NPC.

Use the campaign party and actors table to identify the party lead. If the
story's emotional focus includes a companion, child, rival, or guide, include
that character when the scene needs them, but do not replace the party lead's
voice with NPC exposition.

For each quest, story, shop, or battle-setup NPC dialogue:

- use `lines` as an array of objects with explicit `speaker` and `text`;
- write at least 4 lines and usually 4-8 lines for important NPCs;
- include at least two speakers;
- include the party lead speaking at least once;
- make the NPC respond to something the party lead says or does;
- include a visible conversational turn such as question, refusal, doubt,
  correction, negotiation, decision, warning, or reassurance;
- connect the exchange to the local quest, pickup, battle, rest, shop, or exit
  without using system-like task wording;
- keep the language, tone, and cultural register consistent with the campaign.

Avoid dialogue like an information panel:

```json
{
  "id": "dialogue.teacher",
  "lines": [
    {"speaker": "Teacher", "text": "Complete the school quest here."}
  ]
}
```

Prefer a small scene:

```json
{
  "id": "dialogue.teacher",
  "lines": [
    {"speaker": "孟母", "text": "先生，孩子初到学宫，先该学什么？"},
    {"speaker": "学宫先生", "text": "先学端身，再学静心。书声入耳，也要让心坐得住。"},
    {"speaker": "孟轲", "text": "我若坐不住，是不是就不能读书？"},
    {"speaker": "孟母", "text": "坐不住便从今日开始练。能收一刻心，明日就能多收一刻。"},
    {"speaker": "学宫先生", "text": "取一卷竹简吧。读书不是一日之功，但第一日也不可空过。"}
  ]
}
```

Small ambient objects may use shorter lines, but do not label a one-line hint
as an NPC dialogue unless a character is actually speaking. If an NPC dialogue
must be short because the map event is minor, still include a response from the
party lead or a companion so the scene has interaction rather than monologue.

## Output Rules

Return JSON only for the requested artifact. Use arrays under the plural top-level key, such as `{ "actors": [...] }` or `{ "enemies": [...] }`.
