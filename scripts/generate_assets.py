#!/usr/bin/env python3
"""Generate runtime assets from asset-manifest.json.

This mirrors unity-vn-studio's separation:
- asset-direction.json describes visual intent.
- asset-manifest.json is the deterministic runtime lookup table.
- this generator writes files, prompt snapshots, and a generation report.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
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
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, read_json, write_json, write_text


MOCK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sXl16sAAAAASUVORK5CYII="
)
REMOTE_IMAGE_PROVIDERS = {"gemini", "openai-ppioImage"}


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


def render_background_svg(asset: Json, style_bible: Json) -> str:
    asset_id = str(asset.get("asset_id") or "bg.default")
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    text = " ".join(str(spec.get(key, "")) for key in ("description", "location", "mood")).lower()
    palette = [color for color in as_list(style_bible.get("palette")) if isinstance(color, str) and color.startswith("#")]
    sky = palette[0] if palette else hex_color(asset_id, 1, 68, 24)
    ground = palette[1] if len(palette) > 1 else hex_color(asset_id, 2, 48, 28)
    accent = palette[2] if len(palette) > 2 else hex_color(asset_id, 3, 58, 46)
    warm = palette[3] if len(palette) > 3 else "#e0a94f"
    dark = "#263033"
    layers = [
        f'<rect x="0" y="0" width="1280" height="720" fill="{sky}" />',
        f'<rect x="0" y="330" width="1280" height="390" fill="{ground}" />',
        '<ellipse cx="650" cy="330" rx="420" ry="26" fill="#f5f7f0" opacity="0.24" />',
    ]
    if any(token in text for token in ("湖", "lake", "霜", "frost", "mist")):
        layers.extend([
            '<rect x="0" y="306" width="1280" height="170" fill="#6f94a3" opacity="0.78" />',
            '<ellipse cx="725" cy="356" rx="330" ry="18" fill="#eef8f4" opacity="0.35" />',
            '<polygon points="0,474 280,408 592,432 500,720 0,720" fill="#dfe5dc" opacity="0.8" />',
            '<polygon points="1280,474 1010,400 690,432 782,720 1280,720" fill="#dfe5dc" opacity="0.8" />',
        ])
    if any(token in text for token in ("市集", "market", "摊", "shop")):
        for index, x in enumerate((90, 470, 850)):
            roof = [accent, warm, "#3f7f8c"][index % 3]
            layers.extend([
                f'<rect x="{x}" y="220" width="300" height="250" rx="14" fill="#eadfc9" />',
                f'<polygon points="{x-22},220 {x+322},220 {x+280},152 {x+28},152" fill="{roof}" />',
                f'<rect x="{x+42}" y="270" width="210" height="84" fill="#697b71" opacity="0.82" />',
                f'<ellipse cx="{x+92}" cy="388" rx="34" ry="17" fill="{warm}" />',
                f'<ellipse cx="{x+170}" cy="388" rx="34" ry="17" fill="{accent}" />',
            ])
    if any(token in text for token in ("营地", "camp", "帐", "tent", "热锅", "night", "夜")):
        night = any(token in text for token in ("night", "夜", "星"))
        if night:
            layers[0] = '<rect x="0" y="0" width="1280" height="720" fill="#151c28" />'
            layers[1] = '<rect x="0" y="336" width="1280" height="384" fill="#263126" />'
            for x, y in ((208, 116), (364, 88), (640, 128), (908, 78), (1138, 142)):
                layers.append(f'<ellipse cx="{x}" cy="{y}" rx="3" ry="3" fill="#f9f1c7" />')
        layers.extend([
            f'<polygon points="140,590 320,382 510,590" fill="{accent}" />',
            '<polygon points="320,382 510,590 602,590 402,382" fill="#7f4b42" opacity="0.95" />',
            '<polygon points="268,590 326,458 390,590" fill="#15191f" />',
            '<line x1="690" y1="318" x2="996" y2="250" stroke="#43505a" stroke-width="8" stroke-linecap="round" />',
            '<line x1="996" y1="250" x2="1142" y2="486" stroke="#43505a" stroke-width="8" stroke-linecap="round" />',
            '<polygon points="718,322 996,266 1132,486 870,510" fill="#e3c57f" opacity="0.88" />',
            '<rect x="662" y="548" width="390" height="62" rx="14" fill="#6b5a4a" />',
        ])
        if any(token in text for token in ("热锅", "meal", "汤", "pot")):
            layers.extend([
                '<ellipse cx="856" cy="524" rx="118" ry="34" fill="#272d31" />',
                '<ellipse cx="856" cy="516" rx="92" ry="24" fill="#c9a96f" />',
                '<ellipse cx="612" cy="604" rx="60" ry="24" fill="#e0844f" opacity="0.82" />',
                '<polygon points="584,590 612,526 640,590" fill="#f5ca70" opacity="0.9" />',
            ])
    layers.append('<rect x="0" y="0" width="1280" height="720" fill="#000000" opacity="0.04" />')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">\n  ' + "\n  ".join(layers) + "\n</svg>\n"


def render_cg_svg(asset: Json, style_bible: Json) -> str:
    asset_id = str(asset.get("asset_id") or "cg.default")
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    palette = [color for color in as_list(style_bible.get("palette")) if isinstance(color, str) and color.startswith("#")]
    sky = palette[0] if palette else hex_color(asset_id, 21, 64, 26)
    ground = palette[1] if len(palette) > 1 else hex_color(asset_id, 22, 46, 30)
    accent = palette[2] if len(palette) > 2 else hex_color(asset_id, 23, 58, 52)
    warm = palette[3] if len(palette) > 3 else "#f1c36a"
    description = str(spec.get("description") or asset_id)
    label = escape(description[:70])
    layers = [
        f'<rect x="0" y="0" width="1280" height="720" fill="{sky}" />',
        f'<rect x="0" y="382" width="1280" height="338" fill="{ground}" />',
        '<ellipse cx="640" cy="388" rx="460" ry="42" fill="#ffffff" opacity="0.16" />',
        f'<polygon points="78,612 322,242 544,612" fill="{accent}" opacity="0.9" />',
        f'<polygon points="424,620 726,170 1036,620" fill="{warm}" opacity="0.78" />',
        '<ellipse cx="420" cy="618" rx="120" ry="30" fill="#111418" opacity="0.24" />',
        '<ellipse cx="816" cy="618" rx="156" ry="34" fill="#111418" opacity="0.22" />',
        '<circle cx="418" cy="360" r="62" fill="#efd0b7" />',
        '<rect x="348" y="418" width="142" height="184" rx="48" fill="#3d5967" />',
        '<circle cx="816" cy="326" r="74" fill="#efd0b7" />',
        '<rect x="724" y="396" width="188" height="214" rx="58" fill="#754957" />',
        '<path d="M188 216 C314 116 514 132 640 236 C764 340 980 288 1110 166" fill="none" stroke="#ffffff" stroke-width="12" stroke-opacity="0.36" stroke-linecap="round" />',
        '<rect x="56" y="52" width="1168" height="616" rx="22" fill="none" stroke="#ffffff" stroke-opacity="0.34" stroke-width="8" />',
        f'<text x="640" y="676" font-size="24" text-anchor="middle" fill="#f8f5ec" opacity="0.62">{label}</text>',
    ]
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">\n  ' + "\n  ".join(layers) + "\n</svg>\n"


def render_portrait_svg(character: Json, portrait: Json, style_bible: Json) -> str:
    asset_id = str(portrait.get("asset_id") or "portrait.character")
    display_name = str(character.get("display_name") or asset_id)
    coat = hex_color(asset_id, 11, 48, 34)
    scarf = hex_color(asset_id, 12, 60, 35)
    hair = hex_color(asset_id, 13, 24, 18)
    hat = hex_color(asset_id, 14, 60, 58)
    skin = "#e8c4a7"
    layers = [
        '<ellipse cx="256" cy="728" rx="154" ry="26" fill="#000000" opacity="0.18" />',
        f'<polygon points="142,448 82,718 430,718 370,448" fill="{coat}" />',
        f'<rect x="142" y="410" width="228" height="86" rx="35" fill="{scarf}" />',
        f'<ellipse cx="256" cy="286" rx="112" ry="136" fill="{hair}" />',
        f'<ellipse cx="256" cy="292" rx="94" ry="112" fill="{skin}" />',
        f'<polygon points="158,246 210,148 306,148 370,248 306,214 250,230 202,208" fill="{hair}" />',
        '<ellipse cx="216" cy="294" rx="8" ry="10" fill="#25282c" />',
        '<ellipse cx="296" cy="294" rx="8" ry="10" fill="#25282c" />',
        '<line x1="224" y1="344" x2="290" y2="342" stroke="#9e5c55" stroke-width="5" stroke-linecap="round" />',
        '<ellipse cx="184" cy="326" rx="18" ry="12" fill="#d99a91" opacity="0.38" />',
        '<ellipse cx="328" cy="326" rx="18" ry="12" fill="#d99a91" opacity="0.38" />',
    ]
    if "lin" in asset_id or "澈" in display_name:
        layers.insert(5, f'<rect x="150" y="156" width="212" height="52" rx="22" fill="{hat}" />')
        layers.insert(6, f'<ellipse cx="256" cy="164" rx="106" ry="42" fill="{hat}" />')
    if "tang" in asset_id or "眠" in display_name:
        layers.append('<ellipse cx="256" cy="550" rx="58" ry="14" fill="#d4d7d2" />')
        layers.append('<rect x="212" y="562" width="88" height="54" rx="10" fill="#8a8f93" />')
    if "xu" in asset_id or "晚" in display_name:
        layers.append('<rect x="178" y="584" width="154" height="62" rx="12" fill="#8b9a98" />')
        layers.append('<line x1="194" y1="610" x2="316" y2="610" stroke="#d9e1df" stroke-width="4" opacity="0.62" />')
    label = escape(display_name[:8])
    layers.append(f'<text x="256" y="704" font-size="22" text-anchor="middle" fill="#f5f3ee" opacity="0.54">{label}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="768" viewBox="0 0 512 768">\n  ' + "\n  ".join(layers) + "\n</svg>\n"


def render_ui_svg(asset: Json) -> str:
    asset_id = str(asset.get("asset_id") or "ui.panel")
    accent = hex_color(asset_id, 5, 58, 32)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="160" viewBox="0 0 512 160">
  <rect x="0" y="0" width="512" height="160" rx="16" fill="#101418" opacity="0.86" />
  <rect x="18" y="18" width="476" height="124" rx="10" fill="{accent}" opacity="0.18" stroke="#ffffff" stroke-opacity="0.24" />
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


def resolve_audio_concurrency(value: int | None = None) -> int:
    if value is None:
        raw = os.environ.get("AUDIO_CONCURRENCY")
        if raw and raw.strip():
            try:
                value = int(raw)
            except ValueError:
                value = 1
    return max(1, int(value or 1))


def resolve_image_concurrency(value: int | None = None) -> int:
    if value is None:
        raw = os.environ.get("IMAGE_CONCURRENCY") or os.environ.get("IMAGE_ASSET_CONCURRENCY")
        if raw and raw.strip():
            try:
                value = int(raw)
            except ValueError:
                value = 4
        else:
            value = 4
    return max(1, int(value or 1))


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


def write_audio_file(output_path: Path, audio: Any) -> list[str]:
    ensure_dir(output_path.parent)
    output_path.write_bytes(audio.bytes)
    notes = [f"wrote provider audio ({audio.mime_type}, {len(audio.bytes)} bytes)"]
    if audio.source_url:
        notes.append("downloaded provider audio URL")
    return notes


def remove_background_if_possible(source_path: Path, output_path: Path) -> list[str]:
    ensure_dir(output_path.parent)
    script = r'''
import sys
from pathlib import Path
from PIL import Image
from rembg import remove

source = Path(sys.argv[1])
target = Path(sys.argv[2])
with Image.open(source) as input_image:
    rgba = input_image.convert("RGBA")
    output = remove(rgba)
    if not isinstance(output, Image.Image):
        raise RuntimeError("rembg returned unsupported image payload")
    output = output.convert("RGBA")
    alpha = output.getchannel("A")
    bounds = alpha.getbbox()
    if bounds:
        output = output.crop(bounds)
    output.save(target, "PNG", optimize=True)
'''
    result = subprocess.run(["python3", "-c", script, str(source_path), str(output_path)], capture_output=True, text=True)
    if result.returncode == 0:
        return ["background removal: rembg"]
    shutil.copy2(source_path, output_path)
    detail = (result.stderr or result.stdout).strip().splitlines()
    suffix = detail[-1] if detail else "unknown error"
    return [f"background removal unavailable or failed: {suffix}", "copied source portrait without cutout"]


def build_background_prompt(background: Json, manifest: Json) -> str:
    spec = background.get("spec") if isinstance(background.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    return " ".join([
        str(spec.get("description") or f"Create a visual novel background for {background.get('location_tag', 'scene')}."),
        f"Visual style: {style.get('rendering_mode', 'visual novel illustration')}.",
        "Composition: clean 16:9 environment background for dialogue scenes.",
        "Do not include featured foreground cast portraits or readable text.",
    ])


def build_cg_prompt(cg: Json, manifest: Json) -> str:
    spec = cg.get("spec") if isinstance(cg.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    return " ".join([
        str(spec.get("description") or f"Create a visual novel CG illustration for {cg.get('story_beat_id', 'story beat')}."),
        f"Visual style: {style.get('rendering_mode', 'visual novel illustration')}.",
        "Composition: memorable 16:9 story illustration that can be shown as a full-screen CG.",
        "No readable captions, no speech bubbles, no UI chrome.",
    ])


def build_character_identity_direction(character: Json) -> str:
    profile = character.get("character_profile") if isinstance(character.get("character_profile"), dict) else {}
    gender = str(character.get("gender") or profile.get("gender") or "").strip()
    age = str(character.get("age_impression") or profile.get("age_impression") or profile.get("age") or "").strip()
    persona = str(profile.get("persona") or "").strip()
    profile_prompt = str(profile.get("prompt") or "").strip()
    parts = []
    if gender:
        normalized_gender = gender.lower()
        if normalized_gender == "male":
            parts.append("Mandatory identity: adult male character with clearly masculine face, build, posture, and styling.")
        elif normalized_gender == "female":
            parts.append("Mandatory gender: female.")
        elif normalized_gender != "unspecified":
            parts.append(f"Mandatory gender presentation: {gender}.")
    if age:
        parts.append(f"Age impression: {age}.")
    if persona:
        parts.append(f"Character persona: {persona}.")
    if profile_prompt:
        parts.append(f"Identity prompt: {profile_prompt}.")
    if parts:
        parts.append("These identity constraints override name associations, puns, aliases, and scene nicknames.")
    return " ".join(parts)


def build_portrait_prompt(character: Json, portrait: Json, manifest: Json, reference_image: bool = False) -> str:
    spec = portrait.get("spec") if isinstance(portrait.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    emotion = str(portrait.get("emotion") or "neutral")
    expression_notes = {
        "neutral": "neutral expression with relaxed mouth, attentive eyes, calm upright posture",
        "alert": "clearly alert expression: widened focused eyes, raised brows, tense shoulders, body angled as if reacting to a signal",
        "soft": "clearly soft expression: gentle smile, relaxed eyelids, open shoulders, warm approachable posture",
        "sad": "clearly sad expression: downcast eyes, lowered brows, small tense mouth, slightly bowed head, protective hand posture",
        "resolved": "clearly resolved expression: steady direct gaze, lifted chin, firm mouth, squared shoulders, decisive stance",
        "guarded": "clearly guarded expression: narrowed cautious eyes, closed mouth, body turned slightly away, arms or hands held protectively close",
        "curious": "clearly curious expression: bright widened eyes, slightly parted mouth, head tilted, hand or prop extended toward the unknown",
        "fragile": "clearly fragile expression: trembling vulnerable eyes, worried brows, small parted mouth, shoulders drawn inward, protective posture",
    }.get(emotion, f"clearly readable {emotion} facial expression and matching body language")
    reference_direction = (
        "Use the attached reference image as a strict identity and costume reference; keep the same hair, outfit, colors, accessories, age, and proportions while changing only expression and body language."
        if reference_image
        else "Establish a clean canonical design that can be reused as the identity reference for this character's later expressions."
    )
    return " ".join([
        f"Character name: {character.get('display_name', character.get('id', 'character'))}.",
        build_character_identity_direction(character),
        f"Required expression: {emotion}.",
        f"Expression direction: {expression_notes}.",
        f"Character and costume direction: {spec.get('description', '')}.",
        f"Mood: {spec.get('mood', '')}.",
        f"Art style: {style.get('rendering_mode', 'visual novel illustration')}.",
        reference_direction,
        "Create one waist-up or three-quarter-body visual novel character sprite, 2:3 portrait ratio, transparent background.",
        "The face should occupy roughly 28 to 40 percent of the image height; do not render a tiny full-body sprite.",
        "The expression must be obvious at small visual novel sprite size through eyes, brows, mouth shape, head angle, shoulders, and hands.",
        "Avoid subtle micro-expressions; make the emotional contrast clear while preserving the character design.",
        "No background, no readable text, no logos, no captions, no speech bubbles.",
    ])


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
        if rest.startswith(("“", '"')) or (
            speaker_compact and (label in speaker_compact or speaker_compact in label)
        ):
            return strip_dialogue_quotes(rest)
    return strip_dialogue_quotes(text)


def ordered_portrait_assets(character: Json) -> list[Json]:
    portraits = [portrait for portrait in as_list(character.get("portrait_assets")) if isinstance(portrait, dict)]
    if len(portraits) < 2:
        return portraits
    base_id = str(character.get("base_portrait_asset_id") or "")

    def priority(portrait: Json) -> tuple[int, str]:
        emotion = str(portrait.get("emotion") or "").lower()
        asset_id = str(portrait.get("asset_id") or "")
        if emotion == "neutral":
            return (0, asset_id)
        if asset_id == base_id:
            return (1, asset_id)
        return (2, asset_id)

    return sorted(portraits, key=priority)


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
            raise RuntimeError(
                f"Voice asset {audio.get('asset_id', '<unknown>')} requires exact dialogue or monologue text "
                "in spec.text or spec.line_text."
            )
        return text
    if kind == "sfx":
        return " ".join([
            f"Short visual novel sound effect: {description}.",
            f"Mood: {mood}." if mood else "",
            "Keep it concise, non-musical, and suitable for a single interaction cue.",
        ]).strip()
    return " ".join([
        f"Instrumental visual novel background music cue: {description}.",
        f"Mood: {mood}." if mood else "",
        "Loop-friendly arrangement, no vocals, no lyrics, supports dialogue readability.",
    ]).strip()


def audio_voice_delivery(audio: Json) -> Json:
    if str(audio.get("kind") or "").lower() != "voice":
        return {}
    spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
    binding = {}
    if isinstance(spec.get("provider_bindings"), dict):
        maybe_binding = spec["provider_bindings"].get("minimax-ppio")
        if isinstance(maybe_binding, dict):
            binding = maybe_binding
    delivery = {
        "speaker": spec.get("speaker"),
        "authored_emotion": spec.get("emotion"),
        "authored_tone": spec.get("tone"),
        "provider_voice_emotion": binding.get("voice_emotion") or spec.get("voice_emotion"),
        "voice_profile_id": binding.get("voice_profile_id") or spec.get("voice_id"),
    }
    return {key: value for key, value in delivery.items() if value not in (None, "", [])}


def audio_with_manifest_voice_profile(audio: Json, manifest: Json) -> Json:
    if str(audio.get("kind") or "").lower() != "voice":
        return audio
    spec = audio.get("spec") if isinstance(audio.get("spec"), dict) else {}
    voice_profile_id = spec.get("voice_id") or audio.get("voice_id")
    if not isinstance(voice_profile_id, str) or not voice_profile_id.startswith("voice_profile."):
        return audio
    profiles = manifest.get("voice_profiles") if isinstance(manifest.get("voice_profiles"), dict) else {}
    profile = profiles.get(voice_profile_id)
    if not isinstance(profile, dict):
        return audio
    merged_spec = dict(spec)
    merged_spec["voice_design"] = profile
    if "gender" in profile:
        merged_spec.setdefault("voice_gender", profile["gender"])
    updated = dict(audio)
    updated["spec"] = merged_spec
    return updated


def generate_assets(
    run_root: Path,
    provider: str | None = "local-svg",
    model: str | None = None,
    overwrite: bool = False,
    remove_backgrounds: bool = True,
    audio_provider: str | None = None,
    audio_model: str | None = None,
    audio_fallback_provider: str | None = None,
    bgm_provider: str | None = None,
    sfx_provider: str | None = None,
    voice_provider: str | None = None,
    audio_concurrency: int | None = None,
    image_concurrency: int | None = None,
) -> Json:
    provider = provider or os.environ.get("IMAGE_ASSET_PROVIDER") or "local-svg"
    audio_provider_id = audio_provider or os.environ.get("AUDIO_ASSET_PROVIDER") or os.environ.get("AUDIO_PROVIDER") or "mock"
    audio_fallback_provider = audio_fallback_provider or os.environ.get("AUDIO_FALLBACK_PROVIDER")
    audio_provider_overrides = {"bgm": bgm_provider, "sfx": sfx_provider, "voice": voice_provider}
    audio_concurrency_value = resolve_audio_concurrency(audio_concurrency)
    image_concurrency_value = resolve_image_concurrency(image_concurrency)
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not asset_manifest:
        raise SystemExit("Missing workspace/asset-manifest.json. Run plan_assets.py first.")
    output_root = run_root / "workspace" / "generated-assets"
    ensure_dir(output_root)
    prompt_root = output_root / "prompts"
    entries = []
    warnings = []
    model_id = resolve_provider_model(provider, model)

    def run_parallel_tasks(items: list[Any], worker: Any, concurrency: int) -> list[Any]:
        if concurrency > 1 and len(items) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(worker, item) for item in items]
                return [future.result() for future in futures]
        return [worker(item) for item in items]

    def process_background(background: Json) -> tuple[Json | None, list[str]]:
        local_warnings: list[str] = []
        output_path = output_root / str(background["file_ref"])
        if output_path.exists() and not overwrite:
            local_warnings.append(f"Skipped existing background {background['asset_id']} at {background['file_ref']}.")
            return None, local_warnings
        prompt = build_background_prompt(background, asset_manifest)
        prompt_path = prompt_root / f"{sanitize_file_stem(background['asset_id'])}.txt"
        write_text(prompt_path, prompt + "\n")
        notes = []
        if maybe_copy_provider_hint(run_root, background, output_path):
            notes.append("copied provider_hints source")
        elif provider == "mock":
            notes.extend(write_mock_png(output_path))
        elif provider in REMOTE_IMAGE_PROVIDERS:
            images = generate_provider_images(
                provider=provider,
                model=model,
                asset_id=str(background["asset_id"]),
                output_root=output_root,
                prompt=prompt,
                image_type="background",
                aspect_ratio="16:9",
                expected_count=1,
            )
            if not images:
                raise RuntimeError(f"Provider returned no background image for {background['asset_id']}.")
            notes.extend(write_image_as_png(output_path, images[0]))
        else:
            svg = render_background_svg(background, asset_manifest.get("style_bible", {}))
            source_svg = output_root / "generated" / "sources" / f"{sanitize_file_stem(background['asset_id'])}.svg"
            notes.extend(write_png_from_svg(svg, output_path, source_svg))
        return {
            "asset_id": background["asset_id"],
            "role": "background",
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider,
            "model": model_id,
            "output_files": [str(output_path)],
            "notes": notes,
        }, local_warnings

    backgrounds = [background for background in as_list(asset_manifest.get("backgrounds")) if isinstance(background, dict)]
    for entry, local_warnings in run_parallel_tasks(backgrounds, process_background, image_concurrency_value):
        warnings.extend(local_warnings)
        if entry:
            entries.append(entry)

    def process_cg(cg: Json) -> tuple[Json | None, list[str]]:
        local_warnings: list[str] = []
        output_path = output_root / str(cg["file_ref"])
        if output_path.exists() and not overwrite:
            local_warnings.append(f"Skipped existing CG {cg['asset_id']} at {cg['file_ref']}.")
            return None, local_warnings
        prompt = build_cg_prompt(cg, asset_manifest)
        prompt_path = prompt_root / f"{sanitize_file_stem(cg['asset_id'])}.txt"
        write_text(prompt_path, prompt + "\n")
        notes = []
        if maybe_copy_provider_hint(run_root, cg, output_path):
            notes.append("copied provider_hints source")
        elif provider == "mock":
            notes.extend(write_mock_png(output_path))
        elif provider in REMOTE_IMAGE_PROVIDERS:
            images = generate_provider_images(
                provider=provider,
                model=model,
                asset_id=str(cg["asset_id"]),
                output_root=output_root,
                prompt=prompt,
                image_type="cg",
                aspect_ratio="16:9",
                expected_count=1,
            )
            if not images:
                raise RuntimeError(f"Provider returned no CG image for {cg['asset_id']}.")
            notes.extend(write_image_as_png(output_path, images[0]))
        else:
            svg = render_cg_svg(cg, asset_manifest.get("style_bible", {}))
            source_svg = output_root / "generated" / "sources" / f"{sanitize_file_stem(cg['asset_id'])}.svg"
            notes.extend(write_png_from_svg(svg, output_path, source_svg))
        return {
            "asset_id": cg["asset_id"],
            "role": "cg",
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider,
            "model": model_id,
            "output_files": [str(output_path)],
            "notes": notes,
        }, local_warnings

    cgs = [cg for cg in as_list(asset_manifest.get("cgs")) if isinstance(cg, dict)]
    for entry, local_warnings in run_parallel_tasks(cgs, process_cg, image_concurrency_value):
        warnings.extend(local_warnings)
        if entry:
            entries.append(entry)

    def process_portrait_asset(
        character: Json,
        portrait: Json,
        first_portrait_path: Path | None,
    ) -> tuple[Json | None, list[str], Path | None]:
        local_warnings: list[str] = []
        output_path = output_root / str(portrait["file_ref"])
        source_path = output_root / str(portrait.get("source_file_ref") or portrait["file_ref"])
        if output_path.exists() and not overwrite:
            local_warnings.append(f"Skipped existing portrait {portrait['asset_id']} at {portrait['file_ref']}.")
            return None, local_warnings, output_path
        reference_images = []
        if provider == "gemini" and first_portrait_path and first_portrait_path.exists() and first_portrait_path != output_path:
            reference_images.append(first_portrait_path)
        prompt = build_portrait_prompt(character, portrait, asset_manifest, reference_image=bool(reference_images))
        prompt_path = prompt_root / f"{sanitize_file_stem(portrait['asset_id'])}.txt"
        write_text(prompt_path, prompt + "\n")
        notes = []
        if reference_images:
            notes.append(f"used reference portrait {reference_images[0].relative_to(output_root)}")
        if maybe_copy_provider_hint(run_root, portrait, output_path):
            ensure_dir(source_path.parent)
            shutil.copy2(output_path, source_path)
            notes.append("copied provider_hints source")
        elif provider == "mock":
            notes.extend(write_mock_png(source_path))
            ensure_dir(output_path.parent)
            shutil.copy2(source_path, output_path)
        elif provider in REMOTE_IMAGE_PROVIDERS:
            images = generate_provider_images(
                provider=provider,
                model=model,
                asset_id=str(portrait["asset_id"]),
                output_root=output_root,
                prompt=prompt,
                image_type="character",
                aspect_ratio="2:3",
                expected_count=1,
                reference_images=reference_images,
            )
            if not images:
                raise RuntimeError(f"Provider returned no portrait image for {portrait['asset_id']}.")
            notes.extend(write_image_as_png(source_path, images[0]))
            if remove_backgrounds:
                notes.extend(remove_background_if_possible(source_path, output_path))
            else:
                ensure_dir(output_path.parent)
                shutil.copy2(source_path, output_path)
                notes.append("background removal skipped")
        else:
            svg = render_portrait_svg(character, portrait, asset_manifest.get("style_bible", {}))
            source_svg = output_root / "generated" / "sources" / f"{sanitize_file_stem(portrait['asset_id'])}.svg"
            notes.extend(write_png_from_svg(svg, output_path, source_svg))
            ensure_dir(source_path.parent)
            shutil.copy2(output_path, source_path)
            notes.append("transparent portrait generated directly; background removal skipped")
        return {
            "asset_id": portrait["asset_id"],
            "role": "portrait",
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider,
            "model": model_id,
            "output_files": [str(output_path), str(source_path)],
            "notes": notes,
        }, local_warnings, output_path

    def process_character_base(character: Json) -> tuple[list[Json], list[str], list[tuple[Json, Json, Path | None]]]:
        local_entries: list[Json] = []
        local_warnings: list[str] = []
        portraits = ordered_portrait_assets(character)
        if not portraits:
            return local_entries, local_warnings, []
        entry, portrait_warnings, first_portrait_path = process_portrait_asset(character, portraits[0], None)
        local_warnings.extend(portrait_warnings)
        if entry:
            local_entries.append(entry)
        canon_ref = character.get("canon_ref_file_ref")
        if isinstance(canon_ref, str) and first_portrait_path and first_portrait_path.exists():
            canon_path = output_root / canon_ref
            if overwrite or not canon_path.exists():
                ensure_dir(canon_path.parent)
                shutil.copy2(first_portrait_path, canon_path)
            local_entries.append({
                "asset_id": character.get("canon_ref_asset_id", f"charref.{character.get('id', 'character')}"),
                "role": "canon",
                "prompt": f"Canon reference copied from {first_portrait_path.name}.",
                "provider": provider,
                "model": model_id,
                "output_files": [str(canon_path)],
                "notes": ["copied from generated base portrait"],
            })
        expression_tasks = [(character, portrait, first_portrait_path) for portrait in portraits[1:]]
        return local_entries, local_warnings, expression_tasks

    characters = [character for character in as_list(asset_manifest.get("characters")) if isinstance(character, dict)]
    expression_tasks: list[tuple[Json, Json, Path | None]] = []
    for local_entries, local_warnings, local_expression_tasks in run_parallel_tasks(
        characters,
        process_character_base,
        image_concurrency_value,
    ):
        entries.extend(local_entries)
        warnings.extend(local_warnings)
        expression_tasks.extend(local_expression_tasks)

    def process_expression_task(task: tuple[Json, Json, Path | None]) -> tuple[Json | None, list[str]]:
        character, portrait, first_portrait_path = task
        entry, local_warnings, _ = process_portrait_asset(character, portrait, first_portrait_path)
        return entry, local_warnings

    for entry, local_warnings in run_parallel_tasks(expression_tasks, process_expression_task, image_concurrency_value):
        warnings.extend(local_warnings)
        if entry:
            entries.append(entry)

    for ui_asset in as_list(asset_manifest.get("ui")):
        if not isinstance(ui_asset, dict):
            continue
        output_path = output_root / str(ui_asset["file_ref"])
        if output_path.exists() and not overwrite:
            warnings.append(f"Skipped existing UI asset {ui_asset['asset_id']} at {ui_asset['file_ref']}.")
            continue
        prompt = f"Generate UI asset {ui_asset['asset_id']} for a VN interface."
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

    def process_audio_asset(audio: Json) -> tuple[Json | None, list[str]]:
        local_warnings: list[str] = []
        if not isinstance(audio, dict):
            return None, local_warnings
        audio = audio_with_manifest_voice_profile(audio, asset_manifest)
        asset_id = str(audio.get("asset_id") or "audio")
        file_ref = audio.get("file_ref")
        if not isinstance(file_ref, str) or not file_ref.strip():
            local_warnings.append(f"Skipped audio asset without file_ref: {asset_id}.")
            return None, local_warnings
        output_path = output_root / file_ref
        if output_path.exists() and not overwrite:
            local_warnings.append(f"Skipped existing audio asset {asset_id} at {file_ref}.")
            return None, local_warnings
        prompt = build_audio_prompt(audio, asset_manifest)
        prompt_path = prompt_root / f"{sanitize_file_stem(asset_id)}.txt"
        write_text(prompt_path, prompt + "\n")
        notes = []
        if maybe_copy_provider_hint(run_root, audio, output_path):
            notes.append("copied provider_hints source")
            provider_used = "provider_hint"
        elif audio_provider_id in ("none", "skip"):
            local_warnings.append(f"Audio asset planned but skipped by audio provider setting: {asset_id}.")
            return None, local_warnings
        else:
            audio_kind = str(audio.get("kind") or asset_id.split(".", 1)[0] or "bgm")
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
                local_warnings.append(
                    f"Audio provider {generation['fallback_from']} failed for {asset_id}; "
                    f"fell back to {provider_used}: {generation.get('primary_error')}"
                )
        audio_model_id = resolve_audio_provider_model(provider_used, audio_model, str(audio.get("kind") or "bgm"))
        entry: Json = {
            "asset_id": asset_id,
            "role": str(audio.get("kind") or "audio"),
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider_used,
            "model": audio_model_id,
            "output_files": [str(output_path)],
            "notes": notes,
        }
        delivery = audio_voice_delivery(audio)
        if delivery:
            entry["voice_delivery"] = delivery
        return entry, local_warnings

    audio_assets = [audio for audio in as_list(asset_manifest.get("audio")) if isinstance(audio, dict)]
    if audio_concurrency_value > 1 and len(audio_assets) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=audio_concurrency_value) as executor:
            futures = [executor.submit(process_audio_asset, audio) for audio in audio_assets]
            for future in futures:
                entry, local_warnings = future.result()
                warnings.extend(local_warnings)
                if entry:
                    entries.append(entry)
    else:
        for audio in audio_assets:
            entry, local_warnings = process_audio_asset(audio)
            warnings.extend(local_warnings)
            if entry:
                entries.append(entry)

    report = {
        "project_id": asset_manifest.get("project_id", "generated"),
        "provider": provider,
        "model": model_id,
        "audio_provider": audio_provider_id,
        "audio_model": audio_model,
        "audio_concurrency": audio_concurrency_value,
        "image_concurrency": image_concurrency_value,
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
    parser.add_argument("--audio-concurrency", type=int, default=None)
    parser.add_argument("--image-concurrency", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-remove-backgrounds", action="store_false", dest="remove_backgrounds")
    parser.set_defaults(remove_backgrounds=True)
    args = parser.parse_args()
    provider = args.provider or __import__("os").environ.get("IMAGE_ASSET_PROVIDER") or "local-svg"
    report = generate_assets(
        Path(args.run_root).resolve(),
        provider=provider,
        model=args.model,
        overwrite=args.overwrite,
        remove_backgrounds=args.remove_backgrounds,
        audio_provider=args.audio_provider,
        audio_model=args.audio_model,
        audio_fallback_provider=args.audio_fallback_provider,
        bgm_provider=args.bgm_provider,
        sfx_provider=args.sfx_provider,
        voice_provider=args.voice_provider,
        audio_concurrency=args.audio_concurrency,
        image_concurrency=args.image_concurrency,
    )
    print(json.dumps({"report": str(path_for(Path(args.run_root).resolve(), "asset_generation_report")), "entries": len(report["entries"])}, indent=2))


if __name__ == "__main__":
    main()
