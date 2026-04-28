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
    "requirements": "workspace/design_layer/user_requirements.json",
    "synopsis": "workspace/design_layer/chapter_linear_synopsis.json",
    "branch_graph": "workspace/design_layer/branch_graph.json",
    "game_ir": "workspace/design_layer/game_ir.json",
    "shared_state": "workspace/state/shared-state.schema.json",
    "realization_plans": "workspace/realization/node-realization-plans.json",
    "realization_manifest": "workspace/realization/realization-manifest.json",
    "asset_direction": "workspace/asset-direction.json",
    "asset_manifest": "workspace/asset-manifest.json",
    "story_yarn": "workspace/vn/story.yarn",
    "story_ir": "workspace/vn/story.storyir.json",
    "validation_report": "reports/validation-report.json",
    "story_report": "reports/story-verification.json",
    "asset_generation_report": "reports/asset-generation-report.json",
    "asset_validation_report": "reports/asset-validation.json",
    "final_report": "reports/final-report.json",
}


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
        "workspace/design_layer",
        "workspace/state",
        "workspace/realization/stubs",
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
    serialized_ir = json.dumps(game_ir, ensure_ascii=False)
    for edge in edges:
        edge_id = edge.get("id")
        if not isinstance(edge_id, str):
            continue
        condition_type = edge.get("condition_type", edge.get("type", ""))
        if condition_type not in ("unconditional", "terminal_resolution") and edge_id not in serialized_ir:
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
    write_json(path_for(run_root, "validation_report"), result.to_json())
    return result


def build_realization_manifest(plans: Json) -> Json:
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "narrative_game_pipeline"},
        "units": as_list(plans.get("plans")),
        "source_plan_path": STAGE_PATHS["realization_plans"],
    }


def write_not_implemented_stubs(run_root: Path, plans: Json) -> list[Json]:
    stubs: list[Json] = []
    for plan in as_list(plans.get("plans")):
        if not isinstance(plan, dict):
            continue
        kind = plan.get("realization_kind")
        if kind in ("vn_yarn", "cutscene_yarn"):
            continue
        source_node_id = str(plan.get("source_node_id", "unknown"))
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
            "explanation": "This realization kind is reserved by the self-contained v1 pipeline and is not implemented as playable gameplay.",
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
        match = re.match(r"^([^:]{1,32}):\s*(.+)$", line)
        if match:
            beats.append({"speaker": match.group(1).strip(), "text": match.group(2).strip()})
        else:
            beats.append({"speaker": "Narrator", "text": line})
    return beats or [{"speaker": "Narrator", "text": "The scene continues."}]


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
