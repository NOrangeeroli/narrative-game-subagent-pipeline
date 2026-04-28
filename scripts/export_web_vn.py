#!/usr/bin/env python3
"""Export a self-contained browser VN from accepted artifacts."""

from __future__ import annotations

import argparse
import re
import shutil
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


def runtime_asset_name(asset_id: str, suffix: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", asset_id).strip("_") or "asset"
    return f"{safe_id}{suffix}"


def collect_runtime_assets(run_root: Path, output_root: Path, asset_directions: list[Any]) -> dict[str, str]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    source_root = run_root / "workspace" / "assets" / "web-vn"
    destination_root = output_root / "assets"
    destination_root.mkdir(parents=True, exist_ok=True)
    runtime_paths: dict[str, str] = {}

    def copy_manifest_asset(asset_id: str, file_ref: str) -> None:
        source = generated_root / file_ref
        if not source.exists():
            return
        destination = destination_root / file_ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{file_ref}"

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str) and isinstance(background.get("file_ref"), str):
            copy_manifest_asset(background["asset_id"], background["file_ref"])
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str) and isinstance(cg.get("file_ref"), str):
            copy_manifest_asset(cg["asset_id"], cg["file_ref"])
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str) and isinstance(ui_asset.get("file_ref"), str):
            copy_manifest_asset(ui_asset["asset_id"], ui_asset["file_ref"])
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict) and isinstance(portrait.get("asset_id"), str) and isinstance(portrait.get("file_ref"), str):
                copy_manifest_asset(portrait["asset_id"], portrait["file_ref"])

    if not source_root.exists():
        return runtime_paths

    for asset in asset_directions:
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str):
            continue
        asset_id = asset["asset_id"]
        if asset_id in runtime_paths:
            continue
        source = None
        for suffix in (".png", ".svg", ".jpg", ".jpeg", ".webp"):
            candidate = source_root / runtime_asset_name(asset_id, suffix)
            if candidate.exists():
                source = candidate
                break
        if source is None:
            continue
        destination = destination_root / source.name
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{destination.name}"
    return runtime_paths


def build_story_payload(run_root: Path, runtime_assets: dict[str, str] | None = None) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    shared_state = load_optional_json(path_for(run_root, "shared_state")) or {"variables": []}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    asset_directions = as_list(asset_direction.get("asset_directions"))
    runtime_assets = runtime_assets or {}
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
                "state_writes": binding.get("state_writes") or (plan.get("state_writes", []) if isinstance(plan, dict) else []),
                "conditions": edge.get("conditions", []),
            })
        required_assets = as_list(plan.get("required_assets") if isinstance(plan, dict) else [])
        background_id = next((asset for asset in required_assets if isinstance(asset, str) and asset.startswith("bg.")), None)
        portrait_ids = [asset for asset in required_assets if isinstance(asset, str) and asset.startswith("portrait.")]
        story_nodes.append({
            "id": node_id,
            "title": node.get("title") or node_id,
            "background_id": background_id or node.get("asset_id") or "bg.default",
            "portrait_ids": portrait_ids,
            "beats": beats,
            "choices": choices,
            "is_terminal": bool(node.get("is_terminal") or node.get("node_type") == "terminal" or not choices),
        })

    assets = []
    for asset in asset_directions:
        if not isinstance(asset, dict):
            continue
        enriched = dict(asset)
        asset_id = enriched.get("asset_id")
        if isinstance(asset_id, str) and asset_id in runtime_assets:
            enriched["runtime_path"] = runtime_assets[asset_id]
        assets.append(enriched)

    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_vn.py"},
        "title": branch_graph.get("title") or "Generated Narrative Game",
        "start_node_id": branch_graph.get("start_node_id") or (story_nodes[0]["id"] if story_nodes else ""),
        "initial_state": initial_state,
        "nodes": story_nodes,
        "assets": assets,
    }


def export_web_vn(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-vn"
    copy_tree(skill_root() / "assets" / "web-vn-template", output_root)
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    runtime_assets = collect_runtime_assets(run_root, output_root, as_list(asset_direction.get("asset_directions")))
    story = build_story_payload(run_root, runtime_assets)
    write_text(output_root / "story-data.js", "window.NARRATIVE_GAME_STORY = " + __import__("json").dumps(story, ensure_ascii=False, indent=2) + ";\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_vn(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
