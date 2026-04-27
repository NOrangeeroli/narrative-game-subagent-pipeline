#!/usr/bin/env python3
"""Assemble accepted per-node Yarn fragments into a global story.yarn."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_lib import assemble_yarn_text, load_yarn_fragments, path_for, write_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    fragments = load_yarn_fragments(run_root)
    output_path = write_text(path_for(run_root, "story_yarn"), assemble_yarn_text(fragments))
    print(str(output_path))
    if not fragments:
        raise SystemExit("No Yarn fragments found under workspace/vn/fragments.")


if __name__ == "__main__":
    main()

