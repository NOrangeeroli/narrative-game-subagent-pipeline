#!/usr/bin/env python3
"""Check that V3 player-facing choice labels are authored in SceneWriter Yarn."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from export_web_vn import expanded_runtime_edges, load_v3_edge_origins, parse_vn_yarn, parse_yarn_command
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, load_yarn_fragments, path_for


GENERIC_LABELS = {"", "continue", "继续", "继续前进", "下一步"}
VN_KINDS = {"vn_yarn", "cutscene_yarn"}


def is_v3_run(run_root: Path) -> bool:
    game_ir = load_optional_json(path_for(run_root, "game_ir")) or {}
    design_layer = game_ir.get("design_layer") if isinstance(game_ir.get("design_layer"), dict) else {}
    return design_layer.get("version") == "v3"


def collect_complete_activity_outcomes(yarn_text: str) -> set[str]:
    outcomes: set[str] = set()
    for raw in yarn_text.splitlines():
        command = parse_yarn_command(raw.strip())
        if not command or command.get("command") != "complete_activity":
            continue
        args = command.get("args") if isinstance(command.get("args"), dict) else {}
        outcome = args.get("outcome") or args.get("outcome_id") or args.get("edge_id")
        if isinstance(outcome, str) and outcome:
            outcomes.add(outcome)
    return outcomes


def normalized_label(value: Any) -> str:
    return str(value or "").strip()


def is_generic_label(label: str) -> bool:
    return label.strip().lower() in GENERIC_LABELS


def visible_choice_required(edge: Json, sibling_edges: list[Json]) -> bool:
    condition_type = str(edge.get("condition_type") or "player_choice")
    if condition_type == "player_choice":
        return True
    visible_siblings = [
        sibling for sibling in sibling_edges
        if str(sibling.get("condition_type") or "player_choice") == "player_choice"
    ]
    route_siblings = [
        sibling for sibling in sibling_edges
        if str(sibling.get("condition_type") or "player_choice") != "player_choice"
    ]
    return bool(visible_siblings) or len(route_siblings) > 1


def plan_bindings_by_node(plans: Json) -> dict[str, Json]:
    return {
        str(plan.get("source_node_id")): plan
        for plan in as_list(plans.get("plans"))
        if isinstance(plan, dict) and isinstance(plan.get("source_node_id"), str)
    }


def find_binding(edge: Json, exit_bindings: dict[str, Json]) -> Json | None:
    edge_id = edge.get("id")
    if isinstance(edge_id, str) and edge_id in exit_bindings:
        return exit_bindings[edge_id]
    for source_id in as_list(edge.get("source_rule_ids")):
        if isinstance(source_id, str) and source_id in exit_bindings:
            return exit_bindings[source_id]
    return None


def check_scene_choice_labels(run_root: Path) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    fragments = load_yarn_fragments(run_root)
    edge_origins = load_v3_edge_origins(run_root)

    fragments_by_node = {
        fragment["node_id"]: fragment
        for fragment in fragments
        if isinstance(fragment, dict) and isinstance(fragment.get("node_id"), str)
    }
    plan_by_node = plan_bindings_by_node(plans)

    runtime_edges_by_from: dict[str, list[Json]] = {}
    for edge in as_list(branch_graph.get("edges")):
        if not isinstance(edge, dict) or not isinstance(edge.get("from"), str):
            continue
        runtime_edges_by_from.setdefault(edge["from"], []).extend(expanded_runtime_edges(edge, edge_origins))

    findings: list[Json] = []
    checked_visible_choices = 0
    checked_nodes = 0

    def add(severity: str, kind: str, message: str, **fields: Any) -> None:
        finding: Json = {"severity": severity, "kind": kind, "message": message}
        finding.update({key: value for key, value in fields.items() if value is not None})
        findings.append(finding)

    for node_id, sibling_edges in sorted(runtime_edges_by_from.items()):
        plan = plan_by_node.get(node_id)
        if not isinstance(plan, dict) or plan.get("realization_kind") not in VN_KINDS:
            continue
        checked_nodes += 1
        fragment = fragments_by_node.get(node_id)
        if not isinstance(fragment, dict) or not str(fragment.get("yarn_text") or "").strip():
            add("error", "missing_yarn_fragment", "VN plan has no Yarn fragment.", node_id=node_id)
            continue
        parsed_yarn = parse_vn_yarn(str(fragment.get("yarn_text") or ""))
        complete_outcomes = collect_complete_activity_outcomes(str(fragment.get("yarn_text") or ""))
        yarn_choices_by_outcome: dict[str, list[Json]] = {}
        for choice in as_list(parsed_yarn.get("exit_choices")):
            if not isinstance(choice, dict) or not isinstance(choice.get("outcome_id"), str):
                continue
            yarn_choices_by_outcome.setdefault(choice["outcome_id"], []).append(choice)

        exit_binding_list = [
            binding
            for binding in as_list(plan.get("exit_bindings"))
            if isinstance(binding, dict) and isinstance(binding.get("edge_id"), str)
        ]
        planned_visible_node = len(exit_binding_list) > 1 or bool(yarn_choices_by_outcome)
        bindings = {
            binding.get("edge_id"): binding
            for binding in exit_binding_list
        }
        planned_outcomes = {
            binding.get("outcome_id")
            for binding in exit_binding_list
            if isinstance(binding, dict) and isinstance(binding.get("outcome_id"), str)
        }
        for outcome_id, choices in sorted(yarn_choices_by_outcome.items()):
            if outcome_id not in planned_outcomes:
                add(
                    "error",
                    "unplanned_yarn_choice",
                    "Yarn choice writes an outcome that is not in the realization plan.",
                    node_id=node_id,
                    outcome_id=outcome_id,
                )
            if len(choices) > 1:
                add(
                    "error",
                    "duplicate_yarn_choice_outcome",
                    "Yarn contains multiple choice labels for the same outcome.",
                    node_id=node_id,
                    outcome_id=outcome_id,
                )

        for edge in sibling_edges:
            if not planned_visible_node:
                continue
            if not visible_choice_required(edge, sibling_edges):
                continue
            checked_visible_choices += 1
            edge_id = str(edge.get("id") or "")
            binding = find_binding(edge, bindings)
            if not binding:
                add(
                    "error",
                    "visible_choice_not_planned",
                    "Runtime-visible edge has no realization-plan exit binding; exporter would have to fall back to designer data.",
                    node_id=node_id,
                    edge_id=edge_id,
                    source_rule_ids=as_list(edge.get("source_rule_ids")),
                )
                continue
            outcome_id = str(binding.get("outcome_id") or edge_id)
            if outcome_id not in complete_outcomes:
                add(
                    "error",
                    "missing_complete_activity",
                    "Planned choice outcome is not completed by this Yarn fragment.",
                    node_id=node_id,
                    edge_id=edge_id,
                    outcome_id=outcome_id,
                )
            choices = yarn_choices_by_outcome.get(outcome_id) or []
            if not choices:
                add(
                    "error",
                    "missing_yarn_choice_label",
                    "Runtime-visible choice must have a SceneWriter-authored Yarn '->' label.",
                    node_id=node_id,
                    edge_id=edge_id,
                    outcome_id=outcome_id,
                )
                continue
            label = normalized_label(choices[0].get("label"))
            if is_generic_label(label):
                add(
                    "error",
                    "generic_yarn_choice_label",
                    "Runtime-visible choice label is empty or generic; SceneWriter must author a specific player-facing label.",
                    node_id=node_id,
                    edge_id=edge_id,
                    outcome_id=outcome_id,
                    label=label,
                )

    status = "fail" if any(finding["severity"] == "error" for finding in findings) else "pass"
    return {
        "status": status,
        "checked_nodes": checked_nodes,
        "checked_visible_choices": checked_visible_choices,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--report-path")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    if not is_v3_run(run_root):
        raise SystemExit("check_v3_scene_choice_labels.py expects a compiled V3 run.")
    report = check_scene_choice_labels(run_root)
    if args.write_report or args.report_path:
        report_path = Path(args.report_path).resolve() if args.report_path else run_root / "reports" / "v3-scene-choice-labels.json"
        ensure_dir(report_path.parent)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
