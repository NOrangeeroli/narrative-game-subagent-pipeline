#!/usr/bin/env python3
"""Regression checks for the Advanced VN post-design branch."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Command failed: {' '.join(args)}")
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_design_artifacts(run_root: Path) -> None:
    write_json(run_root / "workspace" / "design_layer" / "user_requirements.json", {
        "prompt": "Advanced VN smoke.",
        "requirements": [{"id": "req.core", "text": "One inspectable scene reaches one ending."}],
    })
    write_json(run_root / "workspace" / "design_layer" / "chapter_linear_synopsis.json", {
        "title": "Locked Garden",
        "events": [{"id": "event.garden", "summary": "The child inspects a locked garden door."}],
    })
    write_json(run_root / "workspace" / "design_layer" / "branch_graph.json", {
        "title": "Locked Garden",
        "start_node_id": "node.garden",
        "nodes": [
            {"id": "node.garden", "title": "Garden Door", "summary": "A locked garden door waits in the rain."},
            {"id": "node.end", "title": "Key Mark", "summary": "The key mark changes what the child understands.", "is_terminal": True},
        ],
        "edges": [
            {
                "id": "edge.garden_end",
                "from": "node.garden",
                "to": "node.end",
                "conditions": [{"state_variable_id": "state.key_mark_seen", "operator": "==", "value": True}],
                "effects": [{"state_variable_id": "state.route", "operation": "set", "value": "observed"}],
            }
        ],
    })
    write_json(run_root / "workspace" / "design_layer" / "game_ir.json", {
        "design_brief": {"target_experience": "Minimal Advanced VN interaction."},
        "global_state_variables": [
            {"id": "state.key_mark_seen", "type": "boolean", "initial_value": False},
            {"id": "state.route", "type": "string", "initial_value": ""},
        ],
        "event_rules": [],
    })


def write_advanced_vn_artifacts(run_root: Path) -> None:
    write_json(run_root / "workspace" / "advanced-vn" / "scene-plan.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNRegression"},
        "plans": [
            {"source_node_id": "node.garden", "outcomes": [{"id": "continue", "edge_id": "edge.garden_end"}]},
            {"source_node_id": "node.end", "outcomes": []},
        ],
    })
    write_json(run_root / "workspace" / "advanced-vn" / "scenes" / "node.garden.scene.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNRegression"},
        "source_node_id": "node.garden",
        "title": "Garden Door",
        "beats": [
            {"type": "command", "command": "show_bg", "args": {"asset_id": "bg.garden_wall"}},
            {"type": "line", "speaker": "Narrator", "text": "Rain darkens the locked garden door."},
        ],
        "interactables": [
            {
                "id": "door_mark",
                "label": "Inspect the key mark",
                "text": "The same key mark appears in the old corridor sketch.",
                "state_writes": [{"state_variable_id": "state.key_mark_seen", "operation": "set", "value": True}],
            }
        ],
        "outcomes": [{"id": "continue", "edge_id": "edge.garden_end"}],
        "ending_variants": [],
    })
    write_json(run_root / "workspace" / "advanced-vn" / "scenes" / "node.end.scene.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdvancedVNRegression"},
        "source_node_id": "node.end",
        "title": "Key Mark",
        "beats": [{"type": "line", "speaker": "Narrator", "text": "The mark makes the silence feel deliberate."}],
        "interactables": [],
        "outcomes": [],
        "ending_variants": [],
    })


def assert_advanced_export(run_root: Path) -> None:
    text = (run_root / "build" / "web-vn" / "story-data.js").read_text(encoding="utf-8")
    prefix = "window.NARRATIVE_GAME_STORY = "
    if not text.startswith(prefix):
        raise SystemExit("story-data.js does not contain expected global assignment.")
    story = json.loads(text[len(prefix):].strip().removesuffix(";"))
    if story.get("metadata", {}).get("post_design") != "advanced-vn":
        raise SystemExit("Advanced VN export did not mark post_design.")
    garden = next((node for node in story.get("nodes", []) if node.get("id") == "node.garden"), None)
    if not isinstance(garden, dict):
        raise SystemExit("Advanced VN export is missing node.garden.")
    if not garden.get("advanced_interactables"):
        raise SystemExit("Advanced VN interactables were not exported.")
    choice = next((item for item in garden.get("choices", []) if item.get("edge_id") == "edge.garden_end"), None)
    if not isinstance(choice, dict):
        raise SystemExit("Advanced VN outcome edge was not exported.")
    if choice.get("condition_type") != "auto":
        raise SystemExit("Single unlabeled Advanced VN outcome should export as auto continue.")
    if not any(effect.get("state_variable_id") == "state.route" for effect in choice.get("effects", [])):
        raise SystemExit("Advanced VN choice did not preserve branch_graph edge effects.")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="narrative-advanced-vn-regression-") as temp:
        run_root = Path(temp) / "advanced_vn_smoke"
        run([sys.executable, "scripts/run_pipeline.py", "init", "--prompt", "Advanced VN smoke.", "--run-root", str(run_root)])
        write_design_artifacts(run_root)
        run([sys.executable, "scripts/validate_artifacts.py", "--run-root", str(run_root), "--write-projections"])
        write_advanced_vn_artifacts(run_root)
        run([sys.executable, "scripts/run_pipeline.py", "validate-advanced-vn", "--run-root", str(run_root)])
        run([sys.executable, "scripts/run_pipeline.py", "build", "--post-design", "advanced-vn", "--run-root", str(run_root)])
        assert_advanced_export(run_root)
    print("Advanced VN regression checks passed.")


if __name__ == "__main__":
    main()
