#!/usr/bin/env python3
"""Design Layer V2 validation, compilation, and projection helpers."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Finding,
    Json,
    ValidationResult,
    as_list,
    ensure_dir,
    project_shared_state,
    read_json,
    stable_id,
    validate_branch_graph,
    validate_game_ir,
    validate_graph_ir_consistency,
    validate_requirements,
    validate_synopsis,
    write_json,
)


DESIGN_V2_ROOT = Path("workspace/design_layer_v2")
DESIGN_V2_COMPILE_REPORT = DESIGN_V2_ROOT / "compile_report.json"
DESIGN_V2_VALIDATION_REPORT = DESIGN_V2_ROOT / "validation/validation_report.json"
DESIGN_V2_SIMULATION_PROFILES = DESIGN_V2_ROOT / "validation/simulation_profiles.json"
DESIGN_V2_SOURCE_COVERAGE_REPORT = DESIGN_V2_ROOT / "validation/source_coverage_report.json"

REQUIRED_V2_FILES = [
    "source_intake/input_profile.json",
    "source_intake/source_segments.json",
    "source_intake/source_beat_table.json",
    "source_intake/adaptation_coverage_matrix.json",
    "source_facts/fact_book.json",
    "source_facts/character_graph.json",
    "source_facts/event_timeline.json",
    "source_facts/world_rules.json",
    "source_facts/foreshadowing_table.json",
    "source_facts/theme_constraints.json",
    "adaptation/adaptation_policy.json",
    "adaptation/canon_lock_table.json",
    "adaptation/variable_process_table.json",
    "adaptation/ending_space.json",
    "state/world_state_model.json",
    "state/state_permissions.json",
    "state/state_invariants.json",
    "macro/macro_story_graph.json",
    "macro/macro_node_contracts.json",
    "control/mesh_expansion_policy.json",
    "control/route_merge_policy.json",
]

V2_DIRECTORIES = [
    "source_intake",
    "source_facts",
    "adaptation",
    "state",
    "macro",
    "subgraphs",
    "control",
    "validation",
    "compiled",
]

STATE_REF_RE = re.compile(r"\b(?:state|relationship|knowledge|quest|local|hidden)\.[A-Za-z0-9_.-]+\b")
SOURCE_DETAIL_TYPES = {
    "plot",
    "setting",
    "object",
    "gesture",
    "inner_state",
    "relationship",
    "world_rule",
    "motif",
}
SOURCE_PRESERVATION_PRIORITIES = {"must_keep", "should_keep", "nice_to_keep"}
INTERNAL_TRACE_KEYS = {
    "source_segment_ids",
    "covered_source_segment_ids",
    "assigned_source_segment_ids",
    "coverage_row_ids",
    "source_intake_notes",
}
GENERIC_CONTINUE_LABELS = {
    "",
    "continue",
    "go on",
    "next",
    "proceed",
    "继续",
    "继续前进",
    "下一步",
    "前进",
    "往前",
    "往前走",
}


def design_v2_root(run_root: Path) -> Path:
    return run_root / DESIGN_V2_ROOT


def design_v2_path(run_root: Path, relative: str | Path) -> Path:
    return design_v2_root(run_root) / relative


def ensure_design_v2_layout(run_root: Path) -> None:
    for relative in V2_DIRECTORIES:
        ensure_dir(design_v2_path(run_root, relative))


def load_v2_json(run_root: Path, relative: str, result: ValidationResult) -> Json | None:
    path = design_v2_path(run_root, relative)
    if not path.exists():
        result.add("error", "missing_artifact", f"Missing required V2 artifact: {DESIGN_V2_ROOT / relative}", str(DESIGN_V2_ROOT / relative))
        return None
    try:
        return read_json(path)
    except Exception as exc:  # noqa: BLE001
        result.add("error", "invalid_json", f"Cannot parse {DESIGN_V2_ROOT / relative}: {exc}", str(DESIGN_V2_ROOT / relative))
        return None


def load_optional_v2_json(path: Path, result: ValidationResult) -> Json | None:
    try:
        return read_json(path)
    except Exception as exc:  # noqa: BLE001
        result.add("error", "invalid_json", f"Cannot parse {path}: {exc}", str(path))
        return None


def list_subgraph_paths(run_root: Path) -> list[Path]:
    return sorted(design_v2_path(run_root, "subgraphs").glob("subgraph.*.json"))


def id_list(items: list[Any], key: str = "id") -> set[str]:
    return {item.get(key) for item in items if isinstance(item, dict) and isinstance(item.get(key), str)}


def unique_id_check(items: list[Any], artifact_path: str, result: ValidationResult, key: str = "id") -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            result.add("error", "schema", "Entries must be objects.", f"{artifact_path}[{index}]")
            continue
        item_id = item.get(key)
        if not isinstance(item_id, str) or not item_id.strip():
            result.add("error", "schema", "Entry needs a stable id.", f"{artifact_path}[{index}].{key}")
        elif item_id in seen:
            result.add("error", "duplicate_id", f"Duplicate id: {item_id}", f"{artifact_path}[{index}].{key}")
        else:
            seen.add(item_id)
    return seen


def dict_by_id(items: list[Any]) -> dict[str, Json]:
    return {item["id"]: item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def values_from_dicts(items: list[Any], key: str) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get(key), str):
            values.append(item[key])
    return values


def normalize_string_items(items: list[Any]) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, str):
            values.append(item)
        elif isinstance(item, dict) and isinstance(item.get("id"), str):
            values.append(item["id"])
    return values


def source_segment_ids_from(item: Any) -> set[str]:
    if not isinstance(item, dict):
        return set()
    refs: set[str] = set()
    for key in ("source_segment_ids", "covered_source_segment_ids", "assigned_source_segment_ids"):
        refs.update(str(value) for value in as_list(item.get(key)) if isinstance(value, str))
    source_trace = item.get("source_trace")
    if isinstance(source_trace, dict):
        refs.update(str(value) for value in as_list(source_trace.get("source_segment_ids")) if isinstance(value, str))
    return refs


def add_segment_reference_findings(
    result: ValidationResult,
    refs: set[str],
    segment_ids: set[str],
    path: str,
) -> None:
    for segment_id in sorted(refs):
        if segment_id not in segment_ids:
            result.add("error", "invalid_reference", f"References missing source segment: {segment_id}", path)


def source_span_segment_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    source_span = item.get("source_span")
    if not isinstance(source_span, dict):
        return None
    source_id = source_span.get("source_id")
    return source_id if isinstance(source_id, str) else None


def strip_internal_trace(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_internal_trace(item)
            for key, item in value.items()
            if key not in INTERNAL_TRACE_KEYS
        }
    if isinstance(value, list):
        return [strip_internal_trace(item) for item in value]
    return value


def state_ref_from_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("state_variable_id", "state", "id"):
            ref = value.get(key)
            if isinstance(ref, str):
                return ref
    return None


def state_refs_from_any(value: Any) -> set[str]:
    return set(STATE_REF_RE.findall(json.dumps(value, ensure_ascii=False)))


def wildcard_match(actor_id: str, allowed: list[str]) -> bool:
    if "*" in allowed:
        return True
    if actor_id in allowed:
        return True
    return any(pattern.endswith(".*") and actor_id.startswith(pattern[:-1]) for pattern in allowed)


def effective_permissions(variables: list[Json], permissions_payload: Json | None) -> dict[str, dict[str, list[str]]]:
    permissions: dict[str, dict[str, list[str]]] = {}
    for variable in variables:
        variable_id = variable.get("id")
        if not isinstance(variable_id, str):
            continue
        permissions[variable_id] = {
            "readable_by": [str(item) for item in as_list(variable.get("readable_by"))],
            "writable_by": [str(item) for item in as_list(variable.get("writable_by"))],
        }
    for entry in as_list((permissions_payload or {}).get("permissions")):
        if not isinstance(entry, dict):
            continue
        variable_id = entry.get("state_variable_id") or entry.get("id")
        if not isinstance(variable_id, str):
            continue
        permissions[variable_id] = {
            "readable_by": [str(item) for item in as_list(entry.get("readable_by"))],
            "writable_by": [str(item) for item in as_list(entry.get("writable_by"))],
        }
    return permissions


def permission_allows(permissions: dict[str, dict[str, list[str]]], variable_id: str, actor_id: str, mode: str) -> bool:
    key = "readable_by" if mode == "read" else "writable_by"
    allowed = permissions.get(variable_id, {}).get(key, [])
    return wildcard_match(actor_id, allowed)


def policy_payload_for_depth(artifacts: dict[str, Any], target_depth: int, parent_depths: dict[str, int] | None = None) -> Json:
    policy = dict(artifacts.get("control/mesh_expansion_policy.json", {}))
    policy["target_expansion_depth"] = target_depth
    policy["depth_budget_by_parent"] = [
        {"parent_ref_id": parent_ref, "target_expansion_depth": depth}
        for parent_ref, depth in sorted((parent_depths or {}).items())
    ]
    return policy


def artifacts_with_policy(artifacts: dict[str, Any], target_depth: int, parent_depths: dict[str, int] | None = None) -> dict[str, Any]:
    clone = dict(artifacts)
    clone["control/mesh_expansion_policy.json"] = policy_payload_for_depth(artifacts, target_depth, parent_depths)
    return clone


def reachable_node_ids(branch_graph: Json) -> set[str]:
    start_node_id = branch_graph.get("start_node_id")
    adjacency: dict[str, list[str]] = {}
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str):
            adjacency.setdefault(edge["from"], []).append(edge["to"])
    seen: set[str] = set()
    stack = [start_node_id] if isinstance(start_node_id, str) else []
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(adjacency.get(node_id, []))
    return seen


def branch_graph_simulation_profile(profile_id: str, target_depth: int, branch_graph: Json, enabled: list[Json]) -> Json:
    nodes = [node for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict) and isinstance(node.get("id"), str)]
    edges = [edge for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)]
    reachable = reachable_node_ids(branch_graph)
    outgoing: dict[str, int] = {}
    visible_outgoing: dict[str, int] = {}
    for edge in edges:
        if isinstance(edge.get("from"), str):
            outgoing[edge["from"]] = outgoing.get(edge["from"], 0) + 1
            if edge.get("condition_type", "player_choice") == "player_choice":
                visible_outgoing[edge["from"]] = visible_outgoing.get(edge["from"], 0) + 1
    terminal_ids = {
        node["id"]
        for node in nodes
        if node.get("is_terminal") is True or node.get("node_type") == "terminal" or outgoing.get(node["id"], 0) == 0
    }
    dead_end_ids = {
        node["id"]
        for node in nodes
        if outgoing.get(node["id"], 0) == 0 and node.get("is_terminal") is not True and node.get("node_type") != "terminal"
    }
    return {
        "id": profile_id,
        "target_expansion_depth": target_depth,
        "enabled_subgraph_ids": [str(subgraph.get("id")) for subgraph in enabled if isinstance(subgraph.get("id"), str)],
        "enabled_mesh_depths": sorted({subgraph_depth(subgraph) for subgraph in enabled}),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "reachable_node_ids": sorted(reachable),
        "unreachable_node_ids": sorted({node["id"] for node in nodes} - reachable),
        "terminal_node_ids": sorted(terminal_ids),
        "reachable_terminal_node_ids": sorted(terminal_ids & reachable),
        "dead_end_node_ids": sorted(dead_end_ids),
        "max_choice_count": max(visible_outgoing.values(), default=0),
    }


def build_simulation_profiles(artifacts: dict[str, Any]) -> Json:
    current_target_depth = policy_target_depth(artifacts)
    current_enabled = enabled_subgraphs(artifacts)
    current_branch_graph = compile_branch_graph(artifacts)
    parent_depth_overrides = policy_parent_depths(artifacts)
    max_depth = artifacts.get("control/mesh_expansion_policy.json", {}).get("max_expansion_depth")
    max_target_depth = max_depth if isinstance(max_depth, int) and max_depth >= 0 else current_target_depth
    max_artifacts = artifacts_with_policy(artifacts, max_target_depth, {})
    max_enabled = enabled_subgraphs(max_artifacts)
    max_branch_graph = compile_branch_graph(max_artifacts)
    current_profile = branch_graph_simulation_profile("profile.current_policy", current_target_depth, current_branch_graph, current_enabled)
    current_profile["parent_depth_overrides"] = parent_depth_overrides
    max_profile = branch_graph_simulation_profile("profile.max_depth", max_target_depth, max_branch_graph, max_enabled)
    max_profile["parent_depth_overrides"] = {}
    profiles = [current_profile, max_profile]
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV2Validator"},
        "profiles": profiles,
    }


def ending_resolver_macro_ids(artifacts: dict[str, Any]) -> set[str]:
    macro_graph = artifacts.get("macro/macro_story_graph.json", {})
    macro_nodes = [node for node in as_list(macro_graph.get("nodes")) if isinstance(node, dict)]
    terminal_macro_ids = {
        str(node.get("id"))
        for node in macro_nodes
        if isinstance(node.get("id"), str) and (node.get("is_terminal") is True or isinstance(node.get("ending_id"), str))
    }
    outgoing_to_terminals: dict[str, int] = {}
    for edge in as_list(macro_graph.get("edges")):
        if not isinstance(edge, dict):
            continue
        source = edge.get("from")
        target = edge.get("to")
        if isinstance(source, str) and target in terminal_macro_ids:
            outgoing_to_terminals[source] = outgoing_to_terminals.get(source, 0) + 1

    resolver_ids = {macro_id for macro_id, count in outgoing_to_terminals.items() if count >= 3}
    resolver_markers = ("final", "ending", "结局", "终局", "resolve", "resolver")
    for node in macro_nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        searchable = " ".join(str(node.get(key, "")) for key in ("id", "kind", "title", "summary")).lower()
        if len(as_list(node.get("allowed_exits"))) >= 3 and any(marker in searchable for marker in resolver_markers):
            resolver_ids.add(node_id)
    return resolver_ids


def branch_edge_root_macro_id(edge: Json, nodes_by_id: dict[str, Json]) -> str | None:
    root_macro_id = edge.get("root_macro_node_id")
    if isinstance(root_macro_id, str):
        return root_macro_id
    source = edge.get("from")
    if isinstance(source, str):
        source_node = nodes_by_id.get(source, {})
        for key in ("root_macro_node_id", "macro_node_id"):
            value = source_node.get(key)
            if isinstance(value, str):
                return value
    return None


def normalized_continue_label(label: Any) -> str:
    text = str(label or "").strip().lower()
    return re.sub(r"[\s\-_:：。.!！?？…]+", " ", text).strip()


def edge_state_effects(edge: Json) -> list[Json]:
    effects = as_list(edge.get("effects"))
    if not effects:
        effects = as_list(edge.get("state_writes"))
    return [effect for effect in effects if isinstance(effect, dict)]


def is_plain_continue_edge(edge: Json) -> bool:
    if edge.get("condition_type", "unconditional") != "unconditional":
        return False
    if as_list(edge.get("conditions")) or edge_state_effects(edge):
        return False
    return normalized_continue_label(edge.get("label")) in GENERIC_CONTINUE_LABELS


def add_adaptation_linearity_warnings(result: ValidationResult, artifacts: dict[str, Any], branch_graph: Json) -> None:
    input_mode = artifacts.get("source_intake/input_profile.json", {}).get("input_mode")
    if input_mode != "source_adaptation":
        return

    nodes = [node for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict) and isinstance(node.get("id"), str)]
    edges = [edge for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)]
    if len(nodes) < 4:
        return

    outgoing_by_from: dict[str, list[Json]] = {}
    incoming_by_to: dict[str, list[Json]] = {}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if isinstance(source, str):
            outgoing_by_from.setdefault(source, []).append(edge)
        if isinstance(target, str):
            incoming_by_to.setdefault(target, []).append(edge)

    visible_choice_count = sum(1 for edge in edges if edge.get("condition_type", "player_choice") == "player_choice")
    stateful_edge_count = sum(1 for edge in edges if as_list(edge.get("conditions")) or edge_state_effects(edge))
    if len(nodes) >= 5 and visible_choice_count < 2 and stateful_edge_count < 2:
        result.add(
            "warning",
            "adaptation_choice_underuse",
            f"Source adaptation compiles to {len(nodes)} nodes with only {visible_choice_count} visible choice edges and {stateful_edge_count} stateful edges; early novel sections usually need canon-safe branchlets or soft-state payoff reads.",
        )

    node_ids = {str(node["id"]) for node in nodes}
    visited: set[str] = set()
    for node in nodes:
        start_id = str(node["id"])
        if start_id in visited:
            continue
        incoming_plain = [edge for edge in incoming_by_to.get(start_id, []) if is_plain_continue_edge(edge)]
        if len(incoming_plain) == 1:
            continue
        chain_nodes = [start_id]
        chain_edges: list[Json] = []
        current_id = start_id
        while current_id in node_ids:
            outgoing = outgoing_by_from.get(current_id, [])
            if len(outgoing) != 1 or not is_plain_continue_edge(outgoing[0]):
                break
            edge = outgoing[0]
            target = edge.get("to")
            if not isinstance(target, str) or target in chain_nodes:
                break
            chain_edges.append(edge)
            chain_nodes.append(target)
            current_id = target
        visited.update(chain_nodes)
        if len(chain_edges) >= 3:
            result.add(
                "warning",
                "adaptation_linear_continue_streak",
                "Source adaptation contains a long generic continuation chain "
                f"({len(chain_edges)} edges): {' -> '.join(chain_nodes[:6])}"
                + (" ..." if len(chain_nodes) > 6 else "")
                + ". Add canon-safe branchlets or concrete transition handoff labels/summaries when the source permits.",
            )


def add_ending_resolver_findings(result: ValidationResult, artifacts: dict[str, Any], branch_graph: Json) -> None:
    resolver_macro_ids = ending_resolver_macro_ids(artifacts)
    if not resolver_macro_ids:
        return

    nodes_by_id = dict_by_id(as_list(branch_graph.get("nodes")))
    edges_by_root: dict[str, list[Json]] = {resolver_id: [] for resolver_id in resolver_macro_ids}
    for edge in as_list(branch_graph.get("edges")):
        if not isinstance(edge, dict):
            continue
        root_macro_id = branch_edge_root_macro_id(edge, nodes_by_id)
        if root_macro_id in resolver_macro_ids:
            edges_by_root.setdefault(root_macro_id, []).append(edge)

    ending_space = artifacts.get("adaptation/ending_space.json", {})
    enabled_endings = [
        ending for ending in as_list(ending_space.get("endings"))
        if isinstance(ending, dict) and ending.get("status") not in ("unavailable", "disabled")
    ]
    enabled_ending_count = len(enabled_endings)
    requirement_state_ids = set()
    for ending in enabled_endings:
        requirement_state_ids.update(state_refs_from_any(ending.get("state_requirements", [])))

    macro_nodes_by_id = dict_by_id(as_list(artifacts.get("macro/macro_story_graph.json", {}).get("nodes")))
    for resolver_id in sorted(resolver_macro_ids):
        resolver_edges = edges_by_root.get(resolver_id, [])
        visible_edges = [
            edge for edge in resolver_edges
            if edge.get("condition_type", "player_choice") == "player_choice"
        ]
        state_gate_edges = [
            edge for edge in resolver_edges
            if edge.get("condition_type") == "state_gate" and as_list(edge.get("conditions"))
        ]
        fallback_edges = [
            edge for edge in resolver_edges
            if edge.get("condition_type") in ("state_gate", "unconditional") and not as_list(edge.get("conditions"))
        ]
        if len(visible_edges) > 4:
            labels = ", ".join(str(edge.get("label") or edge.get("id") or "Continue") for edge in visible_edges[:6])
            result.add(
                "error",
                "ending_menu_overload",
                f"Ending resolver {resolver_id} exposes {len(visible_edges)} visible choices; resolve endings with state_gate routes and keep player-facing ending choice pressure small. Sample labels: {labels}.",
            )
        if enabled_ending_count > 2 and not state_gate_edges:
            result.add(
                "error",
                "ending_resolver_without_state_gate",
                f"Ending resolver {resolver_id} has {enabled_ending_count} enabled endings but no conditional state_gate payoff route.",
            )
        if state_gate_edges and not fallback_edges:
            result.add(
                "warning",
                "ending_resolver_without_fallback",
                f"Ending resolver {resolver_id} has state_gate routes but no unconditional fallback route.",
            )
        macro_node = macro_nodes_by_id.get(resolver_id, {})
        if macro_node.get("kind") == "choice" and enabled_ending_count > 2:
            result.add(
                "warning",
                "ending_resolver_as_choice",
                f"Macro node {resolver_id} is marked as a choice hub; complex ending settlement should normally be a convergence/resolver-style payoff.",
            )

    resolver_condition_state_ids: set[str] = set()
    for resolver_edges in edges_by_root.values():
        for edge in resolver_edges:
            resolver_condition_state_ids.update(state_refs_from_any(edge.get("conditions", [])))
    missing_requirement_state_ids = sorted(requirement_state_ids - resolver_condition_state_ids)
    if missing_requirement_state_ids:
        result.add(
            "warning",
            "ending_requirements_without_resolver_conditions",
            "Ending state requirements are not represented by resolver edge conditions: "
            + ", ".join(missing_requirement_state_ids),
        )


def add_design_quality_warnings(result: ValidationResult, artifacts: dict[str, Any], simulation_profiles: Json) -> None:
    profiles = [profile for profile in as_list(simulation_profiles.get("profiles")) if isinstance(profile, dict)]
    current_profile = next((profile for profile in profiles if profile.get("id") == "profile.current_policy"), profiles[0] if profiles else {})
    for node_id in as_list(current_profile.get("unreachable_node_ids")):
        result.add("warning", "simulation_unreachable_node", f"Compiled current-policy graph contains unreachable node: {node_id}")
    for node_id in as_list(current_profile.get("dead_end_node_ids")):
        result.add("warning", "simulation_dead_end", f"Compiled current-policy graph contains a non-terminal dead end: {node_id}")
    if not as_list(current_profile.get("reachable_terminal_node_ids")):
        result.add("warning", "simulation_no_terminal", "Compiled current-policy graph has no reachable terminal node.")
    if current_profile.get("max_choice_count", 0) > 4:
        result.add("warning", "pacing_choice_overload", f"A compiled node exposes {current_profile.get('max_choice_count')} outgoing choices.")

    branch_graph = compile_branch_graph(artifacts)
    add_ending_resolver_findings(result, artifacts, branch_graph)
    add_adaptation_linearity_warnings(result, artifacts, branch_graph)
    edges_by_from: dict[str, list[Json]] = {}
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            edges_by_from.setdefault(edge["from"], []).append(edge)
    repeated_choice_templates: dict[tuple[str, ...], list[str]] = {}
    for node_id, outgoing in edges_by_from.items():
        visible_labels = tuple(
            str(edge.get("label") or "Continue")
            for edge in outgoing
            if isinstance(edge, dict) and edge.get("condition_type", "player_choice") == "player_choice"
        )
        if len(visible_labels) > 1:
            repeated_choice_templates.setdefault(visible_labels, []).append(node_id)
        state_gates = [edge for edge in outgoing if isinstance(edge, dict) and edge.get("condition_type") == "state_gate"]
        if state_gates:
            has_fallback = any(
                isinstance(edge, dict)
                and edge.get("condition_type") in ("state_gate", "unconditional")
                and not as_list(edge.get("conditions"))
                for edge in outgoing
            )
            if not has_fallback:
                result.add("warning", "state_gate_without_fallback", f"Node {node_id} has state_gate routes without an unconditional fallback route.")
    for labels, node_ids in sorted(repeated_choice_templates.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(node_ids) >= 4:
            sample = ", ".join(node_ids[:4])
            result.add(
                "warning",
                "repeated_choice_template",
                f"The same visible choice set appears on {len(node_ids)} nodes ({sample}); labels: {', '.join(labels)}.",
            )

    written_state_ids: set[str] = set()
    read_state_ids: set[str] = set()
    for macro_edge in as_list(artifacts.get("macro/macro_story_graph.json", {}).get("edges")):
        if isinstance(macro_edge, dict):
            for condition in as_list(macro_edge.get("conditions")):
                if isinstance(condition, dict) and isinstance(condition.get("state_variable_id"), str):
                    read_state_ids.add(condition["state_variable_id"])
    for subgraph in as_list(artifacts.get("_subgraphs")):
        if not isinstance(subgraph, dict):
            continue
        for edge in as_list(subgraph.get("edges")):
            if not isinstance(edge, dict):
                continue
            for condition in as_list(edge.get("conditions")):
                if isinstance(condition, dict) and isinstance(condition.get("state_variable_id"), str):
                    read_state_ids.add(condition["state_variable_id"])
            for effect in as_list(edge.get("effects") or edge.get("state_writes")):
                if isinstance(effect, dict) and isinstance(effect.get("state_variable_id"), str):
                    written_state_ids.add(effect["state_variable_id"])
        for node in as_list(subgraph.get("nodes")):
            if not isinstance(node, dict):
                continue
            for condition in as_list(node.get("preconditions") or node.get("conditions")):
                if isinstance(condition, dict) and isinstance(condition.get("state_variable_id"), str):
                    read_state_ids.add(condition["state_variable_id"])
            for effect in as_list(node.get("state_writes")):
                if isinstance(effect, dict) and isinstance(effect.get("state_variable_id"), str):
                    written_state_ids.add(effect["state_variable_id"])
    for contract in as_list(artifacts.get("macro/macro_node_contracts.json", {}).get("contracts")):
        if not isinstance(contract, dict):
            continue
        for exit_item in as_list(contract.get("exits")):
            if not isinstance(exit_item, dict):
                continue
            for effect in as_list(exit_item.get("effects")):
                if isinstance(effect, dict) and isinstance(effect.get("state_variable_id"), str):
                    written_state_ids.add(effect["state_variable_id"])
    for state_id in sorted(written_state_ids - read_state_ids):
        result.add("warning", "state_without_payoff", f"State variable is written but not read by any V2 edge or node condition: {state_id}")

    policy = artifacts.get("control/mesh_expansion_policy.json", {})
    budget = policy.get("default_branching_budget") if isinstance(policy, dict) else {}
    max_nodes = budget.get("max_nodes_per_subgraph") if isinstance(budget, dict) else None
    max_edges = budget.get("max_edges_per_subgraph") if isinstance(budget, dict) else None
    for subgraph in as_list(artifacts.get("_subgraphs")):
        if not isinstance(subgraph, dict):
            continue
        subgraph_id = subgraph.get("id", "<unknown>")
        node_count = len(as_list(subgraph.get("nodes")))
        edge_count = len(as_list(subgraph.get("edges")))
        if isinstance(max_nodes, int) and node_count > max_nodes:
            result.add("warning", "pacing_budget", f"Subgraph {subgraph_id} has {node_count} nodes, above default budget {max_nodes}.")
        if isinstance(max_edges, int) and edge_count > max_edges:
            result.add("warning", "pacing_budget", f"Subgraph {subgraph_id} has {edge_count} edges, above default budget {max_edges}.")

    fixed_fact_ids = {str(item) for item in as_list(artifacts.get("adaptation/adaptation_policy.json", {}).get("fixed_fact_ids"))}
    used_source_ids: set[str] = set()
    for contract in as_list(artifacts.get("macro/macro_node_contracts.json", {}).get("contracts")):
        if isinstance(contract, dict):
            used_source_ids.update(str(item) for item in as_list(contract.get("source_fact_ids")))
    for subgraph in as_list(artifacts.get("_subgraphs")):
        if not isinstance(subgraph, dict):
            continue
        for node in as_list(subgraph.get("nodes")):
            if isinstance(node, dict):
                used_source_ids.update(str(item) for item in as_list(node.get("source_fact_ids")))
    for fact_id in sorted(fixed_fact_ids - used_source_ids):
        result.add("warning", "theme_drift", f"Fixed fact is validated but not anchored in any macro contract or mesh node: {fact_id}")
    themes = normalize_string_items(as_list(artifacts.get("source_facts/theme_constraints.json", {}).get("themes")))
    if not themes:
        result.add("warning", "theme_drift", "No theme ids are declared for V2 drift checks.")


def validate_source_intake_core(artifacts: dict[str, Any], result: ValidationResult) -> Json:
    input_profile = artifacts["source_intake/input_profile.json"]
    segments_payload = artifacts["source_intake/source_segments.json"]
    beat_table = artifacts["source_intake/source_beat_table.json"]
    coverage_matrix = artifacts["source_intake/adaptation_coverage_matrix.json"]

    input_mode = input_profile.get("input_mode")
    if input_mode not in ("idea", "source_adaptation"):
        result.add(
            "error",
            "schema",
            "input_profile.input_mode must be 'idea' or 'source_adaptation'.",
            "source_intake.input_profile.input_mode",
        )
        input_mode = "idea"
    source_kind = input_profile.get("source_kind")
    if not isinstance(source_kind, str) or not source_kind:
        result.add("error", "schema", "input_profile.source_kind is required.", "source_intake.input_profile.source_kind")
    coverage_policy = input_profile.get("coverage_policy")
    if coverage_policy not in ("inventive", "faithful_adaptation"):
        result.add(
            "warning",
            "schema",
            "input_profile.coverage_policy should be 'inventive' or 'faithful_adaptation'.",
            "source_intake.input_profile.coverage_policy",
        )

    segments = [item for item in as_list(segments_payload.get("segments")) if isinstance(item, dict)]
    segment_ids = unique_id_check(segments, "source_intake.source_segments.segments", result)
    if not segments:
        result.add("error", "schema", "source_segments.segments must contain at least one segment.", "source_intake.source_segments.segments")

    segment_importance: dict[str, str] = {}
    segment_freedom: dict[str, str] = {}
    for index, segment in enumerate(segments):
        segment_id = segment.get("id")
        importance = segment.get("importance", "optional")
        freedom = segment.get("adaptation_freedom", "expandable")
        span = segment.get("source_span") if isinstance(segment.get("source_span"), dict) else {}
        if importance not in ("must_cover", "compressible", "optional"):
            result.add(
                "error",
                "schema",
                f"Unsupported segment importance: {importance}",
                f"source_intake.source_segments.segments[{index}].importance",
            )
        if freedom not in ("locked", "expandable", "reinterpret_allowed"):
            result.add(
                "error",
                "schema",
                f"Unsupported segment adaptation_freedom: {freedom}",
                f"source_intake.source_segments.segments[{index}].adaptation_freedom",
            )
        if isinstance(segment_id, str):
            segment_importance[segment_id] = str(importance)
            segment_freedom[segment_id] = str(freedom)
        if input_mode == "idea" and isinstance(segment_id, str) and not segment_id.startswith("idea."):
            result.add(
                "warning",
                "idea_segment_id",
                f"Idea-mode synthetic segment id should normally use the idea.* namespace: {segment_id}",
                f"source_intake.source_segments.segments[{index}].id",
            )
        normalized_source_kind = str(source_kind).lower()
        if input_mode == "source_adaptation" and "novel" in normalized_source_kind:
            start = span.get("start")
            end = span.get("end")
            if isinstance(start, int) and isinstance(end, int) and end - start > 2500:
                result.add(
                    "warning",
                    "coarse_novel_segment",
                    f"Novel source segment is broad; split chapters into scene/dialogue beats when preserving detail: {segment_id}",
                    f"source_intake.source_segments.segments[{index}].source_span",
                )

    beats = [item for item in as_list(beat_table.get("beats")) if isinstance(item, dict)]
    unique_id_check(beats, "source_intake.source_beat_table.beats", result)
    for index, beat in enumerate(beats):
        refs = source_segment_ids_from(beat) or {str(item) for item in as_list(beat.get("segment_ids")) if isinstance(item, str)}
        if not refs:
            result.add("warning", "beat_without_segment", "Source beat has no source segment reference.", f"source_intake.source_beat_table.beats[{index}]")
        add_segment_reference_findings(result, refs, segment_ids, f"source_intake.source_beat_table.beats[{index}].source_segment_ids")

    normalized_source_kind = str(source_kind).lower()
    if input_mode == "source_adaptation" and (
        normalized_source_kind in ("novel", "full_novel", "fiction") or "novel" in normalized_source_kind
    ):
        chapter_count = input_profile.get("chapter_count")
        if isinstance(chapter_count, int) and chapter_count > 0 and len(segments) <= chapter_count:
            result.add(
                "warning",
                "chapter_level_novel_segments",
                "Novel adaptation currently has no more source segments than chapters; use chapter groups plus finer scene/dialogue segments to preserve detail.",
                "source_intake.source_segments.segments",
            )

    rows = [item for item in as_list(coverage_matrix.get("coverage")) if isinstance(item, dict)]
    coverage_row_ids = unique_id_check(rows, "source_intake.adaptation_coverage_matrix.coverage", result)
    coverage_by_segment: dict[str, Json] = {}
    for index, row in enumerate(rows):
        segment_id = row.get("segment_id")
        if segment_id not in segment_ids:
            result.add(
                "error",
                "invalid_reference",
                f"Coverage row references missing source segment: {segment_id}",
                f"source_intake.adaptation_coverage_matrix.coverage[{index}].segment_id",
            )
            continue
        if segment_id in coverage_by_segment:
            result.add(
                "error",
                "duplicate_id",
                f"Duplicate coverage row for source segment: {segment_id}",
                f"source_intake.adaptation_coverage_matrix.coverage[{index}].segment_id",
            )
        coverage_by_segment[str(segment_id)] = row
        status = row.get("coverage_status", row.get("status"))
        if status not in ("covered", "compressed", "omitted", "deferred"):
            result.add(
                "error",
                "schema",
                f"Unsupported coverage status: {status}",
                f"source_intake.adaptation_coverage_matrix.coverage[{index}].coverage_status",
            )
        if status == "omitted" and not row.get("reason"):
            result.add(
                "error",
                "coverage_without_reason",
                f"Omitted source segment needs a reason: {segment_id}",
                f"source_intake.adaptation_coverage_matrix.coverage[{index}].reason",
            )

    if input_mode == "source_adaptation":
        for segment_id in sorted(segment_ids - set(coverage_by_segment)):
            result.add(
                "error",
                "missing_coverage_row",
                f"Every source segment needs an adaptation coverage row in source_adaptation mode: {segment_id}",
                "source_intake.adaptation_coverage_matrix.coverage",
            )
        for segment_id, importance in sorted(segment_importance.items()):
            row = coverage_by_segment.get(segment_id, {})
            status = row.get("coverage_status", row.get("status"))
            if importance == "must_cover" and status != "covered":
                result.add(
                    "error",
                    "must_cover_segment_not_covered",
                    f"Must-cover source segment must be covered, not {status}: {segment_id}",
                    f"source_intake.adaptation_coverage_matrix.coverage[{segment_id}]",
                )
            if importance == "compressible" and status in ("omitted", "deferred"):
                result.add(
                    "warning",
                    "compressible_segment_not_represented",
                    f"Compressible source segment is not represented in the current design: {segment_id}",
                    f"source_intake.adaptation_coverage_matrix.coverage[{segment_id}]",
                )

    return {
        "input_mode": input_mode,
        "source_kind": source_kind,
        "coverage_policy": coverage_policy,
        "segments": segments,
        "segment_ids": segment_ids,
        "segment_importance": segment_importance,
        "segment_freedom": segment_freedom,
        "coverage_rows": rows,
        "coverage_row_ids": coverage_row_ids,
        "coverage_by_segment": coverage_by_segment,
    }


def validate_source_adaptation_coverage(
    result: ValidationResult,
    intake: Json,
    artifacts: dict[str, Any],
    macro_nodes: list[Json],
    contracts: list[Json],
    subgraphs: list[Json],
) -> Json:
    segment_ids = set(intake.get("segment_ids", set()))
    if not segment_ids:
        return {"status": "skipped", "reason": "no source segments"}

    input_mode = intake.get("input_mode")
    segment_freedom = intake.get("segment_freedom", {})
    coverage_by_segment = intake.get("coverage_by_segment", {})
    actual_refs: dict[str, dict[str, list[str]]] = {
        segment_id: {
            "macro_node_ids": [],
            "contract_ids": [],
            "subgraph_ids": [],
            "subgraph_node_ids": [],
            "edge_ids": [],
            "ending_ids": [],
            "process_ids": [],
        }
        for segment_id in segment_ids
    }

    def add_refs(bucket: str, owner_id: str | None, refs: set[str], path: str) -> None:
        add_segment_reference_findings(result, refs, segment_ids, path)
        if not owner_id:
            return
        for segment_id in refs:
            if segment_id in actual_refs:
                actual_refs[segment_id].setdefault(bucket, []).append(owner_id)

    macro_segment_refs: dict[str, set[str]] = {}
    for index, macro_node in enumerate(macro_nodes):
        macro_id = macro_node.get("id")
        refs = source_segment_ids_from(macro_node)
        add_refs("macro_node_ids", macro_id if isinstance(macro_id, str) else None, refs, f"macro.macro_story_graph.nodes[{index}].source_segment_ids")
        if isinstance(macro_id, str):
            macro_segment_refs[macro_id] = refs
        if input_mode == "source_adaptation" and not refs:
            result.add(
                "error",
                "adaptation_node_without_source_segment",
                f"Macro node needs source_segment_ids in source_adaptation mode: {macro_id}",
                f"macro.macro_story_graph.nodes[{index}].source_segment_ids",
            )

    for index, macro_edge in enumerate(as_list(artifacts["macro/macro_story_graph.json"].get("edges"))):
        if not isinstance(macro_edge, dict):
            continue
        edge_id = macro_edge.get("id")
        refs = source_segment_ids_from(macro_edge)
        add_refs("edge_ids", edge_id if isinstance(edge_id, str) else None, refs, f"macro.macro_story_graph.edges[{index}].source_segment_ids")
        if input_mode == "source_adaptation" and macro_edge.get("condition_type", "player_choice") == "player_choice" and not refs:
            result.add(
                "error",
                "adaptation_choice_without_source_segment",
                f"Macro player-visible choice edge needs source_segment_ids in source_adaptation mode: {edge_id}",
                f"macro.macro_story_graph.edges[{index}].source_segment_ids",
            )
        source_macro_refs = macro_segment_refs.get(str(macro_edge.get("from")), set())
        if source_macro_refs and refs - source_macro_refs:
            result.add(
                "error",
                "segment_distribution_violation",
                f"Macro edge {edge_id} references source segments outside its source macro node packet: {', '.join(sorted(refs - source_macro_refs))}",
                f"macro.macro_story_graph.edges[{index}].source_segment_ids",
            )

    contract_segment_refs: dict[str, set[str]] = {}
    contract_ids = id_list(contracts)
    for index, contract in enumerate(contracts):
        contract_id = contract.get("id")
        macro_id = contract.get("macro_node_id")
        refs = source_segment_ids_from(contract)
        add_refs("contract_ids", contract_id if isinstance(contract_id, str) else None, refs, f"macro.macro_node_contracts.contracts[{index}].source_segment_ids")
        if isinstance(contract_id, str):
            contract_segment_refs[contract_id] = refs
        if input_mode == "source_adaptation" and not refs:
            result.add(
                "error",
                "adaptation_contract_without_source_segment",
                f"Macro contract needs source_segment_ids in source_adaptation mode: {contract_id}",
                f"macro.macro_node_contracts.contracts[{index}].source_segment_ids",
            )
        macro_refs = macro_segment_refs.get(str(macro_id), set())
        missing_macro_refs = macro_refs - refs
        if input_mode == "source_adaptation" and missing_macro_refs:
            result.add(
                "error",
                "contract_missing_macro_segment",
                f"Contract {contract_id} does not carry macro node source coverage: {', '.join(sorted(missing_macro_refs))}",
                f"macro.macro_node_contracts.contracts[{index}].source_segment_ids",
            )

    subgraph_node_segment_refs: dict[str, set[str]] = {}
    subgraph_ids = id_list(subgraphs)
    for subgraph in sorted(subgraphs, key=lambda item: int(item.get("expansion_depth", 0)) if isinstance(item.get("expansion_depth"), int) else 9999):
        subgraph_id = subgraph.get("id")
        root_macro_id = subgraph_root_macro(subgraph)
        parent_ref_id = subgraph_parent_ref(subgraph)
        artifact_path = str(subgraph.get("_artifact_path", "workspace/design_layer_v2/subgraphs"))
        contract = next((item for item in contracts if item.get("macro_node_id") == root_macro_id), {})
        contract_refs = source_segment_ids_from(contract)
        parent_allowed_refs = contract_refs
        if subgraph.get("parent_ref_kind") == "subgraph_node":
            parent_allowed_refs = subgraph_node_segment_refs.get(parent_ref_id, contract_refs)
        refs = source_segment_ids_from(subgraph)
        add_refs("subgraph_ids", subgraph_id if isinstance(subgraph_id, str) else None, refs, f"{artifact_path}.source_segment_ids")
        if input_mode == "source_adaptation" and not refs:
            result.add("error", "adaptation_subgraph_without_source_segment", f"Subgraph needs source_segment_ids: {subgraph_id}", f"{artifact_path}.source_segment_ids")
        if parent_allowed_refs and refs - parent_allowed_refs:
            result.add(
                "error",
                "segment_distribution_violation",
                f"Subgraph {subgraph_id} references source segments outside its assigned parent packet: {', '.join(sorted(refs - parent_allowed_refs))}",
                f"{artifact_path}.source_segment_ids",
            )
        local_allowed_refs = refs or parent_allowed_refs
        for node_index, local_node in enumerate(as_list(subgraph.get("nodes"))):
            if not isinstance(local_node, dict):
                continue
            node_id = local_node.get("id")
            node_refs = source_segment_ids_from(local_node)
            add_refs("subgraph_node_ids", node_id if isinstance(node_id, str) else None, node_refs, f"{artifact_path}.nodes[{node_index}].source_segment_ids")
            if input_mode == "source_adaptation" and not node_refs:
                result.add("error", "adaptation_node_without_source_segment", f"Subgraph node needs source_segment_ids: {node_id}", f"{artifact_path}.nodes[{node_index}].source_segment_ids")
            if local_allowed_refs and node_refs - local_allowed_refs:
                result.add(
                    "error",
                    "segment_distribution_violation",
                    f"Subgraph node {node_id} references source segments outside its assigned parent packet: {', '.join(sorted(node_refs - local_allowed_refs))}",
                    f"{artifact_path}.nodes[{node_index}].source_segment_ids",
                )
            if isinstance(node_id, str):
                subgraph_node_segment_refs[node_id] = node_refs or local_allowed_refs
        for edge_index, edge in enumerate(as_list(subgraph.get("edges"))):
            if not isinstance(edge, dict):
                continue
            edge_id = edge.get("id")
            edge_refs = source_segment_ids_from(edge)
            add_refs("edge_ids", edge_id if isinstance(edge_id, str) else None, edge_refs, f"{artifact_path}.edges[{edge_index}].source_segment_ids")
            if input_mode == "source_adaptation" and edge.get("condition_type", "player_choice") == "player_choice" and not edge_refs:
                result.add(
                    "error",
                    "adaptation_choice_without_source_segment",
                    f"Player-visible choice edge needs source_segment_ids in source_adaptation mode: {edge_id}",
                    f"{artifact_path}.edges[{edge_index}].source_segment_ids",
                )
            if local_allowed_refs and edge_refs - local_allowed_refs:
                result.add(
                    "error",
                    "segment_distribution_violation",
                    f"Subgraph edge {edge_id} references source segments outside its assigned parent packet: {', '.join(sorted(edge_refs - local_allowed_refs))}",
                    f"{artifact_path}.edges[{edge_index}].source_segment_ids",
                )

    adaptation = artifacts["adaptation/adaptation_policy.json"]
    for index, process in enumerate(as_list(adaptation.get("variable_processes"))):
        if not isinstance(process, dict):
            continue
        process_id = process.get("id")
        refs = source_segment_ids_from(process)
        add_refs("process_ids", process_id if isinstance(process_id, str) else None, refs, f"adaptation.adaptation_policy.variable_processes[{index}].source_segment_ids")
        if input_mode == "source_adaptation":
            if not refs:
                result.add(
                    "error",
                    "variable_process_without_source_segment",
                    f"Variable process needs source_segment_ids in source_adaptation mode: {process_id}",
                    f"adaptation.adaptation_policy.variable_processes[{index}].source_segment_ids",
                )
            elif not any(segment_freedom.get(segment_id) in ("expandable", "reinterpret_allowed") for segment_id in refs):
                result.add(
                    "error",
                    "variation_without_permission",
                    f"Variable process has no expandable or reinterpret_allowed source segment: {process_id}",
                    f"adaptation.adaptation_policy.variable_processes[{index}].source_segment_ids",
                )
    for index, ending in enumerate(as_list(adaptation.get("variable_endings"))):
        if isinstance(ending, dict):
            refs = source_segment_ids_from(ending)
            add_refs("ending_ids", ending.get("id") if isinstance(ending.get("id"), str) else None, refs, f"adaptation.adaptation_policy.variable_endings[{index}].source_segment_ids")

    ending_space = artifacts["adaptation/ending_space.json"]
    for index, ending in enumerate(as_list(ending_space.get("endings"))):
        if not isinstance(ending, dict):
            continue
        ending_id = ending.get("id")
        refs = source_segment_ids_from(ending)
        add_refs("ending_ids", ending_id if isinstance(ending_id, str) else None, refs, f"adaptation.ending_space.endings[{index}].source_segment_ids")
        if input_mode == "source_adaptation" and ending.get("status") not in ("unavailable", "disabled") and not refs:
            result.add(
                "error",
                "ending_without_source_tension",
                f"Enabled ending needs source_segment_ids in source_adaptation mode: {ending_id}",
                f"adaptation.ending_space.endings[{index}].source_segment_ids",
            )

    coverage_rows = []
    known_macro_ids = id_list(macro_nodes)
    known_node_ids = set(subgraph_node_segment_refs) | {
        branch_node_id_for_macro(str(macro_node.get("id")))
        for macro_node in macro_nodes
        if isinstance(macro_node, dict) and isinstance(macro_node.get("id"), str)
    }
    for index, row in enumerate(as_list(artifacts["source_intake/adaptation_coverage_matrix.json"].get("coverage"))):
        if not isinstance(row, dict):
            continue
        segment_id = row.get("segment_id")
        if segment_id not in segment_ids:
            continue
        covered_by = row.get("covered_by") if isinstance(row.get("covered_by"), dict) else {}
        for bucket, known in (
            ("macro_node_ids", known_macro_ids),
            ("contract_ids", contract_ids),
            ("subgraph_ids", subgraph_ids),
            ("subgraph_node_ids", known_node_ids),
        ):
            for ref_id in as_list(covered_by.get(bucket) or row.get(bucket)):
                if ref_id not in known:
                    result.add(
                        "error",
                        "invalid_reference",
                        f"Coverage row references missing {bucket[:-1]}: {ref_id}",
                        f"source_intake.adaptation_coverage_matrix.coverage[{index}].covered_by.{bucket}",
                    )
        status = row.get("coverage_status", row.get("status"))
        declared_refs = {
            bucket: [str(item) for item in as_list(covered_by.get(bucket) or row.get(bucket))]
            for bucket in ("macro_node_ids", "contract_ids", "subgraph_ids", "subgraph_node_ids")
        }
        has_declared_refs = any(declared_refs.values())
        has_actual_refs = any(actual_refs.get(str(segment_id), {}).get(bucket) for bucket in actual_refs.get(str(segment_id), {}))
        if input_mode == "source_adaptation" and status in ("covered", "compressed") and not has_actual_refs and not has_declared_refs:
            result.add(
                "error",
                "coverage_without_anchor",
                f"Covered source segment has no macro/contract/subgraph anchor: {segment_id}",
                f"source_intake.adaptation_coverage_matrix.coverage[{index}]",
            )
        coverage_rows.append({
            "segment_id": segment_id,
            "coverage_status": status,
            "importance": intake.get("segment_importance", {}).get(segment_id),
            "adaptation_freedom": segment_freedom.get(segment_id),
            "actual_refs": actual_refs.get(str(segment_id), {}),
            "declared_refs": declared_refs,
            "reason": row.get("reason", ""),
        })

    return {
        "status": "pass" if result.status != "fail" else "fail",
        "input_mode": input_mode,
        "segment_count": len(segment_ids),
        "coverage": coverage_rows,
    }


def validate_design_v2(run_root: Path, write_report: bool = True) -> ValidationResult:
    ensure_design_v2_layout(run_root)
    result = ValidationResult()
    artifacts: dict[str, Json] = {}
    for relative in REQUIRED_V2_FILES:
        payload = load_v2_json(run_root, relative, result)
        if payload is not None:
            artifacts[relative] = payload

    subgraphs: list[Json] = []
    for path in list_subgraph_paths(run_root):
        payload = load_optional_v2_json(path, result)
        if payload is not None:
            payload["_artifact_path"] = str(path.relative_to(run_root))
            subgraphs.append(payload)

    if result.status == "fail":
        if write_report:
            write_json(run_root / DESIGN_V2_VALIDATION_REPORT, result.to_json())
        return result

    source_intake = validate_source_intake_core(artifacts, result)
    segment_ids = set(source_intake.get("segment_ids", set()))

    fact_book = artifacts["source_facts/fact_book.json"]
    character_graph = artifacts["source_facts/character_graph.json"]
    event_timeline = artifacts["source_facts/event_timeline.json"]
    theme_constraints = artifacts["source_facts/theme_constraints.json"]
    adaptation_policy = artifacts["adaptation/adaptation_policy.json"]
    canon_locks = artifacts["adaptation/canon_lock_table.json"]
    variable_processes_payload = artifacts["adaptation/variable_process_table.json"]
    ending_space = artifacts["adaptation/ending_space.json"]
    state_model = artifacts["state/world_state_model.json"]
    state_permissions = artifacts["state/state_permissions.json"]
    state_invariants = artifacts["state/state_invariants.json"]
    macro_graph = artifacts["macro/macro_story_graph.json"]
    macro_contracts = artifacts["macro/macro_node_contracts.json"]
    mesh_expansion_policy = artifacts["control/mesh_expansion_policy.json"]
    route_merge_policy = artifacts["control/route_merge_policy.json"]

    facts = as_list(fact_book.get("facts"))
    fact_ids = unique_id_check(facts, "source_facts.fact_book.facts", result)
    fact_segment_refs: dict[str, set[str]] = {}
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        refs = source_segment_ids_from(fact)
        span_segment_id = source_span_segment_id(fact)
        if span_segment_id in segment_ids:
            refs.add(span_segment_id)
        add_segment_reference_findings(result, refs, segment_ids, f"source_facts.fact_book.facts[{index}].source_segment_ids")
        fact_id = fact.get("id")
        if isinstance(fact_id, str):
            fact_segment_refs[fact_id] = refs
    characters = as_list(character_graph.get("characters"))
    character_ids = unique_id_check(characters, "source_facts.character_graph.characters", result)
    relationships = as_list(character_graph.get("relationships"))
    unique_id_check(relationships, "source_facts.character_graph.relationships", result)
    events = as_list(event_timeline.get("events"))
    event_ids = unique_id_check(events, "source_facts.event_timeline.events", result)
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        refs = source_segment_ids_from(event)
        add_segment_reference_findings(result, refs, segment_ids, f"source_facts.event_timeline.events[{index}].source_segment_ids")
    themes = as_list(theme_constraints.get("themes"))
    theme_ids = set(normalize_string_items(themes))
    source_ids = fact_ids | event_ids

    fixed_fact_ids = [str(item) for item in as_list(adaptation_policy.get("fixed_fact_ids"))]
    for fact_id in fixed_fact_ids:
        if fact_id not in fact_ids:
            result.add("error", "invalid_reference", f"Fixed fact references missing fact: {fact_id}", "adaptation.adaptation_policy.fixed_fact_ids")
        elif source_intake.get("input_mode") == "source_adaptation" and not fact_segment_refs.get(fact_id):
            result.add(
                "error",
                "fixed_fact_without_source_segment",
                f"Fixed fact needs a source segment anchor in source_adaptation mode: {fact_id}",
                "source_facts.fact_book.facts.source_segment_ids",
            )
    for process_index, process in enumerate(as_list(adaptation_policy.get("variable_processes"))):
        if not isinstance(process, dict):
            result.add("error", "schema", "Variable process entries must be objects.", f"adaptation.adaptation_policy.variable_processes[{process_index}]")
            continue
        if not isinstance(process.get("id"), str):
            result.add("error", "schema", "Variable process needs id.", f"adaptation.adaptation_policy.variable_processes[{process_index}].id")
        for fact_id in as_list(process.get("allowed_fact_ids")):
            if fact_id not in fact_ids:
                result.add("error", "invalid_reference", f"Variable process references missing fact: {fact_id}", f"adaptation.adaptation_policy.variable_processes[{process_index}].allowed_fact_ids")

    for locked_fact_id in as_list(canon_locks.get("locked_fact_ids")):
        if locked_fact_id not in fact_ids:
            result.add("error", "invalid_reference", f"Canon lock references missing fact: {locked_fact_id}", "adaptation.canon_lock_table.locked_fact_ids")
        elif source_intake.get("input_mode") == "source_adaptation" and not fact_segment_refs.get(str(locked_fact_id)):
            result.add(
                "error",
                "locked_fact_without_source_segment",
                f"Locked fact needs a source segment anchor in source_adaptation mode: {locked_fact_id}",
                "source_facts.fact_book.facts.source_segment_ids",
            )
    for lock_index, lock in enumerate(as_list(canon_locks.get("locks"))):
        if isinstance(lock, dict):
            fact_id = lock.get("fact_id")
            if fact_id not in fact_ids:
                result.add("error", "invalid_reference", f"Canon lock references missing fact: {fact_id}", f"adaptation.canon_lock_table.locks[{lock_index}].fact_id")
    if source_intake.get("input_mode") == "source_adaptation":
        for fact in facts:
            if isinstance(fact, dict) and fact.get("locked") is True and isinstance(fact.get("id"), str) and not fact_segment_refs.get(fact["id"]):
                result.add(
                    "error",
                    "locked_fact_without_source_segment",
                    f"Locked fact needs a source segment anchor in source_adaptation mode: {fact['id']}",
                    "source_facts.fact_book.facts.source_segment_ids",
                )

    process_ids = unique_id_check(as_list(variable_processes_payload.get("processes")), "adaptation.variable_process_table.processes", result)
    policy_process_ids = id_list(as_list(adaptation_policy.get("variable_processes")))
    for process_id in process_ids | policy_process_ids:
        if process_id and process_id not in process_ids:
            result.add("warning", "missing_process_detail", f"Policy process lacks variable_process_table detail: {process_id}")

    variables = [item for item in as_list(state_model.get("variables")) if isinstance(item, dict)]
    state_ids = unique_id_check(variables, "state.world_state_model.variables", result)
    for index, variable in enumerate(variables):
        variable_id = variable.get("id")
        if variable.get("type") not in ("boolean", "integer", "number", "string", "enum"):
            result.add("error", "schema", f"Unsupported state variable type: {variable.get('type')}", f"state.world_state_model.variables[{index}].type")
        if "initial_value" not in variable:
            result.add("error", "schema", "State variable needs initial_value.", f"state.world_state_model.variables[{index}].initial_value")
        if not as_list(variable.get("readable_by")):
            result.add("error", "schema", "State variable needs readable_by permissions.", f"state.world_state_model.variables[{index}].readable_by")
        if not as_list(variable.get("writable_by")):
            result.add("error", "schema", "State variable needs writable_by permissions.", f"state.world_state_model.variables[{index}].writable_by")
        if not as_list(variable.get("invariants")):
            result.add("warning", "missing_invariants", f"State variable has no invariants: {variable_id}", f"state.world_state_model.variables[{index}].invariants")
    permission_map = effective_permissions(variables, state_permissions)
    for index, permission in enumerate(as_list(state_permissions.get("permissions"))):
        if not isinstance(permission, dict):
            result.add("error", "schema", "Permission entries must be objects.", f"state.state_permissions.permissions[{index}]")
            continue
        variable_id = permission.get("state_variable_id") or permission.get("id")
        if variable_id not in state_ids:
            result.add("error", "invalid_reference", f"Permission references missing state variable: {variable_id}", f"state.state_permissions.permissions[{index}]")
    for index, invariant in enumerate(as_list(state_invariants.get("invariants"))):
        if not isinstance(invariant, dict):
            result.add("error", "schema", "Invariant entries must be objects.", f"state.state_invariants.invariants[{index}]")
            continue
        for variable_id in set(as_list(invariant.get("state_variable_ids"))) | state_refs_from_any(invariant.get("expression", "")):
            if variable_id not in state_ids:
                result.add("error", "invalid_reference", f"Invariant references missing state variable: {variable_id}", f"state.state_invariants.invariants[{index}]")

    macro_nodes = [item for item in as_list(macro_graph.get("nodes")) if isinstance(item, dict)]
    macro_node_ids = unique_id_check(macro_nodes, "macro.macro_story_graph.nodes", result)
    macro_nodes_by_id = dict_by_id(macro_nodes)
    start_macro_id = macro_graph.get("start_macro_node_id")
    if start_macro_id not in macro_node_ids:
        result.add("error", "missing_start", f"start_macro_node_id must reference a macro node: {start_macro_id}", "macro.macro_story_graph.start_macro_node_id")
    macro_edges = [item for item in as_list(macro_graph.get("edges")) if isinstance(item, dict)]
    unique_id_check(macro_edges, "macro.macro_story_graph.edges", result)
    macro_allowed_exits = {
        macro_node["id"]: {str(exit_id) for exit_id in as_list(macro_node.get("allowed_exits"))}
        for macro_node in macro_nodes
        if isinstance(macro_node.get("id"), str)
    }
    for index, edge in enumerate(macro_edges):
        for key in ("from", "to"):
            ref = edge.get(key)
            if ref not in macro_node_ids:
                result.add("error", "invalid_reference", f"Macro edge references missing {key} node: {ref}", f"macro.macro_story_graph.edges[{index}].{key}")
        exit_id = edge.get("exit_id") or edge.get("contract_exit_id")
        from_node = edge.get("from")
        if isinstance(exit_id, str) and isinstance(from_node, str) and exit_id not in macro_allowed_exits.get(from_node, set()):
            result.add("error", "invalid_reference", f"Macro edge exit is not declared by source macro node: {exit_id}", f"macro.macro_story_graph.edges[{index}].exit_id")

    contracts = [item for item in as_list(macro_contracts.get("contracts")) if isinstance(item, dict)]
    contract_macro_ids = values_from_dicts(contracts, "macro_node_id")
    for macro_id in macro_node_ids:
        count = contract_macro_ids.count(macro_id)
        if count == 0:
            result.add("error", "missing_contract", f"Macro node has no contract: {macro_id}", "macro.macro_node_contracts.contracts")
        elif count > 1:
            result.add("error", "duplicate_contract", f"Macro node has multiple contracts: {macro_id}", "macro.macro_node_contracts.contracts")
    contracts_by_macro: dict[str, Json] = {}
    for index, contract in enumerate(contracts):
        macro_id = contract.get("macro_node_id")
        if macro_id not in macro_node_ids:
            result.add("error", "invalid_reference", f"Contract references missing macro node: {macro_id}", f"macro.macro_node_contracts.contracts[{index}].macro_node_id")
            continue
        contracts_by_macro[str(macro_id)] = contract
        allowed_exits = macro_allowed_exits.get(str(macro_id), set())
        contract_exit_ids = id_list(as_list(contract.get("exits")))
        for exit_id in contract_exit_ids:
            if exit_id not in allowed_exits:
                result.add("error", "contract_exit_mismatch", f"Contract exit is not declared by macro node: {exit_id}", f"macro.macro_node_contracts.contracts[{index}].exits")
        for state_id in as_list(contract.get("allowed_state_reads")):
            if state_id not in state_ids:
                result.add("error", "invalid_reference", f"Contract reads missing state variable: {state_id}", f"macro.macro_node_contracts.contracts[{index}].allowed_state_reads")
            elif not permission_allows(permission_map, str(state_id), str(macro_id), "read"):
                result.add("error", "state_permission", f"Contract reads state outside permission: {state_id}", f"macro.macro_node_contracts.contracts[{index}].allowed_state_reads")
        for state_id in as_list(contract.get("allowed_state_writes")):
            if state_id not in state_ids:
                result.add("error", "invalid_reference", f"Contract writes missing state variable: {state_id}", f"macro.macro_node_contracts.contracts[{index}].allowed_state_writes")
            elif not permission_allows(permission_map, str(state_id), str(macro_id), "write"):
                result.add("error", "state_permission", f"Contract writes state outside permission: {state_id}", f"macro.macro_node_contracts.contracts[{index}].allowed_state_writes")
        for source_id in as_list(contract.get("source_fact_ids")):
            if source_id not in source_ids:
                result.add("error", "invalid_reference", f"Contract references missing source fact/event: {source_id}", f"macro.macro_node_contracts.contracts[{index}].source_fact_ids")

    max_depth = mesh_expansion_policy.get("max_expansion_depth")
    target_depth = mesh_expansion_policy.get("target_expansion_depth")
    if not isinstance(max_depth, int) or max_depth < 0:
        result.add("error", "schema", "mesh_expansion_policy.max_expansion_depth must be a non-negative integer.", "control.mesh_expansion_policy.max_expansion_depth")
        max_depth = 0
    if not isinstance(target_depth, int) or target_depth < 0:
        result.add("error", "schema", "mesh_expansion_policy.target_expansion_depth must be a non-negative integer.", "control.mesh_expansion_policy.target_expansion_depth")
        target_depth = 0
    if isinstance(max_depth, int) and isinstance(target_depth, int) and target_depth > max_depth:
        result.add("error", "expansion_depth", "target_expansion_depth cannot exceed max_expansion_depth.", "control.mesh_expansion_policy.target_expansion_depth")
    budget_parent_refs: set[str] = set()
    budget_depth_by_parent: dict[str, int] = {}
    for budget_index, budget in enumerate(as_list(mesh_expansion_policy.get("depth_budget_by_parent"))):
        if not isinstance(budget, dict):
            result.add("error", "schema", "depth_budget_by_parent entries must be objects.", f"control.mesh_expansion_policy.depth_budget_by_parent[{budget_index}]")
            continue
        parent_ref = budget.get("parent_ref_id")
        budget_depth = budget.get("target_expansion_depth")
        if not isinstance(parent_ref, str) or not parent_ref:
            result.add("error", "schema", "depth_budget_by_parent entries need parent_ref_id.", f"control.mesh_expansion_policy.depth_budget_by_parent[{budget_index}].parent_ref_id")
        else:
            budget_parent_refs.add(parent_ref)
        if not isinstance(budget_depth, int) or budget_depth < 0:
            result.add("error", "schema", "depth_budget_by_parent target_expansion_depth must be a non-negative integer.", f"control.mesh_expansion_policy.depth_budget_by_parent[{budget_index}].target_expansion_depth")
        elif isinstance(max_depth, int) and budget_depth > max_depth:
            result.add("error", "expansion_depth", f"depth_budget_by_parent target {budget_depth} exceeds max_expansion_depth {max_depth}.", f"control.mesh_expansion_policy.depth_budget_by_parent[{budget_index}].target_expansion_depth")
        elif isinstance(parent_ref, str) and parent_ref:
            budget_depth_by_parent[parent_ref] = budget_depth

    subgraph_exit_refs: set[str] = set()
    subgraph_node_depth: dict[str, int] = {}
    subgraph_node_macro: dict[str, str] = {}
    seen_subgraph_ids: set[str] = set()
    seen_subgraph_parent_refs: set[str] = set()
    seen_subgraph_node_ids: set[str] = set()
    location_ids = fact_ids | {fact["id"] for fact in facts if isinstance(fact, dict) and fact.get("kind") == "location"}
    for subgraph in sorted(subgraphs, key=lambda item: int(item.get("expansion_depth", 0)) if isinstance(item.get("expansion_depth"), int) else 9999):
        subgraph_id = subgraph.get("id")
        if not isinstance(subgraph_id, str) or not subgraph_id.strip():
            result.add("error", "schema", "Subgraph needs a stable id.", f"{subgraph.get('_artifact_path', 'workspace/design_layer_v2/subgraphs')}.id")
        elif subgraph_id in seen_subgraph_ids:
            result.add("error", "duplicate_id", f"Duplicate subgraph id: {subgraph_id}", f"{subgraph.get('_artifact_path', 'workspace/design_layer_v2/subgraphs')}.id")
        else:
            seen_subgraph_ids.add(subgraph_id)

        root_macro_id = subgraph.get("root_macro_node_id") or subgraph.get("parent_macro_node_id")
        parent_ref_id = subgraph.get("parent_ref_id") or subgraph.get("parent_macro_node_id")
        parent_ref_kind = subgraph.get("parent_ref_kind") or ("macro_node" if parent_ref_id in macro_node_ids else "subgraph_node")
        depth = subgraph.get("expansion_depth")
        artifact_path = str(subgraph.get("_artifact_path", "workspace/design_layer_v2/subgraphs"))
        if isinstance(parent_ref_id, str):
            if parent_ref_id in seen_subgraph_parent_refs:
                result.add("error", "duplicate_expansion", f"Only one enabled subgraph may expand parent_ref_id: {parent_ref_id}", f"{artifact_path}.parent_ref_id")
            seen_subgraph_parent_refs.add(parent_ref_id)
        if root_macro_id not in macro_node_ids:
            result.add("error", "invalid_reference", f"Subgraph references missing root macro node: {root_macro_id}", f"{artifact_path}.root_macro_node_id")
            continue
        if not isinstance(depth, int) or depth < 1:
            result.add("error", "schema", "Subgraph expansion_depth must be a positive integer.", f"{artifact_path}.expansion_depth")
            depth = 1
        if isinstance(max_depth, int) and depth > max_depth:
            result.add("error", "expansion_depth", f"Subgraph depth {depth} exceeds max_expansion_depth {max_depth}.", f"{artifact_path}.expansion_depth")
        effective_target_depth = budget_depth_by_parent.get(str(parent_ref_id), budget_depth_by_parent.get(str(root_macro_id), target_depth))
        if isinstance(effective_target_depth, int) and depth > effective_target_depth:
            result.add("warning", "expansion_depth_disabled", f"Subgraph depth {depth} is beyond its effective target_expansion_depth {effective_target_depth} and will not be compiled by default.", f"{artifact_path}.expansion_depth")
        if parent_ref_kind == "macro_node":
            if parent_ref_id not in macro_node_ids:
                result.add("error", "invalid_reference", f"Subgraph parent macro node is missing: {parent_ref_id}", f"{artifact_path}.parent_ref_id")
            elif depth != 1:
                result.add("error", "expansion_depth", "Subgraphs under macro nodes must use expansion_depth 1.", f"{artifact_path}.expansion_depth")
        elif parent_ref_kind == "subgraph_node":
            parent_depth = subgraph_node_depth.get(str(parent_ref_id))
            if parent_depth is None:
                result.add("error", "invalid_reference", f"Subgraph parent node is missing or not from an earlier depth: {parent_ref_id}", f"{artifact_path}.parent_ref_id")
            elif depth != parent_depth + 1:
                result.add("error", "expansion_depth", f"Subgraph depth must be parent depth + 1; parent is {parent_depth}, subgraph is {depth}.", f"{artifact_path}.expansion_depth")
            parent_macro = subgraph_node_macro.get(str(parent_ref_id))
            if parent_macro and parent_macro != root_macro_id:
                result.add("error", "invalid_reference", f"Subgraph root macro {root_macro_id} does not match parent node macro {parent_macro}.", f"{artifact_path}.root_macro_node_id")
        else:
            result.add("error", "schema", f"Unsupported parent_ref_kind: {parent_ref_kind}", f"{artifact_path}.parent_ref_kind")

        local_nodes = [item for item in as_list(subgraph.get("nodes")) if isinstance(item, dict)]
        local_node_ids = unique_id_check(local_nodes, f"{artifact_path}.nodes", result)
        duplicate_public_ids = local_node_ids & seen_subgraph_node_ids
        if duplicate_public_ids:
            result.add("error", "duplicate_id", f"Subgraph node ids must be globally unique: {sorted(duplicate_public_ids)}", f"{artifact_path}.nodes")
        seen_subgraph_node_ids.update(local_node_ids)
        entry_node_id = subgraph.get("entry_node_id")
        if entry_node_id not in local_node_ids:
            result.add("error", "missing_start", f"Subgraph entry_node_id must reference a local node: {entry_node_id}", f"{artifact_path}.entry_node_id")
        local_edges = [item for item in as_list(subgraph.get("edges")) if isinstance(item, dict)]
        local_edge_ids = unique_id_check(local_edges, f"{artifact_path}.edges", result)
        for edge_index, edge in enumerate(local_edges):
            for key in ("from", "to"):
                if edge.get(key) not in local_node_ids:
                    result.add("error", "invalid_reference", f"Subgraph edge references missing local node: {edge.get(key)}", f"{artifact_path}.edges[{edge_index}].{key}")
        parent_contract = contracts_by_macro.get(str(root_macro_id), {})
        parent_exit_ids = id_list(as_list(parent_contract.get("exits")))
        allowed_chars = [str(item) for item in as_list(parent_contract.get("allowed_characters"))]
        allowed_locations = [str(item) for item in as_list(parent_contract.get("allowed_locations"))]
        allowed_reads = {str(item) for item in as_list(parent_contract.get("allowed_state_reads"))}
        allowed_writes = {str(item) for item in as_list(parent_contract.get("allowed_state_writes"))}
        for node_index, local_node in enumerate(local_nodes):
            node_id = local_node.get("id")
            if isinstance(node_id, str):
                subgraph_node_depth[node_id] = int(depth)
                subgraph_node_macro[node_id] = str(root_macro_id)
            for character_id in as_list(local_node.get("participants")):
                if character_id not in character_ids:
                    result.add("error", "invalid_reference", f"Subgraph node participant is not a known character: {character_id}", f"{artifact_path}.nodes[{node_index}].participants")
                elif allowed_chars and not wildcard_match(str(character_id), allowed_chars):
                    result.add("error", "contract_violation", f"Subgraph node participant is outside root macro contract: {character_id}", f"{artifact_path}.nodes[{node_index}].participants")
            for location_id in as_list(local_node.get("location_constraints")):
                if location_id not in location_ids:
                    result.add("warning", "unknown_location", f"Subgraph node location is not declared as a source fact: {location_id}", f"{artifact_path}.nodes[{node_index}].location_constraints")
                if allowed_locations and not wildcard_match(str(location_id), allowed_locations):
                    result.add("error", "contract_violation", f"Subgraph node location is outside root macro contract: {location_id}", f"{artifact_path}.nodes[{node_index}].location_constraints")
            for read_ref in as_list(local_node.get("state_reads")):
                state_id = state_ref_from_value(read_ref)
                if state_id not in state_ids:
                    result.add("error", "invalid_reference", f"Subgraph node reads missing state variable: {state_id}", f"{artifact_path}.nodes[{node_index}].state_reads")
                elif state_id not in allowed_reads and "*" not in allowed_reads:
                    result.add("error", "contract_violation", f"Subgraph node reads state outside root macro contract: {state_id}", f"{artifact_path}.nodes[{node_index}].state_reads")
            for write_ref in as_list(local_node.get("state_writes")):
                state_id = state_ref_from_value(write_ref)
                if state_id not in state_ids:
                    result.add("error", "invalid_reference", f"Subgraph node writes missing state variable: {state_id}", f"{artifact_path}.nodes[{node_index}].state_writes")
                elif state_id not in allowed_writes and "*" not in allowed_writes:
                    result.add("error", "contract_violation", f"Subgraph node writes state outside root macro contract: {state_id}", f"{artifact_path}.nodes[{node_index}].state_writes")
            for source_id in as_list(local_node.get("source_fact_ids")):
                if source_id not in source_ids:
                    result.add("error", "invalid_reference", f"Subgraph node references missing source fact/event: {source_id}", f"{artifact_path}.nodes[{node_index}].source_fact_ids")
        for mapping_index, mapping in enumerate(as_list(subgraph.get("exit_mappings"))):
            if not isinstance(mapping, dict):
                result.add("error", "schema", "Subgraph exit mappings must be objects.", f"{artifact_path}.exit_mappings[{mapping_index}]")
                continue
            local_exit_id = mapping.get("local_exit_id")
            macro_exit_id = mapping.get("macro_exit_id")
            if local_exit_id not in local_node_ids and local_exit_id not in local_edge_ids:
                result.add("error", "invalid_reference", f"Exit mapping references missing local exit: {local_exit_id}", f"{artifact_path}.exit_mappings[{mapping_index}].local_exit_id")
            if macro_exit_id not in parent_exit_ids:
                result.add("error", "contract_exit_mismatch", f"Exit mapping references missing root macro contract exit: {macro_exit_id}", f"{artifact_path}.exit_mappings[{mapping_index}].macro_exit_id")
            if isinstance(local_exit_id, str):
                subgraph_exit_refs.add(local_exit_id)

    source_coverage_report = validate_source_adaptation_coverage(
        result,
        source_intake,
        artifacts,
        macro_nodes,
        contracts,
        subgraphs,
    )

    known_budget_refs = macro_node_ids | seen_subgraph_node_ids
    for parent_ref in budget_parent_refs:
        if parent_ref not in known_budget_refs:
            result.add("warning", "invalid_reference", f"Expansion depth budget references no known macro or subgraph node: {parent_ref}", "control.mesh_expansion_policy.depth_budget_by_parent")

    artifacts_for_policy: dict[str, Any] = dict(artifacts)
    artifacts_for_policy["_subgraphs"] = subgraphs
    enabled_subgraph_list = enabled_subgraphs(artifacts_for_policy)
    enabled_mesh_node_ids: set[str] = set()
    enabled_subgraph_exit_refs: set[str] = set()
    for subgraph in enabled_subgraph_list:
        enabled_mesh_node_ids.update(id_list(as_list(subgraph.get("nodes"))))
        for mapping in as_list(subgraph.get("exit_mappings")):
            if isinstance(mapping, dict) and isinstance(mapping.get("local_exit_id"), str):
                enabled_subgraph_exit_refs.add(mapping["local_exit_id"])

    for ending_index, ending in enumerate(as_list(ending_space.get("endings"))):
        if not isinstance(ending, dict):
            result.add("error", "schema", "Ending entries must be objects.", f"adaptation.ending_space.endings[{ending_index}]")
            continue
        ending_id = ending.get("id")
        for state_id in state_refs_from_any(ending.get("state_requirements", [])):
            if state_id not in state_ids:
                result.add("error", "invalid_reference", f"Ending references missing state variable: {state_id}", f"adaptation.ending_space.endings[{ending_index}].state_requirements")
        for theme_id in as_list(ending.get("theme_ids")):
            if theme_id not in theme_ids:
                result.add("warning", "invalid_reference", f"Ending references unknown theme: {theme_id}", f"adaptation.ending_space.endings[{ending_index}].theme_ids")
        if ending.get("status") not in ("unavailable", "disabled"):
            reachable = any(node.get("ending_id") == ending_id or node.get("id") == ending_id for node in macro_nodes)
            if not reachable:
                result.add("warning", "unreachable_ending", f"Ending is not directly represented by a macro terminal node: {ending_id}", f"adaptation.ending_space.endings[{ending_index}]")

    for merge_index, merge in enumerate(as_list(route_merge_policy.get("merge_points"))):
        if not isinstance(merge, dict):
            result.add("error", "schema", "Merge point entries must be objects.", f"control.route_merge_policy.merge_points[{merge_index}]")
            continue
        node_id = merge.get("node_id") or merge.get("subgraph_exit_id")
        if node_id not in macro_node_ids and node_id not in enabled_subgraph_exit_refs and node_id not in enabled_mesh_node_ids:
            result.add("error", "invalid_reference", f"Merge point references missing macro node, mesh node, or subgraph exit: {node_id}", f"control.route_merge_policy.merge_points[{merge_index}]")
        for state_id in as_list(merge.get("preserved_state_variable_ids")):
            if state_id not in state_ids:
                result.add("error", "invalid_reference", f"Merge point preserves missing state variable: {state_id}", f"control.route_merge_policy.merge_points[{merge_index}].preserved_state_variable_ids")

    simulation_profiles = None
    if result.status != "fail":
        simulation_profiles = build_simulation_profiles(artifacts_for_policy)
        add_design_quality_warnings(result, artifacts_for_policy, simulation_profiles)

    if write_report:
        if simulation_profiles is not None:
            write_json(run_root / DESIGN_V2_SIMULATION_PROFILES, simulation_profiles)
        write_json(run_root / DESIGN_V2_SOURCE_COVERAGE_REPORT, source_coverage_report)
        report = {
            "design_layer": {"version": "v2", "root": str(DESIGN_V2_ROOT)},
            "simulation_profiles": str(DESIGN_V2_SIMULATION_PROFILES) if simulation_profiles is not None else None,
            "source_coverage_report": str(DESIGN_V2_SOURCE_COVERAGE_REPORT),
            **result.to_json(),
        }
        write_json(run_root / DESIGN_V2_VALIDATION_REPORT, report)
    return result


def load_validated_v2(run_root: Path) -> dict[str, Any]:
    artifacts = {relative: read_json(design_v2_path(run_root, relative)) for relative in REQUIRED_V2_FILES}
    artifacts["_subgraphs"] = [read_json(path) for path in list_subgraph_paths(run_root)]
    return artifacts


def safe_suffix(identifier: str) -> str:
    if "." in identifier:
        identifier = identifier.split(".", 1)[1]
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier).strip("_") or "item"


def branch_node_id_for_macro(macro_id: str) -> str:
    return stable_id(safe_suffix(macro_id), "node")


def normalize_effect(effect: Any) -> Json:
    if not isinstance(effect, dict):
        return {"state_variable_id": str(effect), "operation": "set", "value": True}
    normalized = dict(effect)
    state_id = normalized.pop("state", None) or normalized.get("state_variable_id")
    if state_id is not None:
        normalized["state_variable_id"] = state_id
    normalized.setdefault("operation", "set")
    return normalized


def compile_requirements(run_root: Path, artifacts: dict[str, Any]) -> Json:
    prompt_path = run_root / "inputs" / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
    adaptation = artifacts["adaptation/adaptation_policy.json"]
    themes = artifacts["source_facts/theme_constraints.json"]
    facts_by_id = dict_by_id(as_list(artifacts["source_facts/fact_book.json"].get("facts")))
    requirements: list[Json] = []
    for fact_id in as_list(adaptation.get("fixed_fact_ids")):
        fact = facts_by_id.get(str(fact_id), {})
        requirements.append({
            "id": f"req.preserve.{safe_suffix(str(fact_id))}",
            "priority": "must",
            "text": f"Preserve canon fact {fact_id}: {fact.get('summary', '')}".strip(),
            "source_phrase": str(fact_id),
        })
    for process in as_list(adaptation.get("variable_processes")):
        if isinstance(process, dict):
            requirements.append({
                "id": f"req.process.{safe_suffix(str(process.get('id', 'process')))}",
                "priority": "should",
                "text": process.get("description", "Support a variable narrative process."),
                "source_phrase": str(process.get("id", "")),
            })
    for ending in as_list(adaptation.get("variable_endings")):
        if isinstance(ending, dict):
            requirements.append({
                "id": f"req.ending.{safe_suffix(str(ending.get('id', 'ending')))}",
                "priority": "should",
                "text": f"Support ending family: {ending.get('title') or ending.get('id')}",
                "source_phrase": str(ending.get("id", "")),
            })
    if not requirements:
        requirements.append({
            "id": "req.core",
            "priority": "must",
            "text": "Produce a playable branching narrative from the V2 design layer.",
            "source_phrase": "design-layer-v2",
        })
    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": ["Compiled from Design Layer V2."]},
        "prompt": prompt,
        "target_experience": artifacts["macro/macro_story_graph.json"].get("summary", "A state-driven branching narrative."),
        "requirements": requirements,
        "creative_constraints": {
            "genre": "",
            "tone": themes.get("tone", ""),
            "themes": normalize_string_items(as_list(themes.get("themes"))),
            "motifs": as_list(themes.get("motifs")),
            "prohibited_content": as_list(themes.get("prohibited_content")) + [
                item.get("description", "")
                for item in as_list(adaptation.get("forbidden_changes"))
                if isinstance(item, dict)
            ],
        },
        "production_constraints": {
            "target_language": "en",
            "approximate_node_count": len(as_list(artifacts["macro/macro_story_graph.json"].get("nodes"))),
            "desired_endings": len(as_list(artifacts["adaptation/ending_space.json"].get("endings"))),
            "asset_budget_level": "low",
            "notes": ["Compiled from Design Layer V2."],
        },
        "assumptions": [],
        "unknowns": [],
    }


def compile_synopsis(artifacts: dict[str, Any]) -> Json:
    macro_graph = artifacts["macro/macro_story_graph.json"]
    events = []
    for event in as_list(artifacts["source_facts/event_timeline.json"].get("events")):
        if isinstance(event, dict):
            events.append({
                "id": event.get("id", "event.unknown"),
                "summary": event.get("summary", ""),
                "purpose": event.get("purpose", "source timeline"),
                "requirement_ids": [],
            })
    if not events:
        for node in as_list(macro_graph.get("nodes")):
            if isinstance(node, dict):
                events.append({
                    "id": f"event.{safe_suffix(str(node.get('id', 'macro')))}",
                    "summary": node.get("summary", ""),
                    "purpose": node.get("kind", "macro node"),
                    "requirement_ids": [],
                })
    facts = as_list(artifacts["source_facts/fact_book.json"].get("facts"))
    locations = [
        {"id": fact.get("id"), "name": fact.get("name") or fact.get("id"), "description": fact.get("summary", "")}
        for fact in facts
        if isinstance(fact, dict) and fact.get("kind") == "location"
    ]
    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": ["Compiled from Design Layer V2."]},
        "title": macro_graph.get("title", "Generated Narrative Game"),
        "summary": macro_graph.get("summary", "A state-driven branching narrative."),
        "events": events,
        "cast": [
            {"id": character.get("id"), "name": character.get("name", character.get("id", "")), "role": character.get("summary", "")}
            for character in as_list(artifacts["source_facts/character_graph.json"].get("characters"))
            if isinstance(character, dict)
        ],
        "locations": locations,
        "pacing_notes": ["Compiled from macro graph and source timeline."],
    }


def resolve_subgraph_exit_node(subgraph: Json, local_exit_id: str) -> str | None:
    node_ids = id_list(as_list(subgraph.get("nodes")))
    if local_exit_id in node_ids:
        return local_exit_id
    for edge in as_list(subgraph.get("edges")):
        if isinstance(edge, dict) and edge.get("id") == local_exit_id and isinstance(edge.get("to"), str):
            return edge["to"]
    return None


def policy_target_depth(artifacts: dict[str, Any]) -> int:
    policy = artifacts.get("control/mesh_expansion_policy.json", {})
    target = policy.get("target_expansion_depth") if isinstance(policy, dict) else None
    maximum = policy.get("max_expansion_depth") if isinstance(policy, dict) else None
    if not isinstance(target, int):
        target = maximum if isinstance(maximum, int) else 0
    if isinstance(maximum, int):
        target = min(target, maximum)
    return max(0, target)


def policy_parent_depths(artifacts: dict[str, Any]) -> dict[str, int]:
    policy = artifacts.get("control/mesh_expansion_policy.json", {})
    depths: dict[str, int] = {}
    for item in as_list(policy.get("depth_budget_by_parent") if isinstance(policy, dict) else []):
        if not isinstance(item, dict) or not isinstance(item.get("parent_ref_id"), str):
            continue
        depth = item.get("target_expansion_depth")
        if isinstance(depth, int) and depth >= 0:
            depths[item["parent_ref_id"]] = depth
    return depths


def subgraph_depth(subgraph: Json) -> int:
    depth = subgraph.get("expansion_depth")
    return depth if isinstance(depth, int) else 1


def subgraph_parent_ref(subgraph: Json) -> str:
    return str(subgraph.get("parent_ref_id") or subgraph.get("parent_macro_node_id") or "")


def subgraph_root_macro(subgraph: Json) -> str:
    return str(subgraph.get("root_macro_node_id") or subgraph.get("parent_macro_node_id") or "")


def enabled_subgraphs(artifacts: dict[str, Any]) -> list[Json]:
    target_depth = policy_target_depth(artifacts)
    parent_depths = policy_parent_depths(artifacts)
    macro_ids = id_list(as_list(artifacts.get("macro/macro_story_graph.json", {}).get("nodes")))
    selected: list[Json] = []
    enabled_node_ids: set[str] = set()
    for subgraph in sorted(
        [subgraph for subgraph in artifacts.get("_subgraphs", []) if isinstance(subgraph, dict)],
        key=lambda item: (subgraph_depth(item), subgraph_parent_ref(item), str(item.get("id", ""))),
    ):
        parent_ref = subgraph_parent_ref(subgraph)
        depth_limit = parent_depths.get(parent_ref, parent_depths.get(subgraph_root_macro(subgraph), target_depth))
        if subgraph_depth(subgraph) > depth_limit:
            continue
        parent_kind = subgraph.get("parent_ref_kind") or ("macro_node" if parent_ref in macro_ids else "subgraph_node")
        if parent_kind == "subgraph_node" and parent_ref not in enabled_node_ids:
            continue
        selected.append(subgraph)
        enabled_node_ids.update(id_list(as_list(subgraph.get("nodes"))))
    return selected


def compile_branch_graph(artifacts: dict[str, Any]) -> Json:
    macro_graph = artifacts["macro/macro_story_graph.json"]
    macro_nodes = [item for item in as_list(macro_graph.get("nodes")) if isinstance(item, dict)]
    macro_edges = [item for item in as_list(macro_graph.get("edges")) if isinstance(item, dict)]
    contracts_by_macro = {
        contract.get("macro_node_id"): contract
        for contract in as_list(artifacts["macro/macro_node_contracts.json"].get("contracts"))
        if isinstance(contract, dict)
    }
    subgraphs = enabled_subgraphs(artifacts)
    subgraphs_by_parent = {subgraph_parent_ref(subgraph): subgraph for subgraph in subgraphs}
    expanded_parents = set(subgraphs_by_parent)

    nodes: list[Json] = []
    edges: list[Json] = []
    macro_entry_node: dict[str, str] = {}
    macro_exit_node: dict[tuple[str, str], str] = {}

    for macro_node in macro_nodes:
        macro_id = str(macro_node.get("id"))
        contract = contracts_by_macro.get(macro_id, {})
        contract_id = contract.get("id") or f"contract.{safe_suffix(macro_id)}"
        subgraph = subgraphs_by_parent.get(macro_id)
        if subgraph:
            macro_entry_node[macro_id] = str(subgraph.get("entry_node_id"))
        else:
            node_id = branch_node_id_for_macro(macro_id)
            macro_entry_node[macro_id] = node_id
            for exit_item in as_list(contract.get("exits")):
                if isinstance(exit_item, dict) and isinstance(exit_item.get("id"), str):
                    macro_exit_node[(macro_id, exit_item["id"])] = node_id
            nodes.append({
                "id": node_id,
                "node_type": "terminal" if macro_node.get("is_terminal") else "scene",
                "title": macro_node.get("title", macro_id),
                "summary": macro_node.get("summary", ""),
                "body": "",
                "is_terminal": bool(macro_node.get("is_terminal", False)),
                "layer": "macro",
                "macro_node_id": macro_id,
                "contract_id": contract_id,
                "expansion_depth": 0,
                "source_fact_ids": contract.get("source_fact_ids", []),
                "source_policy_ids": [],
            })

    for subgraph in subgraphs:
        root_macro_id = subgraph_root_macro(subgraph)
        depth = subgraph_depth(subgraph)
        parent_ref = subgraph_parent_ref(subgraph)
        contract = contracts_by_macro.get(root_macro_id, {})
        contract_id = contract.get("id") or f"contract.{safe_suffix(root_macro_id)}"
        if subgraph.get("parent_ref_kind") == "subgraph_node" and isinstance(subgraph.get("entry_node_id"), str):
            edges.append({
                "id": f"edge.expand.{safe_suffix(parent_ref)}.{safe_suffix(str(subgraph.get('entry_node_id')))}",
                "from": parent_ref,
                "to": subgraph.get("entry_node_id"),
                "label": "Continue",
                "condition_type": "unconditional",
                "layer": "mesh_expansion",
                "expansion_depth": depth,
                "root_macro_node_id": root_macro_id,
                "source_rule_ids": [],
            })
        for local_node in as_list(subgraph.get("nodes")):
            if not isinstance(local_node, dict):
                continue
            nodes.append({
                "id": local_node.get("id"),
                "node_type": local_node.get("node_type", "scene"),
                "title": local_node.get("title", local_node.get("id", "")),
                "summary": local_node.get("summary", ""),
                "body": local_node.get("body", ""),
                "is_terminal": bool(local_node.get("is_terminal", False)),
                "layer": "mesh_expansion",
                "expansion_depth": depth,
                "parent_ref_id": parent_ref,
                "root_macro_node_id": root_macro_id,
                "macro_node_id": root_macro_id,
                "contract_id": contract_id,
                "expandable": bool(local_node.get("expandable", False)),
                "source_fact_ids": as_list(local_node.get("source_fact_ids")) or contract.get("source_fact_ids", []),
                "source_policy_ids": [],
            })
        for local_edge in as_list(subgraph.get("edges")):
            if not isinstance(local_edge, dict):
                continue
            if local_edge.get("from") in expanded_parents:
                continue
            edges.append({
                "id": local_edge.get("id"),
                "from": local_edge.get("from"),
                "to": local_edge.get("to"),
                "label": local_edge.get("label", ""),
                "condition_type": local_edge.get("condition_type", "player_choice"),
                "conditions": as_list(local_edge.get("conditions")),
                "layer": "mesh_expansion",
                "expansion_depth": depth,
                "parent_ref_id": parent_ref,
                "root_macro_node_id": root_macro_id,
                "contract_exit_id": local_edge.get("contract_exit_id"),
                "source_rule_ids": [local_edge.get("id")] if local_edge.get("id") else [],
            })
        for mapping in as_list(subgraph.get("exit_mappings")):
            if not isinstance(mapping, dict):
                continue
            local_exit_id = mapping.get("local_exit_id")
            macro_exit_id = mapping.get("macro_exit_id")
            if isinstance(local_exit_id, str) and isinstance(macro_exit_id, str):
                exit_node = resolve_subgraph_exit_node(subgraph, local_exit_id)
                if exit_node:
                    macro_exit_node[(root_macro_id, macro_exit_id)] = exit_node

    for macro_edge in macro_edges:
        from_macro = str(macro_edge.get("from"))
        to_macro = str(macro_edge.get("to"))
        exit_id = macro_edge.get("exit_id") or macro_edge.get("contract_exit_id")
        from_node = macro_exit_node.get((from_macro, str(exit_id))) if isinstance(exit_id, str) else None
        if not from_node:
            from_node = macro_entry_node.get(from_macro)
        to_node = macro_entry_node.get(to_macro)
        if not from_node or not to_node:
            continue
        edges.append({
            "id": macro_edge.get("id"),
            "from": from_node,
            "to": to_node,
            "label": macro_edge.get("label", ""),
            "condition_type": macro_edge.get("condition_type", "unconditional"),
            "conditions": as_list(macro_edge.get("conditions")),
            "layer": "macro",
            "contract_exit_id": exit_id,
            "source_rule_ids": [macro_edge.get("id")] if macro_edge.get("id") else [],
        })

    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": ["Compiled from Design Layer V2."]},
        "title": macro_graph.get("title", "Generated Narrative Game"),
        "graph_scope": "full_game",
        "start_node_id": macro_entry_node.get(str(macro_graph.get("start_macro_node_id")), nodes[0]["id"] if nodes else ""),
        "clusters": [
            {
                "id": macro_node.get("id"),
                "title": macro_node.get("title", macro_node.get("id", "")),
                "node_ids": [
                    node.get("id")
                    for node in nodes
                    if node.get("macro_node_id") == macro_node.get("id")
                ],
            }
            for macro_node in macro_nodes
        ],
        "source_outline_ids": values_from_dicts(as_list(artifacts["source_facts/event_timeline.json"].get("events")), "id"),
        "nodes": nodes,
        "edges": edges,
    }


def compile_game_ir(artifacts: dict[str, Any], branch_graph: Json) -> Json:
    facts = as_list(artifacts["source_facts/fact_book.json"].get("facts"))
    characters = as_list(artifacts["source_facts/character_graph.json"].get("characters"))
    events = as_list(artifacts["source_facts/event_timeline.json"].get("events"))
    themes = artifacts["source_facts/theme_constraints.json"]
    adaptation = artifacts["adaptation/adaptation_policy.json"]
    variables = [dict(item) for item in as_list(artifacts["state/world_state_model.json"].get("variables")) if isinstance(item, dict)]
    macro_nodes = [item for item in as_list(artifacts["macro/macro_story_graph.json"].get("nodes")) if isinstance(item, dict)]
    macro_edges = [item for item in as_list(artifacts["macro/macro_story_graph.json"].get("edges")) if isinstance(item, dict)]
    contracts = [strip_internal_trace(dict(item)) for item in as_list(artifacts["macro/macro_node_contracts.json"].get("contracts")) if isinstance(item, dict)]
    subgraphs = [dict(item) for item in enabled_subgraphs(artifacts) if isinstance(item, dict)]
    contracts_by_macro = {contract.get("macro_node_id"): contract for contract in contracts}
    edge_by_exit = {edge.get("contract_exit_id") or edge.get("exit_id"): edge for edge in branch_graph.get("edges", []) if isinstance(edge, dict)}
    branch_edge_ids = {
        edge.get("id")
        for edge in as_list(branch_graph.get("edges"))
        if isinstance(edge, dict) and isinstance(edge.get("id"), str)
    }

    event_rules: list[Json] = []
    for macro_edge in macro_edges:
        edge_id = macro_edge.get("id")
        exit_id = macro_edge.get("exit_id") or macro_edge.get("contract_exit_id")
        contract = contracts_by_macro.get(macro_edge.get("from"), {})
        exit_effects: list[Json] = []
        for exit_item in as_list(contract.get("exits")):
            if isinstance(exit_item, dict) and exit_item.get("id") == exit_id:
                exit_effects = [normalize_effect(effect) for effect in as_list(exit_item.get("effects"))]
        event_rules.append({
            "id": f"rule.{safe_suffix(str(edge_id or exit_id or 'macro_edge'))}",
            "source_edge_id": edge_id,
            "source_macro_edge_id": edge_id,
            "conditions": as_list(macro_edge.get("conditions")),
            "effects": exit_effects,
            "description": macro_edge.get("label", ""),
        })
    for subgraph in subgraphs:
        subgraph_id = subgraph.get("id")
        for edge in as_list(subgraph.get("edges")):
            if isinstance(edge, dict) and edge.get("id") in branch_edge_ids:
                event_rules.append({
                    "id": f"rule.{safe_suffix(str(edge.get('id', 'mesh_edge')))}",
                    "source_subgraph_id": subgraph_id,
                    "source_edge_id": edge.get("id"),
                    "conditions": as_list(edge.get("conditions")),
                    "effects": [normalize_effect(effect) for effect in as_list(edge.get("effects") or edge.get("state_writes"))],
                    "description": edge.get("label", ""),
                })
        for node in as_list(subgraph.get("nodes")):
            if isinstance(node, dict) and as_list(node.get("state_writes")):
                event_rules.append({
                    "id": f"rule.{safe_suffix(str(node.get('id', 'mesh_node')))}.completion",
                    "source_subgraph_id": subgraph_id,
                    "source_node_id": node.get("id"),
                    "conditions": as_list(node.get("preconditions")),
                    "effects": [normalize_effect(effect) for effect in as_list(node.get("state_writes"))],
                    "description": "Mesh node completion effects.",
                })

    entities: list[Json] = []
    entities.extend({
        "id": character.get("id"),
        "kind": "character",
        "name": character.get("name", character.get("id", "")),
        "description": character.get("summary", ""),
    } for character in characters if isinstance(character, dict))
    entities.extend({
        "id": fact.get("id"),
        "kind": fact.get("kind", "fact"),
        "name": fact.get("name", fact.get("id", "")),
        "description": fact.get("summary", ""),
    } for fact in facts if isinstance(fact, dict) and fact.get("kind") in ("location", "object", "faction"))

    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV2Compiler", "notes": ["Compiled from Design Layer V2."]},
        "design_layer": {"version": "v2"},
        "design_brief": {
            "target_experience": artifacts["macro/macro_story_graph.json"].get("summary", "A state-driven branching narrative."),
            "tone": themes.get("tone", ""),
            "themes": normalize_string_items(as_list(themes.get("themes"))),
            "must_keep_constraints": as_list(adaptation.get("fixed_fact_ids")) + [
                item.get("description", "")
                for item in as_list(adaptation.get("forbidden_changes"))
                if isinstance(item, dict)
            ],
            "production_constraints": {"design_layer": "v2"},
            "narrative_bible": {
                "cast": [
                    {"id": character.get("id"), "name": character.get("name", character.get("id", "")), "summary": character.get("summary", "")}
                    for character in characters
                    if isinstance(character, dict)
                ],
                "locations": [
                    {"id": fact.get("id"), "name": fact.get("name", fact.get("id", "")), "summary": fact.get("summary", "")}
                    for fact in facts
                    if isinstance(fact, dict) and fact.get("kind") == "location"
                ],
                "timeline": [
                    {"id": event.get("id"), "summary": event.get("summary", ""), "order": event.get("order")}
                    for event in events
                    if isinstance(event, dict)
                ],
                "continuity_rules": strip_internal_trace(as_list(artifacts["source_facts/world_rules.json"].get("rules"))),
            },
        },
        "world": {"summary": artifacts["macro/macro_story_graph.json"].get("summary", "")},
        "source_facts_digest": {
            "fact_ids": values_from_dicts(facts, "id"),
            "event_ids": values_from_dicts(events, "id"),
            "theme_ids": normalize_string_items(as_list(themes.get("themes"))),
        },
        "adaptation_policy_digest": {
            "fixed_fact_ids": as_list(adaptation.get("fixed_fact_ids")),
            "variable_process_ids": values_from_dicts(as_list(adaptation.get("variable_processes")), "id"),
            "variable_ending_ids": values_from_dicts(as_list(adaptation.get("variable_endings")), "id"),
            "forbidden_change_ids": values_from_dicts(as_list(adaptation.get("forbidden_changes")), "id"),
        },
        "entities": entities,
        "state_model": {"variables": variables},
        "global_state_variables": variables,
        "relationship_state_variables": [variable for variable in variables if variable.get("scope") == "relationship"],
        "knowledge_state_variables": [variable for variable in variables if variable.get("scope") == "knowledge"],
        "progression_stages": [
            {
                "id": node.get("id"),
                "title": node.get("title", node.get("id", "")),
                "description": node.get("summary", ""),
                "kind": node.get("kind", "mainline"),
                "entry_conditions": as_list(node.get("entry_conditions")),
            }
            for node in macro_nodes
        ],
        "node_contracts": contracts,
        "mesh_expansion_policy": strip_internal_trace(artifacts["control/mesh_expansion_policy.json"]),
        "mesh_expansions": [
            {
                "id": subgraph.get("id"),
                "expansion_depth": subgraph_depth(subgraph),
                "root_macro_node_id": subgraph_root_macro(subgraph),
                "parent_ref_id": subgraph_parent_ref(subgraph),
                "entry_node_id": subgraph.get("entry_node_id"),
                "node_ids": values_from_dicts(as_list(subgraph.get("nodes")), "id"),
                "edge_ids": [
                    edge_id
                    for edge_id in values_from_dicts(as_list(subgraph.get("edges")), "id")
                    if edge_id in branch_edge_ids
                ],
            }
            for subgraph in subgraphs
        ],
        "event_rules": event_rules,
        "validation_expectations": {
            "route_merge_policy": strip_internal_trace(artifacts["control/route_merge_policy.json"]),
            "mesh_expansion_policy": strip_internal_trace(artifacts["control/mesh_expansion_policy.json"]),
            "compiled_branch_edge_count": len(as_list(branch_graph.get("edges"))),
        },
        "compiler_trace": {
            "compiled_from_design_layer_version": "v2",
        },
        "edge_exit_index": {
            str(exit_id): edge.get("id")
            for exit_id, edge in edge_by_exit.items()
            if exit_id
        },
    }


def validate_compiled_public(requirements: Json, synopsis: Json, branch_graph: Json, game_ir: Json) -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_requirements(requirements))
    result.extend(validate_synopsis(synopsis))
    result.extend(validate_branch_graph(branch_graph))
    result.extend(validate_game_ir(game_ir, branch_graph))
    result.extend(validate_graph_ir_consistency(branch_graph, game_ir))
    if result.status != "fail":
        project_shared_state(game_ir)
    return result


def compile_design_v2(run_root: Path) -> ValidationResult:
    ensure_design_v2_layout(run_root)
    validation = validate_design_v2(run_root, write_report=True)
    if validation.status == "fail":
        write_json(run_root / DESIGN_V2_COMPILE_REPORT, {
            "status": "fail",
            "stage": "v2_validation",
            "findings": [finding.to_json() for finding in validation.findings],
        })
        return validation

    artifacts = load_validated_v2(run_root)
    requirements = compile_requirements(run_root, artifacts)
    synopsis = compile_synopsis(artifacts)
    branch_graph = compile_branch_graph(artifacts)
    game_ir = compile_game_ir(artifacts, branch_graph)

    compiled_root = design_v2_path(run_root, "compiled")
    staged = {
        "user_requirements.json": requirements,
        "chapter_linear_synopsis.json": synopsis,
        "branch_graph.json": branch_graph,
        "game_ir.json": game_ir,
    }
    for filename, payload in staged.items():
        write_json(compiled_root / filename, payload)

    public_validation = validate_compiled_public(requirements, synopsis, branch_graph, game_ir)
    if public_validation.status == "fail":
        write_json(run_root / DESIGN_V2_COMPILE_REPORT, {
            "status": "fail",
            "stage": "public_validation",
            "findings": [finding.to_json() for finding in public_validation.findings],
            "staged_outputs": [str(DESIGN_V2_ROOT / "compiled" / filename) for filename in staged],
        })
        return public_validation

    public_root = run_root / "workspace" / "design_layer"
    ensure_dir(public_root)
    for filename in staged:
        shutil.copyfile(compiled_root / filename, public_root / filename)

    from pipeline_lib import validate_all

    validate_all(run_root, write_projections=True)
    write_json(run_root / DESIGN_V2_COMPILE_REPORT, {
        "status": "pass",
        "stage": "copied_public_artifacts",
        "v2_validation_status": validation.status,
        "public_validation_status": public_validation.status,
        "source_coverage_report": str(DESIGN_V2_SOURCE_COVERAGE_REPORT),
        "staged_outputs": [str(DESIGN_V2_ROOT / "compiled" / filename) for filename in staged],
        "public_outputs": [str(Path("workspace/design_layer") / filename) for filename in staged],
        "findings": [finding.to_json() for finding in validation.findings + public_validation.findings],
    })
    return public_validation


def source_node_for_plan(run_root: Path, plan_id: str) -> str | None:
    plans_path = run_root / "workspace" / "realization" / "node-realization-plans.json"
    if not plans_path.exists():
        return None
    plans = read_json(plans_path)
    for plan in as_list(plans.get("plans")):
        if isinstance(plan, dict) and plan.get("unit_id") == plan_id:
            source_node_id = plan.get("source_node_id")
            return source_node_id if isinstance(source_node_id, str) else None
    return None


def project_source_adaptation_context(run_root: Path, node_id: str) -> Json:
    root = design_v2_root(run_root)
    if not root.exists():
        return {}
    segments_path = root / "source_intake" / "source_segments.json"
    if not segments_path.exists():
        return {}

    node_segment_ids: set[str] = set()
    for subgraph_path in list_subgraph_paths(run_root):
        try:
            subgraph = read_json(subgraph_path)
        except Exception:  # noqa: BLE001
            continue
        for local_node in as_list(subgraph.get("nodes")):
            if isinstance(local_node, dict) and local_node.get("id") == node_id:
                node_segment_ids.update(source_segment_ids_from(local_node))
        for edge in as_list(subgraph.get("edges")):
            if isinstance(edge, dict) and (edge.get("from") == node_id or edge.get("to") == node_id):
                node_segment_ids.update(source_segment_ids_from(edge))

    segment_summaries: list[Json] = []
    if segments_path.exists():
        segments_payload = read_json(segments_path)
        for segment in as_list(segments_payload.get("segments")):
            if isinstance(segment, dict) and segment.get("id") in node_segment_ids:
                segment_summaries.append({
                    "id": segment.get("id"),
                    "summary": segment.get("summary", ""),
                    "chapter_number": segment.get("chapter_number"),
                    "chapter_title": segment.get("chapter_title"),
                    "importance": segment.get("importance"),
                    "adaptation_freedom": segment.get("adaptation_freedom"),
                })

    if not segment_summaries:
        return {}
    return {
        "source_segment_ids": sorted(node_segment_ids),
        "segment_summaries": segment_summaries,
        "usage_rules": [
            "Do not invent contradictory dialogue that changes locked source facts.",
            "Treat source context as private authoring material. Do not expose source intake labels or coverage ids in player-facing text.",
            "Treat node summaries, continuity summaries, and transition context as private authoring material. Do not expose reader/player guidance, scene questions, or scene hooks such as 读者, 玩家, 问题是, 问题转向, 问题从, 钩子是, the question is, or the hook is.",
            "Treat source segment summaries as private planning material. Do not paste summary sentences into Yarn; rewrite useful facts into concrete sensory action, object detail, or character speech.",
            "Do not expose run-scope, UI, route, or state-label language such as 前五章暂止, 收束前五章, 不显示结局菜单, route, branch, state, or 余波 in player-facing text.",
            "Write the node as a reader journey, not an excerpt list: orient the player, develop one active question or tension, land a reveal or emotional turn, and transition to the planned outcome.",
            "Introduce world rules only after the scene gives the player a reason to need that explanation; preserve mystery when a later node should answer it.",
        ],
    }


def project_transition_context(node: Json, incoming: list[Json], outgoing: list[Json], nodes_by_id: dict[str, Json]) -> Json:
    def node_summary(node_id: Any) -> Json:
        if not isinstance(node_id, str):
            return {}
        neighbor = nodes_by_id.get(node_id, {})
        return {
            "id": neighbor.get("id"),
            "title": neighbor.get("title", ""),
            "summary": neighbor.get("summary", ""),
            "is_terminal": neighbor.get("is_terminal", False),
        }

    def edge_packet(edge: Json, direction: str) -> Json:
        other_node_id = edge.get("from") if direction == "incoming" else edge.get("to")
        return {
            "edge_id": edge.get("id"),
            "label": edge.get("label", ""),
            "condition_type": edge.get("condition_type", "unconditional"),
            "conditions": as_list(edge.get("conditions")),
            "effects": edge_state_effects(edge),
            "other_node": node_summary(other_node_id),
        }

    incoming_packets = [edge_packet(edge, "incoming") for edge in incoming]
    outgoing_packets = [edge_packet(edge, "outgoing") for edge in outgoing]
    state_payoff_cues: list[Json] = []
    for edge in incoming + outgoing:
        cue = {
            "edge_id": edge.get("id"),
            "label": edge.get("label", ""),
            "condition_type": edge.get("condition_type", "unconditional"),
            "state_reads": as_list(edge.get("conditions")),
            "state_writes": edge_state_effects(edge),
        }
        if cue["state_reads"] or cue["state_writes"]:
            state_payoff_cues.append(cue)
    generic_outgoing = [
        edge.get("id")
        for edge in outgoing
        if isinstance(edge, dict) and is_plain_continue_edge(edge)
    ]
    return {
        "current_node": {
            "id": node.get("id"),
            "title": node.get("title", ""),
            "summary": node.get("summary", ""),
        },
        "incoming": incoming_packets,
        "outgoing": outgoing_packets,
        "state_payoff_cues": state_payoff_cues,
        "handoff_rules": [
            "Open from the predecessor pressure or unanswered question when an incoming edge exists.",
            "Use the current node summary as the entry anchor and dramatic task, not as a visible outline.",
            "Before each planned outcome, make the outgoing edge feel motivated by a consequence, question, or decision.",
            "If an outgoing edge writes or reads state, make the choice or payoff legible in scene prose without changing topology.",
        ],
        "generic_continue_edge_ids": [edge_id for edge_id in generic_outgoing if isinstance(edge_id, str)],
    }


def project_node_context(run_root: Path, node_id: str) -> tuple[Path, Json]:
    branch_graph = read_json(run_root / "workspace" / "design_layer" / "branch_graph.json")
    game_ir = read_json(run_root / "workspace" / "design_layer" / "game_ir.json")
    nodes = [node for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict)]
    edges = [edge for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)]
    node = next((item for item in nodes if item.get("id") == node_id), None)
    if node is None:
        raise SystemExit(f"Unknown branch graph node: {node_id}")
    incoming = [edge for edge in edges if edge.get("to") == node_id]
    outgoing = [edge for edge in edges if edge.get("from") == node_id]
    nodes_by_id = dict_by_id(nodes)
    neighbor_ids = {edge.get("from") for edge in incoming} | {edge.get("to") for edge in outgoing}
    neighbors = [
        {"id": item.get("id"), "title": item.get("title", ""), "summary": item.get("summary", ""), "is_terminal": item.get("is_terminal", False)}
        for item in nodes
        if item.get("id") in neighbor_ids
    ]
    macro_node_id = node.get("macro_node_id")
    contract_id = node.get("contract_id")
    contracts = [
        contract
        for contract in as_list(game_ir.get("node_contracts"))
        if isinstance(contract, dict) and (
            contract.get("id") == contract_id
            or contract.get("macro_node_id") == macro_node_id
            or node_id in as_list(contract.get("branch_node_ids"))
        )
    ]
    mesh_expansions = [
        expansion
        for expansion in as_list(game_ir.get("mesh_expansions"))
        if isinstance(expansion, dict) and (
            node_id in as_list(expansion.get("node_ids"))
            or node_id == expansion.get("parent_ref_id")
            or macro_node_id == expansion.get("root_macro_node_id")
        )
    ]
    outgoing_edge_ids = {edge.get("id") for edge in outgoing}
    event_rules = [
        rule
        for rule in as_list(game_ir.get("event_rules"))
        if isinstance(rule, dict) and (
            rule.get("source_edge_id") in outgoing_edge_ids
            or rule.get("source_subgraph_id") in {expansion.get("id") for expansion in mesh_expansions}
        )
    ]
    relevant_state_ids = state_refs_from_any({
        "node": node,
        "incoming": incoming,
        "outgoing": outgoing,
        "contracts": contracts,
        "mesh_expansions": mesh_expansions,
        "event_rules": event_rules,
    })
    all_variables = as_list(game_ir.get("global_state_variables") or game_ir.get("state_variables"))
    state_variables = [
        variable
        for variable in all_variables
        if isinstance(variable, dict) and variable.get("id") in relevant_state_ids
    ]
    packet = {
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "DesignLayerV2ContextProjector",
            "source": "derived_from_public_branch_graph_and_game_ir",
        },
        "source_node_id": node_id,
        "branch_graph_node": node,
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "neighbor_summaries": neighbors,
        "available_exits": [
            {
                "edge_id": edge.get("id"),
                "label": edge.get("label", ""),
                "to": edge.get("to"),
                "condition_type": edge.get("condition_type", "unconditional"),
                "conditions": as_list(edge.get("conditions")),
                "effects": edge_state_effects(edge),
                "target_summary": nodes_by_id.get(str(edge.get("to")), {}).get("summary", "") if isinstance(edge.get("to"), str) else "",
            }
            for edge in outgoing
        ],
        "node_contract": contracts[0] if contracts else {},
        "mesh_expansions": mesh_expansions,
        "state_variables": state_variables,
        "event_rules": event_rules,
        "source_adaptation_context": project_source_adaptation_context(run_root, node_id),
        "transition_context": project_transition_context(node, incoming, outgoing, nodes_by_id),
        "continuity": {
            "design_brief": game_ir.get("design_brief", {}),
            "source_facts_digest": game_ir.get("source_facts_digest", {}),
            "adaptation_policy_digest": game_ir.get("adaptation_policy_digest", {}),
        },
    }
    output_path = run_root / "workspace" / "agent_context" / f"node.{safe_suffix(node_id)}.json"
    write_json(output_path, packet)
    return output_path, packet
