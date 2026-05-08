#!/usr/bin/env python3
"""Shared helpers for the self-contained narrative game pipeline skill."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


Json = dict[str, Any]


STAGE_PATHS = {
    "prompt": "inputs/prompt.txt",
    "source_full_text": "inputs/source_material/full_text.txt",
    "source_index": "inputs/source_material/source_index.json",
    "source_extraction_report": "inputs/source_material/extraction_report.json",
    "requirements": "workspace/design_layer/user_requirements.json",
    "synopsis": "workspace/design_layer/chapter_linear_synopsis.json",
    "branch_graph": "workspace/design_layer/branch_graph.json",
    "game_ir": "workspace/design_layer/game_ir.json",
    "shared_state": "workspace/state/shared-state.schema.json",
    "realization_plans": "workspace/realization/node-realization-plans.json",
    "realization_manifest": "workspace/realization/realization-manifest.json",
    "gameplay_manifest": "workspace/realization/gameplay-manifest.json",
    "advanced_vn_scene_plan": "workspace/advanced-vn/scene-plan.json",
    "advanced_vn_scene_manifest": "workspace/advanced-vn/scenes/scene-manifest.json",
    "advanced_vn_validation_report": "reports/advanced-vn-validation.json",
    "asset_direction": "workspace/asset-direction.json",
    "asset_manifest": "workspace/asset-manifest.json",
    "story_yarn": "workspace/vn/story.yarn",
    "story_ir": "workspace/vn/story.storyir.json",
    "validation_report": "reports/validation-report.json",
    "story_report": "reports/story-verification.json",
    "gameplay_validation_report": "reports/gameplay-validation.json",
    "gameplay_coverage_report": "reports/gameplay-coverage.json",
    "asset_generation_report": "reports/asset-generation-report.json",
    "asset_validation_report": "reports/asset-validation.json",
    "final_report": "reports/final-report.json",
}

GAMEPLAY_KINDS = ("battle", "interaction", "puzzle", "exploration")
GAMEPLAY_KIND_DIRS = {
    "battle": ("battles", ".battle.json"),
    "interaction": ("interactions", ".interaction.json"),
    "puzzle": ("puzzles", ".puzzle.json"),
    "exploration": ("explorations", ".exploration.json"),
}
GAMEPLAY_ADAPTER_SUPPORT = {
    "battle.choice_duel": {"kind": "battle", "web_vn": True, "unity": False},
    "interaction.inspect_scene": {"kind": "interaction", "web_vn": True, "unity": False},
    "puzzle.sequence_lock": {"kind": "puzzle", "web_vn": True, "unity": False},
    "exploration.room_nav": {"kind": "exploration", "web_vn": True, "unity": False},
}
ADVANCED_VN_PLAN_FIELDS = {"source_node_id", "outcomes", "notes"}
ADVANCED_VN_SCENE_FIELDS = {"metadata", "source_node_id", "title", "beats", "interactables", "outcomes", "ending_variants"}


@dataclass
class Finding:
    severity: str
    kind: str
    message: str
    path: str | None = None

    def to_json(self) -> Json:
        data: Json = {
            "severity": self.severity,
            "kind": self.kind,
            "message": self.message,
        }
        if self.path:
            data["path"] = self.path
        return data


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "fail" if any(f.severity == "error" for f in self.findings) else "pass"

    def add(self, severity: str, kind: str, message: str, path: str | None = None) -> None:
        self.findings.append(Finding(severity, kind, message, path))

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def to_json(self) -> Json:
        return {
            "status": self.status,
            "findings": [f.to_json() for f in self.findings],
        }


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_run_layout(run_root: Path) -> None:
    for relative in [
        "inputs",
        "inputs/source_material/original",
        "inputs/source_material/chunks",
        "workspace/controller-packets",
        "workspace/design_layer",
        "workspace/state",
        "workspace/realization/stubs",
        "workspace/realization/battles",
        "workspace/realization/interactions",
        "workspace/realization/puzzles",
        "workspace/realization/explorations",
        "workspace/advanced-vn",
        "workspace/advanced-vn/scenes",
        "workspace/vn/fragments",
        "workspace/runtime",
        "workspace/generated-assets",
        "build/web-vn",
        "build/unity-project",
        "reports",
        "graph",
    ]:
        ensure_dir(run_root / relative)


def path_for(run_root: Path, key: str) -> Path:
    return run_root / STAGE_PATHS[key]


def read_json(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, data: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(data, encoding="utf-8")
    return path


def load_optional_json(path: Path) -> Json | None:
    if not path.exists():
        return None
    return read_json(path)


def require_json(run_root: Path, key: str, result: ValidationResult) -> Json | None:
    path = path_for(run_root, key)
    if not path.exists():
        result.add("error", "missing_artifact", f"Missing required artifact: {STAGE_PATHS[key]}", STAGE_PATHS[key])
        return None
    try:
        return read_json(path)
    except Exception as exc:  # noqa: BLE001
        result.add("error", "invalid_json", f"Cannot parse {STAGE_PATHS[key]}: {exc}", STAGE_PATHS[key])
        return None


def stable_id(value: str, prefix: str = "id") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip()).strip("_")
    if not cleaned:
        cleaned = "item"
    if "." not in cleaned:
        cleaned = f"{prefix}.{cleaned}"
    if not re.match(r"^[A-Za-z]", cleaned):
        cleaned = f"{prefix}.{cleaned}"
    return cleaned


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def object_has_text(obj: Json, key: str) -> bool:
    return isinstance(obj.get(key), str) and bool(obj[key].strip())


def validate_requirements(payload: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if payload is None:
        return findings
    if not object_has_text(payload, "prompt"):
        findings.append(Finding("error", "schema", "Requirements must include prompt.", "user_requirements.prompt"))
    requirements = as_list(payload.get("requirements"))
    if not requirements:
        findings.append(Finding("error", "schema", "Requirements must include a non-empty requirements array.", "user_requirements.requirements"))
    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            findings.append(Finding("error", "schema", "Requirement entries must be objects.", f"user_requirements.requirements[{index}]"))
            continue
        req_id = requirement.get("id")
        if not isinstance(req_id, str) or not req_id.strip():
            findings.append(Finding("error", "schema", "Requirement entry needs a stable id.", f"user_requirements.requirements[{index}].id"))
        elif req_id in seen:
            findings.append(Finding("error", "duplicate_id", f"Duplicate requirement id: {req_id}", f"user_requirements.requirements[{index}].id"))
        else:
            seen.add(req_id)
        if not object_has_text(requirement, "text"):
            findings.append(Finding("error", "schema", "Requirement entry needs text.", f"user_requirements.requirements[{index}].text"))
    forbidden = re.compile(r"\b(Unity|Yarn|Gemini|Resources/|Assets/)\b", re.I)
    if forbidden.search(json.dumps(payload, ensure_ascii=False)):
        findings.append(Finding("warning", "base_design_leak", "Requirements mention backend-specific terms; keep base design neutral."))
    return findings


def validate_synopsis(payload: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if payload is None:
        return findings
    if not object_has_text(payload, "title"):
        findings.append(Finding("error", "schema", "Synopsis must include title.", "chapter_linear_synopsis.title"))
    events = as_list(payload.get("events"))
    if not events:
        findings.append(Finding("error", "schema", "Synopsis must include a non-empty events array.", "chapter_linear_synopsis.events"))
    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            findings.append(Finding("error", "schema", "Event entries must be objects.", f"chapter_linear_synopsis.events[{index}]"))
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            findings.append(Finding("error", "schema", "Event entry needs a stable id.", f"chapter_linear_synopsis.events[{index}].id"))
        elif event_id in seen:
            findings.append(Finding("error", "duplicate_id", f"Duplicate event id: {event_id}", f"chapter_linear_synopsis.events[{index}].id"))
        else:
            seen.add(event_id)
    return findings


def validate_branch_graph(payload: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if payload is None:
        return findings
    nodes = as_list(payload.get("nodes"))
    edges = as_list(payload.get("edges"))
    if not nodes:
        findings.append(Finding("error", "schema", "Branch graph must include nodes.", "branch_graph.nodes"))
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            findings.append(Finding("error", "schema", "Node entries must be objects.", f"branch_graph.nodes[{index}]"))
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            findings.append(Finding("error", "schema", "Node entry needs id.", f"branch_graph.nodes[{index}].id"))
        elif node_id in node_ids:
            findings.append(Finding("error", "duplicate_id", f"Duplicate node id: {node_id}", f"branch_graph.nodes[{index}].id"))
        else:
            node_ids.add(node_id)
        if not (object_has_text(node, "summary") or object_has_text(node, "body")):
            findings.append(Finding("warning", "thin_node", "Node should include summary or body.", f"branch_graph.nodes[{index}]"))
    start_id = payload.get("start_node_id")
    if not isinstance(start_id, str) or start_id not in node_ids:
        findings.append(Finding("error", "missing_start", "start_node_id must reference an existing node.", "branch_graph.start_node_id"))
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            findings.append(Finding("error", "schema", "Edge entries must be objects.", f"branch_graph.edges[{index}]"))
            continue
        edge_id = edge.get("id")
        if not isinstance(edge_id, str) or not edge_id.strip():
            findings.append(Finding("error", "schema", "Edge entry needs id.", f"branch_graph.edges[{index}].id"))
        elif edge_id in edge_ids:
            findings.append(Finding("error", "duplicate_id", f"Duplicate edge id: {edge_id}", f"branch_graph.edges[{index}].id"))
        else:
            edge_ids.add(edge_id)
        for key in ("from", "to"):
            ref = edge.get(key)
            if not isinstance(ref, str) or ref not in node_ids:
                findings.append(Finding("error", "invalid_reference", f"Edge {edge_id or index} has invalid {key} node reference: {ref}", f"branch_graph.edges[{index}].{key}"))
    terminal_nodes = [node for node in nodes if isinstance(node, dict) and (node.get("is_terminal") is True or node.get("node_type") == "terminal")]
    if not terminal_nodes:
        findings.append(Finding("warning", "no_terminal", "Branch graph has no explicit terminal node."))
    return findings


def validate_game_ir(payload: Json | None, branch_graph: Json | None = None) -> list[Finding]:
    findings: list[Finding] = []
    if payload is None:
        return findings
    variables = as_list(payload.get("global_state_variables") or payload.get("state_variables"))
    if not variables:
        findings.append(Finding("error", "schema", "Game IR must include global_state_variables or state_variables.", "game_ir.global_state_variables"))
    variable_ids: set[str] = set()
    for index, variable in enumerate(variables):
        if not isinstance(variable, dict):
            findings.append(Finding("error", "schema", "State variable entries must be objects.", f"game_ir.global_state_variables[{index}]"))
            continue
        variable_id = variable.get("id")
        if not isinstance(variable_id, str) or not variable_id.strip():
            findings.append(Finding("error", "schema", "State variable entry needs id.", f"game_ir.global_state_variables[{index}].id"))
        elif variable_id in variable_ids:
            findings.append(Finding("error", "duplicate_id", f"Duplicate state variable id: {variable_id}", f"game_ir.global_state_variables[{index}].id"))
        else:
            variable_ids.add(variable_id)
        if variable.get("type") not in ("boolean", "integer", "number", "string", "enum"):
            findings.append(Finding("warning", "state_type", "State variable should use boolean, integer, number, string, or enum.", f"game_ir.global_state_variables[{index}].type"))
    if branch_graph:
        node_ids = {node.get("id") for node in as_list(branch_graph.get("nodes")) if isinstance(node, dict)}
        edge_ids = {edge.get("id") for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)}
        serialized = json.dumps(payload, ensure_ascii=False)
        for ref in re.findall(r"node\.[A-Za-z0-9_.-]+", serialized):
            if ref not in node_ids:
                findings.append(Finding("error", "stale_node_ref", f"Game IR references missing branch node: {ref}"))
        for ref in re.findall(r"edge\.[A-Za-z0-9_.-]+", serialized):
            if ref not in edge_ids:
                findings.append(Finding("error", "stale_edge_ref", f"Game IR references missing branch edge: {ref}"))
    forbidden = re.compile(r"\b(Unity|Yarn|Gemini|Assets/|Resources/|portrait\.|bg\.)\b", re.I)
    if forbidden.search(json.dumps(payload, ensure_ascii=False)):
        findings.append(Finding("warning", "base_design_leak", "Game IR mentions backend or asset terms; persistent semantics should stay mode-neutral."))
    if not isinstance(payload.get("design_brief"), dict):
        findings.append(Finding("warning", "missing_design_brief", "Game IR should include design_brief so downstream agents do not need source design artifacts.", "game_ir.design_brief"))
    return findings


def state_refs_from_transition(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key in ("state_variable_id", "state_id", "id"):
            ref = value.get(key)
            if isinstance(ref, str) and ref:
                refs.add(ref)
        for item in value.values():
            refs.update(state_refs_from_transition(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(state_refs_from_transition(item))
    return refs


def project_shared_state(game_ir: Json) -> Json:
    variables = as_list(game_ir.get("global_state_variables") or game_ir.get("state_variables"))
    projected = []
    for variable in variables:
        if not isinstance(variable, dict):
            continue
        variable_id = variable.get("id")
        if not isinstance(variable_id, str):
            continue
        projected.append({
            "id": variable_id,
            "type": variable.get("type", "string"),
            "allowed_values": variable.get("allowed_values", []),
            "initial_value": variable.get("initial_value"),
            "scope": variable.get("scope", "global"),
            "role": variable.get("role", "runtime_state"),
            "description": variable.get("description", ""),
            "source_game_ir_id": variable_id,
        })
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline_projector"},
        "variables": projected,
    }


def validate_graph_ir_consistency(branch_graph: Json | None, game_ir: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if not branch_graph or not game_ir:
        return findings
    edges = [edge for edge in as_list(branch_graph.get("edges")) if isinstance(edge, dict)]
    variables = as_list(game_ir.get("global_state_variables") or game_ir.get("state_variables"))
    state_ids = {var.get("id") for var in variables if isinstance(var, dict) and isinstance(var.get("id"), str)}
    serialized_ir = json.dumps(game_ir, ensure_ascii=False)
    for edge in edges:
        edge_id = edge.get("id")
        if not isinstance(edge_id, str):
            continue
        condition_type = edge.get("condition_type", edge.get("type", ""))
        transition_refs = state_refs_from_transition(edge.get("conditions")) | state_refs_from_transition(edge.get("effects"))
        for state_id in sorted(transition_refs):
            if state_id not in state_ids:
                findings.append(Finding("error", "state_reference", f"Branch graph edge references missing Game IR state variable: {state_id}", f"branch_graph.edges.{edge_id}"))
        has_transition_semantics = bool(as_list(edge.get("conditions")) or as_list(edge.get("effects")))
        if (has_transition_semantics or condition_type not in ("unconditional", "terminal_resolution")) and edge_id not in serialized_ir:
            findings.append(Finding("warning", "edge_missing_semantics", f"Non-trivial edge is not referenced by Game IR: {edge_id}"))
    return findings


def validate_realization_plans(plans: Json | None, branch_graph: Json | None, shared_state: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if plans is None:
        return findings
    plan_list = as_list(plans.get("plans"))
    if not plan_list:
        findings.append(Finding("error", "schema", "node-realization-plans must include plans.", "node-realization-plans.plans"))
        return findings
    node_ids = {node.get("id") for node in as_list((branch_graph or {}).get("nodes")) if isinstance(node, dict)}
    edges_by_from: dict[str, set[str]] = {}
    for edge in as_list((branch_graph or {}).get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("id"), str):
            edges_by_from.setdefault(edge["from"], set()).add(edge["id"])
    state_ids = {var.get("id") for var in as_list((shared_state or {}).get("variables")) if isinstance(var, dict)}
    seen_nodes: set[str] = set()
    seen_units: set[str] = set()
    for index, plan in enumerate(plan_list):
        if not isinstance(plan, dict):
            findings.append(Finding("error", "schema", "Plan entries must be objects.", f"node-realization-plans.plans[{index}]"))
            continue
        source_node_id = plan.get("source_node_id")
        unit_id = plan.get("unit_id")
        kind = plan.get("realization_kind")
        if source_node_id not in node_ids:
            findings.append(Finding("error", "invalid_reference", f"Plan references missing source node: {source_node_id}", f"node-realization-plans.plans[{index}].source_node_id"))
        if isinstance(source_node_id, str):
            if source_node_id in seen_nodes:
                findings.append(Finding("error", "duplicate_plan", f"Duplicate plan for source node: {source_node_id}", f"node-realization-plans.plans[{index}].source_node_id"))
            seen_nodes.add(source_node_id)
        if not isinstance(unit_id, str) or not unit_id:
            findings.append(Finding("error", "schema", "Plan needs unit_id.", f"node-realization-plans.plans[{index}].unit_id"))
        elif unit_id in seen_units:
            findings.append(Finding("error", "duplicate_unit", f"Duplicate unit id: {unit_id}", f"node-realization-plans.plans[{index}].unit_id"))
        else:
            seen_units.add(unit_id)
        if kind not in ("vn_yarn", "cutscene_yarn", "battle", "interaction", "puzzle", "exploration", "external_stub"):
            findings.append(Finding("error", "schema", f"Unsupported realization_kind: {kind}", f"node-realization-plans.plans[{index}].realization_kind"))
        entry = plan.get("entry_binding")
        if kind in ("vn_yarn", "cutscene_yarn") and not (isinstance(entry, dict) and entry.get("type") == "yarn_node" and isinstance(entry.get("node_title"), str)):
            findings.append(Finding("error", "entry_binding", "VN plans need entry_binding {type:'yarn_node', node_title:string}.", f"node-realization-plans.plans[{index}].entry_binding"))
        expected_edges = edges_by_from.get(str(source_node_id), set())
        actual_edges = {binding.get("edge_id") for binding in as_list(plan.get("exit_bindings")) if isinstance(binding, dict)}
        missing = expected_edges - actual_edges
        extra = actual_edges - expected_edges
        if missing:
            findings.append(Finding("error", "exit_binding", f"Plan missing exit bindings for edges: {sorted(missing)}", f"node-realization-plans.plans[{index}].exit_bindings"))
        if extra:
            findings.append(Finding("error", "exit_binding", f"Plan has exit bindings for non-outgoing edges: {sorted(extra)}", f"node-realization-plans.plans[{index}].exit_bindings"))
        for op_key in ("required_state_reads", "state_writes"):
            for op_index, op in enumerate(as_list(plan.get(op_key))):
                if isinstance(op, dict):
                    ref = op.get("state_variable_id")
                    if ref not in state_ids:
                        findings.append(Finding("error", "state_reference", f"{op_key} references missing shared state variable: {ref}", f"node-realization-plans.plans[{index}].{op_key}[{op_index}]"))
    missing_nodes = node_ids - seen_nodes
    if missing_nodes:
        findings.append(Finding("error", "missing_plan", f"Missing realization plans for nodes: {sorted(missing_nodes)}"))
    return findings


def _graph_edges_by_source(branch_graph: Json | None) -> dict[str, set[str]]:
    edges_by_source: dict[str, set[str]] = {}
    for edge in as_list((branch_graph or {}).get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("id"), str):
            edges_by_source.setdefault(edge["from"], set()).add(edge["id"])
    return edges_by_source


def _declared_state_ids(shared_state: Json | None) -> set[str]:
    return {
        var.get("id")
        for var in as_list((shared_state or {}).get("variables"))
        if isinstance(var, dict) and isinstance(var.get("id"), str)
    }


def _state_ref_from_op(op: Any) -> str | None:
    if isinstance(op, str):
        return op
    if isinstance(op, dict):
        ref = op.get("state_variable_id") or op.get("state_id")
        return ref if isinstance(ref, str) else None
    return None


def _validate_state_ref_list(findings: list[Finding], ops: list[Any], state_ids: set[str], path: str) -> None:
    for index, op in enumerate(ops):
        ref = _state_ref_from_op(op)
        if ref and ref not in state_ids:
            findings.append(Finding("error", "state_reference", f"State operation references missing variable: {ref}", f"{path}[{index}]"))


def _outcome_edges(outcomes: list[Any]) -> set[str]:
    return {
        outcome.get("edge_id")
        for outcome in outcomes
        if isinstance(outcome, dict) and isinstance(outcome.get("edge_id"), str)
    }


def validate_advanced_vn_scene_plan(scene_plan: Json | None, branch_graph: Json | None, shared_state: Json | None) -> list[Finding]:
    findings: list[Finding] = []
    if scene_plan is None:
        return findings
    plans = as_list(scene_plan.get("plans"))
    if not plans:
        findings.append(Finding("error", "schema", "Advanced VN scene plan must include plans.", "advanced-vn.scene-plan.plans"))
        return findings
    node_ids = {node.get("id") for node in as_list((branch_graph or {}).get("nodes")) if isinstance(node, dict)}
    edges_by_source = _graph_edges_by_source(branch_graph)
    state_ids = _declared_state_ids(shared_state)
    seen_nodes: set[str] = set()
    for index, plan in enumerate(plans):
        path = f"advanced-vn.scene-plan.plans[{index}]"
        if not isinstance(plan, dict):
            findings.append(Finding("error", "schema", "Scene plan entries must be objects.", path))
            continue
        extra_fields = sorted(set(plan) - ADVANCED_VN_PLAN_FIELDS)
        if extra_fields:
            findings.append(Finding("error", "unsupported_field", f"Advanced VN scene plan has unsupported fields: {extra_fields}", path))
        source_node_id = plan.get("source_node_id")
        if source_node_id not in node_ids:
            findings.append(Finding("error", "invalid_reference", f"Scene plan references missing source node: {source_node_id}", f"{path}.source_node_id"))
        if isinstance(source_node_id, str):
            if source_node_id in seen_nodes:
                findings.append(Finding("error", "duplicate_plan", f"Duplicate Advanced VN plan for source node: {source_node_id}", f"{path}.source_node_id"))
            seen_nodes.add(source_node_id)
        outcomes = as_list(plan.get("outcomes"))
        expected_edges = edges_by_source.get(str(source_node_id), set())
        actual_edges = _outcome_edges(outcomes)
        missing = expected_edges - actual_edges
        extra = actual_edges - expected_edges
        if missing:
            findings.append(Finding("error", "outcome_binding", f"Scene plan missing outcomes for edges: {sorted(missing)}", f"{path}.outcomes"))
        if extra:
            findings.append(Finding("error", "outcome_binding", f"Scene plan has outcomes for non-outgoing edges: {sorted(extra)}", f"{path}.outcomes"))
        outcome_edge_count = len([outcome for outcome in outcomes if isinstance(outcome, dict) and isinstance(outcome.get("edge_id"), str)])
        if len(actual_edges) != outcome_edge_count:
            findings.append(Finding("error", "duplicate_outcome_edge", "Scene plan has duplicate or malformed outcome edge bindings.", f"{path}.outcomes"))
        for outcome_index, outcome in enumerate(outcomes):
            if isinstance(outcome, dict):
                _validate_state_ref_list(findings, as_list(outcome.get("conditions")), state_ids, f"{path}.outcomes[{outcome_index}].conditions")
                _validate_state_ref_list(findings, as_list(outcome.get("state_writes")), state_ids, f"{path}.outcomes[{outcome_index}].state_writes")
    missing_nodes = node_ids - seen_nodes
    if missing_nodes:
        findings.append(Finding("error", "missing_plan", f"Missing Advanced VN scene plans for nodes: {sorted(missing_nodes)}"))
    return findings


def advanced_vn_scene_artifact_path(run_root: Path, source_node_id: str) -> Path:
    safe_node = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_node_id).strip("_") or "node.unknown"
    return run_root / "workspace" / "advanced-vn" / "scenes" / f"{safe_node}.scene.json"


def validate_advanced_vn_scene_ir(
    scene: Json | None,
    plan: Json,
    branch_graph: Json | None,
    shared_state: Json | None,
    artifact_path: str,
) -> list[Finding]:
    findings: list[Finding] = []
    source_node_id = str(plan.get("source_node_id"))
    if scene is None:
        findings.append(Finding("error", "missing_scene_ir", f"Missing Advanced VN Scene IR for {source_node_id}.", artifact_path))
        return findings
    if not isinstance(scene, dict):
        findings.append(Finding("error", "schema", "Advanced VN Scene IR must be a JSON object.", artifact_path))
        return findings
    extra_fields = sorted(set(scene) - ADVANCED_VN_SCENE_FIELDS)
    if extra_fields:
        findings.append(Finding("error", "unsupported_field", f"Advanced VN Scene IR has unsupported fields: {extra_fields}", artifact_path))
    if scene.get("source_node_id") != source_node_id:
        findings.append(Finding("error", "source_node_id", f"Scene IR source_node_id must be {source_node_id}.", f"{artifact_path}.source_node_id"))
    if not (as_list(scene.get("beats")) or as_list(scene.get("interactables")) or as_list(scene.get("ending_variants"))):
        findings.append(Finding("warning", "empty_scene", "Scene IR should include beats, interactables, or ending variants.", artifact_path))

    expected_edges = _outcome_edges(as_list(plan.get("outcomes")))
    actual_edges = _outcome_edges(as_list(scene.get("outcomes")))
    missing = expected_edges - actual_edges
    extra = actual_edges - expected_edges
    if missing:
        findings.append(Finding("error", "outcome_binding", f"Scene IR missing outcomes for planned edges: {sorted(missing)}", f"{artifact_path}.outcomes"))
    if extra:
        findings.append(Finding("error", "outcome_binding", f"Scene IR has outcomes outside the plan: {sorted(extra)}", f"{artifact_path}.outcomes"))
    outcome_edge_count = len([outcome for outcome in as_list(scene.get("outcomes")) if isinstance(outcome, dict) and isinstance(outcome.get("edge_id"), str)])
    if len(actual_edges) != outcome_edge_count:
        findings.append(Finding("error", "duplicate_outcome_edge", "Scene IR has duplicate or malformed outcome edge bindings.", f"{artifact_path}.outcomes"))

    state_ids = _declared_state_ids(shared_state)
    for index, beat in enumerate(as_list(scene.get("beats"))):
        if not isinstance(beat, dict):
            findings.append(Finding("error", "schema", "Scene beat must be an object.", f"{artifact_path}.beats[{index}]"))
            continue
        beat_type = beat.get("type")
        if beat_type not in ("line", "command", "choice"):
            findings.append(Finding("error", "schema", f"Unsupported Advanced VN beat type: {beat_type}", f"{artifact_path}.beats[{index}].type"))
        if beat_type == "line" and not object_has_text(beat, "text"):
            findings.append(Finding("error", "schema", "Line beat needs text.", f"{artifact_path}.beats[{index}].text"))
        if beat_type == "command" and beat.get("command") == "set":
            args = beat.get("args") if isinstance(beat.get("args"), dict) else {}
            _validate_state_ref_list(findings, [args], state_ids, f"{artifact_path}.beats[{index}].args")
        if beat_type == "choice":
            for choice_index, choice in enumerate(as_list(beat.get("choices"))):
                if isinstance(choice, dict):
                    _validate_state_ref_list(findings, as_list(choice.get("conditions")), state_ids, f"{artifact_path}.beats[{index}].choices[{choice_index}].conditions")
                    _validate_state_ref_list(findings, as_list(choice.get("state_writes")), state_ids, f"{artifact_path}.beats[{index}].choices[{choice_index}].state_writes")

    for index, interactable in enumerate(as_list(scene.get("interactables"))):
        if not isinstance(interactable, dict):
            findings.append(Finding("error", "schema", "Interactable must be an object.", f"{artifact_path}.interactables[{index}]"))
            continue
        if not object_has_text(interactable, "id"):
            findings.append(Finding("error", "schema", "Interactable needs id.", f"{artifact_path}.interactables[{index}].id"))
        if not object_has_text(interactable, "label"):
            findings.append(Finding("error", "schema", "Interactable needs label.", f"{artifact_path}.interactables[{index}].label"))
        if not object_has_text(interactable, "text"):
            findings.append(Finding("error", "schema", "Interactable needs visible text feedback.", f"{artifact_path}.interactables[{index}].text"))
        _validate_state_ref_list(findings, as_list(interactable.get("conditions")), state_ids, f"{artifact_path}.interactables[{index}].conditions")
        _validate_state_ref_list(findings, as_list(interactable.get("state_writes")), state_ids, f"{artifact_path}.interactables[{index}].state_writes")
    for index, outcome in enumerate(as_list(scene.get("outcomes"))):
        if isinstance(outcome, dict):
            _validate_state_ref_list(findings, as_list(outcome.get("conditions")), state_ids, f"{artifact_path}.outcomes[{index}].conditions")
            _validate_state_ref_list(findings, as_list(outcome.get("state_writes")), state_ids, f"{artifact_path}.outcomes[{index}].state_writes")
    for index, variant in enumerate(as_list(scene.get("ending_variants"))):
        if isinstance(variant, dict):
            _validate_state_ref_list(findings, as_list(variant.get("conditions")), state_ids, f"{artifact_path}.ending_variants[{index}].conditions")
            _validate_state_ref_list(findings, as_list(variant.get("state_writes")), state_ids, f"{artifact_path}.ending_variants[{index}].state_writes")

    if len(expected_edges) > 1 and not as_list(scene.get("interactables")):
        findings.append(Finding("warning", "weak_interactivity", "Multi-outcome Advanced VN scene has no interactables.", artifact_path))
    return findings


def validate_advanced_vn_run(run_root: Path, write_reports: bool = True) -> ValidationResult:
    result = ValidationResult()
    branch_graph = require_json(run_root, "branch_graph", result)
    shared_state = require_json(run_root, "shared_state", result)
    scene_plan = require_json(run_root, "advanced_vn_scene_plan", result)
    result.extend(validate_advanced_vn_scene_plan(scene_plan, branch_graph, shared_state))

    scene_entries: list[Json] = []
    for plan in as_list((scene_plan or {}).get("plans")):
        if not isinstance(plan, dict) or not isinstance(plan.get("source_node_id"), str):
            continue
        scene_path = advanced_vn_scene_artifact_path(run_root, plan["source_node_id"])
        relative_path = str(scene_path.relative_to(run_root))
        scene = None
        if scene_path.exists():
            try:
                scene = read_json(scene_path)
            except Exception as exc:  # noqa: BLE001
                result.add("error", "invalid_json", f"Cannot parse {relative_path}: {exc}", relative_path)
        result.extend(validate_advanced_vn_scene_ir(scene, plan, branch_graph, shared_state, relative_path))
        if scene is not None:
            scene_entries.append({
                "source_node_id": plan["source_node_id"],
                "path": relative_path,
            })

    if write_reports:
        write_json(path_for(run_root, "advanced_vn_validation_report"), result.to_json())
        write_json(path_for(run_root, "advanced_vn_scene_manifest"), {
            "metadata": {"schema_version": "0.1.0", "generated_by": "validate_advanced_vn"},
            "scene_plan_path": STAGE_PATHS["advanced_vn_scene_plan"],
            "scenes": scene_entries,
            "validation_status": result.status,
        })
    return result


def load_advanced_vn_scenes(run_root: Path) -> list[Json]:
    scene_plan = load_optional_json(path_for(run_root, "advanced_vn_scene_plan")) or {"plans": []}
    scenes: list[Json] = []
    for plan in as_list(scene_plan.get("plans")):
        if not isinstance(plan, dict) or not isinstance(plan.get("source_node_id"), str):
            continue
        scene_path = advanced_vn_scene_artifact_path(run_root, plan["source_node_id"])
        if not scene_path.exists():
            continue
        scene = read_json(scene_path)
        if isinstance(scene, dict):
            scenes.append({**scene, "_plan": plan, "_path": str(scene_path.relative_to(run_root))})
    return scenes


def gameplay_artifact_path(run_root: Path, kind: str, source_node_id: str) -> Path:
    directory, suffix = GAMEPLAY_KIND_DIRS[kind]
    safe_node = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_node_id).strip("_") or "node.unknown"
    return run_root / "workspace" / "realization" / directory / f"{safe_node}{suffix}"


def gameplay_plans(plans: Json | None) -> list[Json]:
    return [
        plan
        for plan in as_list((plans or {}).get("plans"))
        if isinstance(plan, dict) and plan.get("realization_kind") in GAMEPLAY_KINDS
    ]


def state_ref_from_op(op: Any) -> str | None:
    if isinstance(op, str):
        return op
    if isinstance(op, dict):
        ref = op.get("state_variable_id") or op.get("id")
        return ref if isinstance(ref, str) else None
    return None


def validate_state_ops(findings: list[Finding], ops: list[Any], state_ids: set[str], path: str) -> None:
    for index, op in enumerate(ops):
        ref = state_ref_from_op(op)
        if ref and ref not in state_ids:
            findings.append(Finding("error", "state_reference", f"State operation references missing variable: {ref}", f"{path}[{index}]"))


def validate_gameplay_unit(unit: Json | None, plan: Json, shared_state: Json | None, artifact_path: str) -> list[Finding]:
    findings: list[Finding] = []
    kind = str(plan.get("realization_kind"))
    source_node_id = str(plan.get("source_node_id"))
    unit_id = str(plan.get("unit_id"))
    state_ids = {var.get("id") for var in as_list((shared_state or {}).get("variables")) if isinstance(var, dict)}
    if unit is None:
        findings.append(Finding("error", "missing_gameplay_unit", f"Missing gameplay unit for {source_node_id}.", artifact_path))
        return findings
    if not isinstance(unit, dict):
        findings.append(Finding("error", "schema", "Gameplay unit must be a JSON object.", artifact_path))
        return findings
    if unit.get("source_node_id") != source_node_id:
        findings.append(Finding("error", "source_node_id", f"Gameplay unit source_node_id must be {source_node_id}.", f"{artifact_path}.source_node_id"))
    if unit.get("realization_unit_id") != unit_id:
        findings.append(Finding("error", "realization_unit_id", f"Gameplay unit realization_unit_id must be {unit_id}.", f"{artifact_path}.realization_unit_id"))
    if unit.get("realization_kind") != kind:
        findings.append(Finding("error", "realization_kind", f"Gameplay unit realization_kind must be {kind}.", f"{artifact_path}.realization_kind"))
    adapter_id = unit.get("adapter_id")
    adapter_support = GAMEPLAY_ADAPTER_SUPPORT.get(str(adapter_id))
    if not adapter_support:
        findings.append(Finding("error", "unsupported_adapter", f"Unsupported gameplay adapter: {adapter_id}", f"{artifact_path}.adapter_id"))
    elif adapter_support.get("kind") != kind:
        findings.append(Finding("error", "adapter_kind", f"Adapter {adapter_id} is not valid for {kind}.", f"{artifact_path}.adapter_id"))
    if not isinstance(unit.get("runtime_spec"), dict):
        findings.append(Finding("error", "runtime_spec", "Gameplay unit needs object runtime_spec.", f"{artifact_path}.runtime_spec"))

    expected_edges = {binding.get("edge_id") for binding in as_list(plan.get("exit_bindings")) if isinstance(binding, dict)}
    actual_edges = {binding.get("edge_id") for binding in as_list(unit.get("exit_bindings")) if isinstance(binding, dict)}
    missing = expected_edges - actual_edges
    extra = actual_edges - expected_edges
    if missing:
        findings.append(Finding("error", "exit_binding", f"Gameplay unit missing exit bindings: {sorted(missing)}", f"{artifact_path}.exit_bindings"))
    if extra:
        findings.append(Finding("error", "exit_binding", f"Gameplay unit has extra exit bindings: {sorted(extra)}", f"{artifact_path}.exit_bindings"))

    validate_state_ops(findings, as_list(unit.get("required_state_reads")), state_ids, f"{artifact_path}.required_state_reads")
    validate_state_ops(findings, as_list(unit.get("state_writes")), state_ids, f"{artifact_path}.state_writes")
    for binding_index, binding in enumerate(as_list(unit.get("exit_bindings"))):
        if isinstance(binding, dict):
            validate_state_ops(findings, as_list(binding.get("state_writes")), state_ids, f"{artifact_path}.exit_bindings[{binding_index}].state_writes")
    for asset_index, asset_id in enumerate(as_list(unit.get("required_assets"))):
        if not (isinstance(asset_id, str) and re.match(r"^[a-z][a-z0-9_-]*\.", asset_id)):
            findings.append(Finding("warning", "asset_id", "Gameplay asset ids should use stable prefixed ids.", f"{artifact_path}.required_assets[{asset_index}]"))
    trace = unit.get("source_trace") if isinstance(unit.get("source_trace"), dict) else {}
    if source_node_id not in as_list(trace.get("node_ids") if isinstance(trace, dict) else []):
        findings.append(Finding("warning", "source_trace", "Gameplay unit source_trace should include source node id.", f"{artifact_path}.source_trace.node_ids"))
    findings.extend(validate_gameplay_runtime_spec(unit, artifact_path))
    return findings


def validate_gameplay_runtime_spec(unit: Json, artifact_path: str) -> list[Finding]:
    findings: list[Finding] = []
    kind = unit.get("realization_kind")
    spec = unit.get("runtime_spec") if isinstance(unit.get("runtime_spec"), dict) else {}
    if kind == "battle":
        actions = as_list(spec.get("player_actions") or spec.get("actions"))
        if len([action for action in actions if isinstance(action, dict)]) < 2:
            findings.append(Finding("error", "battle_actions", "Battle runtime_spec needs at least two player actions.", f"{artifact_path}.runtime_spec.player_actions"))
        opponent = spec.get("opponent")
        if not isinstance(opponent, dict):
            findings.append(Finding("error", "battle_opponent", "Battle runtime_spec needs opponent.", f"{artifact_path}.runtime_spec.opponent"))
        win_conditions = as_list(spec.get("win_conditions"))
        if not win_conditions:
            findings.append(Finding("error", "battle_victory", "Battle runtime_spec needs at least one win condition.", f"{artifact_path}.runtime_spec.win_conditions"))
    elif kind == "interaction":
        hotspots = as_list(spec.get("hotspots"))
        if not hotspots:
            findings.append(Finding("error", "interaction_hotspots", "Interaction runtime_spec needs at least one hotspot.", f"{artifact_path}.runtime_spec.hotspots"))
        if not isinstance(spec.get("completion"), dict):
            findings.append(Finding("error", "interaction_completion", "Interaction runtime_spec needs completion.", f"{artifact_path}.runtime_spec.completion"))
    elif kind == "puzzle":
        if not as_list(spec.get("solution")):
            findings.append(Finding("error", "puzzle_solution", "Puzzle runtime_spec needs a deterministic solution.", f"{artifact_path}.runtime_spec.solution"))
        if not as_list(spec.get("clues")):
            findings.append(Finding("warning", "puzzle_clues", "Puzzle runtime_spec should include at least one clue.", f"{artifact_path}.runtime_spec.clues"))
        if not (as_list(spec.get("hints")) or isinstance(unit.get("fail_forward"), dict)):
            findings.append(Finding("warning", "puzzle_fail_forward", "Puzzle should include hints or fail-forward behavior.", artifact_path))
    elif kind == "exploration":
        areas = as_list(spec.get("areas"))
        area_ids = {area.get("id") for area in areas if isinstance(area, dict)}
        if not areas:
            findings.append(Finding("error", "exploration_areas", "Exploration runtime_spec needs at least one area.", f"{artifact_path}.runtime_spec.areas"))
        start_area = spec.get("start_area_id")
        if start_area not in area_ids:
            findings.append(Finding("error", "exploration_start", "Exploration start_area_id must reference an area.", f"{artifact_path}.runtime_spec.start_area_id"))
        for area_index, area in enumerate(areas):
            if not isinstance(area, dict):
                continue
            for exit_index, local_exit in enumerate(as_list(area.get("exits"))):
                if isinstance(local_exit, dict) and local_exit.get("target_area_id") not in area_ids:
                    findings.append(Finding("error", "exploration_exit", "Exploration local exit references missing area.", f"{artifact_path}.runtime_spec.areas[{area_index}].exits[{exit_index}].target_area_id"))
    return findings


def build_gameplay_manifest(run_root: Path, plans: Json, shared_state: Json | None) -> tuple[Json, ValidationResult]:
    result = ValidationResult()
    manifest_units = []
    coverage = {
        "status": "clear",
        "implemented": [],
        "missing": [],
        "unsupported": [],
        "skipped": [],
    }
    for plan in gameplay_plans(plans):
        kind = str(plan.get("realization_kind"))
        source_node_id = str(plan.get("source_node_id"))
        artifact_path = gameplay_artifact_path(run_root, kind, source_node_id)
        relative_artifact = str(artifact_path.relative_to(run_root))
        unit = None
        if artifact_path.exists():
            try:
                unit = read_json(artifact_path)
            except Exception as exc:  # noqa: BLE001
                result.add("error", "invalid_json", f"Cannot parse gameplay unit: {exc}", relative_artifact)
        else:
            coverage["missing"].append(source_node_id)
        if unit is not None:
            result.extend(validate_gameplay_unit(unit, plan, shared_state, relative_artifact))
            adapter_id = str(unit.get("adapter_id"))
            status = "implemented" if adapter_id in GAMEPLAY_ADAPTER_SUPPORT else "unsupported"
            coverage["implemented" if status == "implemented" else "unsupported"].append(source_node_id)
            manifest_units.append({
                "source_node_id": source_node_id,
                "realization_unit_id": plan.get("unit_id"),
                "realization_kind": kind,
                "adapter_id": adapter_id,
                "artifact_path": relative_artifact,
                "status": status,
            })
        else:
            result.extend(validate_gameplay_unit(None, plan, shared_state, relative_artifact))
            manifest_units.append({
                "source_node_id": source_node_id,
                "realization_unit_id": plan.get("unit_id"),
                "realization_kind": kind,
                "adapter_id": None,
                "artifact_path": relative_artifact,
                "status": "missing",
            })
    if coverage["missing"] or coverage["unsupported"]:
        coverage["status"] = "has_gaps"
    manifest = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
        "source_plan_path": STAGE_PATHS["realization_plans"],
        "units": manifest_units,
        "adapter_support": {
            adapter_id: {"web_vn": support["web_vn"], "unity": support["unity"]}
            for adapter_id, support in sorted(GAMEPLAY_ADAPTER_SUPPORT.items())
        },
    }
    write_json(path_for(run_root, "gameplay_manifest"), manifest)
    write_json(path_for(run_root, "gameplay_validation_report"), result.to_json())
    write_json(path_for(run_root, "gameplay_coverage_report"), coverage)
    return manifest, result


def load_gameplay_units(run_root: Path) -> dict[str, Json]:
    manifest = load_optional_json(path_for(run_root, "gameplay_manifest")) or {"units": []}
    units: dict[str, Json] = {}
    for entry in as_list(manifest.get("units")):
        if not isinstance(entry, dict) or entry.get("status") != "implemented":
            continue
        source_node_id = entry.get("source_node_id")
        artifact_path = entry.get("artifact_path")
        if not isinstance(source_node_id, str) or not isinstance(artifact_path, str):
            continue
        path = run_root / artifact_path
        if path.exists():
            units[source_node_id] = read_json(path)
    return units


def validate_all(run_root: Path, write_projections: bool = False) -> ValidationResult:
    ensure_run_layout(run_root)
    result = ValidationResult()
    requirements = require_json(run_root, "requirements", result)
    synopsis = require_json(run_root, "synopsis", result)
    branch_graph = require_json(run_root, "branch_graph", result)
    game_ir = require_json(run_root, "game_ir", result)
    result.extend(validate_requirements(requirements))
    result.extend(validate_synopsis(synopsis))
    result.extend(validate_branch_graph(branch_graph))
    result.extend(validate_game_ir(game_ir, branch_graph))
    result.extend(validate_graph_ir_consistency(branch_graph, game_ir))
    shared_state = None
    if game_ir:
        shared_state = project_shared_state(game_ir)
        if write_projections:
            write_json(path_for(run_root, "shared_state"), shared_state)
    elif path_for(run_root, "shared_state").exists():
        shared_state = read_json(path_for(run_root, "shared_state"))
    plans = load_optional_json(path_for(run_root, "realization_plans"))
    if plans:
        result.extend(validate_realization_plans(plans, branch_graph, shared_state))
    advanced_vn_scene_plan = load_optional_json(path_for(run_root, "advanced_vn_scene_plan"))
    if advanced_vn_scene_plan:
        result.extend(validate_advanced_vn_scene_plan(advanced_vn_scene_plan, branch_graph, shared_state))
    write_json(path_for(run_root, "validation_report"), result.to_json())
    return result


def build_realization_manifest(plans: Json) -> Json:
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
        "units": as_list(plans.get("plans")),
        "source_plan_path": STAGE_PATHS["realization_plans"],
    }


def write_not_implemented_stubs(run_root: Path, plans: Json, gameplay_manifest: Json | None = None) -> list[Json]:
    stubs: list[Json] = []
    implemented_gameplay = {
        unit.get("source_node_id")
        for unit in as_list((gameplay_manifest or {}).get("units"))
        if isinstance(unit, dict) and unit.get("status") == "implemented"
    }
    for plan in as_list(plans.get("plans")):
        if not isinstance(plan, dict):
            continue
        kind = plan.get("realization_kind")
        if kind in ("vn_yarn", "cutscene_yarn"):
            continue
        source_node_id = str(plan.get("source_node_id", "unknown"))
        if kind in GAMEPLAY_KINDS and source_node_id in implemented_gameplay:
            continue
        stub = {
            "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
            "source_node_id": source_node_id,
            "requested_realization_kind": kind,
            "unit_id": plan.get("unit_id"),
            "entry_binding": plan.get("entry_binding", {}),
            "exit_bindings": plan.get("exit_bindings", []),
            "required_state_reads": plan.get("required_state_reads", []),
            "state_writes": plan.get("state_writes", []),
            "implementation_status": "not_implemented",
            "explanation": "This realization kind is not implemented by the current adapter set or was explicitly skipped.",
        }
        write_json(run_root / "workspace" / "realization" / "stubs" / f"{source_node_id}.not-implemented.json", stub)
        stubs.append(stub)
    return stubs


def fragment_manifest_paths(run_root: Path) -> list[Path]:
    return sorted((run_root / "workspace" / "vn" / "fragments").glob("*.manifest.json"))


def load_yarn_fragments(run_root: Path) -> list[Json]:
    fragments: list[Json] = []
    for manifest_path in fragment_manifest_paths(run_root):
        manifest = read_json(manifest_path)
        node_id = str(manifest.get("source_node_id") or manifest_path.name.removesuffix(".manifest.json"))
        yarn_path = manifest_path.with_name(f"{node_id}.yarn")
        if not yarn_path.exists():
            yarn_path = manifest_path.with_suffix("").with_suffix(".yarn")
        fragments.append({
            "node_id": node_id,
            "yarn_text": yarn_path.read_text(encoding="utf-8") if yarn_path.exists() else "",
            "manifest": manifest,
            "manifest_path": str(manifest_path),
            "yarn_path": str(yarn_path),
        })
    return fragments


def assemble_yarn_text(fragments: list[Json]) -> str:
    chunks: list[str] = []
    for fragment in fragments:
        text = str(fragment.get("yarn_text", "")).strip()
        if text:
            chunks.append(text if text.endswith("===") else f"{text}\n===")
    return "\n\n".join(chunks) + ("\n" if chunks else "")


def yarn_title_from_text(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip()
    return None


def dialogue_beats_from_yarn(text: str) -> list[Json]:
    beats: list[Json] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line in ("---", "===") or line.startswith("title:") or line.startswith("<<") or line.startswith("->"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-·\u4e00-\u9fff（）()]{1,24})[:：]\s*(.+)$", line)
        if match:
            beats.append({"speaker": match.group(1).strip(), "text": match.group(2).strip()})
        else:
            beats.append({"speaker": "Narrator", "text": line})
    return beats or [{"speaker": "Narrator", "text": "The scene continues."}]


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
