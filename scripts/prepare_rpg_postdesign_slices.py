#!/usr/bin/env python3
"""Bind RPG overlay intents to frozen public narrative graph slices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from freeze_narrative import node_story_unit_ids, state_refs_from_ops, verify_narrative_freeze
from pipeline_lib import Json, as_list, ensure_dir, ensure_run_layout, load_optional_json, path_for, stable_id, write_json


INTENT_SECTIONS = (
    "map_intents",
    "questline_intents",
    "combat_intents",
    "equipment_intents",
    "progression_axes",
)

DEFAULT_ALLOWED_OUTPUTS = [
    "workspace/rpg/rpg-campaign.json",
    "workspace/rpg/world-map.json",
    "workspace/rpg/maps/*.map.json",
    "workspace/rpg/actors.json",
    "workspace/rpg/enemies.json",
    "workspace/rpg/items.json",
    "workspace/rpg/equipment.json",
    "workspace/rpg/skills.json",
    "workspace/rpg/quests.json",
    "workspace/rpg/npc-dialogue.json",
    "workspace/rpg/scene-scripts.json",
    "workspace/rpg/encounter-tables.json",
    "workspace/rpg/shops.json",
    "workspace/rpg/rest-points.json",
    "workspace/rpg/progression-rules.json",
]


def ids_from(value: Any) -> list[str]:
    return [item for item in as_list(value) if isinstance(item, str) and item.strip()]


def first_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def story_refs(payload: Json) -> set[str]:
    refs: set[str] = set()
    for key in ("source_story_unit_ids", "story_unit_ids", "required_story_unit_ids"):
        refs.update(ids_from(payload.get(key)))
    return refs


def slice_refs(payload: Json) -> set[str]:
    refs = set(ids_from(payload.get("story_slice_ids")) + ids_from(payload.get("slice_ids")))
    for key in ("story_slice_id", "slice_id"):
        value = first_string(payload.get(key))
        if value:
            refs.add(value)
    return refs


def explicit_ids(payload: Json, section: str) -> set[str]:
    singular_by_section = {
        "map_intents": "map_intent",
        "questline_intents": "questline_intent",
        "combat_intents": "combat_intent",
        "equipment_intents": "equipment_intent",
        "progression_axes": "progression_axis",
    }
    singular = singular_by_section.get(section, section.removesuffix("s"))
    candidates = [
        section,
        f"{singular}_ids",
        f"{singular}_id",
    ]
    refs: set[str] = set()
    for key in candidates:
        value = payload.get(key)
        if isinstance(value, str) and value:
            refs.add(value)
        else:
            refs.update(ids_from(value))
    return refs


def trace_state_ids(payload: Json) -> set[str]:
    refs: set[str] = set()
    for key in ("existing_state_ids", "state_ids", "existing_state_refs", "state_refs"):
        refs.update(ids_from(payload.get(key)))
    return refs


def public_indexes(branch_graph: Json) -> tuple[dict[str, Json], dict[str, Json], dict[str, set[str]]]:
    nodes = {
        node["id"]: node
        for node in as_list(branch_graph.get("nodes"))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    edges = {
        edge["id"]: edge
        for edge in as_list(branch_graph.get("edges"))
        if isinstance(edge, dict) and isinstance(edge.get("id"), str)
    }
    story_to_nodes: dict[str, set[str]] = {}
    for node_id, node in nodes.items():
        for story_id in node_story_unit_ids(node):
            story_to_nodes.setdefault(story_id, set()).add(node_id)
    return nodes, edges, story_to_nodes


def summarize_node(node: Json) -> Json:
    return {
        "id": node.get("id"),
        "title": node.get("title", ""),
        "summary": node.get("summary", ""),
        "node_type": node.get("node_type", "scene"),
        "is_terminal": bool(node.get("is_terminal", False)),
        "story_unit_ids": sorted(node_story_unit_ids(node)),
        "ending_id": node.get("ending_id"),
        "ending_variant_id": node.get("ending_variant_id"),
    }


def summarize_edge(edge: Json) -> Json:
    return {
        "id": edge.get("id"),
        "from": edge.get("from"),
        "to": edge.get("to"),
        "label": edge.get("label", ""),
        "condition_type": edge.get("condition_type", "unconditional"),
        "conditions": as_list(edge.get("conditions")),
        "effects": as_list(edge.get("effects")),
    }


def intent_matches_slice(intent: Json, story_slice: Json, section: str) -> bool:
    slice_id = story_slice.get("id")
    intent_id = intent.get("id")
    if isinstance(slice_id, str) and slice_id in slice_refs(intent):
        return True
    if isinstance(intent_id, str) and intent_id in explicit_ids(story_slice, section):
        return True
    slice_story_refs = story_refs(story_slice)
    return bool(slice_story_refs and slice_story_refs & story_refs(intent))


def select_intents(plan: Json, story_slice: Json, section: str) -> list[Json]:
    selected = []
    for intent in as_list(plan.get(section)):
        if isinstance(intent, dict) and intent_matches_slice(intent, story_slice, section):
            selected.append(intent)
    return selected


def scene_script_obligations(story_slice: Json, public_node_ids: set[str], public_edge_ids: set[str]) -> list[Json]:
    explicit = [item for item in as_list(story_slice.get("scene_script_obligations")) if isinstance(item, dict)]
    if explicit:
        return explicit

    stageable_beats = (
        as_list(story_slice.get("required_story_beats"))
        + as_list(story_slice.get("character_arc_beats"))
        + as_list(story_slice.get("emotional_turns"))
    )
    if not stageable_beats:
        return []

    return [{
        "id": stable_id(f"scene.{story_slice.get('id', 'slice')}", "scene"),
        "source": "derived_from_story_slice",
        "suggested_trigger": "on_entry",
        "required_beats": stageable_beats,
        "staging_guidance": [
            "Use scene-scripts.json when the beat benefits from authored actor blocking instead of optional NPC dialogue.",
            "Bind moving NPCs through actors[*].event_id to stable map events and use player for the party lead.",
            "Prefer dialogue, move_actor, face_actor, wait, show_actor, and hide_actor beats for visible character scheduling.",
        ],
        "public_node_ids": sorted(public_node_ids),
        "public_edge_ids": sorted(public_edge_ids),
    }]


def allowed_outputs_for_slice(story_slice: Json) -> list[str]:
    outputs = [item for item in as_list(story_slice.get("postdesign_allowed_outputs")) if isinstance(item, str) and item.strip()]
    if not outputs:
        outputs = list(DEFAULT_ALLOWED_OUTPUTS)

    scene_scripts_output = "workspace/rpg/scene-scripts.json"
    if scene_scripts_output not in outputs:
        outputs.append(scene_scripts_output)
    return outputs


def nodes_for_slice(story_slice: Json, nodes: dict[str, Json], story_to_nodes: dict[str, set[str]]) -> set[str]:
    node_ids: set[str] = set()
    for story_id in story_refs(story_slice):
        node_ids.update(story_to_nodes.get(story_id, set()))
    node_ids.update(node_id for node_id in ids_from(story_slice.get("public_node_ids")) if node_id in nodes)
    return node_ids


def edges_for_nodes(node_ids: set[str], edges: dict[str, Json]) -> set[str]:
    return {
        edge_id
        for edge_id, edge in edges.items()
        if edge.get("from") in node_ids or edge.get("to") in node_ids
    }


def prepare_rpg_postdesign_slices(run_root: Path) -> Json:
    ensure_run_layout(run_root)
    plan = load_optional_json(path_for(run_root, "rpg_overlay_plan"))
    branch_graph = load_optional_json(path_for(run_root, "branch_graph"))
    game_ir = load_optional_json(path_for(run_root, "game_ir"))
    if not isinstance(plan, dict):
        raise SystemExit("Missing workspace/design_layer_rpg/rpg-overlay-plan.json.")
    if not isinstance(branch_graph, dict):
        raise SystemExit("Missing workspace/design_layer/branch_graph.json.")
    if not isinstance(game_ir, dict):
        raise SystemExit("Missing workspace/design_layer/game_ir.json.")

    freeze_status = verify_narrative_freeze(run_root)
    if freeze_status.get("status") == "fail":
        raise SystemExit(json.dumps(freeze_status, ensure_ascii=False, indent=2))

    nodes, edges, story_to_nodes = public_indexes(branch_graph)
    state_ids = {
        variable.get("id")
        for variable in as_list(game_ir.get("global_state_variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }
    story_slices = [item for item in as_list(plan.get("story_slices")) if isinstance(item, dict)]
    packets_dir = run_root / "workspace" / "controller-packets" / "postdesign" / "rpg"
    ensure_dir(packets_dir)

    prepared_slices: list[Json] = []
    for index, story_slice in enumerate(story_slices):
        slice_id = story_slice.get("id") if isinstance(story_slice.get("id"), str) else f"slice.rpg.{index + 1:02d}"
        public_node_ids = nodes_for_slice(story_slice, nodes, story_to_nodes)
        public_edge_ids = edges_for_nodes(public_node_ids, edges)
        section_intents = {
            section: select_intents(plan, story_slice, section)
            for section in INTENT_SECTIONS
        }
        existing_state_ids = set(ids_from(story_slice.get("existing_state_ids")))
        for intents in section_intents.values():
            for intent in intents:
                existing_state_ids.update(trace_state_ids(intent))
        for edge_id in public_edge_ids:
            edge = edges[edge_id]
            existing_state_ids.update(state_refs_from_ops(edge.get("conditions")))
            existing_state_ids.update(state_refs_from_ops(edge.get("effects")))
        existing_state_ids = {state_id for state_id in existing_state_ids if state_id in state_ids or state_id.startswith("state.")}

        repair_notes: list[Json] = []
        if story_refs(story_slice) and not public_node_ids:
            repair_notes.append({
                "kind": "public_binding_gap",
                "message": "No public graph nodes were found for this story slice.",
                "source_story_unit_ids": sorted(story_refs(story_slice)),
            })

        packet: Json = {
            "metadata": {
                "schema_version": "0.1.0",
                "generated_by": "prepare_rpg_postdesign_slices.py",
                "mode": "narrative_first_overlay",
            },
            "slice_id": slice_id,
            "source_story_unit_ids": sorted(story_refs(story_slice)),
            "public_node_ids": sorted(public_node_ids),
            "public_edge_ids": sorted(public_edge_ids),
            "existing_state_ids": sorted(existing_state_ids),
            "required_story_beats": as_list(story_slice.get("required_story_beats")),
            "character_arc_beats": as_list(story_slice.get("character_arc_beats")),
            "emotional_turns": as_list(story_slice.get("emotional_turns")),
            "scene_script_obligations": scene_script_obligations(story_slice, public_node_ids, public_edge_ids),
            "canon_constraints": as_list(story_slice.get("canon_constraints")),
            "forbidden_changes": as_list(story_slice.get("forbidden_changes")),
            "allowed_outputs": allowed_outputs_for_slice(story_slice),
            "map_intents": section_intents["map_intents"],
            "questline_intents": section_intents["questline_intents"],
            "combat_intents": section_intents["combat_intents"],
            "equipment_intents": section_intents["equipment_intents"],
            "progression_axes": section_intents["progression_axes"],
            "public_node_summaries": [summarize_node(nodes[node_id]) for node_id in sorted(public_node_ids)],
            "public_edge_summaries": [summarize_edge(edges[edge_id]) for edge_id in sorted(public_edge_ids)],
            "repair_notes": repair_notes,
        }
        write_json(packets_dir / f"{stable_id(slice_id, 'slice')}.json", packet)
        prepared_slices.append(packet)

    aggregate = {
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "prepare_rpg_postdesign_slices.py",
            "mode": "narrative_first_overlay",
        },
        "status": "needs_repair" if any(packet["repair_notes"] for packet in prepared_slices) else "pass",
        "narrative_freeze_status": freeze_status,
        "slice_count": len(prepared_slices),
        "public_node_count": len(nodes),
        "slices": prepared_slices,
    }
    write_json(path_for(run_root, "rpg_postdesign_slices"), aggregate)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    payload = prepare_rpg_postdesign_slices(Path(args.run_root).resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get("status") == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
