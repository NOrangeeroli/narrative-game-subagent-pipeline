# Independent Advanced VN Post-Design Plan

## Goal

Build Advanced VN as a separate post-design toolchain and agent set. It should
consume only the public design-layer outputs and produce a playable interactive
VN that is not a typed copy of the standard VN/Yarn pipeline.

The Advanced VN branch must be able to create scenes where player interaction
changes the stage through commands, focused overlays, object inspection, state
writes, and route choices. Clicking an interactable should not degrade into a
plain text log unless the scene explicitly chooses that fallback.

## Hard Boundaries

Do not modify any V1 or V3 design-layer artifacts, contracts, agents, or
compilers.

Do not change the shape or meaning of:

```text
workspace/design_layer/user_requirements.json
workspace/design_layer/chapter_linear_synopsis.json
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/design_layer_v3/**
```

Do not read, migrate, or depend on standard VN post-design artifacts:

```text
workspace/vn/fragments/**
workspace/vn/story.yarn
workspace/vn/story.storyir.json
NodeSceneWriter
NodeDialogueWriter
NodeRealizationPlanner
standard VN fragment manifests
Yarn command parsing
standard VN line_performance or voice attachment logic
```

Advanced VN may read only controller-selected slices derived from:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/state/shared-state.schema.json
inputs/source_material/chunks/<assigned-chunk>.txt
```

`shared-state.schema.json` is a derived projection. Advanced VN may use it for
validation and runtime state binding, but it must not write back into V1/V3
design-layer sources.

## Target Architecture

Advanced VN becomes an isolated post-design lane:

```text
branch_graph.json + game_ir.json
  -> advanced_vn_plan.py
  -> AdvancedVNRealizationPlanner
  -> AdvancedVNSceneDesigner / AdvancedVNInteractionDesigner
  -> workspace/advanced-vn/scenes/*.scene.json
  -> advanced_vn_plan_assets.py
  -> workspace/advanced-vn/asset-manifest.json
  -> advanced_vn_generate_assets.py
  -> workspace/advanced-vn/generated-assets/**
  -> advanced_vn_export_web.py
  -> build/advanced-vn-web/**
```

The standard VN build path remains untouched:

```text
workspace/vn/**
build/web-vn/**
```

If both outputs are needed for comparison, the run should contain both:

```text
build/web-vn/
build/advanced-vn-web/
```

## Artifact Layout

Add Advanced VN-owned paths:

```text
workspace/advanced-vn/scene-plan.json
workspace/advanced-vn/scenes/<node-id>.scene.json
workspace/advanced-vn/scenes/scene-manifest.json
workspace/advanced-vn/asset-direction.json
workspace/advanced-vn/asset-manifest.json
workspace/advanced-vn/generated-assets/
workspace/advanced-vn/controller-packets/
reports/advanced-vn-validation.json
reports/advanced-vn-asset-validation.json
reports/advanced-vn-export-report.json
build/advanced-vn-web/
```

Do not store Advanced VN assets in the standard root-level asset manifest:

```text
workspace/asset-direction.json
workspace/asset-manifest.json
workspace/generated-assets/
```

Those remain standard VN/global pipeline paths until a later deliberate
unification is designed.

## Advanced VN Scene IR

Scene IR should be a runtime-facing interactive scene contract, not a Yarn
surrogate.

Required top-level shape:

```json
{
  "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNSceneDesigner", "notes": []},
  "source_node_id": "node.example",
  "title": "Player-facing title",
  "opening_beats": [],
  "interactables": [],
  "outcomes": [],
  "ending_variants": []
}
```

Allowed beat types:

```text
line
command
choice
```

Allowed command ids for the first implementation:

```text
show_bg
show_cg
hide_cg
show_char
set_expression
hide_char
play_bgm
stop_bgm
play_sfx
set
wait
focus_interactable
unlock_interactable
```

`interactables[*]` should support:

```json
{
  "id": "door",
  "label": "Inspect the locked door",
  "hotspot": {"x": 0.66, "y": 0.44, "w": 0.16, "h": 0.22},
  "conditions": [],
  "state_writes": [],
  "beats": [
    {"type": "command", "command": "play_sfx", "args": {"asset_id": "sfx.door.latch"}},
    {"type": "line", "speaker": "Narrator", "text": "The latch gives a dry click."}
  ],
  "fallback_text": "The door is locked."
}
```

Rules:

- `beats` is the primary feedback mechanism.
- `fallback_text` is allowed only for backwards compatibility or tiny flavor.
- If an interactable has no `beats`, validation should warn with
  `weak_text_only_interactable`.
- Multi-outcome scenes should require at least one interactable whose `beats`
  include a command or state write.
- Scene-visible text must not mention graph nodes, route ids, design levels,
  source coverage, workflow terms, or implementation details.

## Dedicated Agents

Create role cards under:

```text
references/subagents/post-design/advanced-vn/
```

### AdvancedVNRealizationPlanner

Owns per-node playable intent and graph outcome coverage.

Inputs:

```text
branch_graph slice
game_ir semantic/state slice
optional source excerpt selected by controller
```

Forbidden inputs:

```text
workspace/vn/**
workspace/advanced-vn/scenes/**
build/**
generated assets
```

Output:

```text
workspace/advanced-vn/scene-plan.json
```

Responsibilities:

- Preserve every public branch graph node.
- Bind every outgoing public edge exactly once.
- Decide the scene's interactive promise: inspect, pressure, memory, object,
  route choice, or terminal resolution.
- Identify required local stage objects and character focus without authoring
  final prose.

### AdvancedVNSceneDesigner

Owns the player-facing scene body for one planned node.

Inputs:

```text
one Advanced VN scene plan
branch_graph node and neighboring edge slice
game_ir state/rule slice
optional source excerpt selected by controller
```

Output:

```text
workspace/advanced-vn/scenes/<source_node_id>.scene.json
```

Responsibilities:

- Write `opening_beats`.
- Write 2-5 meaningful interactables.
- Ensure each interactable changes the stage, state, or revealed context through
  `beats`.
- Write outcome labels and outcome feedback beats.
- Avoid copying standard VN prose or Yarn command structure.

### AdvancedVNInteractionDesigner

Use only when a scene needs richer interaction than SceneDesigner should own in
one pass.

Responsibilities:

- Add hotspot geometry.
- Add unlock conditions.
- Add multi-step inspect sequences.
- Add feedback loops that reveal choices only after objects are inspected.

### AdvancedVNAssetDirector

Owns only Advanced VN asset planning.

Inputs:

```text
workspace/advanced-vn/scenes/*.scene.json
workspace/advanced-vn/scene-plan.json
```

Output:

```text
workspace/advanced-vn/asset-direction.json
```

Responsibilities:

- Collect `bg.*`, `cg.*`, `portrait.*`, `sfx.*`, and `bgm.*` ids from Advanced
  VN commands only.
- Consolidate repeated ids.
- Preserve character identity anchors.
- Do not read Yarn manifests or standard VN asset direction.

## Dedicated Scripts

Add new scripts without routing through standard VN functions:

```text
scripts/advanced_vn_plan.py
scripts/advanced_vn_validate.py
scripts/advanced_vn_plan_assets.py
scripts/advanced_vn_generate_assets.py
scripts/advanced_vn_export_web.py
scripts/advanced_vn_build.py
```

### `advanced_vn_plan.py`

Controller utility for deterministic packet preparation and plan persistence.

Commands:

```text
python scripts/advanced_vn_plan.py init --run-root <run>
python scripts/advanced_vn_plan.py write-packets --run-root <run>
python scripts/advanced_vn_plan.py summarize --run-root <run>
```

It may read `branch_graph.json`, `game_ir.json`, and source chunk metadata. It
must not read `workspace/vn/**`.

### `advanced_vn_validate.py`

Validates scene plan and Scene IR.

Checks:

- every branch graph node has exactly one scene plan
- every scene file exists
- every outgoing edge is covered exactly once
- state refs are declared in projected shared state
- unsupported top-level fields fail
- unsupported command ids fail
- interactable ids are unique within a scene
- text-only interactables warn
- scene-visible text has no workflow leakage

### `advanced_vn_plan_assets.py`

Reads only Advanced VN scenes and writes:

```text
workspace/advanced-vn/asset-manifest.json
reports/advanced-vn-scene-asset-intents.json
```

It must not call `load_yarn_fragments`.

### `advanced_vn_generate_assets.py`

Generates assets under:

```text
workspace/advanced-vn/generated-assets/
```

First provider:

```text
local-svg
```

Remote providers can be added later behind the same manifest contract.

### `advanced_vn_export_web.py`

Exports:

```text
build/advanced-vn-web/index.html
build/advanced-vn-web/story-data.js
build/advanced-vn-web/assets/**
reports/advanced-vn-export-report.json
```

It must not import or call `export_web_vn.py`.

### `advanced_vn_build.py`

Single entry point for the independent lane:

```text
python scripts/advanced_vn_build.py --run-root <run> --asset-provider local-svg
```

Order:

```text
validate core public design artifacts
project shared state into workspace/state/shared-state.schema.json
validate Advanced VN plan and scenes
plan Advanced VN assets
generate Advanced VN assets
validate Advanced VN assets
export Advanced VN web build
write Advanced VN reports
```

## Web Runtime Template

Create:

```text
assets/advanced-vn-template/index.html
assets/advanced-vn-template/runtime.js
assets/advanced-vn-template/style.css
```

Runtime requirements:

- stage background layer
- CG layer
- character portrait layer
- hotspot/interactable layer
- dialogue/overlay layer
- route choice layer
- visited interactable state
- condition checks and state writes
- command execution for every allowed Advanced VN command
- interactable click runs `beats`, not just text logs
- overlay returns to the same scene state after completion
- route choices remain locked, hidden, or available based on conditions

The runtime should treat the exported payload as Advanced VN-native data, not as
standard VN story data.

## Run Pipeline Integration

Keep existing standard commands stable.

Add a separate subcommand or script path:

```text
python scripts/advanced_vn_build.py --run-root runs/secret-garden-v3
```

Optional later integration:

```text
python scripts/run_pipeline.py build-advanced-vn --run-root <run>
```

Do not overload:

```text
python scripts/run_pipeline.py build --post-design advanced-vn
```

until the independent lane is complete and the old compatibility path is
removed or explicitly marked legacy.

## Migration Strategy

1. Leave current standard VN behavior unchanged.
2. Add independent Advanced VN scripts and template behind new file paths.
3. Add tiny fixtures under `tests/fixtures/advanced_vn_independent/`.
4. Generate one isolated Advanced VN sample run from public design artifacts.
5. Compare output against standard VN only by opening separate build folders;
   never by reading standard VN post-design artifacts.
6. Once independent lane passes, deprecate any legacy advanced-vn migration
   helper that was based on Yarn fragments.

## Test Plan

Add a regression script:

```text
tests/run_advanced_vn_independent_regression.py
```

Fixture should include:

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
inputs/source_material/chunks/chapter_01.txt
workspace/advanced-vn/scene-plan.json
workspace/advanced-vn/scenes/node.start.scene.json
```

Assertions:

- validator passes for a scene with interactable beats
- validator warns for text-only interactable
- asset planner reads only `workspace/advanced-vn/scenes`
- export creates `build/advanced-vn-web/story-data.js`
- exported story contains interactable `beats`
- no code path calls `load_yarn_fragments`
- no artifact is written under `workspace/vn`

Add static guards:

```text
rg "load_yarn_fragments|workspace/vn|story.yarn|NodeSceneWriter|NodeDialogueWriter" scripts/advanced_vn_*.py references/subagents/post-design/advanced-vn
```

Expected result: no forbidden dependency except in explicit negative test text.

Browser smoke:

```text
node tests/smoke_advanced_vn_web.js build/advanced-vn-web/index.html
```

Checks:

- first scene loads
- background asset resolves
- clicking an interactable plays an overlay beat
- a command changes portrait or background
- route choice remains available after overlay returns

## Execution Checklist

Implement in this order:

1. Create `assets/advanced-vn-template/` with a minimal independent runtime.
2. Create `scripts/advanced_vn_validate.py`.
3. Create a tiny fixture and make validation pass.
4. Create `scripts/advanced_vn_export_web.py` and export the fixture.
5. Add interactable beat playback to the Advanced VN runtime.
6. Add `scripts/advanced_vn_plan_assets.py` with local asset manifest output.
7. Add `scripts/advanced_vn_generate_assets.py` with local SVG output.
8. Add `scripts/advanced_vn_build.py`.
9. Add dedicated role cards and prompt templates for Advanced VN agents.
10. Update `SKILL.md` to describe Advanced VN as an independent post-design
    lane, not as a standard VN variant.
11. Add regression and browser smoke tests.
12. Run full validation commands listed below.

## Validation Commands

```bash
python -m py_compile scripts/advanced_vn_validate.py scripts/advanced_vn_plan_assets.py scripts/advanced_vn_generate_assets.py scripts/advanced_vn_export_web.py scripts/advanced_vn_build.py
python tests/run_advanced_vn_independent_regression.py
python scripts/advanced_vn_build.py --run-root tests/fixtures/advanced_vn_independent --asset-provider local-svg
node --check assets/advanced-vn-template/runtime.js
node tests/smoke_advanced_vn_web.js tests/fixtures/advanced_vn_independent/build/advanced-vn-web/index.html
```

Before merging, also run existing standard VN regressions to prove no regression:

```bash
python tests/run_v1_regression.py
python tests/run_v3_regression.py
```

## Acceptance Criteria

- Advanced VN build can complete without reading `workspace/vn/**`.
- Advanced VN output is written to `build/advanced-vn-web/`.
- Standard VN output remains written to `build/web-vn/`.
- Advanced VN interactables execute beats that can change stage state.
- Text-only interactables are allowed only as fallback and produce warnings.
- V1/V3 design-layer files are byte-for-byte unchanged by Advanced VN build.
- Existing standard VN regressions still pass.
- The implementation has a fixture proving Advanced VN is not a Yarn migration
  path.
