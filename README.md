# Narrative Game Subagent Pipeline

Codex skill for generating playable branching narrative games from a prompt through a structured artifact pipeline.

The skill coordinates authoring subagents, validates canonical design artifacts, assembles Yarn-style narrative fragments, validates typed gameplay realization units, and exports playable Web VN and optional Unity project scaffolds.

## Contents

- `SKILL.md`: controller instructions and quick-start workflow.
- `references/`: artifact contracts, subagent prompts, and repair routing.
- `references/v1-v3-postdesign-workflow.zh.md`: Chinese explanation of the current V1/V3 + post-design workflow.
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

The design layer has two parallel modules. V1 is the default direct design
module: subagents write `workspace/design_layer/branch_graph.json` and
`workspace/design_layer/game_ir.json` directly. V3 is the hierarchical
source-adaptation module: subagents write private hierarchy artifacts under
`workspace/design_layer_v3/`, then the compiler publishes the same public
runtime interface under `workspace/design_layer/`.

Design Layer V3 extracts story levels from fine to coarse,
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

For V3 source adaptations, finest-level story extraction is also shardable, but
the shard set must cover the complete `source_index.json` inventory. Do not send
only representative chapters to `StoryLevelExtractor`; every chapter/chunk/span
must be assigned to a shard, returned, audited, and merged before higher story
levels or graph/state design begin.

All subagents are dispatched clean-context: role cards and prompt templates are
separate files. The controller selects the exact role card from
`references/subagents/README.md`, renders the matching prompt template from
`references/design-layer-prompts.md`, `references/design-layer-v3-prompts.md`, or
`references/post-design-prompts.md`, and sends only the role card plus the
role-specific packet. The coarsest V3 story extractor and the coarsest V3
graph/state designer are single global workers, not shard sets.

For use as a Codex skill, install or copy this directory under `~/.codex/skills/narrative-game-subagent-pipeline` and invoke it by name.

See `SKILL.md` for the full controller workflow.
