#!/usr/bin/env python3
"""Generate a minimal Unity project from accepted narrative artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from export_web_vn import build_story_payload
from pipeline_lib import copy_tree, skill_root, write_text


def export_unity_project(run_root: Path) -> Path:
    project_root = run_root / "build" / "unity-project"
    copy_tree(skill_root() / "assets" / "unity-template", project_root)
    story = build_story_payload(run_root)
    write_text(project_root / "Assets" / "Resources" / "story.json", json.dumps(story, ensure_ascii=False, indent=2))
    template_path = project_root / "Assets" / "Scripts" / "GameController.cs.template"
    controller_path = project_root / "Assets" / "Scripts" / "GameController.cs"
    controller_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    template_path.unlink()
    return project_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_unity_project(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()

