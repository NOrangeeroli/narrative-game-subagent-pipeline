#!/usr/bin/env python3
"""Validate side-scroller adventure artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adventure_schema import validate_adventure_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    result = validate_adventure_artifacts(Path(args.run_root).resolve(), write_report=args.write_report)
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
