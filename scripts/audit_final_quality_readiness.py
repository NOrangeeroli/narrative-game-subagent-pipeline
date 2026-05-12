#!/usr/bin/env python3
"""Audit whether a Web RPG run has final-quality asset completeness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_RUNTIME_PREFIXES = ("bgv.", "motion.", "voice.", "bgm.")
STANDARD_VISUAL_SECTIONS = (
    "map_assets",
    "sprites",
    "enemy_sprites",
    "battle_backgrounds",
    "item_icons",
    "skill_icons",
    "equipment_icons",
    "rpg_ui",
)
FINAL_VISUAL_PROVIDERS = {
    "imagegen",
    "ppio-image",
    "openai-ppioimage",
    "gemini",
    "sprite-forge",
}
VISUAL_GENERATION_REPORTS = (
    "rpg-background-generation-report.json",
    "rpg-map-assets-generation-report.json",
    "rpg-battle-backgrounds-generation-report.json",
    "secondary-visual-assets-generation-report.json",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_game_data(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if "=" not in raw:
        raise ValueError(f"{path} is not a game-data.js assignment")
    return json.loads(raw.split("=", 1)[1].rsplit(";", 1)[0])


def count_manifest_visual_assets(manifest: dict[str, Any]) -> int:
    total = 0
    for section in STANDARD_VISUAL_SECTIONS:
        value = manifest.get(section)
        if isinstance(value, list):
            total += len(value)
    return total


def final_visual_assets_from_reports(run_root: Path) -> list[str]:
    assets: list[str] = []
    for report_name in VISUAL_GENERATION_REPORTS:
        path = run_root / "reports" / report_name
        if not path.exists():
            continue
        try:
            payload = read_json(path)
        except Exception:
            continue
        for entry in payload.get("entries", []):
            if not isinstance(entry, dict):
                continue
            provider = str(entry.get("final_provider") or entry.get("provider") or "").strip().lower()
            if provider in FINAL_VISUAL_PROVIDERS and entry.get("status") in {None, "success", "generated"}:
                asset_id = entry.get("asset_id")
                if isinstance(asset_id, str) and asset_id:
                    assets.append(asset_id)
    provenance_path = run_root / "reports" / "asset-provenance-report.json"
    if provenance_path.exists():
        try:
            provenance = read_json(provenance_path)
        except Exception:
            provenance = {}
        for entry in provenance.get("assets", []):
            if not isinstance(entry, dict):
                continue
            provider = str(entry.get("final_provider") or entry.get("provider") or "").strip().lower()
            if provider in FINAL_VISUAL_PROVIDERS:
                asset_id = entry.get("asset_id")
                if isinstance(asset_id, str) and asset_id:
                    assets.append(asset_id)
    return sorted(set(assets))


def audit(run_root: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    asset_direction_path = run_root / "workspace" / "asset-direction.json"
    asset_manifest_path = run_root / "workspace" / "asset-manifest.json"
    game_data_path = run_root / "build" / "web-rpg" / "game-data.js"
    sprite_forge_root = run_root / "workspace" / "sprite-forge-assets"

    if not asset_direction_path.exists():
        issues.append("Missing workspace/asset-direction.json.")
        asset_directions: list[dict[str, Any]] = []
    else:
        payload = read_json(asset_direction_path)
        asset_directions = [item for item in payload.get("asset_directions", []) if isinstance(item, dict)]

    provider_hint_assets = [item.get("asset_id") for item in asset_directions if item.get("provider_hints")]
    report_backed_visual_assets = final_visual_assets_from_reports(run_root)
    checks["asset_direction_count"] = len(asset_directions)
    checks["provider_hint_count"] = len(provider_hint_assets)
    checks["provider_hint_assets"] = provider_hint_assets
    checks["report_backed_visual_asset_count"] = len(report_backed_visual_assets)
    checks["report_backed_visual_assets"] = report_backed_visual_assets
    if not provider_hint_assets and not report_backed_visual_assets:
        warnings.append("No provider_hints or final visual generation reports found; still visual art is likely local fallback.")

    if not asset_manifest_path.exists():
        issues.append("Missing workspace/asset-manifest.json.")
        manifest: dict[str, Any] = {}
    else:
        manifest = read_json(asset_manifest_path)
    checks["manifest_visual_asset_count"] = count_manifest_visual_assets(manifest)
    checks["voice_profile_count"] = len(manifest.get("voice_profiles", {})) if isinstance(manifest.get("voice_profiles"), dict) else 0

    if checks["manifest_visual_asset_count"] <= 0:
        issues.append("No visual RPG assets were planned in asset-manifest.json.")
    if checks["voice_profile_count"] <= 0:
        warnings.append("No voice_profiles found; character voices cannot be kept distinct through voice design.")

    if not game_data_path.exists():
        issues.append("Missing build/web-rpg/game-data.js.")
        game_data: dict[str, Any] = {}
    else:
        game_data = read_game_data(game_data_path)

    assets = game_data.get("assets", {}) if isinstance(game_data.get("assets"), dict) else {}
    runtime_counts = {prefix: len([key for key in assets if key.startswith(prefix)]) for prefix in REQUIRED_RUNTIME_PREFIXES}
    checks["runtime_counts"] = runtime_counts
    for prefix, count in runtime_counts.items():
        if count <= 0:
            issues.append(f"No exported runtime assets with prefix {prefix}")

    reports = {
        "asset_validation": run_root / "reports" / "asset-validation.json",
        "audio_coverage": run_root / "reports" / "audio-coverage-report.json",
        "boundary_validation": run_root / "reports" / "boundary-validation-report.json",
    }
    report_statuses: dict[str, str] = {}
    for name, path in reports.items():
        if not path.exists():
            warnings.append(f"Missing {path.relative_to(run_root)}.")
            report_statuses[name] = "missing"
            continue
        status = str(read_json(path).get("status") or "unknown")
        report_statuses[name] = status
        if status != "pass":
            issues.append(f"{path.relative_to(run_root)} status is {status}.")
    checks["report_statuses"] = report_statuses
    checks["sprite_forge_assets_present"] = sprite_forge_root.exists() and any(sprite_forge_root.rglob("*.*"))

    has_final_visual_evidence = bool(provider_hint_assets or report_backed_visual_assets)
    quality_status = "ready" if not issues and has_final_visual_evidence else "playable_but_not_final_quality"
    if issues:
        quality_status = "blocked"

    return {
        "status": "pass" if not issues else "fail",
        "quality_status": quality_status,
        "run_root": str(run_root),
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless quality_status is ready.")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    report = audit(run_root)
    write_json(run_root / "reports" / "final-quality-readiness-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "pass" or (args.strict and report["quality_status"] != "ready"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
