---
agent_id: VNBackgroundGenerator
stage: asset-generation
canonical_output: reports/vn-background-generation-report.json
---

# VNBackgroundGenerator

## Mission

Fulfill VN background generation requests for the `backgrounds` section of
`workspace/asset-manifest.json`.

This subagent shares the same provider configuration as the RPG background
workflow, but does not create RPG boundaries.

## Workflow

1. Read `reports/asset-manifest-probe.json`.
2. Confirm `vn_background` is true.
3. Run:

   ```bash
   python3 scripts/run_pipeline.py generate-backgrounds --run-root <run-root> --scope vn
   ```

4. If the report status is `needs_imagegen`, process
   `workspace/generated-assets/imagegen-requests/*.json` for VN background
   assets:
   - Read `asset_id`, `prompt`, and `output_file`.
   - Call Codex `image_gen`.
   - Copy the selected generated image into `<run-root>/<output_file>`.
5. Rerun the VN background command to continue video generation and provenance
   recording.
6. Do not process `workspace/generated-assets/imagegen-requests/rpg-boundaries/`
   and do not run RPG boundary generation. VN backgrounds have no boundary
   contract in this workflow.

## Success Contract

The workflow succeeds when:

- `reports/vn-background-generation-report.json` has `status: pass`.
- `reports/asset-provenance-report.json` has `status: pass`.
- Every VN background asset has a truthful `final_provider`.
- No RPG boundary report is required for VN-only background generation.
