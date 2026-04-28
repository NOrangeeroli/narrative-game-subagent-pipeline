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
