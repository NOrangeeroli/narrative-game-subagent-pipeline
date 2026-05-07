#!/usr/bin/env python3
"""Shared helpers for side-scroller adventure artifacts."""

from __future__ import annotations

import collections
import json
import math
import re
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Finding,
    Json,
    ValidationResult,
    as_list,
    ensure_run_layout,
    load_optional_json,
    path_for,
    project_shared_state,
    read_json,
    stable_id,
    write_json,
)


GENRE_ID = "side_scroller_adventure"
ADVENTURE_ROOT = Path("workspace/adventure")
ADVENTURE_LEVELS = ADVENTURE_ROOT / "levels"
ADVENTURE_INTERACTIONS = ADVENTURE_ROOT / "interactions"
ADVENTURE_QUESTS = ADVENTURE_ROOT / "quests"
ADVENTURE_DIALOGUE = ADVENTURE_ROOT / "dialogue"
ADVENTURE_BINDINGS = ADVENTURE_ROOT / "bindings" / "narrative-bindings.json"
ADVENTURE_ASSET_DIRECTION = Path("workspace/assets/adventure/asset-direction.json")

CONDITION_OPERATORS = {
    "==",
    "equals",
    "!=",
    "not_equals",
    "in",
    "one_of",
    "not_in",
    "not_one_of",
    "contains",
    "includes",
    "not_contains",
    "excludes",
    "exists",
    "not_exists",
    ">",
    "greater_than",
    ">=",
    "greater_than_or_equal",
    "<",
    "less_than",
    "<=",
    "less_than_or_equal",
}

STATE_OPERATIONS = {
    "set",
    "set_if_unset",
    "set_if_unset_or_unformed",
    "increment",
    "decrement",
    "append",
    "append_unique",
    "remove",
    "clear",
}


def safe_token(value: str, prefix: str = "item") -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    token = token.replace("..", ".")
    if not token:
        token = "unknown"
    if not re.match(r"^[A-Za-z]", token):
        token = f"{prefix}.{token}"
    return token


def compact_id(value: str, prefix: str) -> str:
    value = str(value)
    value = re.sub(r"^(node|edge)\.", "", value)
    token = safe_token(value, prefix=prefix).removeprefix(f"{prefix}.")
    return f"{prefix}.{token}"


def outcome_id(edge_id: str) -> str:
    return "outcome_" + safe_token(str(edge_id).replace(".", "_"), prefix="edge")


def level_id_for_node(node_id: str) -> str:
    return compact_id(node_id, "level")


def interaction_id_for_edge(edge_id: str) -> str:
    return compact_id(edge_id, "interaction")


def quest_id_for_node(node_id: str) -> str:
    return compact_id(node_id, "quest")


def dialogue_id_for_node(node_id: str) -> str:
    return compact_id(node_id, "dialogue")


def relative(path: Path) -> str:
    return path.as_posix()


def node_text(node: Json) -> str:
    return str(node.get("summary") or node.get("body") or node.get("title") or node.get("id") or "")


def classify_secret_garden_region(node: Json) -> str:
    text = " ".join(str(node.get(key, "")) for key in ("id", "title", "summary")).lower()
    if "terminal" in text or "ending" in text or "final" in text or "ch27" in text:
        return "region.final_garden"
    if "colin" in text or "sickroom" in text or "cry" in text or "哭" in text:
        if "garden" not in text and "花园" not in text:
            return "region.colin_room" if "colin" in text else "region.manor_corridors"
    if "secret_garden" in text or "garden" in text or "花园" in text or "rose" in text:
        if "wall" in text or "墙" in text or "key" in text or "钥匙" in text:
            return "region.garden_wall"
        return "region.secret_garden"
    if "india" in text or "bungalow" in text:
        return "region.india_bungalow"
    if "moor" in text or "arrival" in text:
        return "region.moor_arrival"
    if "room" in text or "corridor" in text or "manor" in text or "misselthwaite" in text:
        return "region.manor_rooms"
    return "region.manor_corridors"


def classify_interaction_kind(edge: Json) -> str:
    text = " ".join(str(edge.get(key, "")) for key in ("id", "label", "summary", "condition_label")).lower()
    if any(token in text for token in ("cry", "listen", "hear", "sound", "哭", "听")):
        return "listen"
    if any(token in text for token in ("door", "key", "open", "unlock", "门", "钥匙", "打开")):
        return "open"
    if any(token in text for token in ("talk", "tell", "ask", "martha", "dickon", "colin", "ben", "susan", "问", "告诉", "说")):
        return "talk"
    if any(token in text for token in ("garden", "soil", "rose", "plant", "weed", "water", "花园", "土", "种", "玫瑰")):
        return "tend_garden"
    if any(token in text for token in ("hide", "wait", "guard", "secret", "等", "守", "秘密")):
        return "wait_or_hide"
    if any(token in text for token in ("pick", "take", "collect", "拿", "拾")):
        return "pick_up"
    return "inspect"


def read_public_runtime_inputs(run_root: Path) -> tuple[Json, Json, Json]:
    branch_graph = read_json(path_for(run_root, "branch_graph"))
    game_ir = read_json(path_for(run_root, "game_ir"))
    shared_state = load_optional_json(path_for(run_root, "shared_state"))
    if not shared_state:
        shared_state = project_shared_state(game_ir)
        write_json(path_for(run_root, "shared_state"), shared_state)
    return branch_graph, game_ir, shared_state


def nodes_by_id(branch_graph: Json) -> dict[str, Json]:
    return {
        node["id"]: node
        for node in as_list(branch_graph.get("nodes"))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }


def edges_by_id(branch_graph: Json) -> dict[str, Json]:
    return {
        edge["id"]: edge
        for edge in as_list(branch_graph.get("edges"))
        if isinstance(edge, dict) and isinstance(edge.get("id"), str)
    }


def edges_by_from(branch_graph: Json) -> dict[str, list[Json]]:
    grouped: dict[str, list[Json]] = collections.defaultdict(list)
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            grouped[edge["from"]].append(edge)
    return dict(grouped)


def state_ids(shared_state: Json) -> set[str]:
    return {
        variable["id"]
        for variable in as_list(shared_state.get("variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }


def terminal_nodes(branch_graph: Json) -> list[Json]:
    return [
        node for node in as_list(branch_graph.get("nodes"))
        if isinstance(node, dict) and (node.get("is_terminal") is True or node.get("node_type") == "terminal")
    ]


def plan_default_adventure(run_root: Path) -> Json:
    """Generate complete deterministic adventure artifacts from public graph semantics."""

    ensure_run_layout(run_root)
    branch_graph, game_ir, shared_state = read_public_runtime_inputs(run_root)
    nodes = nodes_by_id(branch_graph)
    outgoing = edges_by_from(branch_graph)

    genre_policy = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdventureGenrePlanner"},
        "genre_id": GENRE_ID,
        "engine_target": "unity_2d_mobile",
        "camera_style": "horizontal_follow",
        "movement_model": {
            "walk": True,
            "run": False,
            "jump": "limited_contextual",
            "climb": "contextual",
            "crouch": "contextual",
        },
        "player_verbs": [
            "move",
            "inspect",
            "listen",
            "open",
            "pick_up",
            "use_item",
            "talk",
            "tend_garden",
            "hide_or_wait",
        ],
        "mobile_controls": {
            "left": "virtual_joystick",
            "primary": "context_action",
            "secondary": "listen_or_observe",
            "pause": "menu",
        },
        "forbidden_adaptations": [
            "combat_as_primary_loop",
            "long_menu_only_branching",
            "unvalidated_arbitrary_scene_code",
        ],
    }

    region_level_ids: dict[str, list[str]] = collections.defaultdict(list)
    levels: list[Json] = []
    interactions: list[Json] = []
    quests: list[Json] = []
    dialogues: list[Json] = []
    node_bindings: list[Json] = []
    edge_bindings: list[Json] = []
    ending_bindings: list[Json] = []

    for node_id, node in nodes.items():
        level_id = level_id_for_node(node_id)
        region_id = classify_secret_garden_region(node)
        region_level_ids[region_id].append(level_id)
        node_edges = outgoing.get(node_id, [])
        source_text = node_text(node)
        is_terminal = bool(node.get("is_terminal") or node.get("node_type") == "terminal")
        interaction_refs = []
        quest_steps = []
        for index, edge in enumerate(node_edges):
            edge_id = str(edge["id"])
            interaction_id = interaction_id_for_edge(edge_id)
            kind = classify_interaction_kind(edge)
            x = min(30, 16 + index * 3)
            interaction_refs.append(interaction_id)
            interactions.append({
                "metadata": {"schema_version": "0.1.0", "generated_by": "InteractionQuestDesigner"},
                "interaction_id": interaction_id,
                "source_node_id": node_id,
                "level_id": level_id,
                "kind": kind,
                "label": edge.get("label") or "Continue",
                "position": {"x": x, "y": 1.5},
                "activation": {
                    "input": "secondary" if kind == "listen" else "primary",
                    "radius": 2.0,
                    "conditions": as_list(edge.get("conditions")),
                },
                "feedback": {
                    "animation": f"mary_{kind}",
                    "sfx": f"sfx.adventure.{kind}",
                    "caption": edge.get("label") or "Continue",
                },
                "completion": {
                    "edge_id": edge_id,
                    "outcome_id": outcome_id(edge_id),
                    "target_node_id": edge.get("to"),
                    "state_writes": as_list(edge.get("effects")),
                },
                "source_trace": {"node_ids": [node_id], "edge_ids": [edge_id]},
            })
            quest_steps.append({
                "step_id": compact_id(edge_id, "step"),
                "level_id": level_id,
                "required_interaction_ids": [interaction_id],
                "optional_interaction_ids": [],
                "completion_edge_id": edge_id,
            })
            edge_bindings.append({
                "edge_id": edge_id,
                "trigger_kind": "interaction_completion",
                "trigger_id": interaction_id,
                "source_node_id": node_id,
                "target_node_id": edge.get("to"),
                "conditions": as_list(edge.get("conditions")),
                "effects": as_list(edge.get("effects")),
            })

        exits = [
            {
                "exit_id": compact_id(edge["id"], "exit"),
                "edge_id": edge["id"],
                "target_node_id": edge.get("to"),
                "position": {"x": 30, "y": 1.5},
                "conditions": as_list(edge.get("conditions")),
            }
            for edge in node_edges
            if isinstance(edge.get("id"), str)
        ]
        levels.append({
            "metadata": {"schema_version": "0.1.0", "generated_by": "LevelBlockoutDesigner"},
            "level_id": level_id,
            "region_id": region_id,
            "source_node_ids": [node_id],
            "title": node.get("title") or node_id,
            "summary": source_text,
            "dimensions": {"width": 34, "height": 8, "unit": "tile"},
            "layers": [
                {"layer_id": "background", "kind": "background_layer", "asset_id": f"bg.{safe_token(region_id)}"},
                {"layer_id": "ground", "kind": "collision_visual", "asset_id": "tileset.adventure.default"},
            ],
            "collision": [{"shape": "rect", "x": 0, "y": 0, "width": 34, "height": 1}],
            "walkable_surfaces": [{"surface_id": "floor.main", "from": {"x": 1, "y": 1}, "to": {"x": 32, "y": 1}}],
            "camera_bounds": [{"x": 0, "y": 0, "width": 34, "height": 8}],
            "spawn_points": [{"spawn_id": "spawn.default", "role": "player", "x": 2, "y": 1.5}],
            "exits": exits,
            "interactable_refs": interaction_refs,
            "npc_refs": [],
            "ambient_audio": [{"asset_id": f"ambience.{safe_token(region_id)}"}],
            "state_variants": [],
            "is_terminal": is_terminal,
        })
        quests.append({
            "metadata": {"schema_version": "0.1.0", "generated_by": "InteractionQuestDesigner"},
            "quest_id": quest_id_for_node(node_id),
            "source_node_ids": [node_id],
            "steps": quest_steps,
            "state_reads": [],
            "state_writes": [],
            "failure_policy": "fail_forward",
            "source_trace": {"node_ids": [node_id], "edge_ids": [step["completion_edge_id"] for step in quest_steps]},
        })
        dialogues.append({
            "metadata": {"schema_version": "0.1.0", "generated_by": "InteractionQuestDesigner"},
            "dialogue_id": dialogue_id_for_node(node_id),
            "source_node_id": node_id,
            "speaker_bindings": [],
            "lines": [{"speaker": "Narrator", "text": source_text or str(node.get("title") or node_id)}],
            "choices": [],
            "state_reads": [],
            "state_writes": [],
            "exit_edge_bindings": [edge["id"] for edge in node_edges if isinstance(edge.get("id"), str)],
        })
        node_bindings.append({
            "node_id": node_id,
            "level_id": level_id,
            "binding_kind": "ending_sequence" if is_terminal else ("interaction_sequence" if node_edges else "cutscene"),
            "required_interaction_ids": interaction_refs,
            "quest_id": quest_id_for_node(node_id),
            "dialogue_id": dialogue_id_for_node(node_id),
        })
        if is_terminal:
            ending_bindings.append({
                "ending_id": node.get("ending_id") or node.get("variant_of_ending_id") or f"ending.{safe_token(node_id)}",
                "ending_variant_id": node.get("ending_variant_id"),
                "terminal_node_id": node_id,
                "level_id": level_id,
                "ending_sequence_id": compact_id(node_id, "ending_sequence"),
            })

    regions = []
    for region_id, level_ids in sorted(region_level_ids.items()):
        regions.append({
            "region_id": region_id,
            "title": region_id.removeprefix("region.").replace("_", " ").title(),
            "narrative_scope_node_ids": [
                node_id for node_id, node in nodes.items()
                if level_id_for_node(node_id) in set(level_ids)
            ],
            "level_ids": level_ids,
            "available_after": [],
            "emotional_function": "Preserve the current story pressure as spatial exploration.",
            "visual_function": "Use readable side-scroller silhouettes and state-reactive props.",
        })

    world_map = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "WorldMapDesigner"},
        "world_id": "world." + safe_token(branch_graph.get("title") or "generated_adventure"),
        "title": branch_graph.get("title") or "Generated Adventure",
        "start_level_id": level_id_for_node(str(branch_graph.get("start_node_id"))),
        "level_order": [level["level_id"] for level in levels],
        "regions": regions,
        "connections": [
            {
                "connection_id": compact_id(edge["id"], "connection"),
                "from_level_id": level_id_for_node(edge["from"]),
                "to_level_id": level_id_for_node(edge["to"]),
                "edge_id": edge["id"],
                "conditions": as_list(edge.get("conditions")),
            }
            for edge in as_list(branch_graph.get("edges"))
            if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str) and isinstance(edge.get("id"), str)
        ],
        "global_state_gates": [],
        "narrative_node_coverage": [{"node_id": node_id, "level_id": level_id_for_node(node_id)} for node_id in nodes],
    }

    bindings = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdventureNarrativeBinder"},
        "node_bindings": node_bindings,
        "edge_bindings": edge_bindings,
        "ending_bindings": ending_bindings,
    }

    asset_direction = build_default_asset_direction(levels, interactions, ending_bindings)

    write_json(path_for(run_root, "adventure_genre_policy"), genre_policy)
    write_json(path_for(run_root, "adventure_world_map"), world_map)
    for level in levels:
        write_json(run_root / ADVENTURE_LEVELS / f"{safe_token(level['level_id'])}.level.json", level)
    for interaction in interactions:
        write_json(run_root / ADVENTURE_INTERACTIONS / f"{safe_token(interaction['interaction_id'])}.interaction.json", interaction)
    for quest in quests:
        write_json(run_root / ADVENTURE_QUESTS / f"{safe_token(quest['quest_id'])}.quest.json", quest)
    for dialogue in dialogues:
        write_json(run_root / ADVENTURE_DIALOGUE / f"{safe_token(dialogue['dialogue_id'])}.dialogue.json", dialogue)
    write_json(run_root / ADVENTURE_BINDINGS, bindings)
    write_json(run_root / ADVENTURE_ASSET_DIRECTION, asset_direction)

    return {
        "status": "planned",
        "run_root": str(run_root),
        "levels": len(levels),
        "interactions": len(interactions),
        "quests": len(quests),
        "dialogue": len(dialogues),
        "ending_bindings": len(ending_bindings),
        "artifacts": {
            "genre_policy": path_for(run_root, "adventure_genre_policy").relative_to(run_root).as_posix(),
            "world_map": path_for(run_root, "adventure_world_map").relative_to(run_root).as_posix(),
            "bindings": (run_root / ADVENTURE_BINDINGS).relative_to(run_root).as_posix(),
            "asset_direction": (run_root / ADVENTURE_ASSET_DIRECTION).relative_to(run_root).as_posix(),
        },
    }


def build_default_asset_direction(levels: list[Json], interactions: list[Json], endings: list[Json]) -> Json:
    region_ids = sorted({level.get("region_id") for level in levels if isinstance(level.get("region_id"), str)})
    directions: list[Json] = [
        {
            "asset_id": "tileset.adventure.default",
            "asset_kind": "tileset",
            "source_trace": {"level_ids": [level.get("level_id") for level in levels]},
            "style_tags": ["readable", "side_scroller", "placeholder_safe"],
            "reuse_group": "adventure.core",
            "required_level_ids": [level.get("level_id") for level in levels],
            "fallback_policy": "generate_placeholder",
        },
        {
            "asset_id": "character.mary.walk",
            "asset_kind": "character_animation",
            "source_trace": {},
            "style_tags": ["player", "mobile_readable"],
            "reuse_group": "adventure.player",
            "required_level_ids": [level.get("level_id") for level in levels],
            "fallback_policy": "generate_placeholder",
        },
        {
            "asset_id": "ui.mobile.controls",
            "asset_kind": "mobile_control_icon",
            "source_trace": {},
            "style_tags": ["mobile_ui"],
            "reuse_group": "adventure.ui",
            "required_level_ids": [],
            "fallback_policy": "generate_placeholder",
        },
    ]
    for region_id in region_ids:
        directions.append({
            "asset_id": f"bg.{safe_token(region_id)}",
            "asset_kind": "background_layer",
            "source_trace": {"region_id": region_id},
            "style_tags": ["side_scroller_background"],
            "reuse_group": f"adventure.{region_id}",
            "required_level_ids": [level.get("level_id") for level in levels if level.get("region_id") == region_id],
            "fallback_policy": "generate_placeholder",
        })
        directions.append({
            "asset_id": f"ambience.{safe_token(region_id)}",
            "asset_kind": "ambient_loop",
            "source_trace": {"region_id": region_id},
            "style_tags": ["ambient"],
            "reuse_group": f"adventure.{region_id}.audio",
            "required_level_ids": [level.get("level_id") for level in levels if level.get("region_id") == region_id],
            "fallback_policy": "silent",
        })
    for kind in sorted({interaction.get("kind") for interaction in interactions if isinstance(interaction.get("kind"), str)}):
        directions.append({
            "asset_id": f"icon.interaction.{kind}",
            "asset_kind": "interaction_icon",
            "source_trace": {"interaction_kind": kind},
            "style_tags": ["interaction_prompt"],
            "reuse_group": "adventure.interaction_icons",
            "required_interaction_ids": [interaction.get("interaction_id") for interaction in interactions if interaction.get("kind") == kind],
            "fallback_policy": "generate_placeholder",
        })
        directions.append({
            "asset_id": f"sfx.adventure.{kind}",
            "asset_kind": "interaction_sfx",
            "source_trace": {"interaction_kind": kind},
            "style_tags": ["feedback"],
            "reuse_group": "adventure.interaction_sfx",
            "required_interaction_ids": [interaction.get("interaction_id") for interaction in interactions if interaction.get("kind") == kind],
            "fallback_policy": "silent",
        })
    for ending in endings:
        ending_id = ending.get("ending_id") or ending.get("terminal_node_id")
        directions.append({
            "asset_id": f"ending_still.{safe_token(str(ending_id))}",
            "asset_kind": "ending_still",
            "source_trace": {"ending_id": ending_id, "terminal_node_id": ending.get("terminal_node_id")},
            "style_tags": ["ending", "payoff"],
            "reuse_group": "adventure.endings",
            "required_level_ids": [ending.get("level_id")],
            "fallback_policy": "generate_placeholder",
        })
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdventureAssetDirector"},
        "asset_directions": directions,
    }


def load_adventure_collection(run_root: Path, folder: Path, suffix: str) -> list[Json]:
    root = run_root / folder
    values = []
    for path in sorted(root.glob(f"*{suffix}")):
        values.append(read_json(path))
    return values


def load_adventure_artifacts(run_root: Path) -> Json:
    return {
        "genre_policy": load_optional_json(path_for(run_root, "adventure_genre_policy")),
        "world_map": load_optional_json(path_for(run_root, "adventure_world_map")),
        "levels": load_adventure_collection(run_root, ADVENTURE_LEVELS, ".level.json"),
        "interactions": load_adventure_collection(run_root, ADVENTURE_INTERACTIONS, ".interaction.json"),
        "quests": load_adventure_collection(run_root, ADVENTURE_QUESTS, ".quest.json"),
        "dialogue": load_adventure_collection(run_root, ADVENTURE_DIALOGUE, ".dialogue.json"),
        "bindings": load_optional_json(run_root / ADVENTURE_BINDINGS),
        "asset_direction": load_optional_json(run_root / ADVENTURE_ASSET_DIRECTION),
    }


def reference_state_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        ref = value.get("state_variable_id") or value.get("state_id") or value.get("id")
        return ref if isinstance(ref, str) else None
    return None


def iter_state_ops(value: Any) -> list[Json]:
    ops: list[Json] = []
    if isinstance(value, dict):
        if reference_state_id(value):
            ops.append(value)
        for child in value.values():
            ops.extend(iter_state_ops(child))
    elif isinstance(value, list):
        for child in value:
            ops.extend(iter_state_ops(child))
    return ops


def validate_conditions_and_writes(result: ValidationResult, items: list[Any], valid_state_ids: set[str], path: str) -> None:
    for index, op in enumerate(items):
        if not isinstance(op, dict):
            result.add("error", "state_operation_schema", "State condition/write must be an object.", f"{path}[{index}]")
            continue
        ref = reference_state_id(op)
        if ref and ref not in valid_state_ids:
            result.add("error", "state_reference", f"Unknown state variable: {ref}", f"{path}[{index}]")
        operator = op.get("operator")
        if operator and operator not in CONDITION_OPERATORS:
            result.add("error", "condition_operator", f"Unsupported condition operator: {operator}", f"{path}[{index}].operator")
        operation = op.get("operation") or op.get("op")
        if operation and operation not in STATE_OPERATIONS:
            result.add("error", "state_operation", f"Unsupported state write operation: {operation}", f"{path}[{index}].operation")
        if operator in ("in", "one_of", "not_in", "not_one_of") and "value" in op and not isinstance(op.get("value"), list):
            result.add("error", "state_gate_type", f"Operator {operator} requires list value.", f"{path}[{index}].value")


def point_in_bounds(point: Json, level: Json) -> bool:
    dimensions = level.get("dimensions") if isinstance(level.get("dimensions"), dict) else {}
    width = float(dimensions.get("width") or 0)
    height = float(dimensions.get("height") or 0)
    try:
        x = float(point.get("x"))
        y = float(point.get("y"))
    except (TypeError, ValueError):
        return False
    return 0 <= x <= width and 0 <= y <= height


def distance_to_floor(point: Json, level: Json) -> float:
    surfaces = [surface for surface in as_list(level.get("walkable_surfaces")) if isinstance(surface, dict)]
    try:
        x = float(point.get("x"))
        y = float(point.get("y"))
    except (TypeError, ValueError):
        return math.inf
    best = math.inf
    for surface in surfaces:
        start = surface.get("from") if isinstance(surface.get("from"), dict) else {}
        end = surface.get("to") if isinstance(surface.get("to"), dict) else {}
        try:
            x1, y1 = float(start.get("x")), float(start.get("y"))
            x2, y2 = float(end.get("x")), float(end.get("y"))
        except (TypeError, ValueError):
            continue
        if min(x1, x2) - 0.5 <= x <= max(x1, x2) + 0.5:
            best = min(best, abs(y - y1), abs(y - y2))
    return best


def validate_adventure_artifacts(run_root: Path, write_report: bool = False) -> ValidationResult:
    ensure_run_layout(run_root)
    result = ValidationResult()
    try:
        branch_graph, _game_ir, shared_state = read_public_runtime_inputs(run_root)
    except Exception as exc:  # noqa: BLE001
        result.add("error", "missing_runtime_design", f"Cannot load public design artifacts: {exc}")
        if write_report:
            write_json(path_for(run_root, "adventure_validation_report"), result.to_json())
        return result

    artifacts = load_adventure_artifacts(run_root)
    valid_state_ids = state_ids(shared_state)
    graph_nodes = nodes_by_id(branch_graph)
    graph_edges = edges_by_id(branch_graph)

    if not isinstance(artifacts["genre_policy"], dict):
        result.add("error", "missing_adventure_genre_policy", "Missing workspace/adventure/genre-policy.json")
    elif artifacts["genre_policy"].get("genre_id") != GENRE_ID:
        result.add("error", "genre_id", f"genre_policy.genre_id must be {GENRE_ID}.", "workspace/adventure/genre-policy.json.genre_id")

    world = artifacts["world_map"]
    if not isinstance(world, dict):
        result.add("error", "missing_world_map", "Missing workspace/adventure/world-map.json")
        world = {}

    levels = artifacts["levels"]
    interactions = artifacts["interactions"]
    quests = artifacts["quests"]
    dialogue = artifacts["dialogue"]
    bindings = artifacts["bindings"] if isinstance(artifacts["bindings"], dict) else {}
    if not bindings:
        result.add("error", "missing_narrative_bindings", "Missing workspace/adventure/bindings/narrative-bindings.json")

    level_by_id = {}
    for index, level in enumerate(levels):
        level_id = level.get("level_id") if isinstance(level, dict) else None
        if not isinstance(level_id, str) or not level_id:
            result.add("error", "level_schema", "Level needs level_id.", f"levels[{index}].level_id")
            continue
        if level_id in level_by_id:
            result.add("error", "duplicate_level_id", f"Duplicate level id: {level_id}", f"levels[{index}].level_id")
        level_by_id[level_id] = level
        if not as_list(level.get("spawn_points")):
            result.add("error", "missing_spawn", f"Level {level_id} needs player spawn.", level_id)
        if not as_list(level.get("walkable_surfaces")):
            result.add("error", "missing_walkable_surface", f"Level {level_id} needs walkable surfaces.", level_id)
        for spawn_index, spawn in enumerate(as_list(level.get("spawn_points"))):
            if not isinstance(spawn, dict) or not point_in_bounds(spawn, level):
                result.add("error", "spawn_out_of_bounds", f"Spawn is outside level bounds: {level_id}", f"{level_id}.spawn_points[{spawn_index}]")
            elif distance_to_floor(spawn, level) > 2.0:
                result.add("error", "blocked_spatial_path", f"Spawn is not near any walkable surface: {level_id}", f"{level_id}.spawn_points[{spawn_index}]")
        for exit_index, exit_spec in enumerate(as_list(level.get("exits"))):
            if isinstance(exit_spec, dict):
                validate_conditions_and_writes(result, as_list(exit_spec.get("conditions")), valid_state_ids, f"{level_id}.exits[{exit_index}].conditions")

    interaction_by_id = {}
    for index, interaction in enumerate(interactions):
        if not isinstance(interaction, dict):
            result.add("error", "interaction_schema", "Interaction entries must be objects.", f"interactions[{index}]")
            continue
        interaction_id = interaction.get("interaction_id")
        if not isinstance(interaction_id, str) or not interaction_id:
            result.add("error", "interaction_schema", "Interaction needs interaction_id.", f"interactions[{index}].interaction_id")
            continue
        if interaction_id in interaction_by_id:
            result.add("error", "duplicate_interaction_id", f"Duplicate interaction id: {interaction_id}", f"interactions[{index}].interaction_id")
        interaction_by_id[interaction_id] = interaction
        level_id = interaction.get("level_id")
        level = level_by_id.get(level_id)
        if not isinstance(level_id, str) or not isinstance(level, dict):
            result.add("error", "missing_level_binding", f"Interaction references missing level: {level_id}", f"{interaction_id}.level_id")
            continue
        position = interaction.get("position") if isinstance(interaction.get("position"), dict) else {}
        if not point_in_bounds(position, level):
            result.add("error", "interaction_out_of_bounds", f"Interaction {interaction_id} is outside level bounds.", f"{interaction_id}.position")
        elif distance_to_floor(position, level) > 3.0:
            result.add("error", "blocked_spatial_path", f"Interaction {interaction_id} is not reachable from floor.", f"{interaction_id}.position")
        activation = interaction.get("activation") if isinstance(interaction.get("activation"), dict) else {}
        validate_conditions_and_writes(result, as_list(activation.get("conditions")), valid_state_ids, f"{interaction_id}.activation.conditions")
        completion = interaction.get("completion") if isinstance(interaction.get("completion"), dict) else {}
        edge_id = completion.get("edge_id")
        if edge_id not in graph_edges:
            result.add("error", "missing_edge_trigger", f"Interaction completion references missing edge: {edge_id}", f"{interaction_id}.completion.edge_id")
        validate_conditions_and_writes(result, as_list(completion.get("state_writes")), valid_state_ids, f"{interaction_id}.completion.state_writes")

    for index, quest in enumerate(quests):
        if not isinstance(quest, dict):
            result.add("error", "quest_schema", "Quest entries must be objects.", f"quests[{index}]")
            continue
        for step_index, step in enumerate(as_list(quest.get("steps"))):
            if not isinstance(step, dict):
                continue
            for ref in as_list(step.get("required_interaction_ids")):
                if ref not in interaction_by_id:
                    result.add("error", "missing_interaction_binding", f"Quest step references missing interaction: {ref}", f"{quest.get('quest_id')}.steps[{step_index}]")
            if step.get("completion_edge_id") not in graph_edges:
                result.add("error", "missing_edge_trigger", f"Quest step references missing edge: {step.get('completion_edge_id')}", f"{quest.get('quest_id')}.steps[{step_index}].completion_edge_id")

    for index, entry in enumerate(as_list(bindings.get("node_bindings"))):
        if not isinstance(entry, dict):
            continue
        if entry.get("node_id") not in graph_nodes:
            result.add("error", "missing_node_binding", f"Node binding references missing graph node: {entry.get('node_id')}", f"node_bindings[{index}]")
        if entry.get("level_id") not in level_by_id:
            result.add("error", "missing_level_binding", f"Node binding references missing level: {entry.get('level_id')}", f"node_bindings[{index}]")
        for ref in as_list(entry.get("required_interaction_ids")):
            if ref not in interaction_by_id:
                result.add("error", "missing_interaction_binding", f"Node binding references missing interaction: {ref}", f"node_bindings[{index}]")

    bound_nodes = {entry.get("node_id") for entry in as_list(bindings.get("node_bindings")) if isinstance(entry, dict)}
    missing_nodes = sorted(set(graph_nodes) - bound_nodes)
    if missing_nodes:
        result.add("error", "missing_node_binding", f"Missing adventure node bindings: {missing_nodes[:20]}{'...' if len(missing_nodes) > 20 else ''}")

    bound_edges = {entry.get("edge_id") for entry in as_list(bindings.get("edge_bindings")) if isinstance(entry, dict)}
    missing_edges = sorted(set(graph_edges) - bound_edges)
    if missing_edges:
        result.add("error", "missing_edge_trigger", f"Missing adventure edge bindings: {missing_edges[:20]}{'...' if len(missing_edges) > 20 else ''}")

    terminal_ids = {node["id"] for node in terminal_nodes(branch_graph)}
    bound_terminal_ids = {
        entry.get("terminal_node_id")
        for entry in as_list(bindings.get("ending_bindings"))
        if isinstance(entry, dict)
    }
    missing_terminal = sorted(terminal_ids - bound_terminal_ids)
    if missing_terminal:
        result.add("error", "ending_binding_mismatch", f"Missing adventure ending bindings for terminals: {missing_terminal}")

    for index, entry in enumerate(as_list(bindings.get("edge_bindings"))):
        if not isinstance(entry, dict):
            continue
        edge_id = entry.get("edge_id")
        trigger_id = entry.get("trigger_id")
        if edge_id not in graph_edges:
            result.add("error", "missing_edge_trigger", f"Edge binding references missing edge: {edge_id}", f"edge_bindings[{index}]")
        if trigger_id not in interaction_by_id:
            result.add("error", "missing_interaction_binding", f"Edge binding references missing interaction: {trigger_id}", f"edge_bindings[{index}]")
        validate_conditions_and_writes(result, as_list(entry.get("conditions")), valid_state_ids, f"edge_bindings[{index}].conditions")
        validate_conditions_and_writes(result, as_list(entry.get("effects")), valid_state_ids, f"edge_bindings[{index}].effects")

    start_level = world.get("start_level_id") if isinstance(world, dict) else None
    if start_level and start_level not in level_by_id:
        result.add("error", "missing_world_region", f"World start_level_id references missing level: {start_level}", "world-map.start_level_id")

    asset_direction = artifacts["asset_direction"]
    if not isinstance(asset_direction, dict) or not as_list(asset_direction.get("asset_directions")):
        result.add("error", "missing_asset_for_level", "Adventure asset direction must include asset_directions.", str(ADVENTURE_ASSET_DIRECTION))

    if write_report:
        coverage = {
            "status": "clear" if result.status == "pass" else "has_gaps",
            "node_bindings": len(bound_nodes),
            "edge_bindings": len(bound_edges),
            "levels": len(levels),
            "interactions": len(interactions),
            "quests": len(quests),
            "dialogue": len(dialogue),
            "ending_bindings": len(bound_terminal_ids),
            "missing_nodes": missing_nodes,
            "missing_edges": missing_edges,
        }
        write_json(path_for(run_root, "adventure_validation_report"), result.to_json())
        write_json(path_for(run_root, "adventure_coverage_report"), coverage)
    return result


def normalize_for_unity(manifest: Json) -> Json:
    """Return a JsonUtility-friendly flattened runtime payload."""

    bindings = manifest.get("bindings") if isinstance(manifest.get("bindings"), dict) else {}
    level_by_id = {level.get("level_id"): level for level in as_list(manifest.get("levels")) if isinstance(level, dict)}
    edge_target = {
        binding.get("edge_id"): binding.get("target_node_id")
        for binding in as_list(bindings.get("edge_bindings"))
        if isinstance(binding, dict)
    }
    runtime_levels = []
    for level in as_list(manifest.get("levels")):
        if not isinstance(level, dict):
            continue
        spawn = (as_list(level.get("spawn_points")) or [{}])[0]
        dimensions = level.get("dimensions") if isinstance(level.get("dimensions"), dict) else {}
        runtime_levels.append({
            "level_id": level.get("level_id"),
            "title": level.get("title") or level.get("level_id"),
            "summary": level.get("summary", ""),
            "width": float(dimensions.get("width") or 34),
            "height": float(dimensions.get("height") or 8),
            "spawn_x": float(spawn.get("x") or 2),
            "spawn_y": float(spawn.get("y") or 1.5),
            "is_terminal": bool(level.get("is_terminal")),
        })
    runtime_interactions = []
    for interaction in as_list(manifest.get("interactions")):
        if not isinstance(interaction, dict):
            continue
        position = interaction.get("position") if isinstance(interaction.get("position"), dict) else {}
        completion = interaction.get("completion") if isinstance(interaction.get("completion"), dict) else {}
        runtime_interactions.append({
            "interaction_id": interaction.get("interaction_id"),
            "level_id": interaction.get("level_id"),
            "kind": interaction.get("kind"),
            "label": interaction.get("label") or (completion.get("edge_id") or "Continue"),
            "x": float(position.get("x") or 18),
            "y": float(position.get("y") or 1.5),
            "edge_id": completion.get("edge_id"),
            "target_node_id": completion.get("target_node_id") or edge_target.get(completion.get("edge_id")),
        })
    node_level = {
        binding.get("node_id"): binding.get("level_id")
        for binding in as_list(bindings.get("node_bindings"))
        if isinstance(binding, dict)
    }
    endings = []
    for ending in as_list(bindings.get("ending_bindings")):
        if isinstance(ending, dict):
            endings.append({
                "ending_id": ending.get("ending_id"),
                "terminal_node_id": ending.get("terminal_node_id"),
                "level_id": ending.get("level_id"),
                "title": ending.get("ending_variant_id") or ending.get("ending_id") or "Ending",
            })
    return {
        "start_node_id": manifest.get("branch_graph", {}).get("start_node_id"),
        "start_level_id": manifest.get("world_map", {}).get("start_level_id"),
        "levels": runtime_levels,
        "interactions": runtime_interactions,
        "node_levels": [{"node_id": node_id, "level_id": level_id} for node_id, level_id in node_level.items()],
        "endings": endings,
    }


def build_adventure_manifest(run_root: Path) -> Json:
    ensure_run_layout(run_root)
    branch_graph, game_ir, shared_state = read_public_runtime_inputs(run_root)
    artifacts = load_adventure_artifacts(run_root)
    adventure_asset_manifest = build_adventure_asset_manifest(run_root, artifacts.get("asset_direction") or {})
    manifest = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "compile_adventure_manifest.py"},
        "genre_policy": artifacts["genre_policy"] or {},
        "world_map": artifacts["world_map"] or {},
        "levels": artifacts["levels"],
        "interactions": artifacts["interactions"],
        "quests": artifacts["quests"],
        "dialogue": artifacts["dialogue"],
        "bindings": artifacts["bindings"] or {},
        "initial_state": {
            variable.get("id"): variable.get("initial_value")
            for variable in as_list(shared_state.get("variables"))
            if isinstance(variable, dict) and isinstance(variable.get("id"), str)
        },
        "state_schema": shared_state,
        "branch_graph": branch_graph,
        "game_ir_summary": {
            "design_layer": game_ir.get("design_layer"),
            "design_brief": game_ir.get("design_brief"),
        },
        "assets": as_list(adventure_asset_manifest.get("assets")),
        "ending_catalog": [
            {
                "node_id": node.get("id"),
                "ending_id": node.get("ending_id"),
                "ending_variant_id": node.get("ending_variant_id"),
                "variant_of_ending_id": node.get("variant_of_ending_id"),
                "title": node.get("title"),
            }
            for node in terminal_nodes(branch_graph)
        ],
        "build_settings": {
            "engine": "manifest_driven_side_scroller",
            "templates": ["assets/web-adventure-template", "assets/unity-adventure-template"],
            "supported_platforms": ["desktop", "webgl", "android", "ios"],
        },
    }
    manifest["unity_runtime"] = normalize_for_unity(manifest)
    write_json(path_for(run_root, "adventure_manifest"), manifest)
    return manifest


def adventure_asset_file_ref(asset_id: str, asset_kind: str) -> str:
    safe = safe_token(asset_id).replace(".", "_")
    if asset_kind in {"ambient_loop", "interaction_sfx", "footstep_sfx", "ui_sfx"} or asset_id.startswith(("sfx.", "bgm.", "ambience.")):
        return f"generated/adventure/audio/{safe}.wav"
    return f"generated/adventure/images/{safe}.svg"


def build_adventure_asset_manifest(run_root: Path, asset_direction: Json | None = None) -> Json:
    asset_direction = asset_direction or load_optional_json(run_root / ADVENTURE_ASSET_DIRECTION) or {"asset_directions": []}
    assets = []
    for direction in as_list(asset_direction.get("asset_directions")):
        if not isinstance(direction, dict) or not isinstance(direction.get("asset_id"), str):
            continue
        asset_id = direction["asset_id"]
        asset_kind = str(direction.get("asset_kind") or direction.get("kind") or asset_id.split(".", 1)[0])
        file_ref = str(direction.get("file_ref") or adventure_asset_file_ref(asset_id, asset_kind))
        entry = {
            "asset_id": asset_id,
            "asset_kind": asset_kind,
            "file_ref": file_ref,
            "runtime_path": f"workspace/generated-assets/{file_ref}",
            "source_trace": direction.get("source_trace", {}),
            "required_level_ids": as_list(direction.get("required_level_ids")),
            "required_interaction_ids": as_list(direction.get("required_interaction_ids")),
            "state_variant_ids": as_list(direction.get("state_variant_ids")),
            "fallback_policy": direction.get("fallback_policy", "generate_placeholder"),
        }
        assets.append(entry)
    manifest = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "AdventureAssetDirector"},
        "source_asset_direction": str(ADVENTURE_ASSET_DIRECTION),
        "assets": assets,
    }
    write_json(path_for(run_root, "adventure_asset_manifest"), manifest)
    return manifest


def simulate_adventure_routes(run_root: Path) -> Json:
    branch_graph, _game_ir, _shared_state = read_public_runtime_inputs(run_root)
    bindings = load_optional_json(path_for(run_root, "adventure_bindings")) or {}
    graph_nodes = nodes_by_id(branch_graph)
    outgoing = edges_by_from(branch_graph)
    bound_edges = {entry.get("edge_id") for entry in as_list(bindings.get("edge_bindings")) if isinstance(entry, dict)}
    terminal = {node["id"]: node for node in terminal_nodes(branch_graph)}
    start = branch_graph.get("start_node_id")
    reached: set[str] = set()
    reached_endings: dict[str, str] = {}
    queue = collections.deque([(start, [])])
    blocked = []
    while queue:
        node_id, path = queue.popleft()
        if not isinstance(node_id, str) or node_id in reached:
            continue
        reached.add(node_id)
        if node_id in terminal:
            ending_id = terminal[node_id].get("ending_id") or terminal[node_id].get("variant_of_ending_id") or node_id
            reached_endings[str(ending_id)] = node_id
            continue
        node_edges = outgoing.get(node_id, [])
        if not node_edges:
            blocked.append({"node_id": node_id, "reason": "nonterminal_sink"})
            continue
        for edge in node_edges:
            edge_id = edge.get("id")
            if edge_id not in bound_edges:
                blocked.append({"node_id": node_id, "edge_id": edge_id, "reason": "missing_edge_binding"})
                continue
            queue.append((edge.get("to"), path + [edge_id]))
    missing_terminals = sorted(set(terminal) - reached)
    status = "pass" if not blocked and not missing_terminals else "fail"
    report = {
        "status": status,
        "start_node_id": start,
        "visited_nodes": len(reached),
        "total_nodes": len(graph_nodes),
        "reached_ending_families": reached_endings,
        "missing_terminal_nodes": missing_terminals,
        "blocked": blocked,
    }
    write_json(path_for(run_root, "adventure_playtest_report"), report)
    return report
