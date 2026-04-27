#!/usr/bin/env python3
"""Export a self-contained browser VN from accepted artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Json,
    as_list,
    copy_tree,
    dialogue_beats_from_yarn,
    load_optional_json,
    load_yarn_fragments,
    path_for,
    skill_root,
    write_text,
)


def node_text(node: Json) -> str:
    return str(node.get("body") or node.get("summary") or node.get("title") or "The scene continues.")


def build_story_payload(run_root: Path) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    shared_state = load_optional_json(path_for(run_root, "shared_state")) or {"variables": []}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    fragments = load_yarn_fragments(run_root)

    fragments_by_node = {fragment["node_id"]: fragment for fragment in fragments}
    plan_by_node = {
        plan.get("source_node_id"): plan
        for plan in as_list(plans.get("plans"))
        if isinstance(plan, dict)
    }
    edges_by_from: dict[str, list[Json]] = {}
    edge_by_id: dict[str, Json] = {}
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            edges_by_from.setdefault(edge["from"], []).append(edge)
            if isinstance(edge.get("id"), str):
                edge_by_id[edge["id"]] = edge

    initial_state = {
        variable.get("id"): variable.get("initial_value")
        for variable in as_list(shared_state.get("variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }

    story_nodes = []
    for node in as_list(branch_graph.get("nodes")):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        node_id = node["id"]
        plan = plan_by_node.get(node_id, {})
        fragment = fragments_by_node.get(node_id)
        beats = dialogue_beats_from_yarn(fragment["yarn_text"]) if fragment else [{"speaker": "Narrator", "text": node_text(node)}]
        exit_bindings = {
            binding.get("edge_id"): binding
            for binding in as_list(plan.get("exit_bindings") if isinstance(plan, dict) else [])
            if isinstance(binding, dict)
        }
        choices = []
        for edge in edges_by_from.get(node_id, []):
            edge_id = edge.get("id")
            binding = exit_bindings.get(edge_id, {})
            choices.append({
                "label": edge.get("label") or edge.get("condition_label") or edge.get("outcome_label") or "Continue",
                "target": edge.get("to"),
                "edge_id": edge_id,
                "outcome_id": binding.get("outcome_id") or edge_id,
                "state_writes": plan.get("state_writes", []) if isinstance(plan, dict) else [],
                "conditions": edge.get("conditions", []),
            })
        required_assets = as_list(plan.get("required_assets") if isinstance(plan, dict) else [])
        background_id = next((asset for asset in required_assets if isinstance(asset, str) and asset.startswith("bg.")), None)
        story_nodes.append({
            "id": node_id,
            "title": node.get("title") or node_id,
            "background_id": background_id or node.get("asset_id") or "bg.default",
            "beats": beats,
            "choices": choices,
            "is_terminal": bool(node.get("is_terminal") or node.get("node_type") == "terminal" or not choices),
        })

    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_vn.py"},
        "title": branch_graph.get("title") or "Generated Narrative Game",
        "start_node_id": branch_graph.get("start_node_id") or (story_nodes[0]["id"] if story_nodes else ""),
        "initial_state": initial_state,
        "nodes": story_nodes,
        "assets": as_list(asset_direction.get("asset_directions")),
    }


def export_web_vn(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-vn"
    copy_tree(skill_root() / "assets" / "web-vn-template", output_root)
    story = build_story_payload(run_root)
    write_text(output_root / "story-data.js", "window.NARRATIVE_GAME_STORY = " + __import__("json").dumps(story, ensure_ascii=False, indent=2) + ";\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_vn(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()

