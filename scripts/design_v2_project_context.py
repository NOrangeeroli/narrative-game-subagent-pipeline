#!/usr/bin/env python3
"""Project a focused downstream agent context from compiled Design Layer V2 output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from design_v2_lib import project_node_context, source_node_for_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--node-id")
    selector.add_argument("--plan-id")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    node_id = args.node_id
    if args.plan_id:
        node_id = source_node_for_plan(run_root, args.plan_id)
        if not node_id:
            raise SystemExit(f"Unknown realization plan id: {args.plan_id}")
    output_path, packet = project_node_context(run_root, node_id)
    print(json.dumps({
        "output_path": str(output_path),
        "context": packet,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
