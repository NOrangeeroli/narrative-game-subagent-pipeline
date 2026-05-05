#!/usr/bin/env python3
"""Regression checks for Design Layer V3."""

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
            f"Narrator: The archive light gathers around {node.get('title') or node_id}.",
        ]
        if exit_bindings:
            yarn_lines.append(f"<<complete_activity outcome=\"{exit_bindings[0]['outcome_id']}\">>")
        yarn_lines.append("===")
        (fragments_root / f"{node_id}.yarn").write_text("\n".join(yarn_lines) + "\n", encoding="utf-8")
        write_json(fragments_root / f"{node_id}.manifest.json", {
            "metadata": {"schema_version": "0.1.0", "generated_by": "V3RegressionFixture"},
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
        "metadata": {"schema_version": "0.1.0", "generated_by": "V3RegressionFixture"},
        "plans": plans,
    })


def assert_public_no_private_v3_paths(run_root: Path) -> None:
    for public_file in (run_root / "workspace" / "design_layer").glob("*.json"):
        text = public_file.read_text(encoding="utf-8")
        forbidden = [
            "workspace/design_layer_v3",
            "design_layer_v3/",
            "shard_returns",
            "source_refs",
            "coverage_row_ids",
        ]
        for needle in forbidden:
            if needle in text:
                raise SystemExit(f"Private V3 implementation detail leaked into {public_file}: {needle}")


def assert_settlement_compiled(run_root: Path) -> None:
    game_ir = read_json(run_root / "workspace" / "design_layer" / "game_ir.json")
    rules = game_ir.get("event_rules", [])
    if not any(isinstance(rule, dict) and rule.get("source_settlement_id") == "settlement.l1.ledger_open.to.l2.archive_arc" for rule in rules):
        raise SystemExit("V3 parent_state_settlements did not compile into game_ir.event_rules.")


def write_source_anchor_expansion_fixture(run_root: Path) -> None:
    graph_path = run_root / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "story_graph.json"
    graph = read_json(graph_path)
    graph["nodes"].append({
        "id": "v3.l1.ch01.key_not_found",
        "title": "Index Desk Without the Key",
        "summary": "A state-conditioned variant of the same source desk scene where Ara fails to find the key and must settle a different local result.",
        "node_type": "scene",
        "story_unit_ids": ["story.l1.ch01"],
        "parent_node_id": "v3.l2.archive_arc",
        "is_terminal": False,
        "source_derivation": {
            "kind": "failure",
            "base_story_unit_ids": ["story.l1.ch01"],
            "canon_function": "Test source-anchored expansion of one story unit into multiple graph nodes.",
            "required_prior_state": [],
            "divergence_from_source": "The key is not found in this variant.",
            "invented_content_scope": "local consequence only"
        },
    })
    write_json(graph_path, graph)

    contracts_path = run_root / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "contracts.json"
    contracts = read_json(contracts_path)
    contracts["contracts"].append({
        "id": "contract.l1.ch01.key_not_found",
        "graph_node_id": "v3.l1.ch01.key_not_found",
        "story_unit_ids": ["story.l1.ch01"],
        "allowed_characters": ["char.ara"],
        "allowed_locations": ["loc.archive"],
        "allowed_state_reads": ["state.l1.key_found"],
        "allowed_state_writes": ["state.l1.key_found"],
        "required_functions": ["Preserve the index desk source anchor as a state-conditioned failure variant."],
        "forbidden_events": []
    })
    write_json(contracts_path, contracts)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="narrative-v3-regression-") as temp:
        temp_root = Path(temp)
        minimal = copy_fixture("v3_hierarchical_minimal", temp_root)
        run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(minimal)])
        run([sys.executable, "scripts/run_pipeline.py", "compile-design", "--run-root", str(minimal), "--design-layer", "v3"])
        run([sys.executable, "scripts/validate_artifacts.py", "--run-root", str(minimal), "--write-projections"])
        assert_public_no_private_v3_paths(minimal)
        assert_settlement_compiled(minimal)

        write_realization_artifacts(minimal)
        run([sys.executable, "scripts/run_pipeline.py", "build", "--run-root", str(minimal), "--skip-assets"])

        expansion = temp_root / "v3_source_anchor_expansion"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", expansion)
        write_source_anchor_expansion_fixture(expansion)
        run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(expansion)])

        violation = copy_fixture("v3_contract_violation", temp_root)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(violation)], expect_success=False)
        if "parent_state_settlement" not in failure.stdout:
            raise SystemExit("Expected parent_state_settlement failure in V3 violation fixture.")

    print("V3 regression checks passed.")


if __name__ == "__main__":
    main()
