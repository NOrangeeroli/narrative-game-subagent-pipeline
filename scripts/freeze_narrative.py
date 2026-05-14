#!/usr/bin/env python3
"""Freeze public narrative artifacts for narrative-first RPG overlay work."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, ensure_run_layout, load_optional_json, path_for, write_json


def canonical_json_hash(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def state_refs_from_ops(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key in ("state_variable_id", "state"):
            item = value.get(key)
            if isinstance(item, str) and item:
                refs.add(item)
        for item in value.values():
            refs.update(state_refs_from_ops(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(state_refs_from_ops(item))
    return refs


def node_story_unit_ids(node: Json) -> set[str]:
    refs = {item for item in as_list(node.get("story_unit_ids")) if isinstance(item, str)}
    derivation = node.get("source_derivation") if isinstance(node.get("source_derivation"), dict) else {}
    refs.update(item for item in as_list(derivation.get("base_story_unit_ids")) if isinstance(item, str))
    return refs


def build_freeze_payload(branch_graph: Json, game_ir: Json) -> Json:
    nodes = [node for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict)]
    edges = [edge for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)]
    state_ids = {
        variable.get("id")
        for variable in as_list(game_ir.get("global_state_variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }
    for rule in as_list(game_ir.get("event_rules")):
        if isinstance(rule, dict):
            state_ids.update(state_refs_from_ops(rule.get("conditions")))
            state_ids.update(state_refs_from_ops(rule.get("effects")))

    story_unit_index: dict[str, list[str]] = {}
    ending_ids: set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        ending_id = node.get("ending_id")
        if isinstance(ending_id, str) and ending_id:
            ending_ids.add(ending_id)
        for story_id in node_story_unit_ids(node):
            story_unit_index.setdefault(story_id, []).append(node_id)

    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "freeze_narrative.py"},
        "mode": "narrative_first_overlay",
        "branch_graph_hash": canonical_json_hash(branch_graph),
        "game_ir_hash": canonical_json_hash(game_ir),
        "public_node_ids": sorted(node.get("id") for node in nodes if isinstance(node.get("id"), str)),
        "public_edge_ids": sorted(edge.get("id") for edge in edges if isinstance(edge.get("id"), str)),
        "public_state_ids": sorted(state_ids),
        "ending_ids": sorted(ending_ids),
        "story_unit_to_public_node_ids": {key: sorted(set(value)) for key, value in sorted(story_unit_index.items())},
    }


def freeze_narrative(run_root: Path) -> Json:
    ensure_run_layout(run_root)
    branch_graph = load_optional_json(path_for(run_root, "branch_graph"))
    game_ir = load_optional_json(path_for(run_root, "game_ir"))
    if not isinstance(branch_graph, dict):
        raise SystemExit("Missing workspace/design_layer/branch_graph.json.")
    if not isinstance(game_ir, dict):
        raise SystemExit("Missing workspace/design_layer/game_ir.json.")
    payload = build_freeze_payload(branch_graph, game_ir)
    write_json(path_for(run_root, "rpg_narrative_freeze"), payload)
    return payload


def verify_narrative_freeze(run_root: Path) -> Json:
    freeze = load_optional_json(path_for(run_root, "rpg_narrative_freeze"))
    if not isinstance(freeze, dict):
        return {"status": "missing", "findings": []}
    branch_graph = load_optional_json(path_for(run_root, "branch_graph"))
    game_ir = load_optional_json(path_for(run_root, "game_ir"))
    findings: list[Json] = []
    if not isinstance(branch_graph, dict):
        findings.append({"severity": "error", "kind": "missing_artifact", "message": "Missing branch_graph.json.", "path": "workspace/design_layer/branch_graph.json"})
    elif freeze.get("branch_graph_hash") != canonical_json_hash(branch_graph):
        findings.append({"severity": "error", "kind": "narrative_freeze_mismatch", "message": "branch_graph.json changed after narrative freeze.", "path": "workspace/design_layer/branch_graph.json"})
    if not isinstance(game_ir, dict):
        findings.append({"severity": "error", "kind": "missing_artifact", "message": "Missing game_ir.json.", "path": "workspace/design_layer/game_ir.json"})
    elif freeze.get("game_ir_hash") != canonical_json_hash(game_ir):
        findings.append({"severity": "error", "kind": "narrative_freeze_mismatch", "message": "game_ir.json changed after narrative freeze.", "path": "workspace/design_layer/game_ir.json"})
    return {"status": "fail" if findings else "pass", "findings": findings}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    payload = verify_narrative_freeze(run_root) if args.verify else freeze_narrative(run_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get("status") == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
