# Narrative Game Subagent Pipeline

Codex skill for generating playable branching narrative games from a prompt through a structured artifact pipeline.

The skill coordinates authoring subagents, validates canonical design artifacts, assembles Yarn-style narrative fragments, validates typed gameplay realization units, and exports playable Web VN and optional Unity project scaffolds.

## Contents

- `SKILL.md`: controller instructions and quick-start workflow.
- `references/`: artifact contracts, subagent prompts, and repair routing.
- `scripts/`: deterministic pipeline tools for init, validation, assembly, export, and reporting.
- `assets/`: Web VN and Unity export templates.
- `agents/`: sample agent configuration.

## Quick Start

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A one-sentence game prompt" \
  --run-root runs/my-game

python3 scripts/run_pipeline.py build \
  --run-root runs/my-game
```

Design Layer V2 is opt-in. It keeps the public runtime interface under
`workspace/design_layer/`, but authors source design data under
`workspace/design_layer_v2/` and compiles it afterward:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A one-sentence game prompt" \
  --run-root runs/my-v2-game \
  --design-layer v2

python3 scripts/run_pipeline.py compile-design \
  --run-root runs/my-v2-game \
  --design-layer v2
```

V2 uses an adjustable multi-level mesh expansion model. Set
`control/mesh_expansion_policy.json` to choose the default target depth and use
`depth_budget_by_parent` to selectively open deeper mesh layers.

For use as a Codex skill, install or copy this directory under `~/.codex/skills/narrative-game-subagent-pipeline` and invoke it by name.

See `SKILL.md` for the full controller workflow.
