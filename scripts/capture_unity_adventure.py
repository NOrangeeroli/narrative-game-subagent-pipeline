#!/usr/bin/env python3
"""Run or record Unity adventure playtests when Unity is available."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from adventure_schema import simulate_adventure_routes
from pipeline_lib import path_for, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--unity-executable", default=None)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    simulation = simulate_adventure_routes(run_root)
    unity_executable = args.unity_executable or shutil.which("Unity") or shutil.which("unity")
    report = {
        "status": "pass" if simulation["status"] == "pass" else "fail",
        "simulation": simulation,
        "unity_available": bool(unity_executable),
        "unity_executable": unity_executable,
        "captures": [],
        "notes": [],
    }
    if not unity_executable:
        report["notes"].append("Unity executable was not found; route simulation completed without engine capture.")
    write_json(path_for(run_root, "adventure_playtest_report"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
