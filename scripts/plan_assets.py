#!/usr/bin/env python3
"""Plan runtime assets from asset direction, following unity-vn-studio's manifest split."""

from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_advanced_vn_scenes, load_gameplay_units, load_optional_json, load_yarn_fragments, path_for, write_json


def sanitize_file_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "asset"


def safe_voice_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_").lower() or "line"


def looks_like_asset_id(value: Any) -> bool:
    return isinstance(value, str) and bool(re.match(r"^[a-z][a-z0-9_-]*\.", value.strip()))


def asset_slug(asset_id: str) -> str:
    parts = asset_id.split(".")
    if len(parts) >= 2:
        return parts[1]
    return sanitize_file_stem(asset_id)


def portrait_emotion(asset_id: str) -> str:
    parts = asset_id.split(".")
    return parts[2] if len(parts) >= 3 else "neutral"


def character_id_for_portrait(asset_id: str) -> str:
    return f"char.{asset_slug(asset_id)}"


def collect_character_names(game_ir: Json) -> dict[str, str]:
    names: dict[str, str] = {}
    for entity in as_list(game_ir.get("entities")):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("id")
        if not isinstance(entity_id, str):
            continue
        if entity.get("kind") != "character" and not entity_id.startswith("char."):
            continue
        names[entity_id] = str(entity.get("name") or entity_id)
    bible = game_ir.get("design_brief", {}).get("narrative_bible", {}) if isinstance(game_ir.get("design_brief"), dict) else {}
    for character in as_list(bible.get("cast") if isinstance(bible, dict) else []):
        if not isinstance(character, dict) or not isinstance(character.get("id"), str):
            continue
        names.setdefault(character["id"], str(character.get("name") or character["id"]))
    return names


def source_node_for_asset(asset: Json, branch_graph: Json) -> str:
    trace = normalized_source_trace(asset)
    node_ids = as_list(trace.get("node_ids") if isinstance(trace, dict) else [])
    for node_id in node_ids:
        if isinstance(node_id, str) and node_id:
            return node_id
    start = branch_graph.get("start_node_id")
    return start if isinstance(start, str) and start else "node.start"


def normalized_source_trace(asset: Json) -> Json:
    trace = dict(asset.get("source_trace")) if isinstance(asset.get("source_trace"), dict) else {}
    node_ids = [node_id for node_id in as_list(trace.get("node_ids")) if isinstance(node_id, str) and node_id]
    for key in ("source_node_id", "node_id"):
        node_id = asset.get(key)
        if isinstance(node_id, str) and node_id and node_id not in node_ids:
            node_ids.append(node_id)
    for node_id in as_list(asset.get("source_node_ids")):
        if isinstance(node_id, str) and node_id and node_id not in node_ids:
            node_ids.append(node_id)
    if node_ids:
        trace["node_ids"] = node_ids
    return trace


def make_style_bible(asset_direction: Json) -> Json:
    style = asset_direction.get("style_pack") if isinstance(asset_direction.get("style_pack"), dict) else {}
    return {
        "palette": as_list(style.get("palette") if isinstance(style, dict) else []),
        "rendering_mode": style.get("rendering") or style.get("summary") or "visual novel illustration",
        "lighting_mood": style.get("lighting", "") if isinstance(style, dict) else "",
        "summary": style.get("summary", "") if isinstance(style, dict) else "",
    }


def normalize_voice_profiles(asset_direction: Json) -> dict[str, Json]:
    raw_profiles = asset_direction.get("voice_profiles") if isinstance(asset_direction, dict) else None
    profiles: dict[str, Json] = {}
    if isinstance(raw_profiles, dict):
        for profile_id, profile in raw_profiles.items():
            if isinstance(profile_id, str) and profile_id.strip() and isinstance(profile, dict):
                profiles[profile_id] = profile
    elif isinstance(raw_profiles, list):
        for profile in raw_profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = profile.get("id") or profile.get("voice_id") or profile.get("profile_id")
            if isinstance(profile_id, str) and profile_id.strip():
                profiles[profile_id] = {key: value for key, value in profile.items() if key not in {"id", "profile_id"}}
    return profiles


def provider_binding(value: Json, provider: str) -> Json:
    bindings = value.get("provider_bindings") if isinstance(value.get("provider_bindings"), dict) else {}
    binding = bindings.get(provider) if isinstance(bindings, dict) else None
    return binding if isinstance(binding, dict) else {}


def voice_profile_for_speaker(speaker: Any, voice_profiles: dict[str, Json]) -> str | None:
    if not isinstance(speaker, str) or not speaker.strip() or not voice_profiles:
        return None
    speaker_text = speaker.strip()
    direct = f"voice_profile.{safe_voice_token(speaker_text)}"
    if direct in voice_profiles:
        return direct
    normalized_speaker = safe_voice_token(speaker_text)
    for profile_id, profile in voice_profiles.items():
        candidates = [
            profile_id.removeprefix("voice_profile."),
            str(profile.get("speaker") or ""),
            str(profile.get("name") or ""),
            str(profile.get("display_name") or ""),
        ]
        if any(candidate.strip() == speaker_text for candidate in candidates if isinstance(candidate, str) and candidate.strip()):
            return profile_id
        if normalized_speaker != "line" and any(
            safe_voice_token(candidate) == normalized_speaker
            for candidate in candidates
            if candidate and safe_voice_token(candidate) != "line"
        ):
            return profile_id
    return None


def character_profile_from_voice_profile(profile: Json) -> Json:
    profile_keys = (
        "speaker",
        "name",
        "display_name",
        "gender",
        "age",
        "age_impression",
        "persona",
        "prompt",
    )
    return {key: profile[key] for key in profile_keys if key in profile and profile[key] not in (None, "", [])}


def strip_dialogue_quotes(value: str) -> str:
    text = value.strip()
    quote_pairs = (("“", "”"), ('"', '"'), ("'", "'"))
    for left, right in quote_pairs:
        if text.startswith(left) and text.endswith(right) and len(text) >= len(left) + len(right):
            return text[len(left): -len(right)].strip()
    return text


def spoken_voice_text(value: Any, speaker: Any = None) -> str:
    text = str(value or "").strip()
    speaker_text = str(speaker or "").strip()
    if not text:
        return ""
    if speaker_text:
        escaped = re.escape(speaker_text)
        action_match = re.match(rf"^{escaped}[^“”\"']*[:：]\s*[“\"](.+?)[”\"]\s*$", text)
        if action_match:
            return action_match.group(1).strip()
        prefix_match = re.match(rf"^{escaped}(?:心想|（心声）|\(心声\))?[:：]\s*(.+)$", text)
        if prefix_match:
            return strip_dialogue_quotes(prefix_match.group(1))
    label_match = re.match(r"^([^:：“”\"'\n]{1,24})[:：]\s*(.+)$", text)
    if label_match:
        label = re.sub(r"\s+", "", label_match.group(1).strip())
        rest = label_match.group(2).strip()
        speaker_compact = re.sub(r"\s+", "", speaker_text)
        if rest.startswith(("“", '"')) or (
            speaker_compact and (label in speaker_compact or speaker_compact in label)
        ):
            return strip_dialogue_quotes(rest)
    return strip_dialogue_quotes(text)


def voice_line_match_key(asset: Json) -> tuple[str, int, str, str] | None:
    kind = str(asset.get("kind") or "").lower()
    asset_id = str(asset.get("asset_id") or "")
    if kind != "voice" and not asset_id.startswith("voice."):
        return None
    trace = normalized_source_trace(asset)
    node_ids = [node_id for node_id in as_list(trace.get("node_ids")) if isinstance(node_id, str) and node_id]
    if not node_ids:
        return None
    try:
        line_index = int(asset.get("line_index"))
    except (TypeError, ValueError):
        return None
    speaker = safe_voice_token(asset.get("speaker"))
    text = spoken_voice_text(asset.get("text") or asset.get("line_text") or "", asset.get("speaker"))
    if speaker == "line" or not text:
        return None
    return (node_ids[0], line_index, speaker, text)


def kind_for_asset_id(asset_id: str) -> str:
    prefix = asset_id.split(".", 1)[0]
    return {
        "bg": "background",
        "cg": "cg",
        "portrait": "portrait",
        "bgm": "bgm",
        "sfx": "sfx",
        "voice": "voice",
        "enemy": "enemy",
        "prop": "prop",
        "hotspot": "hotspot",
        "symbol": "symbol",
        "effect": "effect",
        "icon": "icon",
        "map": "map",
        "ui": "ui",
    }.get(prefix, "ui")


def kind_for_scene_command(command: str, asset_id: str) -> str:
    command_kind = {
        "show_bg": "background",
        "show_cg": "cg",
        "show_char": "portrait",
        "set_expression": "portrait",
        "play_bgm": "bgm",
        "play_sfx": "sfx",
    }.get(command)
    return command_kind or kind_for_asset_id(asset_id)


def audio_kind_for_asset(asset_id: str, kind: Any) -> str:
    if kind in ("bgm", "sfx", "voice"):
        return str(kind)
    prefix = asset_id.split(".", 1)[0]
    if prefix in ("bgm", "sfx", "voice"):
        return prefix
    return "bgm"


def audio_file_extension(audio_kind: str) -> str:
    if audio_kind == "bgm":
        return normalize_audio_extension(os.environ.get("AUDIO_BGM_FORMAT") or os.environ.get("AUDIO_MUSIC_FORMAT") or "mp3")
    return normalize_audio_extension(os.environ.get("AUDIO_FORMAT") or "wav")


def normalize_audio_extension(value: str) -> str:
    cleaned = str(value or "").strip().lower().lstrip(".")
    if cleaned in {"mp3", "wav", "ogg", "m4a", "aac", "flac", "pcm"}:
        return cleaned
    if cleaned in {"mpeg", "mpga"}:
        return "mp3"
    return "wav"


def command_args_from_yarn_line(line: str) -> Json | None:
    stripped = line.strip()
    if not (stripped.startswith("<<") and stripped.endswith(">>")):
        return None
    body = stripped[2:-2].strip()
    if not body:
        return None
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    if not tokens:
        return None
    command = tokens[0]
    args: Json = {}
    positional: list[str] = []
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            args[key] = value.strip().strip('"').strip("'")
        else:
            positional.append(token.strip().strip('"').strip("'"))
    if positional:
        if command in {"show_bg", "show_cg", "play_bgm", "play_sfx"}:
            args.setdefault("asset_id", positional[0])
        elif command == "show_char":
            args.setdefault("character_id", positional[0])
            if len(positional) > 1:
                args.setdefault("asset_id", positional[1])
        elif command == "set_expression":
            args.setdefault("character_id", positional[0])
            if len(positional) > 1:
                args.setdefault("expression_asset_id", positional[1])
    return {"command": command, "args": args}


def command_refs_from_yarn_text(text: str) -> list[Json]:
    refs: list[Json] = []
    for line in text.splitlines():
        parsed = command_args_from_yarn_line(line)
        if parsed:
            refs.append(parsed)
    return refs


def visible_scene_excerpt(yarn_text: str, max_chars: int = 360) -> str:
    parts: list[str] = []
    for raw in yarn_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line in {"---", "==="} or line.startswith(("title:", "<<", "->", "[[")):
            continue
        if re.search(r"[:：]", line):
            line = re.split(r"[:：]", line, 1)[1].strip()
        if line:
            parts.append(line)
        if sum(len(part) for part in parts) >= max_chars:
            break
    excerpt = " ".join(parts)
    return excerpt[:max_chars].strip()


def asset_ids_from_command(command_ref: Json) -> list[str]:
    command = command_ref.get("command")
    args = command_ref.get("args") if isinstance(command_ref.get("args"), dict) else {}
    refs: list[str] = []
    if command in {"show_bg", "show_cg", "play_bgm", "play_sfx"}:
        refs.append(str(args.get("asset_id") or ""))
    elif command == "show_char":
        refs.append(str(args.get("asset_id") or ""))
    elif command == "set_expression":
        refs.append(str(args.get("expression_asset_id") or args.get("asset_id") or ""))
    return [ref for ref in refs if looks_like_asset_id(ref)]


def command_for_asset(command_refs: list[Json], asset_id: str) -> str:
    for command_ref in command_refs:
        if asset_id in asset_ids_from_command(command_ref):
            return str(command_ref.get("command") or "")
    return ""


def scene_asset_description(asset_id: str, command: str, node_id: str, excerpt: str) -> str:
    context = f" Scene context: {excerpt}" if excerpt else ""
    if asset_id.startswith("bg."):
        return f"Background scheduled by {node_id} with {command or 'scene staging'}.{context}"
    if asset_id.startswith("cg."):
        return f"CG illustration scheduled by {node_id} with {command or 'scene staging'}.{context}"
    if asset_id.startswith("portrait."):
        emotion = portrait_emotion(asset_id)
        return f"Transparent VN character portrait for {character_id_for_portrait(asset_id)} expression {emotion}, scheduled by {node_id}.{context}"
    if asset_id.startswith("bgm."):
        return f"Instrumental, loop-friendly BGM scheduled by {node_id} with {command or 'scene staging'}; keep it readable under dialogue.{context}"
    if asset_id.startswith("sfx."):
        return f"Short one-shot SFX scheduled by {node_id} with {command or 'scene staging'}.{context}"
    return f"Runtime asset scheduled by {node_id}.{context}"


def merge_source_trace(existing: Json, incoming: Json) -> Json:
    trace = existing.get("source_trace") if isinstance(existing.get("source_trace"), dict) else {}
    incoming_trace = incoming.get("source_trace") if isinstance(incoming.get("source_trace"), dict) else {}
    merged = dict(trace)
    for key, value in incoming_trace.items():
        current = [item for item in as_list(merged.get(key)) if isinstance(item, str)]
        for item in as_list(value):
            if isinstance(item, str) and item not in current:
                current.append(item)
        if current:
            merged[key] = current
    return merged


def merge_direction(existing: Json, incoming: Json) -> Json:
    for key, value in incoming.items():
        if key == "kind":
            if (
                incoming.get("kind_source") == "scheduled_command"
                and isinstance(value, str)
                and value
                and existing.get("kind") != value
            ):
                existing["kind"] = value
            elif key not in existing or existing.get(key) in (None, "", []):
                existing[key] = value
            continue
        if key == "source_trace":
            existing["source_trace"] = merge_source_trace(existing, incoming)
            continue
        if key == "provider_hints":
            hints = [item for item in as_list(existing.get("provider_hints")) if isinstance(item, str)]
            for item in as_list(value):
                if isinstance(item, str) and item not in hints:
                    hints.append(item)
            if hints:
                existing["provider_hints"] = hints
            continue
        if key not in existing or existing.get(key) in (None, "", []):
            existing[key] = value
    return existing


def add_direction(required: dict[str, Json], direction: Json) -> None:
    asset_id = direction.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        return
    if asset_id in required:
        merge_direction(required[asset_id], direction)
    else:
        required[asset_id] = direction


def collect_required_assets(run_root: Path) -> list[Json]:
    plans = load_optional_json(path_for(run_root, "realization_plans")) or {"plans": []}
    gameplay_units = load_gameplay_units(run_root)
    required: dict[str, Json] = {}
    for plan in as_list(plans.get("plans")):
        if not isinstance(plan, dict):
            continue
        node_id = plan.get("source_node_id")
        for asset_id in as_list(plan.get("required_assets")):
            if isinstance(asset_id, str):
                add_direction(required, {
                    "asset_id": asset_id,
                    "kind": kind_for_asset_id(asset_id),
                    "description": f"Runtime asset required by {node_id}.",
                    "source_trace": {"node_ids": [node_id] if isinstance(node_id, str) else []},
                    "provider_hints": [],
                })
    for unit in gameplay_units.values():
        node_id = unit.get("source_node_id")
        for asset_id in as_list(unit.get("required_assets")):
            if isinstance(asset_id, str):
                add_direction(required, {
                    "asset_id": asset_id,
                    "kind": kind_for_asset_id(asset_id),
                    "description": f"Gameplay asset required by {node_id}.",
                    "source_trace": {"node_ids": [node_id] if isinstance(node_id, str) else []},
                    "provider_hints": [],
                })
    return list(required.values())


def collect_scene_asset_intents(run_root: Path) -> list[Json]:
    required: dict[str, Json] = {}
    for fragment in load_yarn_fragments(run_root):
        node_id = str(fragment.get("node_id") or "")
        yarn_text = str(fragment.get("yarn_text") or "")
        manifest = fragment.get("manifest") if isinstance(fragment.get("manifest"), dict) else {}
        excerpt = visible_scene_excerpt(yarn_text)
        command_refs = [
            ref for ref in as_list(manifest.get("command_refs"))
            if isinstance(ref, dict)
        ]
        command_refs.extend(command_refs_from_yarn_text(yarn_text))
        local_refs = [
            ref for ref in as_list(manifest.get("local_asset_refs"))
            if looks_like_asset_id(ref)
        ]
        command_asset_ids: list[str] = []
        for command_ref in command_refs:
            command_asset_ids.extend(asset_ids_from_command(command_ref))
        for asset_id in dict.fromkeys([*command_asset_ids, *local_refs]):
            command = command_for_asset(command_refs, asset_id)
            kind = kind_for_scene_command(command, asset_id)
            direction: Json = {
                "asset_id": asset_id,
                "kind": kind,
                "description": scene_asset_description(asset_id, command, node_id, excerpt),
                "source_trace": {"node_ids": [node_id] if node_id else []},
                "provider_hints": [],
            }
            if command:
                direction["kind_source"] = "scheduled_command"
            if asset_id.startswith("bgm."):
                direction["mood"] = "scene-specific instrumental cue, dialogue-readable"
            if asset_id.startswith("sfx."):
                direction["duration"] = 1.2
            add_direction(required, direction)

        for performance in as_list(manifest.get("line_performance")):
            if not isinstance(performance, dict):
                continue
            line_index = performance.get("line_index")
            try:
                line_index_int = int(line_index)
            except (TypeError, ValueError):
                continue
            text = str(performance.get("text") or performance.get("line_text") or "").strip()
            speaker = str(performance.get("speaker") or "").strip()
            if not text or not speaker or speaker.lower() in {"narrator", "旁白"}:
                continue
            voice_id = f"voice.{safe_voice_token(node_id)}.{line_index_int}"
            direction = {
                "asset_id": voice_id,
                "kind": "voice",
                "description": f"Generated voice line for {speaker} in {node_id}.",
                "text": text,
                "line_text": text,
                "speaker": speaker,
                "line_index": line_index_int,
                "source_trace": {"node_ids": [node_id] if node_id else []},
                "provider_hints": [],
            }
            for key in ("tone", "emotion", "voice_id", "action", "voice_gender"):
                if key in performance and performance[key] not in (None, ""):
                    direction[key] = performance[key]
            add_direction(required, direction)
    for scene in load_advanced_vn_scenes(run_root):
        node_id = str(scene.get("source_node_id") or "")
        text_parts: list[str] = []
        command_refs: list[Json] = []

        def collect_from_beats(beats: list[Any]) -> None:
            for beat in as_list(beats):
                if not isinstance(beat, dict):
                    continue
                if isinstance(beat.get("text"), str):
                    text_parts.append(beat["text"])
                if beat.get("type") == "command" and isinstance(beat.get("command"), str):
                    command_refs.append({
                        "command": beat["command"],
                        "args": beat.get("args") if isinstance(beat.get("args"), dict) else {},
                    })
                for choice in as_list(beat.get("choices")):
                    if isinstance(choice, dict):
                        collect_from_beats(as_list(choice.get("beats")))

        collect_from_beats(as_list(scene.get("beats")))
        for variant in as_list(scene.get("ending_variants")):
            if isinstance(variant, dict):
                collect_from_beats(as_list(variant.get("beats")))
        for interactable in as_list(scene.get("interactables")):
            if isinstance(interactable, dict) and isinstance(interactable.get("text"), str):
                text_parts.append(interactable["text"])

        excerpt = " ".join(part.strip() for part in text_parts if part.strip())[:240]
        command_asset_ids: list[str] = []
        for command_ref in command_refs:
            command_asset_ids.extend(asset_ids_from_command(command_ref))
        for asset_id in dict.fromkeys(command_asset_ids):
            command = command_for_asset(command_refs, asset_id)
            direction: Json = {
                "asset_id": asset_id,
                "kind": kind_for_scene_command(command, asset_id),
                "description": scene_asset_description(asset_id, command, node_id, excerpt),
                "source_trace": {"node_ids": [node_id] if node_id else []},
                "provider_hints": [],
                "kind_source": "scheduled_command",
            }
            if asset_id.startswith("bgm."):
                direction["mood"] = "scene-specific instrumental cue, dialogue-readable"
            if asset_id.startswith("sfx."):
                direction["duration"] = 1.2
            add_direction(required, direction)
    return list(required.values())


def plan_asset_manifest(run_root: Path) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    game_ir = load_optional_json(path_for(run_root, "game_ir")) or {}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    project_id = sanitize_file_stem(str(branch_graph.get("title") or "generated-narrative-game")).lower()
    voice_profiles = normalize_voice_profiles(asset_direction)
    directions = [asset for asset in as_list(asset_direction.get("asset_directions")) if isinstance(asset, dict) and isinstance(asset.get("asset_id"), str)]
    directions_by_id = {asset["asset_id"]: dict(asset) for asset in directions}
    scene_asset_intents = collect_scene_asset_intents(run_root)
    existing_voice_by_key: dict[tuple[str, int, str, str], str] = {}
    for asset_id, asset in directions_by_id.items():
        key = voice_line_match_key(asset)
        if key and key not in existing_voice_by_key:
            existing_voice_by_key[key] = asset_id
    deduped_scene_asset_intents: list[Json] = []
    for required_asset in scene_asset_intents:
        key = voice_line_match_key(required_asset)
        existing_asset_id = existing_voice_by_key.get(key) if key else None
        if existing_asset_id and existing_asset_id != required_asset.get("asset_id"):
            merge_direction(directions_by_id[existing_asset_id], required_asset)
            continue
        deduped_scene_asset_intents.append(required_asset)
    scene_asset_intents = deduped_scene_asset_intents
    for required_asset in [*collect_required_assets(run_root), *scene_asset_intents]:
        asset_id = required_asset.get("asset_id")
        if not isinstance(asset_id, str):
            continue
        if asset_id in directions_by_id:
            merge_direction(directions_by_id[asset_id], required_asset)
        else:
            directions_by_id[asset_id] = required_asset
    directions = list(directions_by_id.values())
    write_json(run_root / "reports" / "scene-asset-intents.json", {
        "status": "ok",
        "count": len(scene_asset_intents),
        "asset_ids": sorted(asset["asset_id"] for asset in scene_asset_intents if isinstance(asset.get("asset_id"), str)),
        "asset_directions": scene_asset_intents,
    })
    character_names = collect_character_names(game_ir)

    backgrounds = []
    cgs = []
    ui = []
    audio = []
    portrait_ids_by_character: dict[str, list[str]] = {}
    portrait_specs: dict[str, Json] = {}

    for asset in directions:
        asset_id = asset["asset_id"]
        kind = asset.get("kind")
        trace_node = source_node_for_asset(asset, branch_graph)
        spec = {
            "description": asset.get("description", ""),
            "provider_hints": as_list(asset.get("provider_hints")),
            "source_trace": normalized_source_trace(asset),
        }
        if isinstance(asset.get("provider_bindings"), dict):
            spec["provider_bindings"] = asset["provider_bindings"]
        for key in ("mood", "text", "line_text", "speaker", "line_index", "lyrics", "voice_id", "emotion", "tone", "action", "voice_gender", "duration"):
            if key in asset:
                spec[key] = asset[key]
        if kind == "background" or asset_id.startswith("bg."):
            backgrounds.append({
                "asset_id": asset_id,
                "scene_id": trace_node,
                "location_tag": asset_slug(asset_id),
                "time_of_day": asset_id.split(".")[2] if len(asset_id.split(".")) >= 3 else "default",
                "spec": spec,
                "file_ref": f"generated/backgrounds/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind == "cg" or asset_id.startswith("cg."):
            cgs.append({
                "asset_id": asset_id,
                "story_beat_id": trace_node,
                "participating_characters": [],
                "spec": spec,
                "file_ref": f"generated/cgs/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind == "portrait" or asset_id.startswith("portrait."):
            character_id = character_id_for_portrait(asset_id)
            portrait_ids_by_character.setdefault(character_id, []).append(asset_id)
            portrait_specs[asset_id] = spec
            continue
        if kind in ("ui", "enemy", "prop", "hotspot", "symbol", "effect", "icon", "map") or asset_id.startswith(("ui.", "enemy.", "prop.", "hotspot.", "symbol.", "effect.", "icon.", "map.")):
            ui.append({
                "asset_id": asset_id,
                "kind": str(kind or asset_slug(asset_id)),
                "spec": spec,
                "file_ref": f"generated/ui/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind in ("bgm", "sfx", "voice") or asset_id.startswith(("bgm.", "sfx.", "voice.")):
            audio_kind = audio_kind_for_asset(asset_id, kind)
            if audio_kind == "voice":
                raw_voice_text = str(spec.get("text") or spec.get("line_text") or "").strip()
                normalized_voice_text = spoken_voice_text(raw_voice_text, spec.get("speaker"))
                if normalized_voice_text:
                    if raw_voice_text and normalized_voice_text != raw_voice_text:
                        spec.setdefault("source_line_text", raw_voice_text)
                    spec["text"] = normalized_voice_text
                    spec["line_text"] = normalized_voice_text
                minimax_binding = provider_binding(spec, "minimax-ppio")
                provider_profile_id = minimax_binding.get("voice_profile_id") or minimax_binding.get("voice_id")
                if (
                    "voice_id" not in spec
                    and isinstance(provider_profile_id, str)
                    and provider_profile_id.startswith("voice_profile.")
                ):
                    spec["voice_id"] = provider_profile_id
                if "voice_id" not in spec:
                    inferred_profile = voice_profile_for_speaker(spec.get("speaker"), voice_profiles)
                    if inferred_profile:
                        spec["voice_id"] = inferred_profile
            audio.append({
                "asset_id": asset_id,
                "kind": audio_kind,
                "mood": spec.get("mood") or make_style_bible(asset_direction).get("lighting_mood", ""),
                "spec": spec,
                "file_ref": f"audio/{sanitize_file_stem(asset_id)}.{audio_file_extension(audio_kind)}",
            })

    characters = []
    for character_id, portrait_ids in sorted(portrait_ids_by_character.items()):
        slug = character_id.removeprefix("char.")
        portrait_ids = sorted(dict.fromkeys(portrait_ids))
        display_name = character_names.get(character_id, slug.replace("_", " "))
        voice_profile_id = voice_profile_for_speaker(display_name, voice_profiles)
        voice_profile = voice_profiles.get(voice_profile_id, {}) if voice_profile_id else {}
        portrait_assets = [
            {
                "asset_id": portrait_id,
                "emotion": portrait_emotion(portrait_id),
                "file_ref": f"generated/portraits/{sanitize_file_stem(portrait_id)}.png",
                "source_file_ref": f"generated/portraits/source/{sanitize_file_stem(portrait_id)}.png",
                "spec": portrait_specs.get(portrait_id, {}),
            }
            for portrait_id in portrait_ids
        ]
        character_entry: Json = {
            "id": character_id,
            "display_name": display_name,
            "canon_ref_asset_id": f"charref.{slug}.core",
            "canon_ref_file_ref": f"generated/charrefs/charref.{sanitize_file_stem(slug)}.core.png",
            "base_portrait_asset_id": portrait_ids[0],
            "expression_asset_ids": portrait_ids,
            "portrait_assets": portrait_assets,
            "costume_rules": "",
            "color_anchors": [],
        }
        if voice_profile_id:
            character_entry["voice_profile_id"] = voice_profile_id
        if voice_profile:
            character_entry["character_profile"] = character_profile_from_voice_profile(voice_profile)
        characters.append(character_entry)

    manifest: Json = {
        "project_id": project_id,
        "style_bible": make_style_bible(asset_direction),
        "characters": characters,
        "backgrounds": backgrounds,
        "cgs": cgs,
        "ui": ui,
        "audio": audio,
        "voice_profiles": voice_profiles,
        "version": "v1",
        "source_asset_direction": "workspace/asset-direction.json" if path_for(run_root, "asset_direction").exists() else None,
        "source_scene_asset_intents": "reports/scene-asset-intents.json",
    }
    write_json(path_for(run_root, "asset_manifest"), manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    plan_asset_manifest(run_root)
    print(str(path_for(run_root, "asset_manifest")))


if __name__ == "__main__":
    main()
