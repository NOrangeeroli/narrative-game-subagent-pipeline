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
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from asset_image_providers import GeneratedImage, generate_provider_images, resolve_provider_model
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, read_json, write_json, write_text


MOCK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNgYGBgAAAABQABeqhXUAAAAABJRU5ErkJggg=="
)
REMOTE_IMAGE_PROVIDERS = {"gemini", "openai-ppioImage"}
RPG_ASSET_SECTIONS = {
    "terrain_tiles": "terrain_tile",
    "tilesets": "tileset",
    "sprites": "sprite",
    "enemy_sprites": "enemy_sprite",
    "map_props": "map_prop",
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


def render_rpg_svg(asset: Json, role: str) -> str:
    asset_id = str(asset.get("asset_id") or role)
    suffix = asset_id.split(".")[-1]
    primary = hex_color(asset_id, 21, 58, 42)
    secondary = hex_color(asset_id, 22, 42, 28)
    accent = hex_color(asset_id, 23, 68, 46)
    label = escape(asset_id.split(".")[-1][:12])
    if role == "battle_background":
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{secondary}" />
  <rect y="420" width="1280" height="300" fill="{primary}" opacity="0.72" />
  <ellipse cx="640" cy="430" rx="390" ry="54" fill="#f7f2d7" opacity="0.22" />
  <path d="M0 260 C220 190 320 300 520 230 C760 150 900 260 1280 170 L1280 0 L0 0 Z" fill="{accent}" opacity="0.48" />
</svg>
'''
    if role == "tileset":
        tiles = []
        colors = [primary, secondary, accent, "#6b7f64", "#314038", "#9a855d", "#4b7f8f", "#b49659"]
        for y in range(4):
            for x in range(4):
                color = colors[(x + y * 2) % len(colors)]
                tiles.append(f'<rect x="{x * 128}" y="{y * 128}" width="126" height="126" rx="6" fill="{color}" />')
                tiles.append(f'<path d="M{x * 128 + 14} {y * 128 + 94} C{x * 128 + 42} {y * 128 + 78} {x * 128 + 82} {y * 128 + 110} {x * 128 + 116} {y * 128 + 88}" fill="none" stroke="#ffffff" stroke-opacity="0.12" stroke-width="7" stroke-linecap="round" />')
        return '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">\n  ' + "\n  ".join(tiles) + "\n</svg>\n"
    if role == "terrain_tile":
        terrain = suffix
        palette = {
            "grass": ("#2f5a36", "#3f7948", "#8cc36a"),
            "path": ("#7c6544", "#a78b5a", "#d5bf84"),
            "water": ("#235d70", "#3b8fa3", "#a4d6d8"),
            "bridge": ("#5b351f", "#8a5a32", "#d2a062"),
            "sand": ("#9f8758", "#c7b06f", "#eadc9c"),
            "stone": ("#464b4a", "#656c69", "#a5aaa3"),
            "wood": ("#5d3a24", "#8d5a34", "#c58a51"),
            "floor": ("#4f4c46", "#797160", "#b8aa82"),
            "wall": ("#232728", "#3c4140", "#717875"),
        }.get(terrain, (primary, secondary, accent))
        base, mid, light = palette
        if terrain == "water":
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{base}" />
  <path d="M-18 50 C22 26 60 76 104 52 C148 28 188 76 274 40" fill="none" stroke="{mid}" stroke-width="18" opacity="0.62" />
  <path d="M-22 126 C30 98 70 152 118 126 C166 100 194 154 278 116" fill="none" stroke="{light}" stroke-width="10" opacity="0.42" />
  <path d="M-20 200 C36 172 70 222 126 196 C176 174 206 220 276 186" fill="none" stroke="{mid}" stroke-width="16" opacity="0.5" />
</svg>
'''
        if terrain in ("bridge", "wood"):
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{base}" />
  <rect x="0" y="18" width="256" height="44" fill="{mid}" opacity="0.82" />
  <rect x="0" y="82" width="256" height="44" fill="{mid}" opacity="0.72" />
  <rect x="0" y="146" width="256" height="44" fill="{mid}" opacity="0.78" />
  <rect x="0" y="210" width="256" height="44" fill="{mid}" opacity="0.7" />
  <path d="M32 18 V62 M132 82 V126 M78 146 V190 M188 210 V254" stroke="{light}" stroke-width="6" opacity="0.28" />
  <path d="M18 40 C62 28 112 50 154 34 C184 24 214 34 246 28" fill="none" stroke="#2a170e" stroke-width="5" opacity="0.34" />
</svg>
'''
        if terrain in ("stone", "floor", "wall"):
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{base}" />
  <path d="M0 64 H256 M0 128 H256 M0 192 H256" stroke="#171918" stroke-width="7" opacity="0.45" />
  <path d="M58 0 V64 M154 0 V64 M98 64 V128 M210 64 V128 M42 128 V192 M168 128 V192 M118 192 V256 M226 192 V256" stroke="#171918" stroke-width="7" opacity="0.45" />
  <path d="M18 42 C48 24 78 54 108 34 M126 156 C168 132 188 174 230 148" fill="none" stroke="{light}" stroke-width="6" opacity="0.2" />
</svg>
'''
        if terrain in ("path", "sand"):
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{base}" />
  <path d="M-16 38 C50 8 84 72 154 38 C196 18 222 34 274 16" fill="none" stroke="{mid}" stroke-width="34" opacity="0.48" />
  <circle cx="44" cy="72" r="8" fill="{light}" opacity="0.32" />
  <circle cx="122" cy="106" r="5" fill="#3c2b1e" opacity="0.24" />
  <circle cx="198" cy="48" r="7" fill="{light}" opacity="0.26" />
  <circle cx="70" cy="182" r="6" fill="#3c2b1e" opacity="0.18" />
  <circle cx="172" cy="204" r="9" fill="{light}" opacity="0.22" />
</svg>
'''
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="{base}" />
  <path d="M16 208 C58 166 82 232 124 184 C154 150 182 184 240 140" fill="none" stroke="{mid}" stroke-width="20" opacity="0.35" />
  <path d="M28 54 C56 36 76 70 106 48 M142 88 C164 68 194 98 224 74 M54 146 C78 124 106 154 134 132" fill="none" stroke="{light}" stroke-width="9" opacity="0.26" stroke-linecap="round" />
  <circle cx="48" cy="96" r="5" fill="{light}" opacity="0.34" />
  <circle cx="180" cy="164" r="6" fill="{light}" opacity="0.26" />
  <circle cx="214" cy="216" r="4" fill="{light}" opacity="0.24" />
</svg>
'''
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
    if role == "map_prop":
        if suffix in ("tree", "tree_canopy"):
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="226" rx="54" ry="13" fill="#000" opacity="0.2" />
  <rect x="112" y="132" width="32" height="82" rx="10" fill="#7b5435" />
  <circle cx="96" cy="112" r="48" fill="{primary}" />
  <circle cx="142" cy="86" r="55" fill="{accent}" />
  <circle cx="164" cy="134" r="46" fill="{secondary}" />
  <circle cx="112" cy="148" r="43" fill="{primary}" />
</svg>
'''
        if suffix.startswith("house") or suffix == "roof":
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="226" rx="78" ry="14" fill="#000" opacity="0.18" />
  <rect x="58" y="104" width="140" height="94" rx="10" fill="#d0aa76" />
  <polygon points="42,112 128,42 214,112" fill="{secondary}" />
  <rect x="108" y="146" width="38" height="52" rx="5" fill="#5d3a25" />
  <rect x="72" y="126" width="28" height="24" rx="4" fill="#6c8fa0" opacity="0.88" />
  <rect x="156" y="126" width="28" height="24" rx="4" fill="#6c8fa0" opacity="0.88" />
</svg>
'''
        if suffix == "door":
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="214" rx="42" ry="10" fill="#000" opacity="0.16" />
  <rect x="82" y="52" width="92" height="154" rx="10" fill="{secondary}" />
  <rect x="98" y="70" width="60" height="118" rx="6" fill="{primary}" />
  <circle cx="146" cy="132" r="7" fill="#f1d47b" />
</svg>
'''
        if suffix == "chest":
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="202" rx="62" ry="14" fill="#000" opacity="0.18" />
  <rect x="62" y="104" width="132" height="78" rx="12" fill="#8a5129" />
  <path d="M62 114 C70 72 186 72 194 114 Z" fill="#d6a146" />
  <rect x="62" y="124" width="132" height="16" fill="#3d2718" opacity="0.58" />
  <rect x="116" y="120" width="24" height="34" rx="5" fill="#f0d06f" />
</svg>
'''
        if suffix in ("barrel", "crate", "rock", "flower", "fence", "bridge"):
            shapes = {
                "barrel": f'<ellipse cx="128" cy="74" rx="48" ry="20" fill="{accent}" /><rect x="80" y="74" width="96" height="104" rx="28" fill="{secondary}" /><ellipse cx="128" cy="178" rx="48" ry="20" fill="{primary}" /><path d="M92 98 H164 M88 152 H168" stroke="#38271d" stroke-width="9" stroke-linecap="round" />',
                "crate": f'<rect x="72" y="76" width="112" height="112" rx="10" fill="{primary}" /><path d="M84 88 L172 176 M172 88 L84 176 M72 118 H184 M118 76 V188" stroke="#48351f" stroke-width="9" opacity="0.58" />',
                "rock": f'<path d="M72 170 L54 128 L82 84 L140 64 L192 104 L204 156 L166 190 L104 188 Z" fill="{secondary}" /><path d="M96 92 L142 78 L178 110" fill="none" stroke="#fff" stroke-opacity="0.15" stroke-width="8" stroke-linecap="round" />',
                "flower": f'<circle cx="128" cy="128" r="13" fill="#eed66a" /><circle cx="128" cy="96" r="24" fill="{accent}" /><circle cx="128" cy="160" r="24" fill="{accent}" /><circle cx="96" cy="128" r="24" fill="{primary}" /><circle cx="160" cy="128" r="24" fill="{primary}" /><path d="M128 144 C118 174 96 194 74 206" fill="none" stroke="#55783e" stroke-width="8" stroke-linecap="round" />',
                "fence": f'<rect x="40" y="102" width="176" height="18" rx="6" fill="#7a5630" /><rect x="40" y="146" width="176" height="18" rx="6" fill="#7a5630" /><rect x="60" y="72" width="22" height="122" rx="7" fill="{secondary}" /><rect x="118" y="72" width="22" height="122" rx="7" fill="{secondary}" /><rect x="176" y="72" width="22" height="122" rx="7" fill="{secondary}" />',
                "bridge": f'<rect x="34" y="70" width="188" height="116" rx="14" fill="#6f4b2d" /><path d="M58 82 V174 M94 82 V174 M130 82 V174 M166 82 V174 M202 82 V174" stroke="#382516" stroke-width="8" opacity="0.52" /><path d="M48 102 H208 M48 154 H208" stroke="#d1a265" stroke-width="9" opacity="0.72" />',
            }[suffix]
            return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="214" rx="62" ry="13" fill="#000" opacity="0.16" />
  {shapes}
</svg>
'''
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <ellipse cx="128" cy="210" rx="64" ry="13" fill="#000" opacity="0.16" />
  <rect x="58" y="58" width="140" height="140" rx="28" fill="{primary}" />
  <path d="M82 154 C112 112 144 188 174 104" fill="none" stroke="{accent}" stroke-width="18" stroke-linecap="round" />
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


def build_portrait_prompt(character: Json, portrait: Json, manifest: Json) -> str:
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    return " ".join([
        f"Character name: {character.get('display_name', character.get('id', 'character'))}.",
        f"Emotion: {portrait.get('emotion', 'neutral')}.",
        f"Art style: {style.get('rendering_mode', 'visual novel illustration')}.",
        "Create one full-body visual novel character sprite, 2:3 portrait ratio, transparent background.",
    ])


def build_rpg_asset_prompt(asset: Json, role: str, manifest: Json) -> str:
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    style = manifest.get("style_bible") if isinstance(manifest.get("style_bible"), dict) else {}
    description = str(spec.get("description") or f"Create RPG {role} asset {asset.get('asset_id', '')}.")
    if role == "map_asset":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
            "Create a detailed top-down 2D RPG map background for a playable grid scene.",
            "Show terrain, paths, landmarks, props, and mood clearly from an overhead game-camera angle.",
            "No UI, no labels, no readable text, no characters as the focus.",
        ])
    if role == "battle_background":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', '2D RPG illustration')}.",
            "Create a wide 16:9 RPG battle background with strong location identity and clear foreground/midground/depth.",
            "No UI, no labels, no readable text, no character portraits.",
        ])
    if role == "tileset":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', 'top-down 2D RPG tile art')}.",
            "Create a cohesive top-down orthographic RPG tile atlas with grass, path, water, bridge, stone, wood, roof, and accent tiles.",
            "Use a consistent grid scale, clean silhouettes, readable terrain boundaries, no UI, no labels, no readable text.",
        ])
    if role == "terrain_tile":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', 'top-down 2D RPG tile art')}.",
            "Create exactly one seamless square terrain tile for a top-down orthographic RPG map.",
            "The material must fill the whole image and repeat cleanly on a 48px grid.",
            "No atlas, no collage, no border, no props, no characters, no UI, no labels, no readable text.",
        ])
    if role == "map_prop":
        return " ".join([
            description,
            f"Visual style: {style.get('rendering_mode', 'top-down 2D RPG tile art')}.",
            "Create one top-down orthographic RPG map prop as a centered game asset.",
            "Match a 48 to 96 pixel tile scale, clean silhouette, even lighting, transparent or plain background.",
            "No UI, no labels, no readable text, no border, no character focus.",
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


def remote_rpg_asset_shape(role: str) -> tuple[str, str]:
    if role == "battle_background":
        return "background", "16:9"
    if role == "map_asset":
        return "background", "4:3"
    return "asset", "1:1"


def generate_assets(run_root: Path, provider: str | None = "local-svg", model: str | None = None, overwrite: bool = False, remove_backgrounds: bool = True) -> Json:
    provider = provider or os.environ.get("IMAGE_ASSET_PROVIDER") or "local-svg"
    asset_manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not asset_manifest:
        raise SystemExit("Missing workspace/asset-manifest.json. Run plan_assets.py first.")
    output_root = run_root / "workspace" / "generated-assets"
    ensure_dir(output_root)
    prompt_root = output_root / "prompts"
    entries = []
    warnings = []
    model_id = resolve_provider_model(provider, model)

    for background in as_list(asset_manifest.get("backgrounds")):
        if not isinstance(background, dict):
            continue
        output_path = output_root / str(background["file_ref"])
        if output_path.exists() and not overwrite:
            warnings.append(f"Skipped existing background {background['asset_id']} at {background['file_ref']}.")
            continue
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
        entries.append({
            "asset_id": background["asset_id"],
            "role": "background",
            "prompt": prompt,
            "prompt_ref": str(prompt_path.relative_to(output_root)),
            "provider": provider,
            "model": model_id,
            "output_files": [str(output_path)],
            "notes": notes,
        })

    for character in as_list(asset_manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        first_portrait_path: Path | None = None
        for portrait in as_list(character.get("portrait_assets")):
            if not isinstance(portrait, dict):
                continue
            output_path = output_root / str(portrait["file_ref"])
            source_path = output_root / str(portrait.get("source_file_ref") or portrait["file_ref"])
            if output_path.exists() and not overwrite:
                warnings.append(f"Skipped existing portrait {portrait['asset_id']} at {portrait['file_ref']}.")
                if first_portrait_path is None:
                    first_portrait_path = output_path
                continue
            prompt = build_portrait_prompt(character, portrait, asset_manifest)
            prompt_path = prompt_root / f"{sanitize_file_stem(portrait['asset_id'])}.txt"
            write_text(prompt_path, prompt + "\n")
            notes = []
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
            entries.append({
                "asset_id": portrait["asset_id"],
                "role": "portrait",
                "prompt": prompt,
                "prompt_ref": str(prompt_path.relative_to(output_root)),
                "provider": provider,
                "model": model_id,
                "output_files": [str(output_path), str(source_path)],
                "notes": notes,
            })
            if first_portrait_path is None:
                first_portrait_path = output_path
        canon_ref = character.get("canon_ref_file_ref")
        if isinstance(canon_ref, str) and first_portrait_path and first_portrait_path.exists():
            canon_path = output_root / canon_ref
            if overwrite or not canon_path.exists():
                ensure_dir(canon_path.parent)
                shutil.copy2(first_portrait_path, canon_path)
            entries.append({
                "asset_id": character.get("canon_ref_asset_id", f"charref.{character.get('id', 'character')}"),
                "role": "canon",
                "prompt": f"Canon reference copied from {first_portrait_path.name}.",
                "provider": provider,
                "model": model_id,
                "output_files": [str(canon_path)],
                "notes": ["copied from generated base portrait"],
            })

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
        if isinstance(audio, dict):
            warnings.append(f"Audio asset planned but not generated by v1 generator: {audio.get('asset_id')}")

    report = {
        "project_id": asset_manifest.get("project_id", "generated"),
        "provider": provider,
        "model": model_id,
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
    )
    print(json.dumps({"report": str(path_for(Path(args.run_root).resolve(), "asset_generation_report")), "entries": len(report["entries"])}, indent=2))


if __name__ == "__main__":
    main()
