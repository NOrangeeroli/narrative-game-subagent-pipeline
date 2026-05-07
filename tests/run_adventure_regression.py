#!/usr/bin/env python3
"""Regression checks for side-scroller adventure extension."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if expect_success and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Command failed: {' '.join(args)}")
    if not expect_success and result.returncode == 0:
        print(result.stdout)
        raise SystemExit(f"Command unexpectedly passed: {' '.join(args)}")
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_minimal_run(run_root: Path) -> None:
    write_json(run_root / "workspace" / "design_layer" / "user_requirements.json", {
        "prompt": "Build a small side-scroller adventure.",
        "requirements": [{"id": "req.playable", "text": "The player can inspect a door and reach an ending."}],
    })
    write_json(run_root / "workspace" / "design_layer" / "chapter_linear_synopsis.json", {
        "title": "Tiny Adventure",
        "events": [
            {"id": "event.start", "summary": "Ada enters the hall."},
            {"id": "event.ending", "summary": "Ada opens the garden door."},
        ],
    })
    write_json(run_root / "workspace" / "design_layer" / "branch_graph.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "adventure_regression"},
        "title": "Tiny Adventure",
        "start_node_id": "node.start",
        "nodes": [
            {
                "id": "node.start",
                "node_type": "scene",
                "title": "Hall",
                "summary": "Ada stands in a quiet hall with a locked garden door.",
                "is_terminal": False,
            },
            {
                "id": "node.ending",
                "node_type": "terminal",
                "title": "Garden Opens",
                "summary": "Ada opens the garden door and steps into sunlight.",
                "is_terminal": True,
                "ending_id": "ending.garden_opened",
                "ending_variant_id": "ending.garden_opened.default",
                "variant_of_ending_id": "ending.garden_opened",
            },
        ],
        "edges": [
            {
                "id": "edge.start_to_ending",
                "from": "node.start",
                "to": "node.ending",
                "label": "Open the garden door",
                "condition_type": "player_choice",
                "conditions": [
                    {
                        "state_variable_id": "state.key_status",
                        "operator": "in",
                        "value": ["found", "held"],
                    }
                ],
                "effects": [
                    {
                        "state_variable_id": "state.route_memory",
                        "operation": "append_unique",
                        "value": "opened_garden",
                    },
                    {
                        "state_variable_id": "state.game.ending_id",
                        "operation": "set",
                        "value": "ending.garden_opened",
                    },
                ],
            }
        ],
    })
    write_json(run_root / "workspace" / "design_layer" / "game_ir.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "adventure_regression"},
        "design_layer": {"version": "v3"},
        "design_brief": {"summary": "A tiny complete route."},
        "global_state_variables": [
            {"id": "state.key_status", "type": "enum", "allowed_values": ["missing", "found", "held"], "initial_value": "found"},
            {"id": "state.route_memory", "type": "string", "initial_value": ""},
            {"id": "state.game.ending_id", "type": "string", "initial_value": None},
        ],
        "event_rules": [
            {"id": "edge.start_to_ending", "description": "Open the door."}
        ],
    })
    write_json(run_root / "workspace" / "realization" / "node-realization-plans.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "adventure_regression"},
        "plans": [
            {
                "source_node_id": "node.start",
                "realization_kind": "vn_yarn",
                "unit_id": "realization.node_start",
                "entry_binding": {"type": "yarn_node", "node_title": "Node_node_start"},
                "exit_bindings": [{"edge_id": "edge.start_to_ending", "outcome_id": "outcome_edge_start_to_ending"}],
                "required_state_reads": [],
                "state_writes": [],
            },
            {
                "source_node_id": "node.ending",
                "realization_kind": "vn_yarn",
                "unit_id": "realization.node_ending",
                "entry_binding": {"type": "yarn_node", "node_title": "Node_node_ending"},
                "exit_bindings": [],
                "required_state_reads": [],
                "state_writes": [],
            },
        ],
    })


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="adventure-regression-") as temp:
        run_root = Path(temp) / "run"
        write_minimal_run(run_root)

        run([sys.executable, "scripts/run_pipeline.py", "plan-adventure", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "compile-adventure", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "validate-adventure", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "export-adventure-web", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "export-adventure-unity", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "test-adventure", "--run-root", str(run_root)])
        manifest = read_json(run_root / "workspace" / "adventure" / "adventure-manifest.json")
        if not manifest.get("unity_runtime", {}).get("interactions"):
            raise SystemExit("Adventure manifest did not include Unity runtime interactions.")
        if not (run_root / "build" / "web-adventure" / "index.html").exists():
            raise SystemExit("Web adventure export did not write index.html.")
        if not (run_root / "build" / "web-adventure" / "adventure-data.js").exists():
            raise SystemExit("Web adventure export did not write adventure-data.js.")
        if not (run_root / "build" / "unity-adventure" / "Assets" / "StreamingAssets" / "adventure-runtime.json").exists():
            raise SystemExit("Unity adventure export did not write runtime manifest.")

        broken = Path(temp) / "broken"
        shutil.copytree(run_root, broken)
        bindings_path = broken / "workspace" / "adventure" / "bindings" / "narrative-bindings.json"
        bindings = read_json(bindings_path)
        bindings["edge_bindings"] = []
        write_json(bindings_path, bindings)
        failure = run([sys.executable, "scripts/run_pipeline.py", "validate-adventure", "--run-root", str(broken)], expect_success=False)
        if "missing_edge_trigger" not in failure.stdout:
            raise SystemExit("Expected missing_edge_trigger failure for broken adventure bindings.")

    print("Adventure regression checks passed.")


if __name__ == "__main__":
    main()
