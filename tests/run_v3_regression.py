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


def assert_public_edge_effects(run_root: Path) -> None:
    branch_graph = read_json(run_root / "workspace" / "design_layer" / "branch_graph.json")
    edge = next((edge for edge in branch_graph.get("edges", []) if edge.get("id") == "edge.v3.l1.search_to_open"), None)
    if not isinstance(edge, dict):
        raise SystemExit("Compiled V3 public branch_graph is missing edge.v3.l1.search_to_open.")
    effects = edge.get("effects", [])
    if not any(effect.get("state_variable_id") == "state.l1.key_found" and effect.get("value") is True for effect in effects if isinstance(effect, dict)):
        raise SystemExit("Compiled V3 public branch_graph edge did not preserve finest-level edge effects.")


def assert_exported_choice_effects(run_root: Path) -> None:
    text = (run_root / "build" / "web-vn" / "story-data.js").read_text(encoding="utf-8")
    prefix = "window.NARRATIVE_GAME_STORY = "
    if not text.startswith(prefix):
        raise SystemExit("story-data.js does not contain expected global assignment.")
    story = json.loads(text[len(prefix):].strip().removesuffix(";"))
    start = next((node for node in story.get("nodes", []) if node.get("id") == "v3.l1.ch01.entry"), None)
    if not isinstance(start, dict):
        raise SystemExit("Exported V3 story is missing start node v3.l1.ch01.entry.")
    choice = next((choice for choice in start.get("choices", []) if choice.get("edge_id") == "edge.v3.l1.search_to_open"), None)
    if not isinstance(choice, dict):
        raise SystemExit("Exported V3 story is missing runtime choice edge.v3.l1.search_to_open.")
    if not any(effect.get("state_variable_id") == "state.l1.key_found" and effect.get("value") is True for effect in choice.get("effects", []) if isinstance(effect, dict)):
        raise SystemExit("Exported V3 runtime choice did not read effects from public branch_graph.")


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
        assert_public_edge_effects(minimal)

        write_realization_artifacts(minimal)
        shutil.move(minimal / "workspace" / "design_layer_v3" / "design_levels", minimal / "workspace" / "design_layer_v3" / "design_levels.hidden")
        run([sys.executable, "scripts/run_pipeline.py", "build", "--run-root", str(minimal), "--skip-assets"])
        assert_exported_choice_effects(minimal)

        expansion = temp_root / "v3_source_anchor_expansion"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", expansion)
        write_source_anchor_expansion_fixture(expansion)
        run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(expansion)])

        coverage = temp_root / "v3_source_coverage_gap"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", coverage)
        write_json(coverage / "inputs" / "source_material" / "source_index.json", {
            "metadata": {"schema_version": "0.1.0", "generated_by": "V3RegressionFixture"},
            "chunks": [
                {"id": "source.chunk_a", "path": "inputs/source_material/chunks/chunk_a.txt"},
                {"id": "source.chunk_b", "path": "inputs/source_material/chunks/chunk_b.txt"},
            ],
        })
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(coverage)], expect_success=False)
        if "source_coverage_gap" not in failure.stdout:
            raise SystemExit("Expected source_coverage_gap failure for missing V3 level_01 source refs.")
        story_path = coverage / "workspace" / "design_layer_v3" / "story_levels" / "level_01" / "linear_story.json"
        story = read_json(story_path)
        story["units"][0]["source_refs"].append({"source_chunk_id": "source.chunk_a", "path": "inputs/source_material/chunks/chunk_a.txt"})
        story["units"][1]["source_refs"].append({"source_chunk_id": "source.chunk_b", "path": "inputs/source_material/chunks/chunk_b.txt"})
        write_json(story_path, story)
        run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(coverage)])

        coarsest_story_shards = temp_root / "v3_coarsest_story_shards"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", coarsest_story_shards)
        story_returns = coarsest_story_shards / "workspace" / "design_layer_v3" / "story_levels" / "level_02" / "shard_returns"
        write_json(story_returns / "arc_a.json", {"linear_story": {"level": 2, "level_id": "level_02", "units": []}})
        write_json(story_returns / "arc_b.json", {"linear_story": {"level": 2, "level_id": "level_02", "units": []}})
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(coarsest_story_shards)], expect_success=False)
        if "coarsest_story_sharded" not in failure.stdout:
            raise SystemExit("Expected coarsest_story_sharded failure for multiple top-level StoryLevelExtractor returns.")

        coarsest_design_shards = temp_root / "v3_coarsest_design_shards"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", coarsest_design_shards)
        design_returns = coarsest_design_shards / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "shard_returns"
        write_json(design_returns / "arc_a.json", {"story_graph": {"nodes": [], "edges": []}})
        write_json(design_returns / "arc_b.json", {"story_graph": {"nodes": [], "edges": []}})
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(coarsest_design_shards)], expect_success=False)
        if "coarsest_design_sharded" not in failure.stdout:
            raise SystemExit("Expected coarsest_design_sharded failure for multiple top-level LevelStateGraphDesigner returns.")

        parent_child_gap = temp_root / "v3_parent_child_gap"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", parent_child_gap)
        top_story_path = parent_child_gap / "workspace" / "design_layer_v3" / "story_levels" / "level_02" / "linear_story.json"
        top_story = read_json(top_story_path)
        top_story["units"][0]["child_unit_ids"] = top_story["units"][0]["child_unit_ids"][:1]
        write_json(top_story_path, top_story)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(parent_child_gap)], expect_success=False)
        if "story_parent_child_gap" not in failure.stdout:
            raise SystemExit("Expected story_parent_child_gap failure when global story line omits lower-level units.")

        packet_scope = temp_root / "v3_packet_scope_leak"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", packet_scope)
        write_json(packet_scope / "workspace" / "controller-packets" / "design_layer_v3" / "bad_l1_design_packet.json", {
            "metadata": {"schema_version": "0.1.0", "generated_by": "V3RegressionFixture", "packet_kind": "LevelStateGraphDesigner"},
            "level": 1,
            "scope": {
                "role": "LevelStateGraphDesigner",
                "level": 1,
                "level_id": "level_01",
                "shard_id": "bad_l1",
                "global": False,
                "assigned_story_unit_ids": ["story.l1.ch01"],
                "parent_graph_node_ids": ["v3.l2.archive_arc"],
                "allowed_input_paths": ["workspace/design_layer_v3/story_levels/level_01/linear_story.json"],
                "forbidden_input_patterns": []
            },
            "input_paths": {
                "same_level_linear_story": "workspace/design_layer_v3/story_levels/level_01/linear_story.json"
            }
        })
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(packet_scope)], expect_success=False)
        if "packet_scope_leak" not in failure.stdout:
            raise SystemExit("Expected packet_scope_leak failure when a non-coarsest design packet reads full level artifacts.")

        violation = copy_fixture("v3_contract_violation", temp_root)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(violation)], expect_success=False)
        if "parent_state_settlement" not in failure.stdout:
            raise SystemExit("Expected parent_state_settlement failure in V3 violation fixture.")

    print("V3 regression checks passed.")


if __name__ == "__main__":
    main()
