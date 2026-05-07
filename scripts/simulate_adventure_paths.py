#!/usr/bin/env python3
"""Simulate adventure graph routes through compiled bindings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adventure_schema import simulate_adventure_routes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = simulate_adventure_routes(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
