#!/usr/bin/env python3
"""Validate RPG artifacts and refresh the compiled RPG manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compile_rpg_manifest import compile_rpg_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    _, report = compile_rpg_manifest(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
