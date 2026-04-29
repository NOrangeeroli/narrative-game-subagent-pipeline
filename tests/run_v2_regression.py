#!/usr/bin/env python3
"""Regression checks for Design Layer V2."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


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


def copy_fixture(name: str, destination: Path) -> Path:
    target = destination / name
    shutil.copytree(FIXTURES / name, target)
    return target


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_suffix(identifier: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier).strip("_") or "item"


def yarn_title(node_id: str) -> str:
    return "Node_" + safe_suffix(node_id)


def outcome_id(edge_id: str) -> str:
    return "outcome_" + safe_suffix(edge_id)


def write_realization_artifacts(run_root: Path) -> None:
    branch_graph = read_json(run_root / "workspace" / "design_layer" / "branch_graph.json")
    edges_by_from: dict[str, list[dict[str, Any]]] = {}
    for edge in branch_graph.get("edges", []):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            edges_by_from.setdefault(edge["from"], []).append(edge)
    plans: list[dict[str, Any]] = []
    fragments_root = run_root / "workspace" / "vn" / "fragments"
    fragments_root.mkdir(parents=True, exist_ok=True)
    for node in branch_graph.get("nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        node_id = node["id"]
        outgoing = edges_by_from.get(node_id, [])
        exit_bindings = [
            {"outcome_id": outcome_id(str(edge.get("id"))), "edge_id": edge.get("id")}
            for edge in outgoing
            if isinstance(edge.get("id"), str)
        ]
        title = yarn_title(node_id)
        plans.append({
            "source_node_id": node_id,
            "realization_kind": "vn_yarn",
            "unit_id": f"realization.{safe_suffix(node_id)}",
            "entry_binding": {"type": "yarn_node", "node_title": title},
            "exit_bindings": exit_bindings,
            "required_state_reads": [],
            "state_writes": [],
            "required_assets": [],
            "continuity_summary": node.get("summary", ""),
            "implementation_notes": [],
            "source_trace": {"node_ids": [node_id], "edge_ids": [binding["edge_id"] for binding in exit_bindings]},
        })
        yarn_lines = [
            f"title: {title}",
            "---",
            f"// source_node: {node_id}",
            f"Narrator: {node.get('summary') or node.get('title') or 'The scene continues.'}",
        ]
        if exit_bindings:
            yarn_lines.append(f"<<complete_activity outcome=\"{exit_bindings[0]['outcome_id']}\">>")
        yarn_lines.append("===")
        (fragments_root / f"{node_id}.yarn").write_text("\n".join(yarn_lines) + "\n", encoding="utf-8")
        write_json(fragments_root / f"{node_id}.manifest.json", {
            "metadata": {"schema_version": "0.1.0", "generated_by": "V2RegressionFixture"},
            "source_node_id": node_id,
            "realization_unit_id": f"realization.{safe_suffix(node_id)}",
            "yarn_node_title": title,
            "local_asset_refs": [],
            "command_refs": [{"command": "complete_activity", "args": {"outcome": exit_bindings[0]["outcome_id"]}}] if exit_bindings else [],
            "exit_bindings": exit_bindings,
            "state_reads": [],
            "state_writes": [],
            "continuity_summary": node.get("summary", ""),
            "source_trace": {"node_ids": [node_id], "edge_ids": [binding["edge_id"] for binding in exit_bindings]},
        })
    write_json(run_root / "workspace" / "realization" / "node-realization-plans.json", {
        "metadata": {"schema_version": "0.1.0", "generated_by": "V2RegressionFixture"},
        "plans": plans,
    })


def add_ending_menu_overload(run_root: Path) -> None:
    v2_root = run_root / "workspace" / "design_layer_v2"
    macro_path = v2_root / "macro" / "macro_story_graph.json"
    contract_path = v2_root / "macro" / "macro_node_contracts.json"
    ending_path = v2_root / "adaptation" / "ending_space.json"

    macro_graph = read_json(macro_path)
    contract_payload = read_json(contract_path)
    ending_space = read_json(ending_path)

    intro = next(node for node in macro_graph["nodes"] if node["id"] == "macro.intro")
    extra_exits = [f"exit.menu_{index}" for index in range(5)]
    intro["kind"] = "choice"
    intro["title"] = "Final Ending Menu"
    intro["summary"] = "A broad final menu that wrongly exposes all endings."
    intro["allowed_exits"] = [*intro.get("allowed_exits", []), *extra_exits]

    intro_contract = next(contract for contract in contract_payload["contracts"] if contract["macro_node_id"] == "macro.intro")
    for index, exit_id in enumerate(extra_exits):
        ending_id = f"ending.menu_{index}"
        macro_id = f"macro.menu_{index}"
        macro_graph["nodes"].append({
            "id": macro_id,
            "title": f"Menu Ending {index}",
            "summary": "An overloaded menu ending.",
            "allowed_exits": [],
            "is_terminal": True,
            "ending_id": ending_id,
        })
        macro_graph["edges"].append({
            "id": f"edge.macro.intro.menu_{index}",
            "from": "macro.intro",
            "to": macro_id,
            "exit_id": exit_id,
            "label": f"Choose ending {index}",
            "condition_type": "player_choice",
        })
        intro_contract["exits"].append({"id": exit_id, "summary": f"Choose ending {index}.", "effects": []})
        contract_payload["contracts"].append({
            "id": f"contract.menu_{index}",
            "macro_node_id": macro_id,
            "allowed_characters": ["char.ara"],
            "allowed_locations": ["fact.archive"],
            "allowed_state_reads": ["state.key_found"],
            "allowed_state_writes": [],
            "source_fact_ids": ["fact.oath"],
            "exits": [],
        })
        ending_space["endings"].append({
            "id": ending_id,
            "title": f"Menu Ending {index}",
            "status": "available",
            "theme_ids": ["theme.trust"],
            "state_requirements": ["state.key_found == true"],
        })

    write_json(macro_path, macro_graph)
    write_json(contract_path, contract_payload)
    write_json(ending_path, ending_space)


def assert_no_raw_v2_path(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "workspace/design_layer_v2" in text or "design_layer_v2/" in text:
        raise SystemExit(f"Raw V2 path leaked into {path}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="narrative-v2-regression-") as temp:
        temp_root = Path(temp)
        minimal = copy_fixture("v2_minimal_mesh", temp_root)
        run([sys.executable, "scripts/design_v2_validate.py", "--run-root", str(minimal)])
        simulation_profiles = minimal / "workspace" / "design_layer_v2" / "validation" / "simulation_profiles.json"
        if not simulation_profiles.exists():
            raise SystemExit("V2 validation did not write simulation_profiles.json")
        run([sys.executable, "scripts/design_v2_compile.py", "--run-root", str(minimal)])
        run([sys.executable, "scripts/validate_artifacts.py", "--run-root", str(minimal), "--write-projections"])
        for public_file in (minimal / "workspace" / "design_layer").glob("*.json"):
            assert_no_raw_v2_path(public_file)

        write_realization_artifacts(minimal)
        run([sys.executable, "scripts/design_v2_project_context.py", "--run-root", str(minimal), "--node-id", "node.secret.resolve"])
        run([sys.executable, "scripts/design_v2_project_context.py", "--run-root", str(minimal), "--plan-id", "realization.node.secret.resolve"])
        assert_no_raw_v2_path(minimal / "workspace" / "agent_context" / "node.secret.resolve.json")
        run([sys.executable, "scripts/run_pipeline.py", "build", "--run-root", str(minimal), "--skip-assets"])

        exit_mismatch = copy_fixture("v2_minimal_mesh", temp_root / "exit_mismatch_parent")
        subgraph_path = exit_mismatch / "workspace" / "design_layer_v2" / "subgraphs" / "subgraph.macro.intro.json"
        subgraph = read_json(subgraph_path)
        subgraph["exit_mappings"][0]["macro_exit_id"] = "exit.missing"
        write_json(subgraph_path, subgraph)
        mismatch = run([sys.executable, "scripts/design_v2_validate.py", "--run-root", str(exit_mismatch)], expect_success=False)
        if "contract_exit_mismatch" not in mismatch.stdout:
            raise SystemExit("Expected contract_exit_mismatch in mutated fixture output.")

        parent_violation = copy_fixture("v2_contract_violation", temp_root / "parent_violation_parent")
        parent_failure = run([sys.executable, "scripts/design_v2_validate.py", "--run-root", str(parent_violation)], expect_success=False)
        if "node.missing" not in parent_failure.stdout:
            raise SystemExit("Expected missing parent node failure in negative fixture output.")

        ending_menu = copy_fixture("v2_minimal_mesh", temp_root / "ending_menu_parent")
        add_ending_menu_overload(ending_menu)
        ending_menu_failure = run([sys.executable, "scripts/design_v2_validate.py", "--run-root", str(ending_menu)], expect_success=False)
        if "ending_menu_overload" not in ending_menu_failure.stdout:
            raise SystemExit("Expected ending_menu_overload in mutated fixture output.")

    print("V2 regression checks passed.")


if __name__ == "__main__":
    main()
