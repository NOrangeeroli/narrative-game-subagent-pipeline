#!/usr/bin/env python3
"""Export a Unity 2D side-scroller adventure project."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from adventure_schema import build_adventure_manifest, validate_adventure_artifacts
from pipeline_lib import copy_tree, load_optional_json, path_for, skill_root, write_json, write_text


def copy_adventure_assets(run_root: Path, project_root: Path, manifest: dict) -> list[str]:
    copied: list[str] = []
    asset_manifest = load_optional_json(path_for(run_root, "adventure_asset_manifest")) or load_optional_json(path_for(run_root, "asset_manifest")) or {}
    asset_root = project_root / "Assets" / "AdventureAssets"
    asset_root.mkdir(parents=True, exist_ok=True)
    for asset in manifest.get("assets", []):
        if not isinstance(asset, dict):
            continue
        runtime_path = asset.get("runtime_path")
        source = run_root / str(runtime_path) if isinstance(runtime_path, str) else None
        if source and source.exists() and source.is_file():
            destination = asset_root / source.name
            shutil.copy2(source, destination)
            copied.append(str(destination.relative_to(project_root)))
    for asset in asset_manifest.get("assets", []) if isinstance(asset_manifest, dict) else []:
        if not isinstance(asset, dict):
            continue
        runtime_path = asset.get("runtime_path") or asset.get("path")
        source = run_root / str(runtime_path) if isinstance(runtime_path, str) else None
        if source and source.exists() and source.is_file():
            destination = asset_root / source.name
            if not destination.exists():
                shutil.copy2(source, destination)
                copied.append(str(destination.relative_to(project_root)))
    return copied


def export_unity_adventure(run_root: Path) -> Path:
    validation = validate_adventure_artifacts(run_root, write_report=True)
    if validation.status == "fail":
        raise SystemExit(json.dumps(validation.to_json(), ensure_ascii=False, indent=2))
    manifest = build_adventure_manifest(run_root)
    project_root = run_root / "build" / "unity-adventure"
    copy_tree(skill_root() / "assets" / "unity-adventure-template", project_root)
    streaming = project_root / "Assets" / "StreamingAssets"
    streaming.mkdir(parents=True, exist_ok=True)
    write_text(streaming / "adventure-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    write_text(streaming / "adventure-runtime.json", json.dumps(manifest.get("unity_runtime", {}), ensure_ascii=False, indent=2))
    copied_assets = copy_adventure_assets(run_root, project_root, manifest)
    report = {
        "status": "exported",
        "project_root": str(project_root),
        "manifest": str((streaming / "adventure-manifest.json").relative_to(project_root)),
        "runtime_manifest": str((streaming / "adventure-runtime.json").relative_to(project_root)),
        "copied_assets": copied_assets,
        "notes": [
            "Generated project uses a manifest-driven Unity 2D side-scroller runtime.",
            "Compiling or platform packaging requires a local Unity Editor.",
        ],
    }
    write_json(path_for(run_root, "adventure_export_report"), report)
    return project_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    print(str(export_unity_adventure(Path(args.run_root).resolve())))


if __name__ == "__main__":
    main()
