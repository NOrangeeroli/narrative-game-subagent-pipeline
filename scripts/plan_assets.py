#!/usr/bin/env python3
"""Plan runtime assets for the Web RPG pipeline."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


def sanitize_file_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "asset"


def asset_slug(asset_id: str) -> str:
    parts = asset_id.split(".")
    if len(parts) >= 2:
        return parts[1]
    return sanitize_file_stem(asset_id)


def make_style_bible(asset_direction: Json) -> Json:
    style = asset_direction.get("style_pack") if isinstance(asset_direction.get("style_pack"), dict) else {}
    return {
        "palette": as_list(style.get("palette") if isinstance(style, dict) else []),
        "rendering_mode": style.get("rendering") or style.get("summary") or "top-down RPG illustration",
        "lighting_mood": style.get("lighting", "") if isinstance(style, dict) else "",
        "summary": style.get("summary", "") if isinstance(style, dict) else "",
    }


def kind_for_asset_id(asset_id: str) -> str:
    prefix = asset_id.split(".", 1)[0]
    if asset_id.startswith("icon.item."):
        return "item_icon"
    if asset_id.startswith("icon.skill."):
        return "skill_icon"
    if asset_id.startswith("icon.equip.") or asset_id.startswith("icon.equipment."):
        return "equipment_icon"
    return {
        "bgm": "bgm",
        "sfx": "sfx",
        "voice": "voice",
        "enemy": "enemy_sprite",
        "prop": "prop",
        "hotspot": "hotspot",
        "symbol": "symbol",
        "effect": "effect",
        "icon": "icon",
        "map": "map_asset",
        "tileset": "tileset",
        "sprite": "sprite",
        "battlebg": "battle_background",
        "itemicon": "item_icon",
        "skillicon": "skill_icon",
        "equipicon": "equipment_icon",
        "ui": "ui",
    }.get(prefix, "ui")


def audio_kind_for_asset(asset_id: str, kind: Any = None) -> str:
    normalized = str(kind or "").lower()
    if normalized in ("bgm", "sfx", "voice"):
        return normalized
    if asset_id.startswith("voice."):
        return "voice"
    if asset_id.startswith("sfx."):
        return "sfx"
    return "bgm"


def audio_file_extension(kind: str) -> str:
    return "mp3" if kind == "bgm" else "wav"


def safe_voice_token(value: Any) -> str:
    raw = str(value or "").strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    if cleaned:
        return cleaned
    if raw:
        return "u" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return "line"


def dialogue_voice_asset_id(dialogue_id: str, line_index: int) -> str:
    return f"voice.{safe_voice_token(dialogue_id)}.{line_index + 1}"


def outcome_voice_asset_id(event_id: str, outcome_id: str, line_index: int) -> str:
    return f"voice.outcome.{safe_voice_token(event_id)}.{safe_voice_token(outcome_id)}.{line_index + 1}"


def scene_voice_asset_id(scene_id: str, beat_index: int) -> str:
    return f"voice.scene.{safe_voice_token(scene_id)}.{beat_index + 1}"


def speaker_voice_profile_id(speaker: Any) -> str:
    return f"voice_profile.{safe_voice_token(speaker)}"


def speaker_voice_profile(speaker: Any) -> Json:
    name = str(speaker or "Narrator").strip() or "Narrator"
    profiles: dict[str, Json] = {}
    return profiles.get(name, {"speaker": name, "gender": "unknown", "age": "adult", "persona": f"{name} 的独立角色声线", "timbre": "自然清晰、区别于其他角色", "style": "普通话，贴合台词情绪"})


def make_voice_asset(asset_id: str, speaker: str, text: str, line_index: int, source_trace: Json) -> Json:
    profile_id = speaker_voice_profile_id(speaker)
    return {
        "asset_id": asset_id,
        "kind": "voice",
        "description": f"TTS voice line for {speaker or 'Narrator'} line {line_index}.",
        "text": text,
        "line_text": text,
        "speaker": speaker,
        "line_index": line_index,
        "voice_id": profile_id,
        "voice_design": speaker_voice_profile(speaker),
        "provider_bindings": {"minimax-ppio": {"voice_profile_id": profile_id, "voice_emotion": "calm"}},
        "source_trace": source_trace,
        "provider_hints": [],
    }


def make_sfx_asset(asset_id: str, description: str, mood: str, source_trace: Json | None = None) -> Json:
    return {
        "asset_id": asset_id,
        "kind": "sfx",
        "description": description,
        "mood": mood,
        "source_trace": source_trace or {},
        "provider_hints": [],
    }


def collect_rpg_sfx_assets(run_root: Path) -> list[Json]:
    rpg_manifest = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
    event_types: set[str] = set()
    battle_event_ids: list[str] = []
    all_event_ids: list[str] = []
    for game_map in as_list(rpg_manifest.get("maps")):
        if not isinstance(game_map, dict):
            continue
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            event_type = str(event.get("type") or event.get("kind") or "npc").strip().lower()
            if event_id:
                all_event_ids.append(event_id)
            if event_type:
                event_types.add(event_type)
            if event_type in ("battle", "encounter"):
                battle_event_ids.append(event_id)

    assets = [
        make_sfx_asset("sfx.ui.interact", "soft confirm tap for a successful RPG interaction", "clean fairytale UI cue", {"event_ids": all_event_ids}),
        make_sfx_asset("sfx.ui.error", "short blocked or unavailable interaction cue", "gentle but clear negative feedback", {"event_ids": all_event_ids}),
        make_sfx_asset("sfx.dialogue.open", "small magical page turn and character dialogue open cue", "storybook conversation cue", {"event_types": ["npc", "shop", "quest", "story"]}),
    ]
    if event_types.intersection({"pickup", "item"}):
        assets.append(make_sfx_asset("sfx.pickup.item", "sparkling tiny item pickup with dewdrop shimmer", "bright miniature reward cue", {"event_types": ["pickup", "item"]}))
    if "rest" in event_types:
        assets.append(make_sfx_asset("sfx.rest.recover", "warm healing chime with soft nestling ambience", "safe recovery cue", {"event_types": ["rest"]}))
    if "transfer" in event_types:
        assets.append(make_sfx_asset("sfx.transfer.portal", "soft whoosh through flowers and leaves for map transition", "light travel cue", {"event_types": ["transfer"]}))
    if event_types.intersection({"story", "choice"}):
        assets.append(make_sfx_asset("sfx.story.choice", "gentle branching choice shimmer with fairytale sparkle", "meaningful story decision cue", {"event_types": ["story", "choice"]}))
    if event_types.intersection({"quest", "story"}):
        assets.append(make_sfx_asset("sfx.quest.update", "subtle quest update bell with optimistic finish", "progress cue", {"event_types": ["quest", "story"]}))
    if battle_event_ids:
        assets.extend([
            make_sfx_asset("sfx.battle.start", "quick battle encounter sting with tiny dramatic percussion", "storybook danger cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.attack", "short light slash or impact for player basic attack", "crisp combat cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.skill", "brief magical skill burst with petal sparkle and focused hit", "heroic miniature magic cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.guard", "soft shield brace and muted thump for guard action", "protective cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.item", "small restorative item sparkle and warm chime", "healing cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.enemy_hit", "small enemy counter impact with rounded low thud", "safe readable damage cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.victory", "short victory flourish with bright bells and fairytale lift", "rewarding win cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.flee", "quick retreat rustle and footstep whoosh", "escape cue", {"event_ids": battle_event_ids}),
            make_sfx_asset("sfx.battle.defeat", "brief low recovery cue after defeat without harshness", "soft setback cue", {"event_ids": battle_event_ids}),
        ])
    return assets


def collect_dialogue_voice_assets(run_root: Path) -> list[Json]:
    rpg_manifest = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
    assets: list[Json] = []
    for dialogue in as_list(rpg_manifest.get("npc_dialogue")):
        if not isinstance(dialogue, dict) or not isinstance(dialogue.get("id"), str):
            continue
        for index, line in enumerate(as_list(dialogue.get("lines") or dialogue.get("beats"))):
            if isinstance(line, str):
                speaker = ""
                text = line
            elif isinstance(line, dict):
                speaker = str(line.get("speaker") or "")
                text = str(line.get("text") or line.get("line") or "")
            else:
                continue
            text = text.strip()
            if not text:
                continue
            asset_id = dialogue_voice_asset_id(dialogue["id"], index)
            assets.append(make_voice_asset(asset_id, speaker, text, index + 1, {"dialogue_id": dialogue["id"], "line_index": index + 1}))
    for game_map in as_list(rpg_manifest.get("maps")):
        if not isinstance(game_map, dict):
            continue
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "event")
            outcomes = as_list(event.get("outcomes")) + as_list(event.get("win_outcomes"))
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                outcome_id = str(outcome.get("id") or "outcome")
                for index, line in enumerate(as_list(outcome.get("lines"))):
                    if isinstance(line, str):
                        speaker = str(event.get("name") or "")
                        text = line
                    elif isinstance(line, dict):
                        speaker = str(line.get("speaker") or event.get("name") or "")
                        text = str(line.get("text") or line.get("line") or "")
                    else:
                        continue
                    text = text.strip()
                    if not text:
                        continue
                    asset_id = outcome_voice_asset_id(event_id, outcome_id, index)
                    assets.append(make_voice_asset(asset_id, speaker, text, index + 1, {
                        "map_id": game_map.get("id"),
                        "event_id": event_id,
                        "outcome_id": outcome_id,
                        "line_index": index + 1,
                    }))
    for scene in as_list(rpg_manifest.get("scene_scripts")):
        if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
            continue
        for index, beat in enumerate(as_list(scene.get("beats"))):
            if not isinstance(beat, dict):
                continue
            beat_kind = beat.get("kind") or beat.get("type")
            if beat_kind not in ("dialogue", "line"):
                continue
            text = str(beat.get("text") or beat.get("line") or "").strip()
            if not text:
                continue
            speaker = str(beat.get("speaker") or beat.get("speaker_actor_id") or beat.get("actor_id") or "")
            asset_id = scene_voice_asset_id(scene["id"], index)
            assets.append(make_voice_asset(asset_id, speaker, text, index + 1, {
                "scene_id": scene["id"],
                "beat_index": index + 1,
            }))
    return assets


def collect_required_assets(run_root: Path) -> list[Json]:
    required: dict[str, Json] = {}
    rpg_manifest = load_optional_json(path_for(run_root, "rpg_manifest")) or {}
    for asset_id in as_list(rpg_manifest.get("asset_refs")):
        if isinstance(asset_id, str):
            required.setdefault(asset_id, {
                "asset_id": asset_id,
                "kind": kind_for_asset_id(asset_id),
                "description": "Runtime RPG asset required by rpg-manifest.json.",
                "source_trace": {"node_ids": []},
                "provider_hints": [],
            })
    return list(required.values())


RPG_SECTION_BY_KIND = {
    "tileset": "tilesets",
    "sprite": "sprites",
    "sprite_animation": "sprites",
    "enemy_sprite": "enemy_sprites",
    "item_icon": "item_icons",
    "skill_icon": "skill_icons",
    "equipment_icon": "equipment_icons",
    "battle_background": "battle_backgrounds",
    "map_asset": "map_assets",
    "rpg_ui": "rpg_ui",
}


def plan_asset_manifest(run_root: Path) -> Json:
    branch_graph = load_optional_json(path_for(run_root, "branch_graph")) or {}
    asset_direction = load_optional_json(path_for(run_root, "asset_direction")) or {"asset_directions": []}
    project_id = sanitize_file_stem(str(branch_graph.get("title") or "generated-narrative-game")).lower()
    directions = [asset for asset in as_list(asset_direction.get("asset_directions")) if isinstance(asset, dict) and isinstance(asset.get("asset_id"), str)]
    seen_direction_ids = {asset["asset_id"] for asset in directions}
    for required_asset in collect_required_assets(run_root):
        if required_asset["asset_id"] not in seen_direction_ids:
            directions.append(required_asset)
            seen_direction_ids.add(required_asset["asset_id"])
    for sfx_asset in collect_rpg_sfx_assets(run_root):
        if sfx_asset["asset_id"] not in seen_direction_ids:
            directions.append(sfx_asset)
            seen_direction_ids.add(sfx_asset["asset_id"])
    for voice_asset in collect_dialogue_voice_assets(run_root):
        if voice_asset["asset_id"] not in seen_direction_ids:
            directions.append(voice_asset)
            seen_direction_ids.add(voice_asset["asset_id"])
    ui = []
    audio = []
    rpg_sections: dict[str, list[Json]] = {section: [] for section in RPG_SECTION_BY_KIND.values()}

    for asset in directions:
        asset_id = asset["asset_id"]
        kind = asset.get("kind") or kind_for_asset_id(asset_id)
        spec = {
            "description": asset.get("description", ""),
            "provider_hints": as_list(asset.get("provider_hints")),
            "source_trace": asset.get("source_trace", {}),
        }
        for key in ("mood", "text", "line_text", "speaker", "line_index", "lyrics", "voice_id", "voice_design", "provider_bindings", "emotion", "tone", "action", "voice_gender", "duration"):
            if key in asset:
                spec[key] = asset[key]
        section = RPG_SECTION_BY_KIND.get(str(kind))
        if section:
            rpg_sections[section].append({
                "asset_id": asset_id,
                "kind": str(kind),
                "spec": spec,
                "file_ref": f"generated/rpg/{section}/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind in ("ui", "enemy", "prop", "hotspot", "symbol", "effect", "icon", "map") or asset_id.startswith(("ui.", "prop.", "hotspot.", "symbol.", "effect.", "icon.")):
            ui.append({
                "asset_id": asset_id,
                "kind": str(kind or asset_slug(asset_id)),
                "spec": spec,
                "file_ref": f"generated/ui/{sanitize_file_stem(asset_id)}.png",
            })
            continue
        if kind in ("bgm", "sfx", "voice") or asset_id.startswith(("bgm.", "sfx.", "voice.")):
            audio_kind = audio_kind_for_asset(asset_id, kind)
            audio.append({
                "asset_id": asset_id,
                "kind": audio_kind,
                "mood": spec.get("mood") or make_style_bible(asset_direction).get("lighting_mood", ""),
                "spec": spec,
                "file_ref": f"audio/{sanitize_file_stem(asset_id)}.{audio_file_extension(audio_kind)}",
            })
            continue

    voice_profiles = {}
    for audio_asset in audio:
        spec = audio_asset.get("spec") if isinstance(audio_asset.get("spec"), dict) else {}
        profile_id = spec.get("voice_id")
        profile = spec.get("voice_design")
        if isinstance(profile_id, str) and profile_id.startswith("voice_profile.") and isinstance(profile, dict):
            voice_profiles[profile_id] = profile

    manifest: Json = {
        "project_id": project_id,
        "style_bible": make_style_bible(asset_direction),
        "ui": ui,
        **rpg_sections,
        "audio": audio,
        "voice_profiles": voice_profiles,
        "version": "v1",
        "source_asset_direction": "workspace/asset-direction.json",
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
