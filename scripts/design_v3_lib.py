#!/usr/bin/env python3
"""Design Layer V3 validation and compilation helpers.

V3 uses fine-to-coarse story extraction and coarse-to-fine graph/state design.
It compiles its internal hierarchy into the public design interface consumed by
the existing downstream pipeline.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Json,
    ValidationResult,
    as_list,
    ensure_dir,
    path_for,
    read_json,
    stable_id,
    validate_branch_graph,
    validate_game_ir,
    validate_graph_ir_consistency,
    validate_requirements,
    validate_synopsis,
    write_json,
)


DESIGN_V3_ROOT = Path("workspace/design_layer_v3")
DESIGN_V3_VALIDATION_REPORT = DESIGN_V3_ROOT / "validation/validation_report.json"
DESIGN_V3_COMPILE_REPORT = DESIGN_V3_ROOT / "compile_report.json"

BASE_V3_DIRECTORIES = [
    "story_levels",
    "facts",
    "adaptation",
    "design_levels",
    "assembled",
    "validation",
]

STATE_TYPES = {"boolean", "integer", "number", "string", "enum"}
INTERNAL_TRACE_KEYS = {
    "source_refs",
    "source_spans",
    "coverage_ids",
    "coverage_row_ids",
    "shard_id",
    "shard_path",
    "source_coverage_ids",
}


def design_v3_root(run_root: Path) -> Path:
    return run_root / DESIGN_V3_ROOT


def design_v3_path(run_root: Path, relative: str | Path) -> Path:
    return design_v3_root(run_root) / relative


def level_id(level: int) -> str:
    return f"level_{level:02d}"


def ensure_design_v3_layout(run_root: Path, levels: list[int] | None = None) -> None:
    for relative in BASE_V3_DIRECTORIES:
        ensure_dir(design_v3_path(run_root, relative))
    for level in levels or [1, 2, 3]:
        lid = level_id(level)
        for relative in [
            f"story_levels/{lid}/shards",
            f"story_levels/{lid}/shard_returns",
            f"facts/{lid}/shards",
            f"facts/{lid}/shard_returns",
            f"design_levels/{lid}/shards",
            f"design_levels/{lid}/shard_returns",
        ]:
            ensure_dir(design_v3_path(run_root, relative))


def load_json_at(path: Path, result: ValidationResult, relative: str) -> Json | None:
    if not path.exists():
        result.add("error", "missing_artifact", f"Missing V3 artifact: {DESIGN_V3_ROOT / relative}", str(DESIGN_V3_ROOT / relative))
        return None
    try:
        return read_json(path)
    except Exception as exc:  # noqa: BLE001
        result.add("error", "invalid_json", f"Cannot parse {DESIGN_V3_ROOT / relative}: {exc}", str(DESIGN_V3_ROOT / relative))
        return None


def write_merge_report(run_root: Path, relative: str, count: int, output_paths: list[str]) -> None:
    write_json(design_v3_path(run_root, relative), {
        "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
        "status": "merged",
        "input_return_count": count,
        "output_paths": output_paths,
    })


def read_shard_returns(directory: Path) -> list[Json]:
    payloads: list[Json] = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def merge_story_level_shards(run_root: Path, level: int) -> None:
    lid = level_id(level)
    target = design_v3_path(run_root, f"story_levels/{lid}/linear_story.json")
    returns_dir = design_v3_path(run_root, f"story_levels/{lid}/shard_returns")
    if target.exists() or not returns_dir.exists():
        return
    payloads = read_shard_returns(returns_dir)
    if not payloads:
        return
    units: list[Any] = []
    granularity = ""
    for payload in payloads:
        source = payload.get("linear_story") if isinstance(payload.get("linear_story"), dict) else payload
        units.extend(as_list(source.get("units")))
        if not granularity and isinstance(source.get("granularity"), str):
            granularity = source["granularity"]
    write_json(target, {
        "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
        "level": level,
        "level_id": lid,
        "granularity": granularity,
        "units": units,
    })
    write_merge_report(run_root, f"story_levels/{lid}/merge_report.json", len(payloads), [str(DESIGN_V3_ROOT / f"story_levels/{lid}/linear_story.json")])


def merge_fact_level_shards(run_root: Path, level: int, filename: str) -> None:
    lid = level_id(level)
    target = design_v3_path(run_root, f"facts/{lid}/{filename}")
    returns_dir = design_v3_path(run_root, f"facts/{lid}/shard_returns")
    if target.exists() or not returns_dir.exists():
        return
    payloads = read_shard_returns(returns_dir)
    if not payloads:
        return
    merged: Json = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
        "level": level,
    }
    for key in ("facts", "characters", "locations", "objects", "events", "relationships", "world_rules", "foreshadowing", "themes"):
        merged[key] = []
    for payload in payloads:
        source = payload.get("fact_view") or payload.get("local_facts") or payload
        if not isinstance(source, dict):
            continue
        for key in list(merged):
            if key in ("metadata", "level"):
                continue
            merged[key].extend(as_list(source.get(key)))
    write_json(target, merged)
    write_merge_report(run_root, f"facts/{lid}/merge_report.json", len(payloads), [str(DESIGN_V3_ROOT / f"facts/{lid}/{filename}")])


def merge_design_level_shards(run_root: Path, level: int) -> None:
    lid = level_id(level)
    root = design_v3_path(run_root, f"design_levels/{lid}")
    returns_dir = root / "shard_returns"
    if not returns_dir.exists():
        return
    payloads = read_shard_returns(returns_dir)
    if not payloads:
        return

    outputs: dict[str, Json] = {
        "state_model.json": {
            "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
            "level": level,
            "variables": [],
        },
        "story_graph.json": {
            "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
            "level": level,
            "start_node_id": "",
            "nodes": [],
            "edges": [],
        },
        "contracts.json": {
            "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
            "level": level,
            "contracts": [],
        },
        "parent_state_settlements.json": {
            "metadata": {"schema_version": "0.1.0", "generated_by": "DesignLayerV3ShardMerger"},
            "level": level,
            "parent_level": None,
            "settlements": [],
        },
    }

    for payload in payloads:
        state = payload.get("state_model") if isinstance(payload.get("state_model"), dict) else payload
        graph = payload.get("story_graph") if isinstance(payload.get("story_graph"), dict) else payload
        contracts = payload.get("contracts") if isinstance(payload.get("contracts"), dict) else payload
        settlements = payload.get("parent_state_settlements") if isinstance(payload.get("parent_state_settlements"), dict) else payload
        outputs["state_model.json"]["variables"].extend(as_list(state.get("variables")) if isinstance(state, dict) else [])
        if isinstance(graph, dict):
            if not outputs["story_graph.json"]["start_node_id"] and isinstance(graph.get("start_node_id"), str):
                outputs["story_graph.json"]["start_node_id"] = graph["start_node_id"]
            outputs["story_graph.json"]["nodes"].extend(as_list(graph.get("nodes")))
            outputs["story_graph.json"]["edges"].extend(as_list(graph.get("edges")))
        outputs["contracts.json"]["contracts"].extend(as_list(contracts.get("contracts")) if isinstance(contracts, dict) else [])
        if isinstance(settlements, dict):
            if settlements.get("parent_level") is not None:
                outputs["parent_state_settlements.json"]["parent_level"] = settlements.get("parent_level")
            outputs["parent_state_settlements.json"]["settlements"].extend(as_list(settlements.get("settlements")))

    output_paths = []
    for filename, payload in outputs.items():
        path = root / filename
        if path.exists():
            continue
        write_json(path, payload)
        output_paths.append(str(DESIGN_V3_ROOT / f"design_levels/{lid}/{filename}"))
    if output_paths:
        write_merge_report(run_root, f"design_levels/{lid}/merge_report.json", len(payloads), output_paths)


def merge_v3_shard_returns(run_root: Path, levels: list[int]) -> None:
    for level in levels:
        merge_story_level_shards(run_root, level)
        merge_fact_level_shards(run_root, level, "local_facts.json" if level == min(levels) else "fact_view.json")
        merge_design_level_shards(run_root, level)


def unique_id_check(items: list[Any], path: str, result: ValidationResult, key: str = "id") -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            result.add("error", "schema", "Entries must be objects.", f"{path}[{index}]")
            continue
        item_id = item.get(key)
        if not isinstance(item_id, str) or not item_id.strip():
            result.add("error", "schema", "Entry needs a stable id.", f"{path}[{index}].{key}")
        elif item_id in seen:
            result.add("error", "duplicate_id", f"Duplicate id: {item_id}", f"{path}[{index}].{key}")
        else:
            seen.add(item_id)
    return seen


def dict_by_id(items: list[Any]) -> dict[str, Json]:
    return {item["id"]: item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def normalize_levels(policy: Json, result: ValidationResult) -> list[int]:
    entries = [entry for entry in as_list(policy.get("enabled_levels")) if isinstance(entry, dict)]
    levels: list[int] = []
    for index, entry in enumerate(entries):
        level = entry.get("level")
        if not isinstance(level, int) or level < 1:
            result.add("error", "schema", "enabled_levels entries need positive integer level.", f"hierarchy_policy.enabled_levels[{index}].level")
            continue
        levels.append(level)
    if not levels:
        result.add("error", "schema", "hierarchy_policy.enabled_levels must contain at least one level.", "hierarchy_policy.enabled_levels")
        return []
    levels = sorted(set(levels))
    expected = list(range(levels[0], levels[-1] + 1))
    if levels != expected:
        result.add("error", "hierarchy_gap", f"Enabled V3 levels must be continuous: got {levels}, expected {expected}.", "hierarchy_policy.enabled_levels")
    finest = policy.get("finest_level", levels[0])
    coarsest = policy.get("coarsest_level", levels[-1])
    if finest != levels[0] or coarsest != levels[-1]:
        result.add(
            "error",
            "hierarchy_bounds",
            f"finest_level/coarsest_level must match enabled range {levels[0]}..{levels[-1]}.",
            "hierarchy_policy",
        )
    return levels


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


def normalize_effect(effect: Any) -> Json:
    if not isinstance(effect, dict):
        return {"state_variable_id": str(effect), "operation": "set", "value": True}
    normalized = dict(effect)
    state_id = normalized.pop("state", None) or normalized.get("state_variable_id")
    if state_id is not None:
        normalized["state_variable_id"] = state_id
    normalized.setdefault("operation", "set")
    return normalized


def state_refs_from_ops(items: Any) -> set[str]:
    refs: set[str] = set()
    for item in as_list(items):
        if isinstance(item, str):
            refs.add(item)
        elif isinstance(item, dict):
            value = item.get("state_variable_id") or item.get("state") or item.get("id")
            if isinstance(value, str):
                refs.add(value)
    return refs


def load_design_v3_artifacts(run_root: Path, result: ValidationResult, merge_shards: bool = True) -> dict[str, Any] | None:
    ensure_design_v3_layout(run_root)
    policy = load_json_at(design_v3_path(run_root, "hierarchy_policy.json"), result, "hierarchy_policy.json")
    if not policy:
        return None
    levels = normalize_levels(policy, result)
    ensure_design_v3_layout(run_root, levels)
    if merge_shards and levels:
        merge_v3_shard_returns(run_root, levels)

    story_levels: dict[int, Json] = {}
    fact_levels: dict[int, Json] = {}
    design_levels: dict[int, dict[str, Json]] = {}
    for level in levels:
        lid = level_id(level)
        story = load_json_at(design_v3_path(run_root, f"story_levels/{lid}/linear_story.json"), result, f"story_levels/{lid}/linear_story.json")
        if story:
            story_levels[level] = story
        fact_filename = "local_facts.json" if level == min(levels) else "fact_view.json"
        fact_path = design_v3_path(run_root, f"facts/{lid}/{fact_filename}")
        if fact_path.exists():
            fact_levels[level] = read_json(fact_path)
        design_levels[level] = {}
        for name in ("state_model", "story_graph", "contracts", "parent_state_settlements"):
            filename = f"design_levels/{lid}/{name}.json"
            payload = load_json_at(design_v3_path(run_root, filename), result, filename)
            if payload:
                design_levels[level][name] = payload

    canonical_facts = load_json_at(design_v3_path(run_root, "facts/canonical_fact_graph.json"), result, "facts/canonical_fact_graph.json")
    global_policy = load_json_at(design_v3_path(run_root, "adaptation/global_policy.json"), result, "adaptation/global_policy.json")
    if result.status == "fail":
        return None
    return {
        "policy": policy,
        "levels": levels,
        "story_levels": story_levels,
        "fact_levels": fact_levels,
        "canonical_facts": canonical_facts or {},
        "global_policy": global_policy or {},
        "design_levels": design_levels,
    }


def validate_story_levels(result: ValidationResult, artifacts: dict[str, Any]) -> dict[int, dict[str, Json]]:
    levels: list[int] = artifacts["levels"]
    units_by_level: dict[int, dict[str, Json]] = {}
    for level in levels:
        story = artifacts["story_levels"].get(level, {})
        if story.get("level") != level:
            result.add("error", "schema", f"linear_story.level must be {level}.", f"story_levels.{level_id(level)}.level")
        units = [unit for unit in as_list(story.get("units")) if isinstance(unit, dict)]
        unit_ids = unique_id_check(units, f"story_levels.{level_id(level)}.units", result)
        units_by_level[level] = dict_by_id(units)
        if not units:
            result.add("error", "schema", "linear_story.units must be non-empty.", f"story_levels.{level_id(level)}.units")
    for level in levels:
        units = list(units_by_level.get(level, {}).values())
        for index, unit in enumerate(units):
            if not isinstance(unit.get("summary"), str) or not unit["summary"].strip():
                result.add("warning", "thin_story_unit", f"Story unit has no summary: {unit.get('id')}", f"story_levels.{level_id(level)}.units[{index}].summary")
            if level < max(levels):
                parent = unit.get("parent_unit_id")
                if not isinstance(parent, str) or parent not in units_by_level.get(level + 1, {}):
                    result.add("error", "missing_parent_story_unit", f"Story unit needs parent_unit_id for level {level + 1}: {unit.get('id')}", f"story_levels.{level_id(level)}.units[{index}].parent_unit_id")
            for child_id in as_list(unit.get("child_unit_ids")):
                if level == min(levels):
                    result.add("warning", "unexpected_child_story_unit", f"Finest story level should not normally declare child_unit_ids: {unit.get('id')}", f"story_levels.{level_id(level)}.units[{index}].child_unit_ids")
                elif child_id not in units_by_level.get(level - 1, {}):
                    result.add("error", "invalid_reference", f"child_unit_id references missing lower-level story unit: {child_id}", f"story_levels.{level_id(level)}.units[{index}].child_unit_ids")
        if level > min(levels):
            lower_units = units_by_level.get(level - 1, {})
            for unit in units:
                for child_id in as_list(unit.get("child_unit_ids")):
                    child = lower_units.get(str(child_id), {})
                    if child and child.get("parent_unit_id") != unit.get("id"):
                        result.add("error", "story_parent_child_mismatch", f"Child {child_id} does not point back to parent {unit.get('id')}.", f"story_levels.{level_id(level)}.units.child_unit_ids")
        _ = unit_ids
    return units_by_level


def validate_design_v3(run_root: Path, write_report: bool = True) -> ValidationResult:
    result = ValidationResult()
    artifacts = load_design_v3_artifacts(run_root, result, merge_shards=True)
    if artifacts is None:
        if write_report:
            write_json(run_root / DESIGN_V3_VALIDATION_REPORT, result.to_json())
        return result

    levels: list[int] = artifacts["levels"]
    finest = min(levels)
    coarsest = max(levels)
    units_by_level = validate_story_levels(result, artifacts)

    facts = artifacts["canonical_facts"]
    fact_ids = unique_id_check(as_list(facts.get("facts")), "facts.canonical_fact_graph.facts", result)
    character_ids = unique_id_check(as_list(facts.get("characters")), "facts.canonical_fact_graph.characters", result)
    location_ids = unique_id_check(as_list(facts.get("locations")), "facts.canonical_fact_graph.locations", result)
    event_ids = unique_id_check(as_list(facts.get("events")), "facts.canonical_fact_graph.events", result)
    fixed_fact_ids = set(str(item) for item in as_list(artifacts["global_policy"].get("fixed_fact_ids")))
    for fact_id in fixed_fact_ids:
        if fact_id not in fact_ids:
            result.add("error", "invalid_reference", f"global_policy.fixed_fact_ids references missing fact: {fact_id}", "adaptation.global_policy.fixed_fact_ids")
    _ = character_ids | location_ids | event_ids

    state_ids_by_level: dict[int, set[str]] = {}
    state_defs: dict[str, tuple[int, Json]] = {}
    graph_node_ids_by_level: dict[int, set[str]] = {}
    graph_nodes_by_level: dict[int, dict[str, Json]] = {}
    graph_edges_by_level: dict[int, list[Json]] = {}

    for level in sorted(levels, reverse=True):
        lid = level_id(level)
        design = artifacts["design_levels"].get(level, {})
        state_model = design.get("state_model", {})
        variables = [var for var in as_list(state_model.get("variables")) if isinstance(var, dict)]
        state_ids = unique_id_check(variables, f"design_levels.{lid}.state_model.variables", result)
        state_ids_by_level[level] = state_ids
        for index, variable in enumerate(variables):
            variable_id = variable.get("id")
            if variable.get("type") not in STATE_TYPES:
                result.add("error", "schema", f"Unsupported state variable type: {variable.get('type')}", f"design_levels.{lid}.state_model.variables[{index}].type")
            if "initial_value" not in variable:
                result.add("error", "schema", "State variable needs initial_value.", f"design_levels.{lid}.state_model.variables[{index}].initial_value")
            owner_story_unit = variable.get("owner_story_unit_id")
            if isinstance(owner_story_unit, str) and owner_story_unit not in units_by_level.get(level, {}):
                result.add("error", "invalid_reference", f"State owner_story_unit_id is not in this level: {owner_story_unit}", f"design_levels.{lid}.state_model.variables[{index}].owner_story_unit_id")
            if isinstance(variable_id, str):
                existing = state_defs.get(variable_id)
                if existing:
                    _, previous = existing
                    if previous.get("type") != variable.get("type") or previous.get("initial_value") != variable.get("initial_value"):
                        result.add("error", "state_conflict", f"State variable has conflicting definitions: {variable_id}", f"design_levels.{lid}.state_model.variables[{index}]")
                else:
                    state_defs[variable_id] = (level, variable)

        graph = design.get("story_graph", {})
        nodes = [node for node in as_list(graph.get("nodes")) if isinstance(node, dict)]
        edges = [edge for edge in as_list(graph.get("edges")) if isinstance(edge, dict)]
        node_ids = unique_id_check(nodes, f"design_levels.{lid}.story_graph.nodes", result)
        graph_node_ids_by_level[level] = node_ids
        graph_nodes_by_level[level] = dict_by_id(nodes)
        graph_edges_by_level[level] = edges
        story_unit_ids_this_level = set(units_by_level.get(level, {}))
        if graph.get("start_node_id") not in node_ids:
            result.add("error", "missing_start", f"story_graph.start_node_id must reference a node at level {level}.", f"design_levels.{lid}.story_graph.start_node_id")
        unique_id_check(edges, f"design_levels.{lid}.story_graph.edges", result)
        story_unit_to_nodes: dict[str, list[str]] = {}
        for node_index, node in enumerate(nodes):
            node_story_unit_ids = [story_unit_id for story_unit_id in as_list(node.get("story_unit_ids")) if isinstance(story_unit_id, str)]
            if not node_story_unit_ids:
                result.add(
                    "error",
                    "design_story_anchor",
                    "Each graph node must reference at least one same-level source story unit.",
                    f"design_levels.{lid}.story_graph.nodes[{node_index}].story_unit_ids",
                )
            for story_unit_id in node_story_unit_ids:
                if story_unit_id not in units_by_level.get(level, {}):
                    result.add("error", "invalid_reference", f"Graph node references missing story unit: {story_unit_id}", f"design_levels.{lid}.story_graph.nodes[{node_index}].story_unit_ids")
                elif isinstance(node.get("id"), str):
                    story_unit_to_nodes.setdefault(story_unit_id, []).append(node["id"])
            source_derivation = node.get("source_derivation")
            if isinstance(source_derivation, dict):
                for anchor_id in as_list(source_derivation.get("base_story_unit_ids")):
                    if isinstance(anchor_id, str) and anchor_id not in units_by_level.get(level, {}):
                        result.add("error", "invalid_reference", f"source_derivation.base_story_unit_ids references missing story unit: {anchor_id}", f"design_levels.{lid}.story_graph.nodes[{node_index}].source_derivation.base_story_unit_ids")
            if level < coarsest:
                parent_node_id = node.get("parent_node_id")
                if parent_node_id not in graph_node_ids_by_level.get(level + 1, set()):
                    result.add("error", "invalid_reference", f"Graph node needs parent_node_id from level {level + 1}: {parent_node_id}", f"design_levels.{lid}.story_graph.nodes[{node_index}].parent_node_id")
        missing_story_unit_ids = sorted(story_unit_ids_this_level - set(story_unit_to_nodes))
        if missing_story_unit_ids:
            shown = ", ".join(missing_story_unit_ids[:10])
            suffix = "" if len(missing_story_unit_ids) <= 10 else f", and {len(missing_story_unit_ids) - 10} more"
            result.add(
                "error",
                "design_story_anchor",
                f"Story units missing same-level graph node anchors: {shown}{suffix}",
                f"design_levels.{lid}.story_graph.nodes",
            )
        for edge_index, edge in enumerate(edges):
            for key in ("from", "to"):
                if edge.get(key) not in node_ids:
                    result.add("error", "invalid_reference", f"Edge references missing {key} node: {edge.get(key)}", f"design_levels.{lid}.story_graph.edges[{edge_index}].{key}")
            for state_id in state_refs_from_ops(edge.get("conditions")) | state_refs_from_ops(edge.get("effects")):
                if state_id not in state_defs and not any(state_id in ids for ids in state_ids_by_level.values()):
                    result.add("error", "invalid_reference", f"Graph edge references missing state variable: {state_id}", f"design_levels.{lid}.story_graph.edges[{edge_index}]")

    all_state_ids = set(state_defs)
    all_node_ids = set().union(*graph_node_ids_by_level.values()) if graph_node_ids_by_level else set()
    for level in levels:
        lid = level_id(level)
        design = artifacts["design_levels"].get(level, {})
        contracts = [contract for contract in as_list(design.get("contracts", {}).get("contracts")) if isinstance(contract, dict)]
        unique_id_check(contracts, f"design_levels.{lid}.contracts.contracts", result)
        for index, contract in enumerate(contracts):
            node_id = contract.get("graph_node_id")
            if node_id not in graph_node_ids_by_level.get(level, set()):
                result.add("error", "invalid_reference", f"Contract references missing graph node at level {level}: {node_id}", f"design_levels.{lid}.contracts.contracts[{index}].graph_node_id")
            for state_id in set(as_list(contract.get("allowed_state_reads"))) | set(as_list(contract.get("allowed_state_writes"))):
                if state_id not in all_state_ids:
                    result.add("error", "invalid_reference", f"Contract references missing state variable: {state_id}", f"design_levels.{lid}.contracts.contracts[{index}]")
            for story_unit_id in as_list(contract.get("story_unit_ids")):
                if story_unit_id not in units_by_level.get(level, {}):
                    result.add("error", "invalid_reference", f"Contract references missing story unit: {story_unit_id}", f"design_levels.{lid}.contracts.contracts[{index}].story_unit_ids")

        settlements_payload = design.get("parent_state_settlements", {})
        settlements = [settlement for settlement in as_list(settlements_payload.get("settlements")) if isinstance(settlement, dict)]
        unique_id_check(settlements, f"design_levels.{lid}.parent_state_settlements.settlements", result)
        if level == coarsest:
            if settlements_payload.get("parent_level") is not None:
                result.add("error", "parent_level", "Coarsest level parent_state_settlements.parent_level must be null.", f"design_levels.{lid}.parent_state_settlements.parent_level")
            if settlements:
                result.add("warning", "coarsest_settlement", "Coarsest level has no parent state; settlements will be ignored.", f"design_levels.{lid}.parent_state_settlements.settlements")
            continue
        if settlements_payload.get("parent_level") != level + 1:
            result.add("error", "parent_level", f"parent_level must be {level + 1}.", f"design_levels.{lid}.parent_state_settlements.parent_level")
        if not settlements:
            result.add("error", "missing_parent_state_settlement", f"Level {level} must declare at least one parent state settlement.", f"design_levels.{lid}.parent_state_settlements.settlements")
        parent_state_ids = state_ids_by_level.get(level + 1, set())
        current_or_parent_state_ids = state_ids_by_level.get(level, set()) | parent_state_ids
        for index, settlement in enumerate(settlements):
            source_node = settlement.get("source_graph_node_id")
            parent_node = settlement.get("parent_graph_node_id")
            if source_node not in graph_node_ids_by_level.get(level, set()):
                result.add("error", "invalid_reference", f"Settlement source_graph_node_id is not in level {level}: {source_node}", f"design_levels.{lid}.parent_state_settlements.settlements[{index}].source_graph_node_id")
            if parent_node not in graph_node_ids_by_level.get(level + 1, set()):
                result.add("error", "invalid_reference", f"Settlement parent_graph_node_id is not in level {level + 1}: {parent_node}", f"design_levels.{lid}.parent_state_settlements.settlements[{index}].parent_graph_node_id")
            for state_id in state_refs_from_ops(settlement.get("conditions")):
                if state_id not in current_or_parent_state_ids:
                    result.add("error", "invalid_reference", f"Settlement condition references missing current/parent state: {state_id}", f"design_levels.{lid}.parent_state_settlements.settlements[{index}].conditions")
            effects = [normalize_effect(effect) for effect in as_list(settlement.get("effects_on_parent_state")) if isinstance(effect, dict)]
            if not effects and not isinstance(settlement.get("reason"), str):
                result.add("warning", "empty_settlement_without_reason", "Empty parent state settlement should explain why no parent state changes.", f"design_levels.{lid}.parent_state_settlements.settlements[{index}].reason")
            for effect in effects:
                state_id = effect.get("state_variable_id")
                if state_id not in parent_state_ids:
                    result.add("error", "parent_state_settlement", f"effects_on_parent_state must write an immediate parent state variable: {state_id}", f"design_levels.{lid}.parent_state_settlements.settlements[{index}].effects_on_parent_state")

    if write_report:
        write_json(run_root / DESIGN_V3_VALIDATION_REPORT, {
            "design_layer": {"version": "v3", "root": str(DESIGN_V3_ROOT)},
            **result.to_json(),
        })
    _ = finest, all_node_ids
    return result


def graph_order(graph: Json) -> dict[str, int]:
    return {
        str(node.get("id")): index
        for index, node in enumerate(as_list(graph.get("nodes")))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }


def public_graph_from_v3(artifacts: dict[str, Any]) -> tuple[Json, dict[str, Json], dict[str, Json]]:
    levels: list[int] = artifacts["levels"]
    design = artifacts["design_levels"]
    finest = min(levels)
    coarsest = max(levels)
    all_nodes: dict[str, Json] = {}
    node_level: dict[str, int] = {}
    children_by_parent: dict[str, list[str]] = {}
    level_orders: dict[int, dict[str, int]] = {}

    for level in levels:
        graph = design[level]["story_graph"]
        level_orders[level] = graph_order(graph)
        for node in as_list(graph.get("nodes")):
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                continue
            node_id = node["id"]
            all_nodes[node_id] = node
            node_level[node_id] = level
            parent = node.get("parent_node_id")
            if isinstance(parent, str):
                children_by_parent.setdefault(parent, []).append(node_id)

    expanded_node_ids = set(children_by_parent)
    public_node_ids = {node_id for node_id, level in node_level.items() if level == finest}

    def sort_nodes(ids: list[str]) -> list[str]:
        return sorted(ids, key=lambda node_id: (node_level.get(node_id, 999), level_orders.get(node_level.get(node_id, 0), {}).get(node_id, 9999), node_id))

    def entry_for(node_id: str, seen: set[str] | None = None) -> str | None:
        if node_id in public_node_ids:
            return node_id
        if node_id not in expanded_node_ids:
            return None
        seen = seen or set()
        if node_id in seen:
            return None
        seen.add(node_id)
        children = sort_nodes(children_by_parent.get(node_id, []))
        if not children:
            return None
        child_set = set(children)
        child_level = node_level.get(children[0])
        incoming = {
            edge.get("to")
            for edge in as_list(design.get(child_level, {}).get("story_graph", {}).get("edges"))
            if isinstance(edge, dict) and edge.get("from") in child_set and edge.get("to") in child_set
        }
        candidates = [child for child in children if child not in incoming] or children
        return entry_for(candidates[0], seen)

    def exit_for(node_id: str, seen: set[str] | None = None) -> str | None:
        if node_id in public_node_ids:
            return node_id
        if node_id not in expanded_node_ids:
            return None
        seen = seen or set()
        if node_id in seen:
            return None
        seen.add(node_id)
        children = sort_nodes(children_by_parent.get(node_id, []))
        if not children:
            return None
        child_set = set(children)
        child_level = node_level.get(children[0])
        outgoing = {
            edge.get("from")
            for edge in as_list(design.get(child_level, {}).get("story_graph", {}).get("edges"))
            if isinstance(edge, dict) and edge.get("from") in child_set and edge.get("to") in child_set
        }
        candidates = [child for child in children if child not in outgoing] or children
        return exit_for(candidates[-1], seen)

    public_nodes: list[Json] = []
    for node_id in sort_nodes(list(public_node_ids)):
        node = all_nodes[node_id]
        level = node_level[node_id]
        public_node = {
            "id": node_id,
            "node_type": node.get("node_type", "scene"),
            "title": node.get("title", node_id),
            "summary": node.get("summary", ""),
            "body": node.get("body", ""),
            "is_terminal": bool(node.get("is_terminal", False)),
            "layer": f"v3.{level_id(level)}",
            "parent_node_id": node.get("parent_node_id"),
            "story_unit_ids": as_list(node.get("story_unit_ids")),
        }
        if isinstance(node.get("source_derivation"), dict):
            public_node["source_derivation"] = node["source_derivation"]
        public_nodes.append(public_node)

    public_edges: list[Json] = []
    public_edge_origins: dict[str, Json] = {}
    seen_edge_ids: set[str] = set()
    for edge in as_list(design[finest]["story_graph"].get("edges")):
        if not isinstance(edge, dict) or not isinstance(edge.get("id"), str):
            continue
        source = edge.get("from")
        target = edge.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if source not in public_node_ids or target not in public_node_ids or source == target:
            continue
        edge_id = str(edge["id"])
        if edge_id in seen_edge_ids:
            edge_id = stable_id(f"{edge_id}.{source}.{target}", "edge")
        seen_edge_ids.add(edge_id)
        public_edge = {
            "id": edge_id,
            "from": source,
            "to": target,
            "label": str(edge.get("label", "")),
            "condition_type": str(edge.get("condition_type", "unconditional")),
            "conditions": as_list(edge.get("conditions")),
            "source_rule_ids": [edge["id"]],
            "layer": f"v3.{level_id(finest)}",
        }
        public_edges.append(public_edge)
        public_edge_origins[edge_id] = edge

    clusters = []
    for node_id in sort_nodes(list(expanded_node_ids)):
        descendants = []
        stack = list(children_by_parent.get(node_id, []))
        while stack:
            child = stack.pop()
            if child in public_node_ids:
                descendants.append(child)
            stack.extend(children_by_parent.get(child, []))
        clusters.append({
            "id": node_id,
            "title": all_nodes.get(node_id, {}).get("title", node_id),
            "node_ids": sort_nodes(descendants),
        })

    coarsest_start = design[coarsest]["story_graph"].get("start_node_id")
    start_node_id = entry_for(str(coarsest_start)) if isinstance(coarsest_start, str) else None
    if not start_node_id and public_nodes:
        start_node_id = public_nodes[0]["id"]

    public_node_map = {
        node_id: {
            "entry": entry_for(node_id) or node_id,
            "exit": exit_for(node_id) or node_id,
        }
        for node_id in all_nodes
    }

    return {
        "metadata": {
            "schema_version": "0.2.0",
            "generated_by": "DesignLayerV3Assembler",
            "notes": [
                "Compiled from Design Layer V3.",
                "Runtime-facing branch_graph nodes and edges are exported from the finest design level only; higher-level graphs are design/context artifacts.",
            ],
        },
        "title": artifacts["policy"].get("title") or artifacts["canonical_facts"].get("title") or "Generated Narrative Game",
        "graph_scope": "full_game",
        "start_node_id": start_node_id or "",
        "clusters": clusters,
        "source_outline_ids": [
            str(unit.get("id"))
            for level in sorted(levels)
            for unit in as_list(artifacts["story_levels"].get(level, {}).get("units"))
            if isinstance(unit, dict) and isinstance(unit.get("id"), str)
        ],
        "nodes": public_nodes,
        "edges": public_edges,
    }, public_edge_origins, public_node_map


def compile_requirements(run_root: Path, artifacts: dict[str, Any]) -> Json:
    prompt_path = path_for(run_root, "prompt")
    prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
    policy = artifacts["global_policy"]
    facts_by_id = dict_by_id(as_list(artifacts["canonical_facts"].get("facts")))
    requirements = []
    for fact_id in as_list(policy.get("fixed_fact_ids")):
        fact = facts_by_id.get(str(fact_id), {})
        requirements.append({
            "id": f"req.preserve.{safe_suffix(str(fact_id))}",
            "priority": "must",
            "text": f"Preserve canon fact {fact_id}: {fact.get('summary', '')}".strip(),
            "source_phrase": str(fact_id),
        })
    for process in as_list(policy.get("variable_processes")):
        if isinstance(process, dict):
            requirements.append({
                "id": f"req.process.{safe_suffix(str(process.get('id', 'process')))}",
                "priority": "should",
                "text": process.get("description", "Support a variable narrative process."),
                "source_phrase": str(process.get("id", "")),
            })
    if not requirements:
        requirements.append({
            "id": "req.core",
            "priority": "must",
            "text": "Produce a playable branching narrative from the V3 hierarchical design layer.",
            "source_phrase": "design-layer-v3",
        })
    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV3Assembler", "notes": ["Compiled from Design Layer V3."]},
        "prompt": prompt,
        "target_experience": policy.get("target_experience", "A hierarchical branching narrative."),
        "requirements": requirements,
        "creative_constraints": {
            "genre": policy.get("genre", ""),
            "tone": policy.get("tone", ""),
            "themes": as_list(policy.get("themes")),
            "motifs": as_list(policy.get("motifs")),
            "prohibited_content": [
                item.get("description", "")
                for item in as_list(policy.get("forbidden_changes"))
                if isinstance(item, dict)
            ],
        },
        "production_constraints": {"target_language": policy.get("target_language", "en"), "asset_budget_level": "low", "notes": ["Compiled from Design Layer V3."]},
        "assumptions": [],
        "unknowns": [],
    }


def safe_suffix(identifier: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier).strip("_") or "item"


def compile_synopsis(artifacts: dict[str, Any]) -> Json:
    finest = min(artifacts["levels"])
    coarsest = max(artifacts["levels"])
    coarsest_story = artifacts["story_levels"].get(coarsest, {})
    finest_story = artifacts["story_levels"].get(finest, {})
    events = [
        {
            "id": unit.get("id", f"event.{index}"),
            "summary": unit.get("summary", ""),
            "purpose": unit.get("granularity", f"level_{coarsest} story unit"),
            "requirement_ids": [],
        }
        for index, unit in enumerate(as_list(coarsest_story.get("units")))
        if isinstance(unit, dict)
    ] or [
        {
            "id": unit.get("id", f"event.{index}"),
            "summary": unit.get("summary", ""),
            "purpose": f"level_{finest} story unit",
            "requirement_ids": [],
        }
        for index, unit in enumerate(as_list(finest_story.get("units")))
        if isinstance(unit, dict)
    ]
    facts = artifacts["canonical_facts"]
    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV3Assembler", "notes": ["Compiled from Design Layer V3."]},
        "title": artifacts["policy"].get("title") or "Generated Narrative Game",
        "summary": artifacts["global_policy"].get("target_experience", "A hierarchical branching narrative."),
        "events": events,
        "cast": [
            {"id": character.get("id"), "name": character.get("name", character.get("id", "")), "role": character.get("summary", "")}
            for character in as_list(facts.get("characters"))
            if isinstance(character, dict)
        ],
        "locations": [
            {"id": location.get("id"), "name": location.get("name", location.get("id", "")), "description": location.get("summary", "")}
            for location in as_list(facts.get("locations"))
            if isinstance(location, dict)
        ],
        "pacing_notes": ["Compiled from V3 story hierarchy."],
    }


def compile_game_ir(artifacts: dict[str, Any], branch_graph: Json, public_edge_origins: dict[str, Json], node_public_map: dict[str, Json]) -> Json:
    facts = artifacts["canonical_facts"]
    policy = artifacts["global_policy"]
    variables: list[Json] = []
    seen_state_ids: set[str] = set()
    for level in sorted(artifacts["levels"], reverse=True):
        for variable in as_list(artifacts["design_levels"][level]["state_model"].get("variables")):
            if not isinstance(variable, dict) or not isinstance(variable.get("id"), str):
                continue
            if variable["id"] in seen_state_ids:
                continue
            seen_state_ids.add(variable["id"])
            variables.append(strip_internal_trace(variable))

    event_rules: list[Json] = []
    for edge in as_list(branch_graph.get("edges")):
        if not isinstance(edge, dict) or not isinstance(edge.get("id"), str):
            continue
        origin = public_edge_origins.get(edge["id"], {})
        effects = [normalize_effect(effect) for effect in as_list(origin.get("effects"))]
        if edge.get("conditions") or effects or edge.get("condition_type") not in ("unconditional", ""):
            event_rules.append({
                "id": f"rule.{safe_suffix(edge['id'])}",
                "source_edge_id": edge["id"],
                "source_rule_ids": [edge["id"]],
                "conditions": as_list(edge.get("conditions")),
                "effects": effects,
                "description": edge.get("label", ""),
            })

    for level in artifacts["levels"]:
        settlements = as_list(artifacts["design_levels"][level]["parent_state_settlements"].get("settlements"))
        for settlement in settlements:
            if not isinstance(settlement, dict) or not isinstance(settlement.get("id"), str):
                continue
            source_node_id = settlement.get("source_graph_node_id")
            public_source_info = node_public_map.get(str(source_node_id), {})
            public_source = public_source_info.get("exit") if isinstance(public_source_info, dict) else None
            if not isinstance(public_source, str):
                public_source = str(source_node_id)
            event_rules.append({
                "id": f"rule.{safe_suffix(settlement['id'])}",
                "source_node_id": public_source,
                "source_settlement_id": settlement["id"],
                "conditions": as_list(settlement.get("conditions")),
                "effects": [normalize_effect(effect) for effect in as_list(settlement.get("effects_on_parent_state"))],
                "description": settlement.get("reason", "Parent state settlement."),
            })

    entities: list[Json] = []
    entities.extend({
        "id": character.get("id"),
        "kind": "character",
        "name": character.get("name", character.get("id", "")),
        "description": character.get("summary", ""),
    } for character in as_list(facts.get("characters")) if isinstance(character, dict))
    entities.extend({
        "id": location.get("id"),
        "kind": "location",
        "name": location.get("name", location.get("id", "")),
        "description": location.get("summary", ""),
    } for location in as_list(facts.get("locations")) if isinstance(location, dict))
    entities.extend({
        "id": item.get("id"),
        "kind": item.get("kind", "fact"),
        "name": item.get("name", item.get("id", "")),
        "description": item.get("summary", ""),
    } for item in as_list(facts.get("objects")) if isinstance(item, dict))

    return {
        "metadata": {"schema_version": "0.2.0", "generated_by": "DesignLayerV3Assembler", "notes": ["Compiled from Design Layer V3."]},
        "design_layer": {"version": "v3"},
        "design_brief": {
            "target_experience": policy.get("target_experience", "A hierarchical branching narrative."),
            "tone": policy.get("tone", ""),
            "themes": as_list(policy.get("themes")),
            "must_keep_constraints": as_list(policy.get("fixed_fact_ids")) + [
                item.get("description", "")
                for item in as_list(policy.get("forbidden_changes"))
                if isinstance(item, dict)
            ],
            "production_constraints": {"design_layer": "v3"},
            "narrative_bible": {
                "cast": [
                    {"id": character.get("id"), "name": character.get("name", character.get("id", "")), "summary": character.get("summary", "")}
                    for character in as_list(facts.get("characters"))
                    if isinstance(character, dict)
                ],
                "locations": [
                    {"id": location.get("id"), "name": location.get("name", location.get("id", "")), "summary": location.get("summary", "")}
                    for location in as_list(facts.get("locations"))
                    if isinstance(location, dict)
                ],
                "timeline": strip_internal_trace(as_list(facts.get("events"))),
                "continuity_rules": strip_internal_trace(as_list(facts.get("world_rules"))),
            },
        },
        "world": {"summary": policy.get("world_summary", "")},
        "entities": entities,
        "global_state_variables": variables,
        "progression_stages": [
            {
                "id": node.get("id"),
                "title": node.get("title", node.get("id", "")),
                "description": node.get("summary", ""),
            }
            for node in as_list(branch_graph.get("nodes"))
            if isinstance(node, dict)
        ],
        "node_contracts": [
            strip_internal_trace(contract)
            for level in artifacts["levels"]
            for contract in as_list(artifacts["design_levels"][level]["contracts"].get("contracts"))
            if isinstance(contract, dict)
        ],
        "event_rules": event_rules,
        "compiler_trace": {"compiled_from_design_layer_version": "v3"},
    }


def validate_compiled_public(requirements: Json, synopsis: Json, branch_graph: Json, game_ir: Json) -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_requirements(requirements))
    result.extend(validate_synopsis(synopsis))
    result.extend(validate_branch_graph(branch_graph))
    result.extend(validate_game_ir(game_ir, branch_graph))
    result.extend(validate_graph_ir_consistency(branch_graph, game_ir))
    return result


def compile_design_v3(run_root: Path) -> ValidationResult:
    ensure_design_v3_layout(run_root)
    validation = validate_design_v3(run_root, write_report=True)
    if validation.status == "fail":
        write_json(run_root / DESIGN_V3_COMPILE_REPORT, {
            "status": "fail",
            "stage": "v3_validation",
            "findings": [finding.to_json() for finding in validation.findings],
        })
        return validation

    loader_result = ValidationResult()
    artifacts = load_design_v3_artifacts(run_root, loader_result, merge_shards=False)
    if artifacts is None or loader_result.status == "fail":
        write_json(run_root / DESIGN_V3_COMPILE_REPORT, {
            "status": "fail",
            "stage": "v3_load",
            "findings": [finding.to_json() for finding in loader_result.findings],
        })
        return loader_result

    requirements = compile_requirements(run_root, artifacts)
    synopsis = compile_synopsis(artifacts)
    branch_graph, public_edge_origins, node_public_map = public_graph_from_v3(artifacts)
    game_ir = compile_game_ir(artifacts, branch_graph, public_edge_origins, node_public_map)

    assembled_root = design_v3_path(run_root, "assembled")
    staged = {
        "user_requirements.json": requirements,
        "chapter_linear_synopsis.json": synopsis,
        "branch_graph.json": branch_graph,
        "game_ir.json": game_ir,
    }
    for filename, payload in staged.items():
        write_json(assembled_root / filename, payload)

    public_validation = validate_compiled_public(requirements, synopsis, branch_graph, game_ir)
    if public_validation.status == "fail":
        write_json(run_root / DESIGN_V3_COMPILE_REPORT, {
            "status": "fail",
            "stage": "public_validation",
            "findings": [finding.to_json() for finding in public_validation.findings],
            "staged_outputs": [str(DESIGN_V3_ROOT / "assembled" / filename) for filename in staged],
        })
        return public_validation

    public_root = run_root / "workspace" / "design_layer"
    ensure_dir(public_root)
    for filename in staged:
        shutil.copyfile(assembled_root / filename, public_root / filename)

    from pipeline_lib import validate_all

    validate_all(run_root, write_projections=True)
    write_json(assembled_root / "assembly_report.json", {
        "status": "pass",
        "public_outputs": [str(Path("workspace/design_layer") / filename) for filename in staged],
        "findings": [finding.to_json() for finding in validation.findings + public_validation.findings],
    })
    write_json(run_root / DESIGN_V3_COMPILE_REPORT, {
        "status": "pass",
        "stage": "copied_public_artifacts",
        "v3_validation_status": validation.status,
        "public_validation_status": public_validation.status,
        "assembled_outputs": [str(DESIGN_V3_ROOT / "assembled" / filename) for filename in staged],
        "public_outputs": [str(Path("workspace/design_layer") / filename) for filename in staged],
        "findings": [finding.to_json() for finding in validation.findings + public_validation.findings],
    })
    return public_validation
