# V2 Design Layer Implementation Plan

## Goal

Implement a new design layer in parallel with v1 that follows a state-driven, hierarchical, verifiable narrative production workflow.

The v2 design layer may use many internal artifacts, but it compiles them into the same two downstream-facing files:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

All later agents should continue to need only graph and IR context prepared from those two files.

## Design Principle

V2 should not create a giant choice tree.

It should create:

```text
source understanding
fact base
adaptation rules
world state model
macro graph
node contracts
subgraphs
storylets
validation reports
compiled branch_graph.json
compiled game_ir.json
```

The internal layer can be rich. The external layer must stay small.

## Public Interface

The public interface remains:

```text
branch_graph.json = topology authority
game_ir.json      = semantic and state authority
```

No realization, dialogue, asset, or export agent should read v2 internal artifacts directly.

The controller may generate compact per-node context slices from those public files:

```text
node topology slice
neighbor summaries
available exits
relevant state variables
relevant rules
relevant contracts
local storylets
narrative brief
```

Those slices are derived views, not new sources of truth.

## Internal Artifact Layout

Add a parallel v2 workspace:

```text
workspace/design_layer/v2/source_facts.json
workspace/design_layer/v2/adaptation_policy.json
workspace/design_layer/v2/world_state_model.json
workspace/design_layer/v2/macro_graph.json
workspace/design_layer/v2/node_contracts.json
workspace/design_layer/v2/subgraphs/*.json
workspace/design_layer/v2/storylets.json
workspace/design_layer/v2/branch_control.json
workspace/design_layer/v2/validation_manifest.json
workspace/design_layer/v2/compile_report.json
```

The compiled public artifacts stay outside the v2 folder:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

## V2 Internal Stages

### 1. Source Fact Extraction

Create `source_facts.json`.

This is source understanding only. It should not create branches.

Contents:

```text
characters
locations
groups
key objects
core events
causal links
relationships
secrets
foreshadowing
world rules
timeline
themes
non-breaking constraints
```

The artifact should keep trace ids so later generated material can explain where each design claim came from.

### 2. Adaptation Policy

Create `adaptation_policy.json`.

Classify narrative material into:

```text
fixed facts
variable processes
variable endings
prohibited changes
allowed expansions
tone and theme constraints
```

This becomes the permission boundary for every later design agent.

### 3. World State Model

Create `world_state_model.json`.

Define state variables before expanding branches:

```text
global state
region or chapter state
relationship state
knowledge state
quest state
local scene state
hidden system state
```

Every variable should define:

```text
id
type
allowed values
initial value
read authority
write authority
affected graph elements
source facts or policy ids
```

This stage prevents branch explosion by moving consequences into state.

### 4. Macro Graph

Create `macro_graph.json`.

This is the coarse narrative graph:

```text
large phases
entry conditions
mainline nodes
side route nodes
skippable nodes
failure nodes
convergence nodes
ending nodes
```

It is not required to be chapter-shaped. It can be a route mesh, investigation graph, social schedule graph, or storylet availability graph.

### 5. Node Contracts

Create `node_contracts.json`.

Each macro node gets an interface contract:

```text
node id
narrative function
entry conditions
required story functions
allowed characters
allowed locations
allowed state reads
allowed state writes
forbidden events
allowed exits
exit state effects
dependencies
source traces
```

The contract is the boundary between macro design and local expansion.

### 6. Subgraph Expansion

Create one file per expandable macro node:

```text
workspace/design_layer/v2/subgraphs/<node-id>.json
```

Each subgraph may contain:

```text
local scenes
local choices
local tasks
local conflicts
failures
loops
convergences
exit mapping back to parent contract
```

Subgraphs can be complex internally, but their exits must map to parent node contract exits.

### 7. Storylet Design

Create `storylets.json`.

Each storylet defines:

```text
id
preconditions
content function
characters
locations
choices
state reads
state writes
repeatability
priority
mutual exclusions
unlock effects
parent node or subgraph trace
```

Storylets should be usable by realization agents as local content units, but only through the compiled public files.

### 8. Branch Complexity Control

Create `branch_control.json`.

Classify decisions:

```text
route-level choices
method choices
relationship choices
information choices
ethical choices
local-only choices
ending-affecting choices
```

Define where branches must converge and which state differences survive convergence.

### 9. Automated Design Validation

Create `validation_manifest.json`.

Run deterministic checks before compiling public files:

```text
node reachability
exit reachability
ending reachability
dead states
unbounded loops
state contradictions
character status consistency
knowledge leaks
timeline contradictions
state write authority violations
mainline breaks
unresolved side routes
source fact violations
theme drift warnings
contract exit mismatch
storylet precondition impossibility
```

The validator should simulate multiple player policies:

```text
mainline
exploration
relationship-first
utility-first
resistance
conservative
random
speedrun
```

## Compiler Output

### `branch_graph.json`

V2 compiles topology into a v1-compatible graph with optional extensions:

```json
{
  "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": []},
  "title": "",
  "graph_scope": "full_game",
  "start_node_id": "node.start",
  "clusters": [],
  "nodes": [],
  "edges": []
}
```

V2 node extensions:

```json
{
  "id": "node.example",
  "node_type": "scene",
  "title": "",
  "summary": "",
  "is_terminal": false,
  "layer": "macro",
  "contract_id": "contract.example",
  "storylet_ids": [],
  "source_fact_ids": [],
  "source_policy_ids": []
}
```

V2 edge extensions:

```json
{
  "id": "edge.example",
  "from": "node.a",
  "to": "node.b",
  "label": "",
  "condition_type": "state_gate",
  "contract_exit_id": "exit.example",
  "source_rule_ids": []
}
```

The graph still owns topology only. It does not own executable effects.

### `game_ir.json`

V2 compiles semantic authority into:

```json
{
  "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": []},
  "design_layer": {"version": "v2"},
  "design_brief": {},
  "world": {},
  "source_facts_digest": {},
  "adaptation_policy_digest": {},
  "entities": [],
  "state_model": {},
  "global_state_variables": [],
  "relationship_state_variables": [],
  "knowledge_state_variables": [],
  "progression_stages": [],
  "node_contracts": [],
  "storylets": [],
  "event_rules": [],
  "validation_expectations": {}
}
```

`game_ir.json` must contain enough compact contract and storylet information for downstream realization without reopening v2 internals.

## New Subagent Roles

Add v2 prompt templates in a new reference file:

```text
references/design-layer-v2-prompts.md
```

Recommended roles:

```text
SourceFactBuilder
AdaptationPolicyDesigner
WorldStateModeler
MacroGraphDesigner
NodeContractDesigner
SubgraphDesigner
StoryletDesigner
DesignV2CompilerReviewer
```

Controller rule:

```text
All v2 authoring agents write typed payloads only.
Only deterministic scripts compile public branch_graph.json and game_ir.json.
No downstream realization agent reads v2 internal artifacts.
```

## Deterministic Scripts

Add scripts:

```text
scripts/design_v2_compile.py
scripts/design_v2_validate.py
scripts/design_v2_project_context.py
```

### `design_v2_validate.py`

Responsibilities:

```text
validate internal schemas
check source trace ids
check contract authority
check subgraph exits against parent contracts
check storylet preconditions against state model
run graph reachability and ending reachability
write validation_manifest.json
```

### `design_v2_compile.py`

Responsibilities:

```text
read v2 internal artifacts
fail if validation has blocking errors
compile public branch_graph.json
compile public game_ir.json
write compile_report.json
do not write graph compatibility aliases
```

### `design_v2_project_context.py`

Responsibilities:

```text
create per-node context slices from branch_graph.json and game_ir.json
prepare NodeRealizationPlanner batch inputs
prepare NodeDialogueWriter node inputs
prepare AssetDirector compact inputs
```

This script protects the agent interface: downstream agents receive slices generated from the two public files, not raw v2 internals.

## CLI Integration

Add a design-layer option to `run_pipeline.py`.

Initial commands:

```bash
python3 scripts/run_pipeline.py init \
  --prompt "..." \
  --run-root runs/my-game \
  --design-layer v2
```

Add a compile command:

```bash
python3 scripts/run_pipeline.py compile-design \
  --run-root runs/my-game \
  --design-layer v2
```

Build remains unchanged:

```bash
python3 scripts/run_pipeline.py build \
  --run-root runs/my-game
```

`build` should not care whether `branch_graph.json` and `game_ir.json` came from v1 or v2.

## Implementation Milestones

### Milestone 1: Contract Documentation

Add:

```text
references/design-layer-v2-contracts.md
references/design-layer-v2-prompts.md
```

Include exact JSON shapes for every v2 internal artifact and the compiled public files.

### Milestone 2: Runtime Compatibility Refactor

Complete the v1 refactor first:

```text
canonical branch_graph.json
game_ir design_brief
two-file downstream prompts
no legacy graph alias support
two-file validation fixture
```

V2 depends on this stable public target.

### Milestone 3: V2 Internal Validator

Implement `design_v2_validate.py`.

Start with structural checks:

```text
required files
unique ids
valid references
contract exit coverage
state read/write authority
subgraph exit mapping
storylet state references
```

Then add simulation checks:

```text
reachable endings
dead states
unreachable storylets
loop limit
knowledge leaks
```

### Milestone 4: V2 Compiler

Implement `design_v2_compile.py`.

Compiler rules:

```text
macro nodes become branch graph nodes
subgraph nodes may either flatten into branch graph nodes or remain summarized under parent nodes
storylets compile into game_ir.storylets
node contracts compile into game_ir.node_contracts
state model compiles into game_ir state variables
contract exits compile into branch graph edges and game_ir event rules
```

The first implementation should prefer a flattened branch graph for clarity. Later versions can support grouped clusters.

### Milestone 5: Prompt Pack and Controller Workflow

Update `SKILL.md` and the relevant role cards under `references/subagents/`:

```text
v1 workflow remains default
v2 workflow is opt-in
v2 internal agents generate artifacts under workspace/design_layer/v2/
controller compiles v2 artifacts before realization
realization agents still receive only branch_graph/game_ir context
```

### Milestone 6: Context Projection

Implement `design_v2_project_context.py` or fold the logic into `pipeline_lib.py`.

Required projections:

```text
node realization context
dialogue writer node packet
asset direction packet
review packet
```

Each packet should include:

```text
source node
incoming and outgoing edges
allowed exits
relevant state variables
relevant event rules
relevant storylets
contract constraints
local cast
local locations
continuity constraints
```

### Milestone 7: Fixtures and Regression Tests

Add fixtures:

```text
tests/fixtures/v2_minimal_mesh/
tests/fixtures/v2_contract_violation/
tests/fixtures/v2_storylet_unreachable/
tests/fixtures/v2_compile_to_v1_runtime/
```

Test cases:

```text
V2 minimal mesh validates and compiles.
Compiled branch_graph/game_ir pass v1 runtime validation.
Build can run from compiled public files.
Contract exit mismatch fails before compile.
Storylet with impossible preconditions fails or warns.
State write outside contract authority fails.
Downstream prompts and generated packets do not include v2 internal file paths.
```

### Milestone 8: Default Switch

Keep v1 as default until:

```text
v2 fixtures are stable
compiled outputs build successfully
repair routing exists for v2 validation errors
documentation explains when to use v1 vs v2
```

Then decide whether to:

```text
make v2 default for long-form prompts
keep v1 default for short VN prompts
select automatically based on prompt complexity
```

## Validation Gates

V2 should have two validation gates.

### Internal Gate

Before compile:

```text
source facts valid
policy valid
state model valid
macro graph valid
contracts valid
subgraphs obey contracts
storylets valid
branch complexity controlled
simulations pass minimum reachability
```

### Public Gate

After compile:

```text
branch_graph.json valid
game_ir.json valid
graph and IR references consistent
runtime state projection valid
realization plans can cover every graph node
```

The public gate should reuse the v1 refactored validator. This keeps exporters independent from design-layer complexity.

## Repair Routing

Extend repair routing:

| Failure | Owner |
| --- | --- |
| Missing source fact trace | SourceFactBuilder |
| Invalid adaptation authority | AdaptationPolicyDesigner |
| Invalid state variable | WorldStateModeler |
| Unreachable macro node | MacroGraphDesigner |
| Contract exit mismatch | NodeContractDesigner |
| Subgraph violates parent contract | SubgraphDesigner |
| Impossible storylet precondition | StoryletDesigner |
| Compiler output mismatch | deterministic compiler repair |
| Public graph/IR mismatch | compiler or source artifact owner based on trace |

The controller should retry only the smallest failed artifact, then re-run deterministic validation and compile.

## Acceptance Criteria

The v2 design layer is implemented when:

```text
1. `run_pipeline.py init --design-layer v2` creates the v2 workspace layout.
2. V2 internal contracts are documented.
3. V2 prompt templates exist for every internal authoring role.
4. `design_v2_validate.py` validates internal artifacts and writes validation_manifest.json.
5. `design_v2_compile.py` emits branch_graph.json and game_ir.json.
6. Compiled public files pass the v1 runtime validator.
7. Downstream realization, dialogue, asset, and export steps read only compiled graph/IR context.
8. A minimal v2 fixture builds a playable Web VN.
9. At least one negative fixture proves contract validation catches invalid expansion.
10. Final reports clearly identify whether the run used v1 or v2 design generation.
```

## Risks

The biggest risk is letting v2 internal artifacts leak into downstream prompts. That would recreate the current coupling problem with more files.

Mitigation:

```text
Make branch_graph.json and game_ir.json the only documented downstream design inputs.
Generate all downstream prompt packets through a deterministic projection script.
Add tests that fail when downstream prompt templates mention v2 internal artifact paths.
```

The second risk is making `game_ir.json` too large.

Mitigation:

```text
Keep full internal details under workspace/design_layer/v2/.
Compile only durable, realization-relevant summaries into game_ir.json.
Use source ids and digests instead of copying every source note.
Let per-node projection extract compact packets for workers.
```

The third risk is over-validating creative design too early.

Mitigation:

```text
Start with structural errors and consistency warnings.
Promote warnings to errors only when they correspond to concrete runtime failure modes.
Keep theme drift and pacing checks advisory until fixtures prove stable behavior.
```
