#!/usr/bin/env python3
"""Validate narrative-first RPG overlay design artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_lib import Json, ValidationResult, as_list, ensure_run_layout, load_optional_json, path_for, read_json, write_json


INTENT_SECTIONS = (
    "region_intents",
    "map_intents",
    "questline_intents",
    "combat_intents",
    "equipment_intents",
    "progression_axes",
)

RECOMMENDED_NARRATIVE_FUNCTIONS = {
    "reveal",
    "relationship_shift",
    "moral_choice",
    "loss",
    "setup",
    "payoff",
    "ending_pressure",
    "access",
    "trial",
    "recovery",
    "atmosphere",
    "exploration",
    "combat_pressure",
    "resource_pressure",
}

CONCRETE_RUNTIME_KEYS = {
    "hp",
    "attack",
    "defense",
    "speed",
    "stats",
    "enemy_stats",
    "item_rows",
    "equipment_rows",
    "shop_inventory",
    "dialogue_lines",
    "lines",
    "xp_curve",
    "level_curve",
    "drop_table",
    "price",
    "stock",
    "damage",
}


def collect_story_units(run_root: Path, result: ValidationResult) -> dict[str, Json]:
    story_units: dict[str, Json] = {}
    story_root = run_root / "workspace" / "design_layer_v3" / "story_levels"
    if not story_root.exists():
        result.add("error", "missing_artifact", "Missing V3 story levels for RPG overlay validation.", "workspace/design_layer_v3/story_levels")
        return story_units
    for path in sorted(story_root.glob("level_*/linear_story.json")):
        try:
            payload = read_json(path)
        except Exception as exc:  # noqa: BLE001
            result.add("error", "invalid_json", f"Cannot parse V3 story level: {exc}", str(path.relative_to(run_root)))
            continue
        for unit in as_list(payload.get("units")):
            if isinstance(unit, dict) and isinstance(unit.get("id"), str):
                story_units[unit["id"]] = unit
    if not story_units:
        result.add("error", "empty_story", "No V3 story units found for RPG overlay validation.", "workspace/design_layer_v3/story_levels")
    return story_units


def ids_from(value: Any) -> list[str]:
    return [item for item in as_list(value) if isinstance(item, str) and item.strip()]


def first_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def story_refs(payload: Json) -> list[str]:
    refs: list[str] = []
    for key in ("source_story_unit_ids", "story_unit_ids", "required_story_unit_ids"):
        refs.extend(ids_from(payload.get(key)))
    return sorted(set(refs))


def slice_refs(payload: Json) -> list[str]:
    refs = ids_from(payload.get("story_slice_ids")) + ids_from(payload.get("slice_ids"))
    for key in ("story_slice_id", "slice_id"):
        value = first_string(payload.get(key))
        if value:
            refs.append(value)
    return sorted(set(refs))


def is_critical(payload: Json) -> bool:
    criticality = str(payload.get("criticality") or payload.get("importance") or "").lower()
    return bool(payload.get("story_critical") is True or payload.get("critical") is True or criticality in {"critical", "required", "must"})


def has_obligation(payload: Json) -> bool:
    obligation_keys = (
        "required_story_beats",
        "story_obligations",
        "character_arc_beats",
        "emotional_turns",
        "canon_constraints",
    )
    return any(as_list(payload.get(key)) for key in obligation_keys)


def narrative_functions(payload: Json) -> list[str]:
    value = payload.get("narrative_function")
    if isinstance(value, str) and value.strip():
        return [value]
    return ids_from(value)


def find_concrete_runtime_keys(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in CONCRETE_RUNTIME_KEYS:
                findings.append(child_path)
            findings.extend(find_concrete_runtime_keys(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(find_concrete_runtime_keys(item, f"{path}[{index}]"))
    return findings


def public_story_index(branch_graph: Json) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for node in as_list(branch_graph.get("nodes")):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        node_id = node["id"]
        refs = set(story_refs(node))
        derivation = node.get("source_derivation") if isinstance(node.get("source_derivation"), dict) else {}
        refs.update(ids_from(derivation.get("base_story_unit_ids")))
        for story_id in refs:
            index.setdefault(story_id, set()).add(node_id)
    return index


def validate_overlay_plan(run_root: Path, *, write_report: bool = True) -> ValidationResult:
    ensure_run_layout(run_root)
    result = ValidationResult()
    plan = load_optional_json(path_for(run_root, "rpg_overlay_plan"))
    if not isinstance(plan, dict):
        result.add("error", "missing_artifact", "Missing workspace/design_layer_rpg/rpg-overlay-plan.json.", "workspace/design_layer_rpg/rpg-overlay-plan.json")
        if write_report:
            write_json(path_for(run_root, "rpg_overlay_validation_report"), result.to_json())
        return result

    story_units = collect_story_units(run_root, result)
    story_unit_ids = set(story_units)
    story_slices = [item for item in as_list(plan.get("story_slices")) if isinstance(item, dict)]
    if not story_slices:
        result.add("error", "schema", "RPG overlay plan needs non-empty story_slices.", "rpg-overlay-plan.story_slices")

    slice_ids: set[str] = set()
    covered_story_units: set[str] = set()
    for index, story_slice in enumerate(story_slices):
        slice_id = story_slice.get("id")
        path = f"rpg-overlay-plan.story_slices[{index}]"
        if not isinstance(slice_id, str) or not slice_id.strip():
            result.add("error", "schema", "Story slice needs a stable id.", f"{path}.id")
        elif slice_id in slice_ids:
            result.add("error", "duplicate_id", f"Duplicate story slice id: {slice_id}", f"{path}.id")
        else:
            slice_ids.add(slice_id)
        refs = story_refs(story_slice)
        if not refs:
            result.add("error", "story_trace", "Story slice needs source_story_unit_ids.", f"{path}.source_story_unit_ids")
        for story_id in refs:
            if story_id not in story_unit_ids:
                result.add("error", "invalid_reference", f"Story slice references missing V3 story unit: {story_id}", f"{path}.source_story_unit_ids")
            else:
                covered_story_units.add(story_id)
        if is_critical(story_slice) and not has_obligation(story_slice):
            result.add("error", "thin_critical_slice", "Critical story slice needs required story beats or obligations.", path)

    critical_story_unit_ids = set(ids_from(plan.get("critical_story_unit_ids")))
    missing_critical = sorted(critical_story_unit_ids - covered_story_units)
    if missing_critical:
        result.add("error", "critical_coverage_gap", f"Critical story units are not covered by RPG slices: {', '.join(missing_critical[:10])}", "rpg-overlay-plan.critical_story_unit_ids")

    for section in INTENT_SECTIONS:
        seen_ids: set[str] = set()
        for index, intent in enumerate(as_list(plan.get(section))):
            path = f"rpg-overlay-plan.{section}[{index}]"
            if not isinstance(intent, dict):
                result.add("error", "schema", f"{section} entries must be objects.", path)
                continue
            intent_id = intent.get("id")
            if not isinstance(intent_id, str) or not intent_id.strip():
                result.add("error", "schema", "RPG intent needs a stable id.", f"{path}.id")
            elif intent_id in seen_ids:
                result.add("error", "duplicate_id", f"Duplicate intent id: {intent_id}", f"{path}.id")
            else:
                seen_ids.add(intent_id)
            functions = narrative_functions(intent)
            if not functions:
                result.add("error", "narrative_function", "RPG intent needs narrative_function.", f"{path}.narrative_function")
            elif not set(functions) & RECOMMENDED_NARRATIVE_FUNCTIONS:
                result.add("warning", "narrative_function", f"Narrative function is outside the recommended set: {functions}", f"{path}.narrative_function")
            refs = story_refs(intent)
            refs.extend(ref for ref in slice_refs(intent) if ref in slice_ids)
            if not refs:
                result.add("error", "story_trace", "RPG intent needs story_slice_ids or source_story_unit_ids.", path)
            for story_id in story_refs(intent):
                if story_id not in story_unit_ids:
                    result.add("error", "invalid_reference", f"RPG intent references missing V3 story unit: {story_id}", path)
            for slice_id in slice_refs(intent):
                if slice_id not in slice_ids:
                    result.add("error", "invalid_reference", f"RPG intent references missing story slice: {slice_id}", path)
            if is_critical(intent) and not has_obligation(intent):
                result.add("error", "thin_critical_intent", "Critical RPG intent needs story obligations.", path)

    for concrete_path in find_concrete_runtime_keys(plan):
        result.add(
            "error",
            "concrete_runtime_content",
            "RPG overlay must not contain concrete runtime rows, stats, dialogue lines, shops, or XP curves.",
            f"rpg-overlay-plan.{concrete_path}",
        )

    branch_graph = load_optional_json(path_for(run_root, "branch_graph"))
    if isinstance(branch_graph, dict):
        nodes = [node for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict)]
        node_count = len(nodes)
        if node_count and len(story_slices) > max(1, int(node_count * 0.75)):
            result.add(
                "warning",
                "slice_ratio",
                f"RPG slice count ({len(story_slices)}) is close to public node count ({node_count}); RPG slicing may be too fine-grained.",
                "rpg-overlay-plan.story_slices",
            )
        story_index = public_story_index(branch_graph)
        unbound = sorted(story_id for story_id in covered_story_units if story_id not in story_index)
        if unbound:
            result.add(
                "warning",
                "public_binding_gap",
                f"Some RPG story units are not present on public graph nodes yet: {', '.join(unbound[:10])}",
                "workspace/design_layer/branch_graph.json",
            )

    report = {
        "overlay": {"mode": "narrative_first_overlay", "plan_path": "workspace/design_layer_rpg/rpg-overlay-plan.json"},
        **result.to_json(),
    }
    if write_report:
        write_json(path_for(run_root, "rpg_overlay_validation_report"), report)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    result = validate_overlay_plan(Path(args.run_root).resolve())
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    if result.status == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
