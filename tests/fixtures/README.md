# Design Layer Fixtures

- `v2_minimal_mesh`: a passing `source_adaptation` fixture with source-intake segments, coverage matrix, a root macro mesh, one depth-1 mesh expansion, and one depth-2 expansion enabled by `depth_budget_by_parent`.
- `v2_contract_violation`: a failing fixture where a depth-2 subgraph points to a missing parent mesh node.
- The regression test also derives an `idea`-mode temporary fixture from `v2_minimal_mesh` to verify that synthetic source intake works without leaking source-intake trace into public outputs.
- `v3_hierarchical_minimal`: a passing V3 fixture with two story levels, coarse-to-fine graph/state design, and a fine-level `parent_state_settlements.json` that writes immediate parent state.
- `v3_contract_violation`: a failing V3 fixture where a child-level settlement writes a missing parent-level state variable.

Run examples:

```bash
python3 scripts/design_v2_validate.py --run-root tests/fixtures/v2_minimal_mesh
python3 scripts/design_v2_compile.py --run-root tests/fixtures/v2_minimal_mesh
python3 scripts/design_v2_validate.py --run-root tests/fixtures/v2_contract_violation
python3 tests/run_v2_regression.py
python3 scripts/design_v3_validate.py --run-root tests/fixtures/v3_hierarchical_minimal
python3 scripts/design_v3_compile.py --run-root tests/fixtures/v3_hierarchical_minimal
python3 scripts/design_v3_validate.py --run-root tests/fixtures/v3_contract_violation
python3 tests/run_v3_regression.py
```

Use a temporary copy when running compile commands if you do not want generated reports written into the fixture tree.
