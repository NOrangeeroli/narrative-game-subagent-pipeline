#!/usr/bin/env python3
"""Apply PresentationDirector staging edits to accepted Yarn fragments."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, load_yarn_fragments, path_for, read_json, write_json


PRESENTATION_COMMANDS = {"show_char", "set_expression", "hide_char"}
PRESENTATION_MARKER_PREFIX = "// presentation_plan:"


def command_args_from_line(line: str) -> dict[str, str]:
    line = line.strip()
    if not (line.startswith("<<") and line.endswith(">>")):
        return {}
    body = line[2:-2].strip()
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    args: dict[str, str] = {}
    for token in tokens[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        args[key] = value
    return args


def command_name_from_line(line: str) -> str | None:
    line = line.strip()
    if not (line.startswith("<<") and line.endswith(">>")):
        return None
    body = line[2:-2].strip()
    return body.split(None, 1)[0] if body else None


def strip_previous_presentation_edits(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith(PRESENTATION_MARKER_PREFIX):
            if index + 1 < len(lines) and command_name_from_line(lines[index + 1]) in PRESENTATION_COMMANDS:
                index += 2
                continue
            index += 1
            continue
        cleaned.append(line)
        index += 1
    return cleaned


def is_line_beat(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped in {"---", "==="} or stripped.startswith("title:") or stripped.startswith("//"):
        return False
    if stripped.startswith(("<<", "[[", "->")):
        return False
    return True


def insertion_index(lines: list[str], line_index: int, placement: str) -> int:
    if line_index <= 0:
        for index, line in enumerate(lines):
            if line.strip() == "---":
                return index + 1
        return 0
    seen = 0
    for index, line in enumerate(lines):
        if is_line_beat(line):
            seen += 1
            if seen == line_index:
                return index if placement == "before" else index + 1
    for index, line in enumerate(lines):
        if line.strip() == "===":
            return index
    return len(lines)


def quote_arg(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def command_line(command: str, args: dict[str, Any]) -> str:
    ordered_args = " ".join(f"{key}={quote_arg(value)}" for key, value in args.items() if value is not None)
    return f"<<{command}{(' ' + ordered_args) if ordered_args else ''}>>"


def validate_command(insert: Json, portrait_ids: set[str], character_ids: set[str]) -> tuple[str, dict[str, Any]]:
    command = str(insert.get("command") or "").strip()
    if command not in PRESENTATION_COMMANDS:
        raise ValueError(f"Unsupported presentation command: {command}")
    args = insert.get("args") if isinstance(insert.get("args"), dict) else {}
    character_id = args.get("character_id")
    if command in {"show_char", "set_expression", "hide_char"}:
        if not isinstance(character_id, str) or character_id not in character_ids:
            raise ValueError(f"{command} needs a known character_id; got {character_id!r}")
    asset_id = args.get("asset_id")
    expression_asset_id = args.get("expression_asset_id")
    if command == "show_char" and (not isinstance(asset_id, str) or asset_id not in portrait_ids):
        raise ValueError(f"show_char needs known portrait asset_id; got {asset_id!r}")
    if command == "set_expression" and (not isinstance(expression_asset_id, str) or expression_asset_id not in portrait_ids):
        raise ValueError(f"set_expression needs known expression_asset_id; got {expression_asset_id!r}")
    return command, dict(args)


def manifest_asset_refs_for_command(command: str, args: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("asset_id", "expression_asset_id"):
        value = args.get(key)
        if isinstance(value, str) and value:
            refs.append(value)
    return refs


def parse_command_refs(lines: list[str]) -> list[Json]:
    refs: list[Json] = []
    for line in lines:
        command = command_name_from_line(line)
        if not command:
            continue
        refs.append({"command": command, "args": command_args_from_line(line)})
    return refs


def apply_presentation_plan(run_root: Path) -> Json:
    plan_path = path_for(run_root, "presentation_plan")
    if not plan_path.exists():
        report = {"status": "skipped", "message": "Missing workspace/presentation/presentation-plan.json", "applied_edits": 0, "issues": []}
        write_json(path_for(run_root, "presentation_validation_report"), report)
        return report
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not asset_manifest:
        raise SystemExit("Presentation plan requires workspace/asset-manifest.json.")
    plan = read_json(plan_path)
    portrait_ids: set[str] = set()
    character_ids: set[str] = set()
    for character in as_list(asset_manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        if isinstance(character.get("id"), str):
            character_ids.add(character["id"])
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict) and isinstance(portrait.get("asset_id"), str):
                portrait_ids.add(portrait["asset_id"])

    fragments = {fragment["node_id"]: fragment for fragment in load_yarn_fragments(run_root)}
    issues: list[Json] = []
    applied_edits = 0
    edits_by_node = plan.get("edits")
    if not isinstance(edits_by_node, list):
        issues.append({"code": "schema", "message": "presentation-plan.json must include edits[]."})
        edits_by_node = []

    for node_edit in edits_by_node:
        if not isinstance(node_edit, dict):
            issues.append({"code": "schema", "message": "Each presentation edit entry must be an object."})
            continue
        node_id = node_edit.get("source_node_id")
        fragment = fragments.get(node_id)
        if not isinstance(node_id, str) or not fragment:
            issues.append({"code": "missing_fragment", "source_node_id": node_id, "message": "No Yarn fragment found for source_node_id."})
            continue
        insertions = [insert for insert in as_list(node_edit.get("insertions")) if isinstance(insert, dict)]
        yarn_path = Path(str(fragment["yarn_path"]))
        manifest_path = Path(str(fragment["manifest_path"]))
        lines = strip_previous_presentation_edits(yarn_path.read_text(encoding="utf-8").splitlines())
        prepared: list[tuple[int, int, str, str, dict[str, Any]]] = []
        for order, insert in enumerate(insertions):
            try:
                command, args = validate_command(insert, portrait_ids, character_ids)
                line_index = int(insert.get("line_index", 0))
                placement = str(insert.get("placement") or "before")
                if placement not in {"before", "after"}:
                    raise ValueError(f"Invalid placement: {placement}")
                edit_id = str(insert.get("id") or f"{node_id}.{order + 1}")
                prepared.append((insertion_index(lines, line_index, placement), order, edit_id, command, args))
            except Exception as exc:  # noqa: BLE001 - collect all authoring issues in one report.
                issues.append({"code": "invalid_insertion", "source_node_id": node_id, "message": str(exc), "insertion": insert})
        for insert_at, _order, edit_id, command, args in sorted(prepared, key=lambda item: (item[0], item[1]), reverse=True):
            lines[insert_at:insert_at] = [f"{PRESENTATION_MARKER_PREFIX} {edit_id}", command_line(command, args)]
            applied_edits += 1
        yarn_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

        manifest = read_json(manifest_path)
        manifest["command_refs"] = parse_command_refs(lines)
        refs = set(as_list(manifest.get("local_asset_refs")))
        for _insert_at, _order, _edit_id, command, args in prepared:
            refs.update(manifest_asset_refs_for_command(command, args))
        manifest["local_asset_refs"] = sorted(ref for ref in refs if isinstance(ref, str))
        metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
        metadata["presentation_plan_applied"] = "workspace/presentation/presentation-plan.json"
        manifest["metadata"] = metadata
        write_json(manifest_path, manifest)

    report = {
        "status": "fail" if issues else "pass",
        "presentation_plan": "workspace/presentation/presentation-plan.json",
        "applied_edits": applied_edits,
        "issues": issues,
    }
    write_json(path_for(run_root, "presentation_validation_report"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = apply_presentation_plan(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
