#!/usr/bin/env python3
"""Validate narrative game artifacts and optionally project shared state."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_lib import validate_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--write-projections", action="store_true")
    args = parser.parse_args()

    result = validate_all(Path(args.run_root).resolve(), write_projections=args.write_projections)
    print(result.to_json())
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

