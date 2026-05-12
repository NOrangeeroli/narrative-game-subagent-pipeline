#!/usr/bin/env python3
"""Bind subagent-generated assets to an asset manifest.

This script is intentionally lightweight: it does not generate images, audio,
SVG placeholders, or mock files. It verifies that every manifest `file_ref`
already exists under `workspace/generated-assets/` and writes the standard
asset generation report consumed by the rest of the pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pipeline_lib import Json, load_optional_json, path_for, write_json


VISUAL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".flac"}
LEGACY_PLACEHOLDER_EXTENSIONS = {".svg"}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_provider_environment(run_root: Path, env_file: str | None = None) -> None:
    candidates: list[Path] = []
    if env_file:
        candidates.append(Path(env_file).expanduser())
    candidates.extend([run_root / ".env", Path.cwd() / ".env"])
    for candidate in candidates:
        load_dotenv(candidate)


def provider_snapshot() -> Json:
    keys = (
        "IMAGE_PROVIDER",
        "IMAGE_ASSET_PROVIDER",
        "BACKGROUND_IMAGE_PROVIDER",
        "VIDEO_PROVIDER",
        "AUDIO_PROVIDER",
        "AUDIO_ASSET_PROVIDER",
        "BGM_PROVIDER",
        "SFX_PROVIDER",
        "VOICE_PROVIDER",
    )
    return {key: os.environ[key] for key in keys if os.environ.get(key)}


def iter_manifest_assets(manifest: Any) -> list[Json]:
    assets: list[Json] = []
    seen: set[tuple[str, str]] = set()

    def add(asset_id: Any, file_ref: Any, manifest_path: str, role: str) -> None:
        if not isinstance(asset_id, str) or not isinstance(file_ref, str):
            return
        key = (asset_id, file_ref)
        if key in seen:
            return
        seen.add(key)
        assets.append({
            "asset_id": asset_id,
            "file_ref": file_ref,
            "manifest_path": manifest_path,
            "role": role,
        })

    def visit(value: Any, path: str, role: str) -> None:
        if isinstance(value, dict):
            add(value.get("asset_id"), value.get("file_ref"), path, role)
            add(value.get("canon_ref_asset_id"), value.get("canon_ref_file_ref"), path, "canon")
            for key, child in value.items():
                child_role = key if path == "$" else role
                visit(child, f"{path}.{key}", child_role)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]", role)

    visit(manifest, "$", "asset")
    return assets


def bind_generated_assets(run_root: Path, *, allow_svg: bool = False, env_file: str | None = None) -> Json:
    load_provider_environment(run_root, env_file)
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    output_root = run_root / "workspace" / "generated-assets"
    entries: list[Json] = []
    issues: list[Json] = []
    warnings: list[str] = []

    if not manifest:
        report = {
            "status": "fail",
            "mode": "bind-existing",
            "output_root": str(output_root),
            "entries": entries,
            "issues": [{"code": "missing_manifest", "message": "Missing workspace/asset-manifest.json."}],
            "warnings": warnings,
            "providers": provider_snapshot(),
        }
        write_json(path_for(run_root, "asset_generation_report"), report)
        return report

    for asset in iter_manifest_assets(manifest):
        asset_id = asset["asset_id"]
        file_ref = asset["file_ref"]
        target = output_root / file_ref
        suffix = target.suffix.lower()
        entry: Json = {
            "asset_id": asset_id,
            "file_ref": file_ref,
            "role": asset["role"],
            "manifest_path": asset["manifest_path"],
            "provider": "existing",
            "status": "bound" if target.exists() else "missing",
        }
        if target.exists():
            entry["bytes"] = target.stat().st_size
            entry["path"] = str(target)
        entries.append(entry)

        if not target.exists():
            issues.append({
                "asset_id": asset_id,
                "file_ref": file_ref,
                "code": "missing_file",
                "message": "Subagent-generated asset is missing; binder will not generate a placeholder.",
            })
            continue
        if target.stat().st_size <= 0:
            issues.append({
                "asset_id": asset_id,
                "file_ref": file_ref,
                "code": "empty_file",
                "message": "Generated asset file is empty.",
            })
        if suffix in LEGACY_PLACEHOLDER_EXTENSIONS and not allow_svg:
            issues.append({
                "asset_id": asset_id,
                "file_ref": file_ref,
                "code": "legacy_svg_placeholder",
                "message": "SVG visual placeholders are disabled for subagent asset binding.",
            })
        elif suffix not in VISUAL_EXTENSIONS and suffix not in AUDIO_EXTENSIONS:
            warnings.append(f"{asset_id} has an unrecognized extension: {suffix or '<none>'}.")

    report = {
        "status": "pass" if not issues else "fail",
        "mode": "bind-existing",
        "output_root": str(output_root),
        "entries": entries,
        "issues": issues,
        "warnings": warnings,
        "providers": provider_snapshot(),
    }
    write_json(path_for(run_root, "asset_generation_report"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--allow-svg", action="store_true")
    args = parser.parse_args()
    report = bind_generated_assets(Path(args.run_root).resolve(), allow_svg=args.allow_svg, env_file=args.env_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
