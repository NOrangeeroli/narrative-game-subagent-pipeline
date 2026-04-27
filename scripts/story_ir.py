#!/usr/bin/env python3
"""Lower simple Yarn text to StoryIR and verify basic VN routing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pipeline_lib import Json, path_for, write_json


def parse_yarn(yarn_text: str) -> Json:
    nodes: list[Json] = []
    current: list[str] = []
    for line in yarn_text.splitlines():
        current.append(line)
        if line.strip() == "===":
            node = parse_node("\n".join(current))
            if node:
                nodes.append(node)
            current = []
    if current:
        node = parse_node("\n".join(current))
        if node:
            nodes.append(node)
    return {"metadata": {"schema_version": "0.1.0", "generated_by": "story_ir.py"}, "nodes": nodes}


def parse_node(text: str) -> Json | None:
    title = None
    source_node_id = None
    commands: list[Json] = []
    jumps: list[str] = []
    choices: list[Json] = []
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("// source_node:"):
            source_node_id = line.split(":", 1)[1].strip()
        elif line.startswith("[[") and "|" in line and line.endswith("]]"):
            _, target = line.strip("[]").split("|", 1)
            jumps.append(target.strip())
        elif line.startswith("->"):
            choices.append({"label": line[2:].strip()})
        elif line.startswith("<<") and line.endswith(">>"):
            body = line[2:-2].strip()
            name = body.split()[0] if body else ""
            args = dict(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=\"([^\"]*)\"", body))
            commands.append({"command": name, "args": args})
        elif line and line not in ("---", "===") and not line.startswith("//"):
            lines.append(line)
    if not title:
        return None
    return {
        "title": title,
        "source_node_id": source_node_id,
        "commands": commands,
        "jumps": jumps,
        "choices": choices,
        "line_count": len(lines),
    }


def verify_story_ir(story_ir: Json) -> Json:
    findings: list[Json] = []
    nodes = story_ir.get("nodes", [])
    titles: set[str] = set()
    for index, node in enumerate(nodes):
        title = node.get("title")
        if not isinstance(title, str):
            findings.append({"severity": "error", "kind": "missing_title", "message": f"Node {index} has no title."})
            continue
        if title in titles:
            findings.append({"severity": "error", "kind": "duplicate_title", "message": f"Duplicate Yarn title: {title}"})
        titles.add(title)
    for node in nodes:
        for target in node.get("jumps", []):
            if target not in titles:
                findings.append({"severity": "error", "kind": "broken_jump", "message": f"{node.get('title')} jumps to missing target {target}."})
        for command in node.get("commands", []):
            if command.get("command") not in ("complete_activity", "set", "wait", "show", "hide", "play_sfx", "play_bgm", "stop_bgm"):
                findings.append({"severity": "warning", "kind": "unknown_command", "message": f"Unknown Yarn command: {command.get('command')}"})
            if command.get("command") == "complete_activity" and "outcome" not in command.get("args", {}):
                findings.append({"severity": "error", "kind": "missing_outcome", "message": f"complete_activity in {node.get('title')} needs outcome arg."})
    status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
    return {"status": status, "findings": findings, "node_count": len(nodes)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    yarn_path = path_for(run_root, "story_yarn")
    if not yarn_path.exists():
        raise SystemExit(f"Missing {yarn_path}")
    story_ir = parse_yarn(yarn_path.read_text(encoding="utf-8"))
    report = verify_story_ir(story_ir)
    story_ir["verification"] = report
    write_json(path_for(run_root, "story_ir"), story_ir)
    write_json(path_for(run_root, "story_report"), report)
    print(json.dumps(report, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

