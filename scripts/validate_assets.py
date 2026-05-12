#!/usr/bin/env python3
"""Validate generated assets against asset-manifest.json."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json

RPG_ASSET_SECTIONS = (
    "tilesets",
    "sprites",
    "enemy_sprites",
    "item_icons",
    "skill_icons",
    "equipment_icons",
    "battle_backgrounds",
    "map_assets",
    "rpg_ui",
)


def identify(path: Path) -> dict[str, str] | None:
    try:
        output = subprocess.check_output(
            ["magick", "identify", "-format", "%w %h %[channels]", str(path)],
            text=True,
        )
    except Exception:
        return None
    width, height, channels = output.strip().split(" ", 2)
    return {"width": width, "height": height, "channels": channels}


def has_transparency(path: Path) -> bool:
    metadata = identify(path)
    if not metadata or "a" not in metadata["channels"].lower():
        return False
    try:
        minimum = subprocess.check_output(
            ["magick", str(path), "-channel", "A", "-separate", "-format", "%[min]", "info:"],
            text=True,
        ).strip()
        return int(float(minimum)) < 65535
    except Exception:
        return False


def read_report(run_root: Path, name: str) -> Json | None:
    path = run_root / "reports" / name
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def resolve_asset_mode(asset_mode: str) -> str:
    if asset_mode != "auto":
        return asset_mode
    image_provider = (
        os.environ.get("IMAGE_ASSET_PROVIDER")
        or os.environ.get("IMAGE_PROVIDER")
        or ""
    ).strip().lower()
    audio_provider = (
        os.environ.get("AUDIO_ASSET_PROVIDER")
        or os.environ.get("AUDIO_PROVIDER")
        or ""
    ).strip().lower()
    if image_provider in {"imagegen", "ppio", "gemini", "openai-ppioimage"}:
        return "final-quality"
    if audio_provider and audio_provider not in {"mock", "none", "skip"}:
        return "final-quality"
    return "fast-validation"


def check_report_status(run_root: Path, report_name: str, issues: list[Json]) -> Json | None:
    report = read_report(run_root, report_name)
    if not report:
        issues.append({
            "code": "missing_report",
            "report": f"reports/{report_name}",
            "message": f"Final-quality validation requires reports/{report_name}.",
        })
        return None
    if report.get("status") != "pass":
        issues.append({
            "code": "report_not_pass",
            "report": f"reports/{report_name}",
            "status": report.get("status"),
            "message": f"Final-quality validation requires reports/{report_name} status pass.",
        })
    return report


def check_final_quality_backgrounds(run_root: Path, manifest: Json, issues: list[Json]) -> None:
    map_assets = [asset for asset in as_list(manifest.get("map_assets")) if isinstance(asset, dict)]
    if not map_assets:
        return
    background_report = check_report_status(run_root, "rpg-background-generation-report.json", issues)
    boundary_report = check_report_status(run_root, "rpg-boundary-mask-generation-report.json", issues)
    check_report_status(run_root, "boundary-validation-report.json", issues)
    check_report_status(run_root, "asset-provenance-report.json", issues)

    if background_report:
        for entry in as_list(background_report.get("entries")):
            if not isinstance(entry, dict):
                continue
            final_provider = str(entry.get("final_provider") or "")
            if final_provider in {"local-svg", "mock"}:
                issues.append({
                    "asset_id": entry.get("asset_id"),
                    "code": "final_quality_background_fallback",
                    "message": "Final-quality RPG background cannot use local-svg/mock fallback.",
                })

    if boundary_report:
        for entry in as_list(boundary_report.get("entries")):
            if not isinstance(entry, dict):
                continue
            requested = str(entry.get("requested_provider") or boundary_report.get("provider") or "")
            final_provider = str(entry.get("final_provider") or "")
            if final_provider in {"local-svg", "mock"}:
                issues.append({
                    "asset_id": entry.get("asset_id"),
                    "map_id": entry.get("map_id"),
                    "code": "final_quality_boundary_fallback",
                    "message": "Final-quality RPG boundary masks cannot use local-svg/mock fallback.",
                })
            if requested == "imagegen" and final_provider != "imagegen":
                issues.append({
                    "asset_id": entry.get("asset_id"),
                    "map_id": entry.get("map_id"),
                    "code": "missing_imagegen_boundary",
                    "message": "IMAGE_PROVIDER=imagegen requires imagegen cyan walkable-mask boundary generation.",
                })

    for asset in map_assets:
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id:
            continue
        video_root = run_root / "workspace" / "generated-assets" / "generated" / "videos"
        expected_mp4 = video_root / f"bgv.{asset_id}.loop.mp4"
        expected_gif = video_root / f"bgv.{asset_id}.loop.gif"
        if not expected_mp4.exists() and not expected_gif.exists():
            issues.append({
                "asset_id": asset_id,
                "code": "missing_dynamic_background",
                "message": "Final-quality RPG map background requires a dynamic bgv.* MP4 or GIF.",
            })


def validate_assets(run_root: Path, asset_mode: str = "auto") -> Json:
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not manifest:
        report = {"status": "skipped", "issues": [], "warnings": ["Missing workspace/asset-manifest.json."]}
        write_json(path_for(run_root, "asset_validation_report"), report)
        return report
    output_root = run_root / "workspace" / "generated-assets"
    issues: list[Json] = []
    warnings: list[str] = []

    def check_file(asset_id: str, file_ref: str, role: str, require_transparency: bool = False) -> None:
        path = output_root / file_ref
        if not path.exists():
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "missing_file", "message": "Manifest file_ref was not generated."})
            return
        info = identify(path)
        if not info:
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "not_inspectable", "message": "ImageMagick could not inspect generated image."})
            return
        if require_transparency and not has_transparency(path):
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "portrait_missing_transparency", "message": "Portrait output is not transparent."})
        if role == "background" and (int(info["width"]) < 640 or int(info["height"]) < 360):
            warnings.append(f"Background {asset_id} is small: {info['width']}x{info['height']}.")

    def check_binary_file(asset_id: str, file_ref: str, role: str) -> None:
        path = output_root / file_ref
        if not path.exists():
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "missing_file", "message": "Manifest file_ref was not generated."})
            return
        if path.stat().st_size <= 0:
            issues.append({"asset_id": asset_id, "file_ref": file_ref, "code": "empty_file", "message": f"Generated {role} file is empty."})

    for background in as_list(manifest.get("backgrounds")):
        if isinstance(background, dict):
            check_file(str(background.get("asset_id")), str(background.get("file_ref")), "background")
    for cg in as_list(manifest.get("cgs")):
        if isinstance(cg, dict):
            check_file(str(cg.get("asset_id")), str(cg.get("file_ref")), "cg")
    for ui_asset in as_list(manifest.get("ui")):
        if isinstance(ui_asset, dict):
            check_file(str(ui_asset.get("asset_id")), str(ui_asset.get("file_ref")), "ui")
    for section in RPG_ASSET_SECTIONS:
        for rpg_asset in as_list(manifest.get(section)):
            if isinstance(rpg_asset, dict):
                check_file(str(rpg_asset.get("asset_id")), str(rpg_asset.get("file_ref")), section)
    for audio in as_list(manifest.get("audio")):
        if isinstance(audio, dict):
            check_binary_file(str(audio.get("asset_id")), str(audio.get("file_ref")), str(audio.get("kind") or "audio"))
    for character in as_list(manifest.get("characters")):
        if not isinstance(character, dict):
            continue
        for portrait in as_list(character.get("portrait_assets")):
            if isinstance(portrait, dict):
                check_file(str(portrait.get("asset_id")), str(portrait.get("file_ref")), "portrait", require_transparency=True)
        canon_ref = character.get("canon_ref_file_ref")
        if isinstance(canon_ref, str):
            check_file(str(character.get("canon_ref_asset_id")), canon_ref, "canon", require_transparency=True)
    resolved_mode = resolve_asset_mode(asset_mode)
    if resolved_mode == "final-quality":
        check_final_quality_backgrounds(run_root, manifest, issues)
    report = {
        "status": "pass" if not issues else "fail",
        "asset_mode": resolved_mode,
        "output_root": str(output_root),
        "issues": issues,
        "warnings": warnings,
    }
    write_json(path_for(run_root, "asset_validation_report"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--asset-mode", choices=("auto", "final-quality", "fast-validation"), default="auto")
    args = parser.parse_args()
    report = validate_assets(Path(args.run_root).resolve(), asset_mode=args.asset_mode)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
