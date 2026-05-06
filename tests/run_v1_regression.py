#!/usr/bin/env python3
"""Regression checks for the V1 public design interface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline_lib import validate_graph_ir_consistency  # noqa: E402


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_v1_artifacts(run_root: Path) -> None:
    write_json(run_root / "workspace" / "design_layer" / "user_requirements.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "PromptAnalyst", "notes": []},
        "prompt": "V1 public edge semantics smoke test.",
        "target_experience": "A tiny branching visual novel.",
        "requirements": [{"id": "req.core", "priority": "must", "text": "One stateful choice reaches two endings.", "source_phrase": "stateful choice"}],
        "creative_constraints": {"genre": "mystery", "tone": "quiet", "themes": ["consequence"], "motifs": ["door"], "prohibited_content": []},
        "production_constraints": {"target_language": "en", "approximate_node_count": 3, "desired_endings": 2, "asset_budget_level": "low", "notes": []},
        "assumptions": [],
        "unknowns": [],
    })
    write_json(run_root / "workspace" / "design_layer" / "chapter_linear_synopsis.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "LinearSynopsisDesigner", "notes": []},
        "title": "Greenhouse Door",
        "summary": "A visitor sees a lit greenhouse door and chooses how to respond.",
        "events": [{"id": "event.door", "summary": "The door glows at night.", "purpose": "Present the stateful choice.", "requirement_ids": ["req.core"]}],
        "cast": [{"id": "char.lin", "name": "Lin", "role": "visitor"}],
        "locations": [{"id": "loc.hall", "name": "Hall", "description": "A quiet hall."}],
        "pacing_notes": ["One setup, one choice, two endings."],
    })
    write_json(run_root / "workspace" / "design_layer" / "branch_graph.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "BranchGraphDesigner", "notes": []},
        "title": "Greenhouse Door",
        "graph_scope": "full_game",
        "clusters": [],
        "source_outline_ids": ["event.door"],
        "start_node_id": "node.start",
        "nodes": [
            {"id": "node.start", "node_type": "start", "title": "Lit Door", "summary": "Lin sees light under the greenhouse door.", "is_terminal": False, "source_event_ids": ["event.door"]},
            {"id": "node.enter", "node_type": "terminal", "title": "Enter", "summary": "Lin enters and finds the watered plant.", "is_terminal": True, "source_event_ids": ["event.door"]},
            {"id": "node.ask", "node_type": "terminal", "title": "Ask", "summary": "Lin wakes the steward before entering.", "is_terminal": True, "source_event_ids": ["event.door"]},
        ],
        "edges": [
            {
                "id": "edge.start_enter",
                "from": "node.start",
                "to": "node.enter",
                "label": "Open the greenhouse door",
                "condition_type": "player_choice",
                "conditions": [],
                "effects": [{"id": "state.route", "operation": "set", "value": "entered"}],
            },
            {
                "id": "edge.start_ask",
                "from": "node.start",
                "to": "node.ask",
                "label": "Call the steward",
                "condition_type": "player_choice",
                "conditions": [],
                "effects": [{"state_variable_id": "state.route", "operation": "set", "value": "asked"}],
            },
        ],
    })
    write_json(run_root / "workspace" / "design_layer" / "game_ir.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "BaseGameIRDesigner", "notes": []},
        "design_brief": {
            "target_experience": "A compact V1 stateful branch.",
            "tone": "quiet",
            "themes": ["consequence"],
            "must_keep_constraints": [],
            "production_constraints": {"target_language": "en"},
            "narrative_bible": {"cast": [], "locations": [], "timeline": [], "continuity_rules": []},
        },
        "world": {"summary": "A quiet house at night."},
        "entities": [{"id": "char.lin", "kind": "character", "name": "Lin", "description": "A curious visitor."}],
        "global_state_variables": [
            {"id": "state.route", "type": "enum", "allowed_values": ["undecided", "entered", "asked"], "initial_value": "undecided", "description": "Chosen route."}
        ],
        "progression_stages": [{"id": "stage.choice", "description": "Door choice."}],
        "event_rules": [
            {"id": "rule.enter", "source_edge_id": "edge.start_enter", "conditions": [], "effects": [{"state_variable_id": "state.route", "operation": "set", "value": "entered"}]},
            {"id": "rule.ask", "source_edge_id": "edge.start_ask", "conditions": [], "effects": [{"state_variable_id": "state.route", "operation": "set", "value": "asked"}]},
        ],
    })
    plans = []
    fragments_root = run_root / "workspace" / "vn" / "fragments"
    nodes = [
        ("node.start", "Node_Start", "vn_yarn", [("enter", "edge.start_enter"), ("ask", "edge.start_ask")]),
        ("node.enter", "Node_Enter", "cutscene_yarn", []),
        ("node.ask", "Node_Ask", "cutscene_yarn", []),
    ]
    for node_id, title, kind, exits in nodes:
        exit_bindings = [{"outcome_id": outcome, "edge_id": edge_id} for outcome, edge_id in exits]
        plans.append({
            "source_node_id": node_id,
            "realization_kind": kind,
            "unit_id": f"realization.{node_id.removeprefix('node.')}",
            "entry_binding": {"type": "yarn_node", "node_title": title},
            "exit_bindings": exit_bindings,
            "required_state_reads": [],
            "state_writes": [],
            "terminal_variants": [],
            "required_assets": [],
            "continuity_summary": "V1 regression node.",
            "implementation_notes": [],
            "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.door"], "node_ids": [node_id], "edge_ids": [edge_id for _, edge_id in exits], "game_ir_ids": []},
        })
        if exits:
            yarn = f"""title: {title}
---
// source_node: {node_id}
Narrator: Light lies under the greenhouse door.
-> Open the greenhouse door
    Narrator: Lin opens the door.
    <<complete_activity outcome="enter">>
-> Call the steward
    Narrator: Lin steps back and calls for help.
    <<complete_activity outcome="ask">>
===
"""
        else:
            yarn = f"""title: {title}
---
// source_node: {node_id}
Narrator: The choice settles into a different ending.
===
"""
        write_text(fragments_root / f"{node_id}.yarn", yarn)
        write_json(fragments_root / f"{node_id}.manifest.json", {
            "metadata": {"schema_version": "0.1.0", "generated_by": "V1RegressionFixture", "notes": []},
            "source_node_id": node_id,
            "realization_unit_id": f"realization.{node_id.removeprefix('node.')}",
            "yarn_node_title": title,
            "local_asset_refs": [],
            "command_refs": [],
            "line_performance": [],
            "exit_bindings": exit_bindings,
            "state_reads": [],
            "state_writes": [],
            "terminal_variants": [],
            "continuity_summary": "V1 regression fragment.",
            "source_trace": {"node_ids": [node_id], "edge_ids": [edge_id for _, edge_id in exits]},
        })
    write_json(run_root / "workspace" / "realization" / "node-realization-plans.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "V1RegressionFixture", "notes": []},
        "plans": plans,
    })


def assert_exported_edge_effects(run_root: Path) -> None:
    text = (run_root / "build" / "web-vn" / "story-data.js").read_text(encoding="utf-8")
    prefix = "window.NARRATIVE_GAME_STORY = "
    story = json.loads(text[len(prefix):].strip().removesuffix(";"))
    start = next(node for node in story["nodes"] if node["id"] == "node.start")
    choices = {choice["edge_id"]: choice for choice in start["choices"]}
    if not any(effect.get("state_variable_id") == "state.route" and effect.get("value") == "entered" for effect in choices["edge.start_enter"].get("effects", [])):
        raise SystemExit("V1 runtime choice did not read effects from branch_graph.edges[*].effects.")
    if not any(effect.get("state_variable_id") == "state.route" and effect.get("value") == "asked" for effect in choices["edge.start_ask"].get("effects", [])):
        raise SystemExit("V1 runtime choice did not read effects from branch_graph.edges[*].effects.")


def assert_id_form_state_refs_are_validated() -> None:
    findings = validate_graph_ir_consistency(
        {
            "edges": [
                {
                    "id": "edge.bad",
                    "from": "node.start",
                    "to": "node.end",
                    "conditions": [],
                    "effects": [{"id": "state.missing", "operation": "set", "value": True}],
                }
            ]
        },
        {"global_state_variables": [{"id": "state.known", "type": "boolean", "initial_value": False}]},
    )
    if not any(finding.kind == "state_reference" and "state.missing" in finding.message for finding in findings):
        raise SystemExit("Branch graph validation did not catch id-form edge state reference.")


def main() -> None:
    assert_id_form_state_refs_are_validated()
    with tempfile.TemporaryDirectory(prefix="narrative-v1-regression-") as temp:
        run_root = Path(temp) / "v1_smoke"
        run([sys.executable, "scripts/run_pipeline.py", "init", "--design-layer", "v1", "--prompt", "V1 public edge semantics smoke test.", "--run-root", str(run_root)])
        write_v1_artifacts(run_root)
        run([sys.executable, "scripts/validate_artifacts.py", "--run-root", str(run_root), "--write-projections"])
        run([sys.executable, "scripts/run_pipeline.py", "build", "--run-root", str(run_root), "--skip-assets"])
        assert_exported_edge_effects(run_root)
    print("V1 regression checks passed.")


if __name__ == "__main__":
    main()
