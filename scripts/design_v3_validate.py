#!/usr/bin/env python3
"""Validate Design Layer V3 hierarchical source design artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from design_v3_lib import validate_design_v3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    result = validate_design_v3(Path(args.run_root).resolve(), write_report=True)
    print(json.dumps(result.to_json(), indent=2, ensure_ascii=False))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
