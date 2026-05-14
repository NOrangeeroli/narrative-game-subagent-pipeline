# Narrative RPG Subagent Pipeline

Codex skill for generating playable narrative RPGs from a prompt through a structured artifact pipeline.

The skill coordinates authoring subagents, validates canonical design and RPG artifacts, binds story beats into maps, actors, objects, quests, scene scripts, assets, and exports a playable Web RPG.

## Contents

- `SKILL.md`: controller instructions and quick-start workflow.
- `references/`: artifact contracts, subagent prompts, and repair routing.
- `scripts/`: deterministic pipeline tools for init, validation, RPG compilation, export, and reporting.
- `assets/`: Web RPG export template.
- `agents/`: sample agent configuration.

## Quick Start

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A one-sentence RPG prompt" \
  --target web-rpg \
  --run-root runs/my-game

python3 scripts/run_pipeline.py build \
  --target web-rpg \
  --run-root runs/my-game
```

RPG campaigns can define multiple narrative entry points in
`workspace/rpg/rpg-campaign.json` with `entry_points`. The Web RPG export shows
an entry selection screen and can start each route with a different actor, map
position, initial quests, flags, and inventory. Map events may use
`entry_point_id` or `entry_point_ids` so one map can expose different story
triggers by perspective.

Design Layer V3 is available as an opt-in front half for hierarchical,
multi-branch story design:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A multi-perspective RPG prompt" \
  --target web-rpg \
  --design-layer v3 \
  --run-root runs/my-rpg

python3 scripts/run_pipeline.py compile-design \
  --design-layer v3 \
  --run-root runs/my-rpg
```

Sprite Forge map and sprite production references are vendored under
`references/sprite-forge/`, with helper scripts under `scripts/sprite_forge/`.
Use those contracts to create layered RPG maps, transparent sprites, prop packs,
and preview compositions, then connect accepted images through
`asset-direction.json` `provider_hints` or the normal asset manifest pipeline.

For use as a Codex skill, install or copy this directory under `~/.codex/skills/narrative-game-subagent-pipeline` and invoke it by name.

See `SKILL.md` for the full controller workflow.
