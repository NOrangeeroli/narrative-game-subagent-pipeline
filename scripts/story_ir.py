#!/usr/bin/env python3
"""Lower simple Yarn text to StoryIR and verify basic VN routing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


AUTHORING_LEAK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("source_context_label", re.compile(r"\b(source detail|source_dialogue|must_keep|detail row|transition context)\b", re.I)),
    ("source_context_label", re.compile(r"原文细节")),
    ("reader_reference", re.compile(r"(读者|玩家)")),
    ("reader_guidance", re.compile(r"(读者|玩家).{0,80}(抓住|注意|了解|沉浸|问题|钩子|选择|看到)")),
    ("reader_guidance", re.compile(r"\b(reader|player).{0,80}\b(journey|hook|question|tension|notice|learn)\b", re.I)),
    ("scene_hook_note", re.compile(r"钩子是")),
    ("scene_question_hook_note", re.compile(r"问题(是|从|转向|撕开).{0,100}钩子")),
    ("english_scene_note", re.compile(r"\b(the question is|the hook is)\b", re.I)),
    ("runtime_instruction", re.compile(r"(不显示|显示).{0,20}(菜单|按钮|结局)")),
    ("scope_note", re.compile(r"前五章.{0,12}(暂止|收束|结局|菜单)")),
    ("summary_voice", re.compile(r"(被展开|这是前五章暂止点|场景继续向前推进)")),
]


def split_private_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) >= 12:
        phrases.append(cleaned)
    for part in re.split(r"[。！？；;]\s*", cleaned):
        part = part.strip()
        if len(part) >= 12:
            phrases.append(part)
    return phrases


def collect_private_authoring_phrases(run_root: Path) -> list[str]:
    phrases: list[str] = []
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    for node in as_list(branch_graph.get("nodes")):
        if not isinstance(node, dict):
            continue
        for key in ("summary", "body"):
            value = node.get(key)
            if isinstance(value, str):
                phrases.extend(split_private_phrases(value))
    source_segments = load_optional_json(run_root / "workspace" / "design_layer_v2" / "source_intake" / "source_segments.json") or {}
    for segment in as_list(source_segments.get("segments")):
        if not isinstance(segment, dict):
            continue
        value = segment.get("summary")
        if isinstance(value, str):
            phrases.extend(split_private_phrases(value))
    return sorted(set(phrases), key=len, reverse=True)


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
        "lines": lines,
        "line_count": len(lines),
    }


def verify_story_ir(story_ir: Json, private_authoring_phrases: list[str] | None = None) -> Json:
    findings: list[Json] = []
    nodes = story_ir.get("nodes", [])
    titles: set[str] = set()
    private_authoring_phrases = private_authoring_phrases or []
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
            if command.get("command") not in (
                "complete_activity",
                "set",
                "wait",
                "show",
                "hide",
                "show_bg",
                "show_char",
                "set_expression",
                "hide_char",
                "show_cg",
                "hide_cg",
                "play_sfx",
                "play_bgm",
                "stop_bgm",
            ):
                findings.append({"severity": "warning", "kind": "unknown_command", "message": f"Unknown Yarn command: {command.get('command')}"})
            if command.get("command") == "complete_activity" and "outcome" not in command.get("args", {}):
                findings.append({"severity": "error", "kind": "missing_outcome", "message": f"complete_activity in {node.get('title')} needs outcome arg."})
        for line in node.get("lines", []):
            if not isinstance(line, str):
                continue
            for kind, pattern in AUTHORING_LEAK_PATTERNS:
                if pattern.search(line):
                    snippet = line if len(line) <= 120 else line[:117] + "..."
                    findings.append({
                        "severity": "error",
                        "kind": "authoring_text_leak",
                        "code": kind,
                        "message": f"{node.get('title')} contains authoring-only text: {snippet}",
                    })
                    break
            visible_text = re.split(r"[:：]", line, 1)[1].strip() if re.search(r"[:：]", line) else line.strip()
            for phrase in private_authoring_phrases:
                if phrase and phrase in visible_text:
                    snippet = visible_text if len(visible_text) <= 120 else visible_text[:117] + "..."
                    findings.append({
                        "severity": "error",
                        "kind": "authoring_text_leak",
                        "code": "private_summary_reuse",
                        "message": f"{node.get('title')} reuses private design/source summary text: {snippet}",
                    })
                    break
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
    report = verify_story_ir(story_ir, collect_private_authoring_phrases(run_root))
    story_ir["verification"] = report
    write_json(path_for(run_root, "story_ir"), story_ir)
    write_json(path_for(run_root, "story_report"), report)
    print(json.dumps(report, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
