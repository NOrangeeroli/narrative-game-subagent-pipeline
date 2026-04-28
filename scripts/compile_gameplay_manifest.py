#!/usr/bin/env python3
"""Compile gameplay unit artifacts into gameplay-manifest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_lib import build_gameplay_manifest, load_optional_json, path_for, read_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    plans = load_optional_json(path_for(run_root, "realization_plans"))
    if not plans:
        raise SystemExit("Missing workspace/realization/node-realization-plans.json")
    shared_state = read_json(path_for(run_root, "shared_state")) if path_for(run_root, "shared_state").exists() else {"variables": []}
    manifest, result = build_gameplay_manifest(run_root, plans, shared_state)
    print(json.dumps({
        "manifest": str(path_for(run_root, "gameplay_manifest")),
        "units": len(manifest.get("units", [])),
        "status": result.status,
    }, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
