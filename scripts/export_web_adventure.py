#!/usr/bin/env python3
"""Export a self-contained browser side-scroller adventure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adventure_schema import build_adventure_manifest, validate_adventure_artifacts
from pipeline_lib import copy_tree, path_for, skill_root, write_json, write_text


def export_web_adventure(run_root: Path) -> Path:
    validation = validate_adventure_artifacts(run_root, write_report=True)
    if validation.status == "fail":
        raise SystemExit(json.dumps(validation.to_json(), ensure_ascii=False, indent=2))
    manifest = build_adventure_manifest(run_root)
    build_root = run_root / "build" / "web-adventure"
    copy_tree(skill_root() / "assets" / "web-adventure-template", build_root)
    write_text(
        build_root / "adventure-data.js",
        "window.NARRATIVE_ADVENTURE = "
        + json.dumps(manifest, ensure_ascii=False, indent=2)
        + ";\n",
    )
    report = {
        "status": "exported",
        "output_root": str(build_root),
        "index": str((build_root / "index.html").relative_to(run_root)),
        "data": str((build_root / "adventure-data.js").relative_to(run_root)),
        "levels": len(manifest.get("levels", [])),
        "interactions": len(manifest.get("interactions", [])),
        "ending_catalog": len(manifest.get("ending_catalog", [])),
        "notes": [
            "Generated export is a self-contained browser side-scroller.",
            "Open index.html directly; no Unity Editor or local server is required.",
        ],
    }
    write_json(path_for(run_root, "adventure_web_export_report"), report)
    return build_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_adventure(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
