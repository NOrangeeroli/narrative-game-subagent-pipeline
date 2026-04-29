# Design Layer V2 Fixtures

- `v2_minimal_mesh`: a passing fixture with a root macro mesh, one depth-1 mesh expansion, and one depth-2 expansion enabled by `depth_budget_by_parent`.
- `v2_contract_violation`: a failing fixture where a depth-2 subgraph points to a missing parent mesh node.

Run examples:

```bash
python3 scripts/design_v2_validate.py --run-root tests/fixtures/v2_minimal_mesh
python3 scripts/design_v2_compile.py --run-root tests/fixtures/v2_minimal_mesh
python3 scripts/design_v2_validate.py --run-root tests/fixtures/v2_contract_violation
python3 tests/run_v2_regression.py
```

Use a temporary copy when running compile commands if you do not want generated reports written into the fixture tree.
