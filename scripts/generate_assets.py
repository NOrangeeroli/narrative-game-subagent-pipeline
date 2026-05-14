#!/usr/bin/env python3
"""Generate runtime assets from asset-manifest.json for Web RPG builds."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from asset_audio_providers import generate_audio_file, resolve_audio_provider_model
from asset_image_providers import GeneratedImage, generate_provider_images, resolve_provider_model
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, write_json, write_text


MOCK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sXl16sAAAAASUVORK5CYII="
)
REMOTE_IMAGE_PROVIDERS = {"gemini", "openai-ppioImage"}
RPG_ASSET_SECTIONS = {
    "tilesets": "tileset",
    "sprites": "sprite",
    "enemy_sprites": "enemy_sprite",
    "item_icons": "item_icon",
    "skill_icons": "skill_icon",
    "equipment_icons": "equipment_icon",
    "battle_backgrounds": "battle_background",
    "map_assets": "map_asset",
    "rpg_ui": "rpg_ui",
}


def sanitize_file_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value.strip()).strip("-")
    return cleaned or "asset"


def asset_runtime_name(asset_id: str) -> str:
    return sanitize_file_stem(asset_id.replace(".", "_"))


def hex_color(seed: str, salt: int, lightness: int = 55, saturation: int = 42) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).digest()
    hue = digest[0] / 255
    chroma = saturation / 100
    x = chroma * (1 - abs((hue * 6) % 2 - 1))
    if hue < 1 / 6:
        r, g, b = chroma, x, 0
    elif hue < 2 / 6:
        r, g, b = x, chroma, 0
    elif hue < 3 / 6:
        r, g, b = 0, chroma, x
    elif hue < 4 / 6:
        r, g, b = 0, x, chroma
    elif hue < 5 / 6:
        r, g, b = x, 0, chroma
    else:
        r, g, b = chroma, 0, x
    m = lightness / 100 - chroma / 2
    return f"#{int((r + m) * 255):02x}{int((g + m) * 255):02x}{int((b + m) * 255):02x}"


def maybe_copy_provider_hint(run_root: Path, asset: Json, output_path: Path) -> bool:
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    for hint in as_list(spec.get("provider_hints")):
        if not isinstance(hint, str):
            continue
        candidate = (run_root / hint).resolve() if not Path(hint).is_absolute() else Path(hint)
        if candidate.exists() and candidate.is_file():
            ensure_dir(output_path.parent)
            shutil.copy2(candidate, output_path)
            return True
    return False


def render_ui_svg(asset: Json) -> str:
    asset_id = str(asset.get("asset_id") or "ui.panel")
    accent = hex_color(asset_id, 5, 58, 32)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="160" viewBox="0 0 512 160">
  <rect x="0" y="0" width="512" height="160" rx="16" fill="#101418" opacity="0.86" />
  <rect x="18" y="18" width="476" height="124" rx="10" fill="{accent}" opacity="0.18" stroke="#ffffff" stroke-opacity="0.24" />
</svg>
'''


def render_rpg_svg(asset: Json, role: str) -> str:
    asset_id = str(asset.get("asset_id") or role)
    primary = hex_color(asset_id, 21, 58, 42)
    secondary = hex_color(asset_id, 22, 42, 28)
    accent = hex_color(asset_id, 23, 68, 46)
    label = escape(asset_id.split(".")[-1][:12])
    if role in ("battle_background", "map_asset"):
        path_color = "#d8bd77" if role == "map_asset" else "#f7f2d7"
        water = "#5f9ca9" if role == "map_asset" else accent
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{secondary}" />
  <rect y="420" width="1280" height="300" fill="{primary}" opacity="0.72" />
  <path d="M120 560 C300 460 420 440 585 355 C760 260 875 250 1160 190" fill="none" stroke="{path_color}" stroke-width="106" stroke-linecap="round" opacity="0.58" />
  <path d="M0 260 C220 190 320 300 520 230 C760 150 900 260 1280 170 L1280 0 L0 0 Z" fill="{accent}" opacity="0.48" />
  <ellipse cx="340" cy="165" rx="190" ry="64" fill="{water}" opacity="0.36" />
  <ellipse cx="860" cy="500" rx="220" ry="76" fill="#1f2b24" opacity="0.32" />
</svg>
'''
    if role == "tileset":
        tiles = []
        colors = [primary, secondary, accent, "#6b7f64", "#314038", "#9a855d"]
        for y in range(4):
            for x in range(4):
                color = colors[(x + y * 2) % len(colors)]
                tiles.append(f'<rect x="{x * 128}" y="{y * 128}" width="126" height="126" fill="{color}" />')
        return '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">\n  ' + "\n  ".join(tiles) + "\n</svg>\n"
    if role in ("sprite", "enemy_sprite"):
        face = "#e8c4a7" if role == "sprite" else "#d6a0a0"
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="226" rx="58" ry="12" fill="#000" opacity="0.24" />
  <rect x="82" y="96" width="92" height="104" rx="24" fill="{primary}" />
  <circle cx="128" cy="78" r="48" fill="{face}" />
  <path d="M84 76 C94 26 162 22 174 78 C150 58 108 58 84 76 Z" fill="{secondary}" />
  <circle cx="112" cy="78" r="5" fill="#222" />
  <circle cx="144" cy="78" r="5" fill="#222" />
  <path d="M108 108 C124 119 138 119 152 108" fill="none" stroke="#773e3e" stroke-width="5" stroke-linecap="round" />
</svg>
'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="18" y="18" width="220" height="220" rx="32" fill="#1c211c" />
  <rect x="38" y="38" width="180" height="180" rx="24" fill="{primary}" opacity="0.86" />
  <circle cx="128" cy="112" r="48" fill="{accent}" opacity="0.78" />
  <text x="128" y="188" text-anchor="middle" font-size="22" fill="#f8f1dc">{label}</text>
</svg>
'''


def write_png_from_svg(svg: str, output_path: Path, source_svg_path: Path) -> list[str]:
    ensure_dir(output_path.parent)
    ensure_dir(source_svg_path.parent)
    write_text(source_svg_path, svg)
    try:
        subprocess.run(["magick", "-background", "none", str(source_svg_path), f"PNG32:{output_path}"], check=True, capture_output=True, text=True)
        return [f"rasterized from {source_svg_path.name}"]
    except Exception as exc:  # noqa: BLE001
        fallback = output_path.with_suffix(".svg")
        shutil.copy2(source_svg_path, fallback)
        return [f"ImageMagick rasterization failed; kept SVG fallback: {exc}"]


def write_mock_png(output_path: Path) -> list[str]:
    ensure_dir(output_path.parent)
    output_path.write_bytes(MOCK_PNG_BYTES)
    return ["mock 1x1 png"]


def extension_for_mime(mime_type: str) -> str:
    normalized = mime_type.split(";", 1)[0].strip().lower()
    if normalized in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if normalized == "image/webp":
        return ".webp"
    return ".png"


def audio_format_for_file_ref(file_ref: str) -> str:
    suffix = Path(file_ref).suffix.lower().lstrip(".")
    if suffix in ("mp3", "wav", "ogg", "m4a", "aac", "flac", "pcm"):
        return suffix
    return os.environ.get("AUDIO_FORMAT") or "wav"


def audio_provider_for_kind(default_provider: str, kind: str, overrides: dict[str, str | None]) -> str:
    normalized = kind.strip().lower()
    env_name = {
        "bgm": "AUDIO_BGM_PROVIDER",
        "sfx": "AUDIO_SFX_PROVIDER",
        "voice": "AUDIO_VOICE_PROVIDER",
    }.get(normalized)
    return overrides.get(normalized) or (os.environ.get(env_name) if env_name else None) or default_provider


def strip_dialogue_quotes(value: str) -> str:
    text = value.strip()
    for left, right in (("“", "”"), ('"', '"'), ("'", "'")):
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
        if rest.startswith(("“", '"')) or (speaker_compact and (label in speaker_compact or speaker_compact in label)):
            return strip_dialogue_quotes(rest)
    return strip_dialogue_quotes(text)


def write_image_as_png(output_path: Path, image: GeneratedImage, raw_path: Path | None = None) -> list[str]:
    ensure_dir(output_path.parent)
    notes: list[str] = []
    raw_target = raw_path or output_path
    ensure_dir(raw_target.parent)
    if image.mime_type.split(";", 1)[0].strip().lower() == "image/png":
        raw_target.write_bytes(image.bytes)
        if raw_target != output_path:
            shutil.copy2(raw_target, output_path)
        notes.append("wrote provider PNG")
        return notes

    source_path = raw_target.with_suffix(extension_for_mime(image.mime_type))
    source_path.write_bytes(image.bytes)
    try:
        subprocess.run(["magick", str(source_path), f"PNG32:{output_path}"], check=True, capture_output=True, text=True)
        notes.append(f"converted provider {image.mime_type} to PNG")
    except Exception as exc:  # noqa: BLE001
        shutil.copy2(source_path, output_path)
        notes.append(f"ImageMagick conversion failed; copied provider image bytes: {exc}")
    return notes


def build_rpg_asset_prompt(asset: Json, role: str, manifest: Json) -> str:
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    description = str(spec.get("description") or f"Create RPG {role} asset {asset.get('asset_id', '')}.")
    if role == "map_asset":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
            "Create a detailed 16:9 top-down 2D RPG map background for a playable scene.",
            "Fill the entire 16:9 canvas edge to edge; do not add black bars, letterboxing, side padding, UI frames, or empty margins.",
            "Show terrain, walkable paths, blockers, landmarks, entrances, exits, and collision-relevant terrain boundaries clearly from an overhead game-camera angle.",
            "Do not draw debug overlays, colored collision masks, outlines, grid labels, arrows, callouts, readable text, UI, or featured characters as the focus.",
            "The formal collision boundary export is authored separately as pixel-coordinate JSON and preview overlays, not baked into this background image.",
        ])
    if role == "battle_background":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
            "Create a wide 16:9 RPG battle background with strong location identity and clear foreground/midground/depth.",
            "No UI, no labels, no readable text, no featured character art.",
        ])
    if role in ("sprite", "enemy_sprite"):
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
            "Create a single readable RPG sprite on a plain transparent or simple background.",
            "Clean silhouette, centered full body, no readable text.",
        ])
    return " ".join([
        description,
        f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
        "Readable at small scale, clean silhouette, no readable text unless the asset is a UI label.",
    ])


def build_audio_prompt(audio: Json, manifest: Json) -> str:
    spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    kind = str(audio.get("kind") or "").lower()
    description = str(spec.get("description") or audio.get("description") or audio.get("asset_id") or "audio cue")
    mood = str(spec.get("mood") or audio.get("mood") or style.get("lighting_mood") or "")
    if kind == "voice":
        text = spoken_voice_text(
            spec.get("text") or spec.get("line_text") or audio.get("text") or "",
            spec.get("speaker") or audio.get("speaker"),
        )
        if not text:
            raise RuntimeError(f"Voice asset {audio.get('asset_id', '<unknown>')} requires exact dialogue text.")
        return text
    if kind == "sfx":
        return " ".join([
            f"Short RPG sound effect: {description}.",
            f"Mood: {mood}." if mood else "",
            "Keep it concise, non-musical, and suitable for a single interaction cue.",
        ]).strip()
    return " ".join([
        f"Instrumental RPG background music cue: {description}.",
        f"Mood: {mood}." if mood else "",
        "Loop-friendly arrangement, no vocals, no lyrics, supports dialogue readability.",
    ]).strip()


def remote_rpg_asset_shape(role: str) -> tuple[str, str]:
    if role == "battle_background":
        return "background", "16:9"
    if role == "map_asset":
        return "background", "16:9"
    return "asset", "1:1"


def generate_assets(
    run_root: Path,
    provider: str | None = "local-svg",
    model: str | None = None,
    overwrite: bool = False,
    audio_provider: str | None = None,
    audio_model: str | None = None,
    audio_fallback_provider: str | None = None,
    bgm_provider: str | None = None,
    sfx_provider: str | None = None,
    voice_provider: str | None = None,
) -> Json:
    provider = provider or os.environ.get("IMAGE_ASSET_PROVIDER") or "local-svg"
    audio_provider_id = audio_provider or os.environ.get("AUDIO_ASSET_PROVIDER") or os.environ.get("AUDIO_PROVIDER") or "mock"
    audio_fallback_provider = audio_fallback_provider or os.environ.get("AUDIO_FALLBACK_PROVIDER")
    audio_provider_overrides = {"bgm": bgm_provider, "sfx": sfx_provider, "voice": voice_provider}
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not asset_manifest:
        raise SystemExit("Missing workspace/asset-manifest.json. Run plan_assets.py first.")
    output_root = run_root / "workspace" / "generated-assets"
    ensure_dir(output_root)
    prompt_root = output_root / "prompts"
    entries = []
    warnings = []
    model_id = resolve_provider_model(provider, model)

    for ui_asset in as_list(asset_manifest.get("ui")):
        if not isinstance(ui_asset, dict):
            continue
        output_path = output_root / str(ui_asset["file_ref"])
        if output_path.exists() and not overwrite:
            warnings.append(f"Skipped existing UI asset {ui_asset['asset_id']} at {ui_asset['file_ref']}.")
            continue
        prompt = f"Generate UI asset {ui_asset['asset_id']} for a Web RPG interface."
        prompt_path = prompt_root / f"{sanitize_file_stem(ui_asset['asset_id'])}.txt"
        write_text(prompt_path, prompt + "\n")
        notes = write_png_from_svg(render_ui_svg(ui_asset), output_path, output_root / "generated" / "sources" / f"{sanitize_file_stem(ui_asset['asset_id'])}.svg")
        entries.append({
            "asset_id": ui_asset["asset_id"],
            "role": "ui",
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider,
            "model": model_id,
            "output_files": [str(output_path)],
            "notes": notes,
        })

    for section, role in RPG_ASSET_SECTIONS.items():
        for rpg_asset in as_list(asset_manifest.get(section)):
            if not isinstance(rpg_asset, dict):
                continue
            output_path = output_root / str(rpg_asset["file_ref"])
            if output_path.exists() and not overwrite:
                warnings.append(f"Skipped RPG asset {rpg_asset['asset_id']} at {rpg_asset['file_ref']}.")
                continue
            prompt = build_rpg_asset_prompt(rpg_asset, role, asset_manifest)
            prompt_path = prompt_root / f"{sanitize_file_stem(rpg_asset['asset_id'])}.txt"
            write_text(prompt_path, prompt + "\n")
            notes = []
            if maybe_copy_provider_hint(run_root, rpg_asset, output_path):
                notes.append("copied provider_hints source")
            elif provider == "mock":
                notes.extend(write_mock_png(output_path))
            elif provider in REMOTE_IMAGE_PROVIDERS:
                image_type, aspect_ratio = remote_rpg_asset_shape(role)
                images = generate_provider_images(
                    provider=provider,
                    model=model,
                    asset_id=str(rpg_asset["asset_id"]),
                    output_root=output_root,
                    prompt=prompt,
                    image_type=image_type,
                    aspect_ratio=aspect_ratio,
                    expected_count=1,
                )
                if not images:
                    raise RuntimeError(f"Provider returned no RPG asset image for {rpg_asset['asset_id']}.")
                notes.extend(write_image_as_png(output_path, images[0]))
            else:
                source_svg = output_root / "generated" / "sources" / f"{sanitize_file_stem(rpg_asset['asset_id'])}.svg"
                notes.extend(write_png_from_svg(render_rpg_svg(rpg_asset, role), output_path, source_svg))
            entries.append({
                "asset_id": rpg_asset["asset_id"],
                "role": role,
                "prompt": prompt,
                "prompt_ref": str(prompt_path.relative_to(output_root)),
                "provider": provider,
                "model": model_id,
                "output_files": [str(output_path)],
                "notes": notes,
            })

    for audio in as_list(asset_manifest.get("audio")):
        if not isinstance(audio, dict):
            continue
        asset_id = str(audio.get("asset_id") or "audio")
        file_ref = audio.get("file_ref")
        if not isinstance(file_ref, str) or not file_ref.strip():
            warnings.append(f"Skipped audio asset without file_ref: {asset_id}.")
            continue
        output_path = output_root / file_ref
        if output_path.exists() and not overwrite:
            warnings.append(f"Skipped existing audio asset {asset_id} at {file_ref}.")
            continue
        audio_kind = str(audio.get("kind") or asset_id.split(".", 1)[0] or "bgm")
        prompt = build_audio_prompt(audio, asset_manifest)
        prompt_path = prompt_root / f"{sanitize_file_stem(asset_id)}.txt"
        write_text(prompt_path, prompt + "\n")
        notes: list[str] = []
        if maybe_copy_provider_hint(run_root, audio, output_path):
            provider_used = "provider_hint"
            notes.append("copied provider_hints source")
        elif audio_provider_id in ("none", "skip"):
            warnings.append(f"Audio asset planned but skipped by audio provider setting: {asset_id}.")
            continue
        else:
            provider_for_asset = audio_provider_for_kind(audio_provider_id, audio_kind, audio_provider_overrides)
            generation = generate_audio_file(
                provider=provider_for_asset,
                asset=audio,
                prompt=prompt,
                output_path=output_path,
                audio_kind=audio_kind,
                model=audio_model,
                expected_format=audio_format_for_file_ref(file_ref),
                output_root=output_root,
                fallback_provider=audio_fallback_provider,
            )
            provider_used = str(generation["provider"])
            notes.append(f"wrote audio ({generation['mime_type']}, {generation['bytes']} bytes)")
            if generation.get("source_url_present"):
                notes.append("downloaded provider audio URL")
            if generation.get("fallback_from"):
                warnings.append(
                    f"Audio provider {generation['fallback_from']} failed for {asset_id}; "
                    f"fell back to {provider_used}: {generation.get('primary_error')}"
                )
        entries.append({
            "asset_id": asset_id,
            "role": audio_kind,
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider_used,
            "model": resolve_audio_provider_model(provider_used, audio_model, audio_kind),
            "output_files": [str(output_path)],
            "notes": notes,
        })

    report = {
        "project_id": asset_manifest.get("project_id", "generated"),
        "provider": provider,
        "model": model_id,
        "audio_provider": audio_provider_id,
        "audio_model": audio_model,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "output_root": str(output_root),
        "entries": entries,
        "warnings": warnings,
    }
    write_json(path_for(run_root, "asset_generation_report"), report)
    write_json(output_root / "manifest.snapshot.json", asset_manifest)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--audio-provider", default=None)
    parser.add_argument("--audio-model", default=None)
    parser.add_argument("--audio-fallback-provider", default=None)
    parser.add_argument("--bgm-provider", default=None)
    parser.add_argument("--sfx-provider", default=None)
    parser.add_argument("--voice-provider", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    provider = args.provider or __import__("os").environ.get("IMAGE_ASSET_PROVIDER") or "local-svg"
    report = generate_assets(
        Path(args.run_root).resolve(),
        provider=provider,
        model=args.model,
        overwrite=args.overwrite,
        audio_provider=args.audio_provider,
        audio_model=args.audio_model,
        audio_fallback_provider=args.audio_fallback_provider,
        bgm_provider=args.bgm_provider,
        sfx_provider=args.sfx_provider,
        voice_provider=args.voice_provider,
    )
    print(json.dumps({"report": str(path_for(Path(args.run_root).resolve(), "asset_generation_report")), "entries": len(report["entries"])}, indent=2))


if __name__ == "__main__":
    main()
