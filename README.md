# Narrative Game Subagent Pipeline

Codex skill for generating playable branching narrative games from a prompt through a structured artifact pipeline.

The skill coordinates authoring subagents, validates canonical design artifacts, assembles Yarn-style narrative fragments, and exports playable Web VN and optional Unity project scaffolds.

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

For use as a Codex skill, install or copy this directory under `~/.codex/skills/narrative-game-subagent-pipeline` and invoke it by name.

See `SKILL.md` for the full controller workflow.
