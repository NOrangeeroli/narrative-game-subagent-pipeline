#!/usr/bin/env python3
"""Compile Design Layer V3 into the public graph/state design interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from design_v3_lib import DESIGN_V3_COMPILE_REPORT, compile_design_v3
from pipeline_lib import load_optional_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    result = compile_design_v3(run_root)
    report = load_optional_json(run_root / DESIGN_V3_COMPILE_REPORT) or result.to_json()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
