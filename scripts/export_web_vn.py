#!/usr/bin/env python3
"""Export a self-contained browser VN from accepted artifacts."""

from __future__ import annotations

import argparse
import collections
import json
import shlex
import re
import shutil
from pathlib import Path
from typing import Any

from pipeline_lib import (
    Json,
    as_list,
    copy_tree,
    load_gameplay_units,
    load_optional_json,
    load_yarn_fragments,
    path_for,
    skill_root,
    write_text,
)


AUTHORING_TEXT_PATTERNS = [
    re.compile(r"\b(source detail|source_dialogue|must_keep|detail row|transition context)\b", re.I),
    re.compile(r"原文细节"),
    re.compile(r"(读者|玩家)"),
    re.compile(r"(读者|玩家).{0,80}(抓住|注意|了解|沉浸|问题|钩子|选择|看到)"),
    re.compile(r"\b(reader|player).{0,80}\b(journey|hook|question|tension|notice|learn)\b", re.I),
    re.compile(r"钩子是"),
    re.compile(r"问题(是|从|转向|撕开).{0,100}钩子"),
    re.compile(r"\b(the question is|the hook is)\b", re.I),
    re.compile(r"(不显示|显示).{0,20}(菜单|按钮|结局)"),
    re.compile(r"前五章.{0,12}(暂止|收束|结局|菜单)"),
    re.compile(r"(被展开|这是前五章暂止点|场景继续向前推进)"),
    re.compile(r"余波"),
]


def contains_authoring_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in AUTHORING_TEXT_PATTERNS)


def contains_cjk(text: Any) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", str(text or "")))


def story_beats_contain_cjk(beats: list[Any]) -> bool:
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        if contains_cjk(beat.get("text")) or contains_cjk(beat.get("label")):
            return True
        if beat.get("type") == "choice":
            for choice in as_list(beat.get("choices")):
                if isinstance(choice, dict) and (
                    contains_cjk(choice.get("label"))
                    or story_beats_contain_cjk(as_list(choice.get("beats")))
                ):
                    return True
    return False


def exported_story_uses_cjk(story_nodes: list[Json]) -> bool:
    for node in story_nodes:
        if not isinstance(node, dict):
            continue
        if story_beats_contain_cjk(as_list(node.get("beats"))):
            return True
        for choice in as_list(node.get("choices")):
            if isinstance(choice, dict) and (
                contains_cjk(choice.get("label"))
                or story_beats_contain_cjk(as_list(choice.get("beats")))
            ):
                return True
        for variant in as_list(node.get("ending_variants")):
            if isinstance(variant, dict) and (
                contains_cjk(variant.get("title"))
                or story_beats_contain_cjk(as_list(variant.get("beats")))
            ):
                return True
    return False


def localized_story_title(title: Any, story_nodes: list[Json]) -> str:
    source_title = str(title or "").strip()
    if not exported_story_uses_cjk(story_nodes) or contains_cjk(source_title):
        return source_title or "Narrative Game"
    if "alice" in source_title.lower():
        return "爱丽丝梦游奇境：网状改编"
    return "互动叙事"


def localize_choice_fallbacks_for_cjk(story_nodes: list[Json]) -> None:
    if not exported_story_uses_cjk(story_nodes):
        return
    for node in story_nodes:
        if not isinstance(node, dict):
            continue
        for choice in as_list(node.get("choices")):
            if isinstance(choice, dict) and not contains_cjk(choice.get("label")):
                choice["label"] = "继续"


def node_text(node: Json) -> str:
    for value in (node.get("body"), node.get("summary")):
        if isinstance(value, str) and value.strip() and not contains_authoring_text(value):
            return value
    return str(node.get("title") or "The scene continues.")


def filter_player_beats(beats: list[Json]) -> list[Json]:
    filtered = [
        beat for beat in beats
        if not (isinstance(beat, dict) and contains_authoring_text(str(beat.get("text", ""))))
    ]
    return filtered or beats


def validate_player_facing_story(story: Json) -> None:
    leaks: list[str] = []

    def check_beats(node_id: str, beats: list[Any]) -> None:
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            text = str(beat.get("text") or "")
            if text and contains_authoring_text(text):
                leaks.append(f"{node_id} beat: {text}")
            if beat.get("type") == "choice":
                for choice in as_list(beat.get("choices")):
                    if not isinstance(choice, dict):
                        continue
                    label = str(choice.get("label") or "")
                    if label and contains_authoring_text(label):
                        leaks.append(f"{node_id} inline choice: {label}")
                    check_beats(node_id, as_list(choice.get("beats")))

    for node in as_list(story.get("nodes")):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "<unknown>")
        title = str(node.get("title") or "")
        if title and contains_authoring_text(title):
            leaks.append(f"{node_id} title: {title}")
        check_beats(node_id, as_list(node.get("beats")))
        for variant in as_list(node.get("ending_variants")):
            if not isinstance(variant, dict):
                continue
            variant_title = str(variant.get("title") or "")
            if variant_title and contains_authoring_text(variant_title):
                leaks.append(f"{node_id} ending variant title: {variant_title}")
            check_beats(node_id, as_list(variant.get("beats")))
        for choice in as_list(node.get("choices")):
            if isinstance(choice, dict):
                label = str(choice.get("label") or "")
                if label and contains_authoring_text(label):
                    leaks.append(f"{node_id} choice: {label}")
                check_beats(node_id, as_list(choice.get("beats")))
    if leaks:
        sample = "\n".join(leaks[:20])
        raise SystemExit(f"Player-facing authoring text leak detected:\n{sample}")


def runtime_asset_name(asset_id: str, suffix: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", asset_id).strip("_") or "asset"
    return f"{safe_id}{suffix}"


def normalize_command_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip('"').strip("'")
    return value or None


def character_id_for_portrait(asset_id: str) -> str:
    parts = asset_id.split(".")
    if len(parts) >= 2:
        return f"char.{parts[1]}"
    return "char.unknown"


def safe_voice_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_").lower()


def is_narration_speaker(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"", "旁白", "narrator"}


def parse_dialogue_line(line: str) -> Json | None:
    match = re.match(r"^([A-Za-z0-9_.\-·\u4e00-\u9fff（）()]{1,24})[:：]\s*(.+)$", line)
    if not match:
        return None
    speaker = match.group(1).strip()
    text = match.group(2).strip()
    if not speaker or not text:
        return None
    return {"type": "line", "speaker": speaker, "text": text}


def parse_yarn_command(line: str) -> Json | None:
    if not (line.startswith("<<") and line.endswith(">>")):
        return None
    body = line[2:-2].strip()
    if not body:
        return None
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    if not tokens:
        return None
    command = tokens[0]
    named: dict[str, str] = {}
    positional: list[str] = []
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            if key:
                named[key] = value
        else:
            positional.append(token)

    def first(*keys: str) -> str | None:
        for key in keys:
            value = normalize_command_token(named.get(key))
            if value:
                return value
        while positional and not normalize_command_token(positional[0]):
            positional.pop(0)
        return normalize_command_token(positional.pop(0)) if positional else None

    args: Json = {}
    if command in ("show_bg", "show_cg", "play_bgm", "play_sfx"):
        asset_id = first("asset_id", "bg", "cg", "track", "location")
        if asset_id:
            args["asset_id"] = asset_id
    elif command == "show_char":
        character_id = first("character_id", "character", "name")
        asset_id = first("asset_id", "portrait", "expression_asset_id")
        if character_id:
            args["character_id"] = character_id
        if asset_id:
            args["asset_id"] = asset_id
    elif command == "set_expression":
        character_id = first("character_id", "character", "name")
        expression = first("expression_asset_id", "asset_id", "expression", "expr", "emotion")
        if character_id:
            args["character_id"] = character_id
        if expression:
            args["expression_asset_id"] = expression
    elif command in ("hide_char", "hide_cg"):
        character_id = first("character_id", "character", "name")
        if character_id:
            args["character_id"] = character_id
        asset_id = first("asset_id", "cg")
        if asset_id:
            args["asset_id"] = asset_id
    elif command == "stop_bgm":
        pass
    elif command == "set":
        state_id = first("state_variable_id", "state_id", "id")
        operation = first("operation", "op") or "set"
        value = first("value")
        if state_id:
            args["state_variable_id"] = state_id
        if operation:
            args["operation"] = operation
        if value is not None:
            args["value"] = value
    elif command == "complete_activity":
        outcome = first("outcome", "outcome_id", "edge_id")
        if outcome:
            args["outcome"] = outcome
    elif command == "ending_variant":
        variant_id = first("id", "variant_id", "ending_id")
        title = first("title", "label")
        priority = first("priority")
        if variant_id:
            args["id"] = variant_id
            args["ending_id"] = variant_id
        if title:
            args["title"] = title
        if priority is not None:
            args["priority"] = priority
    elif command in ("end_ending_variant", "ending_variant_end"):
        pass
    else:
        return None
    return {"type": "command", "command": command, "args": args}


def parse_yarn_beat_line(line: str) -> Json | None:
    if not line or line.startswith("//") or line in ("---", "===") or line.startswith("title:") or line.startswith("[["):
        return None
    command = parse_yarn_command(line)
    if command:
        return command
    if line.startswith("<<") and line.endswith(">>"):
        return None
    dialogue = parse_dialogue_line(line)
    return dialogue if dialogue else {"type": "line", "speaker": "Narrator", "text": line}


def split_choice_label(label: str) -> tuple[str, str | None]:
    match = re.search(r"\s*<<if\s+(.+?)>>\s*$", label)
    if not match:
        return label.strip(), None
    return label[:match.start()].strip(), match.group(1).strip()


def parse_yarn_choice_branch(label: str, raw_lines: list[str]) -> Json:
    clean_label, condition_text = split_choice_label(label)
    beats: list[Json] = []
    outcome_id: str | None = None
    for raw in raw_lines:
        line = raw.strip()
        command = parse_yarn_command(line)
        if command and command.get("command") == "complete_activity":
            outcome = command.get("args", {}).get("outcome") if isinstance(command.get("args"), dict) else None
            if isinstance(outcome, str) and outcome:
                outcome_id = outcome
            continue
        beat = parse_yarn_beat_line(line)
        if beat:
            beats.append(beat)
    choice: Json = {"label": clean_label or "Continue", "beats": beats}
    if condition_text:
        choice["condition_text"] = condition_text
    if outcome_id:
        choice["outcome_id"] = outcome_id
    return choice


def parse_vn_yarn(text: str) -> Json:
    beats: list[Json] = []
    exit_choices: list[Json] = []
    ending_variants: list[Json] = []
    current_variant: Json | None = None

    def append_beat(beat: Json) -> None:
        if current_variant is not None:
            current_variant.setdefault("beats", []).append(beat)
        else:
            beats.append(beat)

    def close_variant() -> None:
        nonlocal current_variant
        if current_variant is not None:
            ending_variants.append(current_variant)
            current_variant = None

    def parse_priority(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        if not line:
            index += 1
            continue
        if line.startswith("->"):
            group: list[Json] = []
            while index < len(lines) and lines[index].strip().startswith("->"):
                label = lines[index].strip()[2:].strip()
                index += 1
                branch_lines: list[str] = []
                while index < len(lines):
                    next_raw = lines[index]
                    next_line = next_raw.strip()
                    if next_line.startswith("->"):
                        break
                    if next_line in ("---", "===") or next_line.startswith("title:"):
                        break
                    if not next_line or next_raw[:1].isspace():
                        branch_lines.append(next_raw)
                        index += 1
                        continue
                    break
                group.append(parse_yarn_choice_branch(label, branch_lines))
                if index >= len(lines) or not lines[index].strip().startswith("->"):
                    break
            if group and all(choice.get("outcome_id") for choice in group):
                exit_choices.extend(group)
            elif group:
                inline_choices = [choice for choice in group if not choice.get("outcome_id")]
                exit_choices.extend(choice for choice in group if choice.get("outcome_id"))
                if inline_choices:
                    append_beat({"type": "choice", "choices": inline_choices})
            continue

        command = parse_yarn_command(line)
        if command and command.get("command") == "ending_variant":
            close_variant()
            args = command.get("args") if isinstance(command.get("args"), dict) else {}
            variant_id = str(args.get("id") or args.get("ending_id") or f"ending.variant.{len(ending_variants) + 1}")
            current_variant = {
                "id": variant_id,
                "ending_id": args.get("ending_id") or variant_id,
                "title": args.get("title") or variant_id,
                "priority": parse_priority(args.get("priority")),
                "beats": [],
            }
            index += 1
            continue
        if command and command.get("command") in ("end_ending_variant", "ending_variant_end"):
            close_variant()
            index += 1
            continue
        if command and command.get("command") == "complete_activity":
            target_beats = current_variant.get("beats", []) if current_variant is not None else beats
            while target_beats and isinstance(target_beats[-1], dict) and target_beats[-1].get("type") == "command" and target_beats[-1].get("command") == "set":
                target_beats.pop()
            index += 1
            continue
        beat = parse_yarn_beat_line(line)
        if beat:
            append_beat(beat)
        index += 1
    close_variant()
    if not beats:
        beats = [{"type": "line", "speaker": "Narrator", "text": "The scene continues."}]
    return {"beats": beats, "exit_choices": exit_choices, "ending_variants": ending_variants}


def voice_asset_lookup(manifest: Json) -> tuple[set[str], dict[str, Json]]:
    voice_ids: set[str] = set()
    voice_specs: dict[str, Json] = {}
    for audio in as_list(manifest.get("audio")):
        if not isinstance(audio, dict) or not isinstance(audio.get("asset_id"), str):
            continue
        kind = str(audio.get("kind") or "").lower()
        asset_id = audio["asset_id"]
        if kind == "voice" or asset_id.startswith("voice."):
            voice_ids.add(asset_id)
            voice_specs[asset_id] = audio
    return voice_ids, voice_specs


def attach_voice_assets(beats: list[Json], node_id: str, manifest: Json, allow_fallback: bool = True) -> None:
    voice_ids, voice_specs = voice_asset_lookup(manifest)
    if not voice_ids:
        return
    node_token = safe_voice_token(node_id)
    node_short_token = safe_voice_token(str(node_id).removeprefix("node."))
    line_index = 0
    for beat in beats:
        if not isinstance(beat, dict) or beat.get("type") != "line":
            continue
        line_index += 1
        speaker_token = safe_voice_token(beat.get("speaker"))
        beat_text = str(beat.get("text") or "").strip()
        beat_speaker = str(beat.get("speaker") or "").strip()
        for asset_id, audio in voice_specs.items():
            spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
            trace = spec.get("source_trace") if isinstance(spec.get("source_trace"), dict) else {}
            source_nodes = as_list(trace.get("node_ids"))
            if node_id not in source_nodes:
                continue
            spec_text = str(spec.get("line_text") or spec.get("text") or "").strip()
            spec_speaker = str(spec.get("speaker") or "").strip()
            if spec_text and spec_text == beat_text and (
                not spec_speaker or not beat_speaker or spec_speaker == beat_speaker or is_narration_speaker(beat_speaker)
            ):
                if spec_speaker and is_narration_speaker(beat.get("speaker")):
                    beat["speaker"] = spec_speaker
                    speaker_token = safe_voice_token(spec_speaker)
                    beat_speaker = spec_speaker
                beat["voice_asset_id"] = asset_id
                break
        if beat.get("voice_asset_id"):
            continue
        if not allow_fallback:
            continue
        for asset_id, audio in voice_specs.items():
            spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
            trace = spec.get("source_trace") if isinstance(spec.get("source_trace"), dict) else {}
            source_nodes = as_list(trace.get("node_ids"))
            if node_id not in source_nodes:
                continue
            try:
                spec_line_index = int(spec.get("line_index"))
            except (TypeError, ValueError):
                continue
            if spec_line_index != line_index:
                continue
            spec_speaker = str(spec.get("speaker") or "").strip()
            if spec_speaker and (not beat_speaker or spec_speaker == beat_speaker or is_narration_speaker(beat_speaker)):
                if is_narration_speaker(beat.get("speaker")):
                    beat["speaker"] = spec_speaker
                beat["voice_asset_id"] = asset_id
                break
        if beat.get("voice_asset_id"):
            continue
        if is_narration_speaker(beat.get("speaker")):
            continue
        candidates = [
            f"voice.{node_id}.{line_index}",
            f"voice.{node_id}.{line_index - 1}",
            f"voice.{node_token}.{line_index}",
            f"voice.{node_token}.{line_index - 1}",
            f"voice.{node_short_token}.{line_index}",
            f"voice.{node_short_token}.{line_index - 1}",
        ]
        if speaker_token:
            candidates.extend([
                f"voice.{node_token}.{speaker_token}.{line_index}",
                f"voice.{node_token}.{speaker_token}.{line_index - 1}",
                f"voice.{node_short_token}.{speaker_token}.{line_index}",
                f"voice.{node_short_token}.{speaker_token}.{line_index - 1}",
            ])
        for asset_id in candidates:
            if asset_id in voice_ids:
                beat["voice_asset_id"] = asset_id
                break


def attach_voice_assets_recursive(beats: list[Json], node_id: str, manifest: Json, allow_fallback: bool = True) -> None:
    attach_voice_assets(beats, node_id, manifest, allow_fallback=allow_fallback)
    for beat in beats:
        if not isinstance(beat, dict) or beat.get("type") != "choice":
            continue
        for choice in as_list(beat.get("choices")):
            if isinstance(choice, dict):
                attach_voice_assets_recursive(as_list(choice.get("beats")), node_id, manifest, allow_fallback=False)


def collect_runtime_assets(run_root: Path, output_root: Path, asset_directions: list[Any]) -> dict[str, str]:
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    generated_root = run_root / "workspace" / "generated-assets"
    source_root = run_root / "workspace" / "assets" / "web-vn"
    destination_root = output_root / "assets"
    destination_root.mkdir(parents=True, exist_ok=True)
    runtime_paths: dict[str, str] = {}

    def copy_manifest_asset(asset_id: str, file_ref: str) -> None:
        source = generated_root / file_ref
        if not source.exists():
            return
        destination = destination_root / file_ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{file_ref}"

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str) and isinstance(background.get("file_ref"), str):
            copy_manifest_asset(background["asset_id"], background["file_ref"])
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str) and isinstance(cg.get("file_ref"), str):
            copy_manifest_asset(cg["asset_id"], cg["file_ref"])
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str) and isinstance(ui_asset.get("file_ref"), str):
            copy_manifest_asset(ui_asset["asset_id"], ui_asset["file_ref"])
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict) and isinstance(audio.get("asset_id"), str) and isinstance(audio.get("file_ref"), str):
            copy_manifest_asset(audio["asset_id"], audio["file_ref"])
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        if isinstance(character.get("canon_ref_asset_id"), str) and isinstance(character.get("canon_ref_file_ref"), str):
            copy_manifest_asset(character["canon_ref_asset_id"], character["canon_ref_file_ref"])
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict) and isinstance(portrait.get("asset_id"), str) and isinstance(portrait.get("file_ref"), str):
                copy_manifest_asset(portrait["asset_id"], portrait["file_ref"])

    if not source_root.exists():
        return runtime_paths

    for asset in asset_directions:
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str):
            continue
        asset_id = asset["asset_id"]
        if asset_id in runtime_paths:
            continue
        source = None
        for suffix in (".png", ".svg", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac"):
            candidate = source_root / runtime_asset_name(asset_id, suffix)
            if candidate.exists():
                source = candidate
                break
        if source is None:
            continue
        destination = destination_root / source.name
        shutil.copy2(source, destination)
        runtime_paths[asset_id] = f"assets/{destination.name}"
    return runtime_paths


def manifest_asset_entries(manifest: Json, runtime_assets: dict[str, str]) -> list[Json]:
    entries: list[Json] = []

    def add_entry(asset_id: str, kind: str, source: Json) -> None:
        entry = {"asset_id": asset_id, "kind": kind}
        for key in ("scene_id", "story_beat_id", "location_tag", "time_of_day", "emotion", "character_id", "display_name"):
            if key in source:
                entry[key] = source[key]
        spec = source.get("spec")
        if isinstance(spec, dict):
            entry["spec"] = spec
        if asset_id in runtime_assets:
            entry["runtime_path"] = runtime_assets[asset_id]
        entries.append(entry)

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict) and isinstance(background.get("asset_id"), str):
            add_entry(background["asset_id"], "background", background)
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict) and isinstance(cg.get("asset_id"), str):
            add_entry(cg["asset_id"], "cg", cg)
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict) and isinstance(ui_asset.get("asset_id"), str):
            add_entry(ui_asset["asset_id"], str(ui_asset.get("kind") or "ui"), ui_asset)
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict) and isinstance(audio.get("asset_id"), str):
            add_entry(audio["asset_id"], str(audio.get("kind") or "audio"), audio)
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        character_id = character.get("id")
        if isinstance(character.get("canon_ref_asset_id"), str):
            add_entry(character["canon_ref_asset_id"], "charref", {
                "character_id": character_id,
                "display_name": character.get("display_name"),
            })
        for portrait in as_list(character.get("portrait_assets")):
            if not isinstance(portrait, dict) or not isinstance(portrait.get("asset_id"), str):
                continue
            add_entry(portrait["asset_id"], "portrait", {
                **portrait,
                "character_id": character_id or character_id_for_portrait(portrait["asset_id"]),
                "display_name": character.get("display_name"),
            })
    return entries


def manifest_character_entries(manifest: Json) -> list[Json]:
    characters = []
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict) or not isinstance(character.get("id"), str):
            continue
        characters.append({
            "id": character["id"],
            "display_name": character.get("display_name") or character["id"],
            "base_portrait_asset_id": character.get("base_portrait_asset_id"),
            "expression_asset_ids": as_list(character.get("expression_asset_ids")),
            "portrait_assets": as_list(character.get("portrait_assets")),
        })
    return characters


def normalize_state_ops(value: Any) -> list[Json]:
    ops: list[Json] = []
    for item in as_list(value):
        if not isinstance(item, dict):
            continue
        state_id = item.get("state_variable_id") or item.get("state_id") or item.get("id")
        if not isinstance(state_id, str) or not state_id:
            continue
        op = dict(item)
        op["state_variable_id"] = state_id
        op.setdefault("operation", "set")
        ops.append(op)
    return ops


def expanded_runtime_edges(edge: Json) -> list[Json]:
    merged = dict(edge)
    merged["conditions"] = as_list(merged.get("conditions"))
    merged["effects"] = normalize_state_ops(merged.get("effects"))
    return [merged]


def attach_choice_beats(choice: Json, branch: Json | None, node_id: str, manifest: Json) -> None:
    if not isinstance(branch, dict):
        if str(choice.get("condition_type") or "") != "player_choice":
            choice["label"] = "继续"
        return
    beats = as_list(branch.get("beats"))
    attach_voice_assets_recursive(beats, node_id, manifest, allow_fallback=False)
    if beats:
        choice["beats"] = beats
    if branch.get("label"):
        choice["label"] = branch["label"]
    if branch.get("condition_text"):
        choice["condition_text"] = branch["condition_text"]


def normalize_terminal_variants(parsed_yarn: Json, plan: Json, fragment_manifest: Json, node_id: str, asset_manifest: Json) -> list[Json]:
    metadata_by_id: dict[str, Json] = {}
    for source in (as_list(plan.get("terminal_variants")) if isinstance(plan, dict) else []):
        if isinstance(source, dict) and isinstance(source.get("id"), str):
            metadata_by_id[source["id"]] = dict(source)
    for source in as_list(fragment_manifest.get("terminal_variants") if isinstance(fragment_manifest, dict) else []):
        if isinstance(source, dict) and isinstance(source.get("id"), str):
            metadata_by_id[source["id"]] = {**metadata_by_id.get(source["id"], {}), **source}

    variants: list[Json] = []
    used_ids: set[str] = set()
    for parsed in as_list(parsed_yarn.get("ending_variants")):
        if not isinstance(parsed, dict):
            continue
        variant_id = parsed.get("id")
        if not isinstance(variant_id, str) or not variant_id:
            continue
        merged = {**metadata_by_id.get(variant_id, {}), **parsed}
        beats = filter_player_beats(as_list(merged.get("beats")))
        attach_voice_assets_recursive(beats, node_id, asset_manifest, allow_fallback=False)
        merged["beats"] = beats
        merged["conditions"] = as_list(merged.get("conditions"))
        merged["state_writes"] = normalize_state_ops(merged.get("state_writes"))
        try:
            merged["priority"] = int(merged.get("priority", 0))
        except (TypeError, ValueError):
            merged["priority"] = 0
        if "ending_id" not in merged:
            merged["ending_id"] = variant_id
        if "title" not in merged:
            merged["title"] = variant_id
        merged = {
            "id": merged.get("id"),
            "ending_id": merged.get("ending_id"),
            "title": merged.get("title"),
            "priority": merged.get("priority"),
            "beats": merged.get("beats", []),
            "conditions": merged.get("conditions", []),
            "state_writes": merged.get("state_writes", []),
        }
        variants.append(merged)
        used_ids.add(variant_id)

    for variant_id, metadata in metadata_by_id.items():
        if variant_id in used_ids:
            continue
        merged = dict(metadata)
        merged["conditions"] = as_list(merged.get("conditions"))
        merged["state_writes"] = normalize_state_ops(merged.get("state_writes"))
        merged.setdefault("ending_id", variant_id)
        merged.setdefault("title", variant_id)
        merged.setdefault("priority", 0)
        merged.setdefault("beats", [])
        merged = {
            "id": merged.get("id"),
            "ending_id": merged.get("ending_id"),
            "title": merged.get("title"),
            "priority": merged.get("priority"),
            "beats": merged.get("beats", []),
            "conditions": merged.get("conditions", []),
            "state_writes": merged.get("state_writes", []),
        }
        variants.append(merged)

    return sorted(variants, key=lambda item: int(item.get("priority", 0)), reverse=True)


def normalize_node_completion_rules(game_ir: Json) -> list[Json]:
    rules: list[Json] = []
    for rule in as_list(game_ir.get("event_rules") if isinstance(game_ir, dict) else []):
        if not isinstance(rule, dict) or not isinstance(rule.get("source_node_id"), str):
            continue
        if rule.get("source_edge_id"):
            continue
        effects = normalize_state_ops(rule.get("effects"))
        if not effects:
            continue
        rules.append({
            "id": rule.get("id") or f"rule.node_completion.{len(rules) + 1}",
            "source_node_id": rule["source_node_id"],
            "conditions": as_list(rule.get("conditions")),
            "effects": effects,
            "description": rule.get("description", ""),
            "source_settlement_id": rule.get("source_settlement_id"),
        })
    return rules


def build_story_payload(run_root: Path, runtime_assets: dict[str, str] | None = None) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    game_ir = load_optional_json(path_for(run_root, "game_ir")) or {}
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    shared_state = load_optional_json(path_for(run_root, "shared_state")) or {"variables": []}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    asset_directions = as_list(asset_direction.get("asset_directions"))
    runtime_assets = runtime_assets or {}
    fragments = load_yarn_fragments(run_root)
    gameplay_units = load_gameplay_units(run_root)

    fragments_by_node = {fragment["node_id"]: fragment for fragment in fragments}
    plan_by_node = {
        plan.get("source_node_id"): plan
        for plan in as_list(plans.get("plans"))
        if isinstance(plan, dict)
    }
    edges_by_from: dict[str, list[Json]] = {}
    for edge in as_list(branch_graph.get("edges")):
        if isinstance(edge, dict) and isinstance(edge.get("from"), str):
            edges_by_from.setdefault(edge["from"], []).extend(expanded_runtime_edges(edge))

    initial_state = {
        variable.get("id"): variable.get("initial_value")
        for variable in as_list(shared_state.get("variables"))
        if isinstance(variable, dict) and isinstance(variable.get("id"), str)
    }

    story_nodes = []
    for node in as_list(branch_graph.get("nodes")):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        node_id = node["id"]
        plan = plan_by_node.get(node_id, {})
        fragment = fragments_by_node.get(node_id)
        gameplay_unit = gameplay_units.get(node_id)
        fragment_manifest = fragment.get("manifest") if isinstance(fragment, dict) and isinstance(fragment.get("manifest"), dict) else {}
        entry_text = str(gameplay_unit.get("entry_text") or node_text(node)) if gameplay_unit else node_text(node)
        parsed_yarn = parse_vn_yarn(fragment["yarn_text"]) if fragment else {"beats": [{"type": "line", "speaker": "Narrator", "text": entry_text}], "exit_choices": []}
        beats = as_list(parsed_yarn.get("beats"))
        beats = filter_player_beats(beats)
        attach_voice_assets_recursive(beats, node_id, asset_manifest)
        terminal_variants = normalize_terminal_variants(parsed_yarn, plan if isinstance(plan, dict) else {}, fragment_manifest, node_id, asset_manifest)
        yarn_choice_by_outcome = {
            choice.get("outcome_id"): choice
            for choice in as_list(parsed_yarn.get("exit_choices"))
            if isinstance(choice, dict) and isinstance(choice.get("outcome_id"), str)
        }
        exit_bindings = {
            binding.get("edge_id"): binding
            for binding in as_list((gameplay_unit or plan).get("exit_bindings") if isinstance((gameplay_unit or plan), dict) else [])
            if isinstance(binding, dict)
        }
        choices = []
        for edge in edges_by_from.get(node_id, []):
            edge_id = edge.get("id")
            source_rule_ids = [source_id for source_id in as_list(edge.get("source_rule_ids")) if isinstance(source_id, str)]
            binding = exit_bindings.get(edge_id, {})
            if not binding:
                binding = next((exit_bindings.get(source_id) for source_id in source_rule_ids if exit_bindings.get(source_id)), {})
            outcome_id = binding.get("outcome_id") or edge_id
            choice: Json = {
                "label": binding.get("label") or edge.get("label") or edge.get("condition_label") or edge.get("outcome_label") or "Continue",
                "target": edge.get("to"),
                "edge_id": edge_id,
                "outcome_id": outcome_id,
                "condition_type": edge.get("condition_type", "player_choice"),
                "effects": normalize_state_ops(edge.get("effects")),
                "state_writes": normalize_state_ops(binding.get("state_writes")),
                "conditions": edge.get("conditions", []),
            }
            if source_rule_ids:
                choice["source_rule_ids"] = source_rule_ids
            branch = yarn_choice_by_outcome.get(str(outcome_id)) or yarn_choice_by_outcome.get(str(edge_id))
            if not branch:
                branch = next((yarn_choice_by_outcome.get(source_id) for source_id in source_rule_ids if yarn_choice_by_outcome.get(source_id)), None)
            attach_choice_beats(choice, branch, node_id, asset_manifest)
            choices.append(choice)
        required_assets = as_list(plan.get("required_assets") if isinstance(plan, dict) else [])
        if isinstance(gameplay_unit, dict):
            required_assets = [*required_assets, *as_list(gameplay_unit.get("required_assets"))]
        background_id = next((asset for asset in required_assets if isinstance(asset, str) and asset.startswith("bg.")), None)
        portrait_ids = [asset for asset in required_assets if isinstance(asset, str) and asset.startswith("portrait.")]
        node_title = fragment_manifest.get("display_title") if isinstance(fragment_manifest, dict) else None
        if not isinstance(node_title, str) or not node_title.strip():
            node_title = "" if story_beats_contain_cjk(beats) else str(node.get("title") or node_id)
        story_node = {
            "id": node_id,
            "title": node_title,
            "background_id": background_id or node.get("asset_id") or "bg.default",
            "portrait_ids": portrait_ids,
            "beats": beats,
            "choices": choices,
            "is_terminal": bool(node.get("is_terminal") or node.get("node_type") == "terminal" or not choices),
            "realization_kind": plan.get("realization_kind") if isinstance(plan, dict) else "vn_yarn",
        }
        if isinstance(gameplay_unit, dict):
            story_node["gameplay_unit_id"] = gameplay_unit.get("realization_unit_id")
            story_node["gameplay"] = {
                "adapter_id": gameplay_unit.get("adapter_id"),
                "entry_text": gameplay_unit.get("entry_text", ""),
                "runtime_spec": gameplay_unit.get("runtime_spec", {}),
                "exit_bindings": gameplay_unit.get("exit_bindings", []),
                "fail_forward": gameplay_unit.get("fail_forward", {}),
            }
        if terminal_variants:
            story_node["ending_variants"] = terminal_variants
        story_nodes.append(story_node)

    localize_choice_fallbacks_for_cjk(story_nodes)
    assets = manifest_asset_entries(asset_manifest, runtime_assets)
    seen_asset_ids = {asset.get("asset_id") for asset in assets if isinstance(asset, dict)}
    for asset in asset_directions:
        if not isinstance(asset, dict):
            continue
        enriched = dict(asset)
        asset_id = enriched.get("asset_id")
        if asset_id in seen_asset_ids:
            continue
        if isinstance(asset_id, str) and asset_id in runtime_assets:
            enriched["runtime_path"] = runtime_assets[asset_id]
        assets.append(enriched)

    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "export_web_vn.py"},
        "title": localized_story_title(branch_graph.get("title") or "Generated Narrative Game", story_nodes),
        "start_node_id": branch_graph.get("start_node_id") or (story_nodes[0]["id"] if story_nodes else ""),
        "initial_state": initial_state,
        "nodes": story_nodes,
        "characters": manifest_character_entries(asset_manifest),
        "assets": assets,
        "gameplay_units": gameplay_units,
        "node_completion_rules": normalize_node_completion_rules(game_ir),
    }


def web_export_audio_report(story: Json) -> Json:
    non_narration_lines = 0
    voiced_lines = 0
    voice_ids: list[str] = []
    unvoiced_lines: list[Json] = []

    def iter_beats(beats: list[Any]) -> Any:
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            if beat.get("type") == "choice":
                for choice in as_list(beat.get("choices")):
                    if isinstance(choice, dict):
                        yield from iter_beats(as_list(choice.get("beats")))
                continue
            yield beat

    for node in as_list(story.get("nodes")):
        if not isinstance(node, dict):
            continue
        all_beats = list(iter_beats(as_list(node.get("beats"))))
        for variant in as_list(node.get("ending_variants")):
            if isinstance(variant, dict):
                all_beats.extend(iter_beats(as_list(variant.get("beats"))))
        for choice in as_list(node.get("choices")):
            if isinstance(choice, dict):
                all_beats.extend(iter_beats(as_list(choice.get("beats"))))
        for index, beat in enumerate(all_beats):
            if not isinstance(beat, dict) or beat.get("type") != "line" or is_narration_speaker(beat.get("speaker")):
                continue
            if str(beat.get("text") or "").strip() in {"...", "…"}:
                continue
            non_narration_lines += 1
            voice_asset_id = beat.get("voice_asset_id")
            if isinstance(voice_asset_id, str) and voice_asset_id:
                voiced_lines += 1
                voice_ids.append(voice_asset_id)
            else:
                unvoiced_lines.append({
                    "node_id": node.get("id"),
                    "beat_index": index,
                    "speaker": beat.get("speaker"),
                    "text": beat.get("text"),
                })
    duplicate_voice_asset_ids = [
        {"asset_id": asset_id, "count": count}
        for asset_id, count in collections.Counter(voice_ids).items()
        if count > 1
    ]
    voice_expected = bool(voice_ids)
    status = "pass" if not unvoiced_lines or not voice_expected else "fail"
    warnings = []
    if unvoiced_lines and not voice_expected:
        warnings.append({
            "kind": "voice_assets_missing",
            "message": "No voice assets were attached; exported VN remains playable as an unvoiced build.",
        })
    return {
        "status": status,
        "non_narration_lines": non_narration_lines,
        "voiced_lines": voiced_lines,
        "unique_voice_asset_ids": len(set(voice_ids)),
        "unvoiced_lines": unvoiced_lines,
        "duplicate_voice_asset_ids": duplicate_voice_asset_ids,
        "warnings": warnings,
    }


def export_web_vn(run_root: Path) -> Path:
    output_root = run_root / "build" / "web-vn"
    copy_tree(skill_root() / "assets" / "web-vn-template", output_root)
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    runtime_assets = collect_runtime_assets(run_root, output_root, as_list(asset_direction.get("asset_directions")))
    story = build_story_payload(run_root, runtime_assets)
    validate_player_facing_story(story)
    write_text(output_root / "story-data.js", "window.NARRATIVE_GAME_STORY = " + json.dumps(story, ensure_ascii=False, indent=2) + ";\n")
    write_text(run_root / "reports" / "web-vn-export-report.json", json.dumps(web_export_audio_report(story), ensure_ascii=False, indent=2) + "\n")
    return output_root / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_web_vn(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
