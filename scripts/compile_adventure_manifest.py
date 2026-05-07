#!/usr/bin/env python3
"""Compile side-scroller adventure artifacts into a runtime manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adventure_schema import build_adventure_manifest, validate_adventure_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    if not args.skip_validation:
        result = validate_adventure_artifacts(run_root, write_report=True)
        if result.status == "fail":
            print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
            raise SystemExit(1)
    manifest = build_adventure_manifest(run_root)
    print(json.dumps({
        "status": "compiled",
        "manifest": "workspace/adventure/adventure-manifest.json",
        "levels": len(manifest.get("levels", [])),
        "interactions": len(manifest.get("interactions", [])),
        "quests": len(manifest.get("quests", [])),
        "dialogue": len(manifest.get("dialogue", [])),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
