#!/usr/bin/env python3
"""Regression checks for Design Layer V3."""

from __future__ import annotations

import json
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


def assert_public_ending_metadata_and_closure(run_root: Path) -> None:
    branch_graph = read_json(run_root / "workspace" / "design_layer" / "branch_graph.json")
    nodes = {
        node["id"]: node
        for node in branch_graph.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    edges = [
        edge for edge in branch_graph.get("edges", [])
        if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str)
    ]
    terminal = nodes.get("v3.l1.ch02.resolve")
    if not isinstance(terminal, dict):
        raise SystemExit("Compiled V3 public branch_graph is missing terminal v3.l1.ch02.resolve.")
    if terminal.get("ending_id") != "ending.archive_remembered":
        raise SystemExit("Compiled V3 public terminal did not preserve ending_id.")
    if terminal.get("ending_variant_id") != "ending.archive_remembered.key_found":
        raise SystemExit("Compiled V3 public terminal did not preserve ending_variant_id.")
    if "v3.l2.ending.archive_remembered" not in terminal.get("ending_lineage", []):
        raise SystemExit("Compiled V3 public terminal did not preserve ending lineage.")

    adjacency: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge["from"], []).append(edge["to"])
        reverse.setdefault(edge["to"], []).append(edge["from"])
    terminals = {
        node_id
        for node_id, node in nodes.items()
        if node.get("is_terminal") is True or node.get("node_type") == "terminal"
    }
    can_reach_terminal = set(terminals)
    stack = list(terminals)
    while stack:
        node_id = stack.pop()
        for predecessor in reverse.get(node_id, []):
            if predecessor not in can_reach_terminal:
                can_reach_terminal.add(predecessor)
                stack.append(predecessor)
    reachable = set()
    stack = [branch_graph.get("start_node_id")]
    while stack:
        node_id = stack.pop()
        if not isinstance(node_id, str) or node_id in reachable:
            continue
        reachable.add(node_id)
        stack.extend(adjacency.get(node_id, []))
    missing = sorted(node_id for node_id in reachable if node_id not in can_reach_terminal)
    if missing:
        raise SystemExit(f"Compiled V3 public reachable nodes cannot reach terminal endings: {missing}")


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
        assert_public_ending_metadata_and_closure(minimal)

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

        missing_coarsest_ending = temp_root / "v3_missing_coarsest_ending"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", missing_coarsest_ending)
        graph_path = missing_coarsest_ending / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        graph["nodes"] = [node for node in graph["nodes"] if node.get("id") != "v3.l2.ending.archive_remembered"]
        graph["edges"] = []
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(missing_coarsest_ending)], expect_success=False)
        if "missing_coarsest_ending" not in failure.stdout:
            raise SystemExit("Expected missing_coarsest_ending failure when top-level ending nodes are absent.")

        missing_ending_id = temp_root / "v3_coarsest_terminal_missing_ending_id"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", missing_ending_id)
        graph_path = missing_ending_id / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l2.ending.archive_remembered":
                node.pop("ending_id", None)
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(missing_ending_id)], expect_success=False)
        if "missing_ending_id" not in failure.stdout:
            raise SystemExit("Expected missing_ending_id failure when a top-level terminal lacks ending_id.")

        ending_transition_mismatch = temp_root / "v3_ending_transition_mismatch"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", ending_transition_mismatch)
        graph_path = ending_transition_mismatch / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l2.ending.archive_remembered":
                node["ending_id"] = "ending.other"
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(ending_transition_mismatch)], expect_success=False)
        if "ending_transition_mismatch" not in failure.stdout:
            raise SystemExit("Expected ending_transition_mismatch when state.game.ending_id disagrees with the target ending node.")

        ambiguous_ending_target = temp_root / "v3_ambiguous_coarsest_ending_node"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", ambiguous_ending_target)
        graph_path = ambiguous_ending_target / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        alternate_edge = dict(graph["edges"][0])
        alternate_edge["id"] = "edge.v3.l2.archive_to_alternate_ending"
        alternate_edge["effects"] = [{
            "state_variable_id": "state.game.ending_id",
            "operation": "set",
            "value": "ending.alternate",
        }]
        graph["edges"].append(alternate_edge)
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(ambiguous_ending_target)], expect_success=False)
        if "ambiguous_coarsest_ending_node" not in failure.stdout:
            raise SystemExit("Expected ambiguous_coarsest_ending_node when multiple ending ids target one top-level ending node.")

        duplicate_ending = temp_root / "v3_duplicate_ending_id"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", duplicate_ending)
        graph_path = duplicate_ending / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        duplicate_node = dict(next(node for node in graph["nodes"] if node.get("id") == "v3.l2.ending.archive_remembered"))
        duplicate_node["id"] = "v3.l2.ending.archive_remembered_duplicate"
        graph["nodes"].append(duplicate_node)
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(duplicate_ending)], expect_success=False)
        if "duplicate_ending_id" not in failure.stdout:
            raise SystemExit("Expected duplicate_ending_id failure for repeated coarsest ending ids.")

        lower_invents_ending = temp_root / "v3_lower_invents_ending"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", lower_invents_ending)
        graph_path = lower_invents_ending / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l1.ch02.resolve":
                node["ending_id"] = "ending.invented_by_lower_level"
                node["variant_of_ending_id"] = "ending.invented_by_lower_level"
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(lower_invents_ending)], expect_success=False)
        if "unknown_ending_id" not in failure.stdout:
            raise SystemExit("Expected unknown_ending_id failure when a lower level invents an ending family.")

        lineage_mismatch = temp_root / "v3_ending_lineage_mismatch"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", lineage_mismatch)
        graph_path = lineage_mismatch / "workspace" / "design_layer_v3" / "design_levels" / "level_02" / "story_graph.json"
        graph = read_json(graph_path)
        other_node = dict(next(node for node in graph["nodes"] if node.get("id") == "v3.l2.ending.archive_remembered"))
        other_node["id"] = "v3.l2.ending.other"
        other_node["ending_id"] = "ending.other"
        graph["nodes"].append(other_node)
        write_json(graph_path, graph)
        graph_path = lineage_mismatch / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l1.ch02.resolve":
                node["ending_id"] = "ending.other"
                node["variant_of_ending_id"] = "ending.other"
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(lineage_mismatch)], expect_success=False)
        if "ending_lineage_mismatch" not in failure.stdout:
            raise SystemExit("Expected ending_lineage_mismatch failure when variant parent chain reaches a different ending.")

        ending_without_finest = temp_root / "v3_ending_without_finest_terminal"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", ending_without_finest)
        graph_path = ending_without_finest / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l1.ch02.resolve":
                node["parent_node_id"] = "v3.l2.archive_arc"
                node.pop("ending_id", None)
                node.pop("ending_variant_id", None)
                node.pop("variant_of_ending_id", None)
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(ending_without_finest)], expect_success=False)
        if "ending_without_finest_terminal" not in failure.stdout:
            raise SystemExit("Expected ending_without_finest_terminal failure when top-level ending has no finest terminal descendant.")
        if "terminal_without_ending_lineage" not in failure.stdout:
            raise SystemExit("Expected terminal_without_ending_lineage failure when a finest terminal is not under an ending.")

        public_path_without_terminal = temp_root / "v3_public_path_without_terminal"
        shutil.copytree(FIXTURES / "v3_hierarchical_minimal", public_path_without_terminal)
        graph_path = public_path_without_terminal / "workspace" / "design_layer_v3" / "design_levels" / "level_01" / "story_graph.json"
        graph = read_json(graph_path)
        for node in graph["nodes"]:
            if node.get("id") == "v3.l1.ch02.resolve":
                node["node_type"] = "scene"
                node["is_terminal"] = False
        write_json(graph_path, graph)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(public_path_without_terminal)], expect_success=False)
        if "path_without_terminal" not in failure.stdout and "nonterminal_sink" not in failure.stdout:
            raise SystemExit("Expected path closure failure when the finest public path has no terminal.")

        violation = copy_fixture("v3_contract_violation", temp_root)
        failure = run([sys.executable, "scripts/design_v3_validate.py", "--run-root", str(violation)], expect_success=False)
        if "parent_state_settlement" not in failure.stdout:
            raise SystemExit("Expected parent_state_settlement failure in V3 violation fixture.")

    print("V3 regression checks passed.")


if __name__ == "__main__":
    main()
