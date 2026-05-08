#!/usr/bin/env python3
"""Validate Advanced VN scene plan and Scene IR artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_lib import validate_advanced_vn_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    result = validate_advanced_vn_run(Path(args.run_root).resolve(), write_reports=True)
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
