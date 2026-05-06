# Design Layer Fixtures

- `v3_hierarchical_minimal`: a passing V3 fixture with two story levels, coarse-to-fine graph/state design, and a fine-level `parent_state_settlements.json` that writes immediate parent state.
- `v3_contract_violation`: a failing V3 fixture where a child-level settlement writes a missing parent-level state variable.

Run examples:

```bash
python3 scripts/design_v3_validate.py --run-root tests/fixtures/v3_hierarchical_minimal
python3 scripts/design_v3_compile.py --run-root tests/fixtures/v3_hierarchical_minimal
python3 scripts/design_v3_validate.py --run-root tests/fixtures/v3_contract_violation
python3 tests/run_v3_regression.py
```

Use a temporary copy when running compile commands if you do not want generated reports written into the fixture tree.
