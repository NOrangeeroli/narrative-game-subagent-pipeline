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

Design Layer V3 is also opt-in. It extracts story levels from fine to coarse,
captures facts during story extraction, designs graph/state levels from coarse
to fine with state-first level design, and requires each non-coarsest design
level to declare how local state settlement affects immediate parent state.
For branch-permitted adaptations, V3 graph/state task prompts should require
visible network topology rather than a linear story-unit spine: state-gated
routes, optional/revisit/delayed traversal, convergence with route memory, and
downstream contracts that read prior route state:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "A one-sentence game prompt" \
  --run-root runs/my-v3-game \
  --design-layer v3

python3 scripts/run_pipeline.py compile-design \
  --run-root runs/my-v3-game \
  --design-layer v3
```

V3 internal artifacts live under `workspace/design_layer_v3/`, but the compiler
still publishes `workspace/design_layer/branch_graph.json` and
`workspace/design_layer/game_ir.json` for downstream stages.

For source-adaptation runs, the controller extracts source material before the
first authoring subagent. Canonical extraction outputs live under
`inputs/source_material/`: `full_text.txt`, `source_index.json`,
`chunks/*.txt`, and `extraction_report.json`. Clean-context subagents should
receive role-specific packets from `workspace/controller-packets/`, not the full
run directory or global contract files.

For long sources, the controller may shard `SourceSegmenter` across multiple
parallel clean-context workers. Shard packets live under
`workspace/controller-packets/source_segmenter/`, raw partial returns live under
`workspace/controller-packets/source_segmenter_returns/`, and only the
controller merges those returns into canonical `source_intake` artifacts.

For use as a Codex skill, install or copy this directory under `~/.codex/skills/narrative-game-subagent-pipeline` and invoke it by name.

See `SKILL.md` for the full controller workflow.
