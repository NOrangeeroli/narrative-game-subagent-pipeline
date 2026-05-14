# RPG Overlay Prompt Templates

Use these templates only for `--target web-rpg --design-layer v3` narrative-first
overlay runs.

## Role Map

| Agent | Role Card | Output |
| --- | --- | --- |
| RPGSystemPlanner | `subagents/design-layer-rpg/RPGSystemPlanner.md` | `workspace/design_layer_rpg/rpg-overlay-plan.json` |
| RPGDesignReviewer | `subagents/design-layer-rpg/RPGDesignReviewer.md` | `workspace/design_layer_rpg/rpg-overlay-review.json` |

## RPGSystemPlanner Packet

Pass only:

```text
inputs/prompt.txt
workspace/design_layer_v3/story_levels/*/linear_story.json
workspace/design_layer_v3/facts/canonical_fact_graph.json
workspace/design_layer_v3/adaptation/global_policy.json
references/design-layer-rpg-contracts.md
references/subagents/design-layer-rpg/RPGSystemPlanner.md
```

Do not pass:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/design_layer_v3/design_levels/*
workspace/rpg/*
```

Prompt:

```text
You are RPGSystemPlanner.

Create a narrative-first RPG overlay plan. Read the V3 story hierarchy, facts,
adaptation policy, prompt, contract, and role card. Group story units into RPG
story slices and define map, questline, combat, equipment, and progression
intents that express the existing story.

Do not change V3 narrative topology, endings, edge conditions, edge effects, or
state authority. Do not write concrete runtime rows such as enemy stats,
dialogue lines, item tables, shop inventories, XP curves, map layouts, or asset
prompts.

Return JSON only for workspace/design_layer_rpg/rpg-overlay-plan.json.
```

## RPGDesignReviewer Packet

Pass only:

```text
workspace/design_layer_rpg/rpg-overlay-plan.json
workspace/design_layer_v3/story_levels/*/linear_story.json
workspace/design_layer_v3/facts/canonical_fact_graph.json
workspace/design_layer_v3/adaptation/global_policy.json
reports/rpg-overlay-validation.json if present
references/design-layer-rpg-contracts.md
references/subagents/design-layer-rpg/RPGDesignReviewer.md
```

Prompt:

```text
You are RPGDesignReviewer.

Review the RPG overlay plan for narrative fidelity and RPG usefulness. Check
that critical story beats are covered by RPG slices, every RPG system intent has
a narrative function, and the plan does not smuggle concrete runtime rows or
new public narrative branches into the overlay.

Return JSON only for workspace/design_layer_rpg/rpg-overlay-review.json. Use
status pass, needs_repair, or fail. Include targeted repair notes with paths.
```

## Post-Compile Controller Prompts

After `compile-design`, run:

```bash
python3 scripts/run_pipeline.py validate-rpg-overlay --run-root <run>
python3 scripts/run_pipeline.py freeze-narrative --run-root <run>
python3 scripts/run_pipeline.py prepare-rpg-postdesign-slices --run-root <run>
```

RPG postdesign agents should receive their assigned packet from:

```text
workspace/controller-packets/postdesign/rpg/*.json
```

They should not receive the full public graph by default.
