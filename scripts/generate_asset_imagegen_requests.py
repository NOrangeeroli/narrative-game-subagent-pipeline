#!/usr/bin/env python3
"""Dispatch non-background visual assets to the built-in imagegen workflow.

This script does not call an external image API. It writes broker request files
for the Codex controller to fulfill with the built-in image_gen tool, then
records imagegen provenance once the requested files exist.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from asset_provenance import record_asset_result
from generate_assets import build_rpg_asset_prompt, sanitize_file_stem
from pipeline_lib import Json, as_list, ensure_dir, load_optional_json, path_for, write_json, write_text


REPORT_NAME = "asset-imagegen-dispatch-report.json"
REQUEST_ROOT = Path("imagegen-requests") / "assets"
SOURCE_ROOT = Path("generated") / "imagegen-source"

SECTION_ROLES: dict[str, str] = {
    "tilesets": "tileset",
    "sprites": "sprite",
    "enemy_sprites": "enemy_sprite",
    "item_icons": "item_icon",
    "skill_icons": "skill_icon",
    "equipment_icons": "equipment_icon",
    "rpg_ui": "rpg_ui",
    "ui": "ui",
}
BACKGROUND_SECTIONS = {"map_assets", "battle_backgrounds"}
TRANSPARENT_SECTIONS = {
    "sprites",
    "enemy_sprites",
    "item_icons",
    "skill_icons",
    "equipment_icons",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def rel(run_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(run_root))
    except ValueError:
        return str(path)


def output_path(run_root: Path, file_ref: Any) -> Path | None:
    if not isinstance(file_ref, str) or not file_ref.strip():
        return None
    return run_root / "workspace" / "generated-assets" / file_ref


def request_path(run_root: Path, asset_id: str) -> Path:
    return run_root / "workspace" / "generated-assets" / REQUEST_ROOT / f"{sanitize_file_stem(asset_id)}.json"


def source_path(run_root: Path, section: str, asset_id: str) -> Path:
    return (
        run_root
        / "workspace"
        / "generated-assets"
        / SOURCE_ROOT
        / sanitize_file_stem(section)
        / f"{sanitize_file_stem(asset_id)}.png"
    )


def provenance_provider(run_root: Path, asset_id: str) -> str:
    report = load_optional_json(run_root / "reports" / "asset-provenance-report.json") or {}
    for entry in as_list(report.get("assets")):
        if isinstance(entry, dict) and entry.get("asset_id") == asset_id:
            return str(entry.get("final_provider") or entry.get("provider") or "")
    return ""


def imagegen_output_ready(run_root: Path, asset_id: str, target: Path, request: Path, accept_existing: bool) -> bool:
    if not target.exists() or target.stat().st_size <= 0:
        return False
    if provenance_provider(run_root, asset_id) == "imagegen":
        return True
    return accept_existing


def chroma_helper() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return codex_home / "skills" / ".system" / "imagegen" / "scripts" / "remove_chroma_key.py"


def remove_chroma_key(source: Path, target: Path) -> list[str]:
    helper = chroma_helper()
    if not helper.exists():
        raise FileNotFoundError(f"Missing chroma-key helper: {helper}")
    ensure_dir(target.parent)
    subprocess.run([
        "python3",
        str(helper),
        "--input",
        str(source),
        "--out",
        str(target),
        "--auto-key",
        "border",
        "--soft-matte",
        "--transparent-threshold",
        "12",
        "--opaque-threshold",
        "220",
        "--despill",
        "--force",
    ], check=True)
    return ["removed #00ff00 chroma-key background"]


def transparent_prompt_suffix() -> str:
    return (
        "Create this asset on a perfectly flat solid #00ff00 chroma-key background for background removal. "
        "The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation. "
        "Keep the subject fully separated from the background with crisp edges and generous padding. "
        "Do not use #00ff00 anywhere in the subject. No cast shadow, no contact shadow, no reflection, no watermark, and no text unless explicitly requested."
    )


def asset_prompt(manifest: Json, entry: Json) -> str:
    section = str(entry["section"])
    asset = entry["asset"]
    role = str(entry["role"])
    if section in SECTION_ROLES:
        prompt = build_rpg_asset_prompt(asset, SECTION_ROLES.get(section, role), manifest)
    else:
        spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
        prompt = str(spec.get("description") or f"Create final-quality game asset {entry['asset_id']}.")
    if role == "sprite_animation":
        prompt = " ".join([
            prompt,
            "Create a 4x4 four-direction walking animation sheet. Rows must be down, left, right, up; each row has four centered frames with consistent feet alignment. No labels, no grid lines, no UI.",
        ])
    if entry["requires_chroma_key"]:
        prompt = f"{prompt} {transparent_prompt_suffix()}"
    return prompt


def collect_assets(manifest: Json) -> list[Json]:
    assets: list[Json] = []

    def add(section: str, asset: Json, role: str) -> None:
        asset_id = asset.get("asset_id")
        file_ref = asset.get("file_ref")
        if not isinstance(asset_id, str) or not asset_id or not isinstance(file_ref, str) or not file_ref:
            return
        assets.append({
            "asset_id": asset_id,
            "section": section,
            "role": role,
            "file_ref": file_ref,
            "asset": asset,
            "requires_chroma_key": section in TRANSPARENT_SECTIONS,
        })

    for section, role in SECTION_ROLES.items():
        if section in BACKGROUND_SECTIONS:
            continue
        for asset in as_list(manifest.get(section)):
            if isinstance(asset, dict):
                add(section, asset, str(asset.get("kind") or role))

    return assets


def dispatch_asset_imagegen_requests(
    run_root: Path,
    *,
    overwrite: bool = False,
    accept_existing: bool = False,
) -> Json:
    manifest = load_optional_json(path_for(run_root, "asset_manifest"))
    if not isinstance(manifest, dict):
        report = {
            "status": "fail",
            "issues": [{"code": "missing_manifest", "message": "Missing workspace/asset-manifest.json."}],
            "entries": [],
        }
        write_json(run_root / "reports" / REPORT_NAME, report)
        return report

    output_root = run_root / "workspace" / "generated-assets"
    entries: list[Json] = []
    issues: list[Json] = []
    section_entries: dict[str, list[Json]] = {}

    for item in collect_assets(manifest):
        asset_id = str(item["asset_id"])
        section = str(item["section"])
        target = output_path(run_root, item["file_ref"])
        if target is None:
            continue
        request = request_path(run_root, asset_id)
        source = source_path(run_root, section, asset_id)
        prompt = asset_prompt(manifest, item)
        prompt_ref = output_root / "prompts" / f"{sanitize_file_stem(asset_id)}.txt"
        write_text(prompt_ref, prompt + "\n")

        notes: list[str] = []
        processed_imagegen_source = False
        if item["requires_chroma_key"] and source.exists() and (overwrite or not target.exists() or source.stat().st_mtime > target.stat().st_mtime):
            try:
                notes.extend(remove_chroma_key(source, target))
                processed_imagegen_source = True
            except Exception as exc:  # noqa: BLE001
                issue = {
                    "asset_id": asset_id,
                    "section": section,
                    "status": "fail",
                    "code": "chroma_key_failed",
                    "message": str(exc),
                }
                entries.append(issue)
                issues.append(issue)
                section_entries.setdefault(section, []).append(issue)
                continue

        if processed_imagegen_source or (not overwrite and imagegen_output_ready(run_root, asset_id, target, request, accept_existing)):
            entry: Json = {
                "asset_id": asset_id,
                "asset_kind": item["role"],
                "section": section,
                "status": "success",
                "requested_provider": "imagegen",
                "final_provider": "imagegen",
                "output_file": rel(run_root, target),
                "prompt_ref": rel(run_root, prompt_ref),
                "notes": notes or ["found imagegen output"],
            }
            record_asset_result(run_root, entry)
        else:
            payload: Json = {
                "asset_id": asset_id,
                "asset_kind": item["role"],
                "section": section,
                "provider": "imagegen",
                "prompt": prompt,
                "output_file": rel(run_root, target),
                "prompt_ref": rel(run_root, prompt_ref),
                "requires_chroma_key_removal": bool(item["requires_chroma_key"]),
                "source_output_file": rel(run_root, source) if item["requires_chroma_key"] else None,
                "postprocess": "remove_chroma_key" if item["requires_chroma_key"] else None,
                "note": (
                    "Use the built-in image_gen tool. Save the result to source_output_file for chroma-key assets, "
                    "or output_file for opaque assets, then rerun run_pipeline.py dispatch-asset-imagegen."
                ),
            }
            write_json(request, payload)
            entry = {
                "asset_id": asset_id,
                "asset_kind": item["role"],
                "section": section,
                "status": "needs_asset_imagegen",
                "requested_provider": "imagegen",
                "final_provider": "imagegen",
                "request_ref": rel(run_root, request),
                "output_file": rel(run_root, target),
                "source_output_file": rel(run_root, source) if item["requires_chroma_key"] else None,
                "prompt_ref": rel(run_root, prompt_ref),
            }
        entries.append(entry)
        section_entries.setdefault(section, []).append(entry)

    status = "fail" if issues else ("needs_asset_imagegen" if any(entry.get("status") == "needs_asset_imagegen" for entry in entries) else "pass")
    report: Json = {
        "status": status,
        "generated_at": utc_now(),
        "provider": "imagegen",
        "entry_count": len(entries),
        "entries": entries,
        "issues": issues,
    }
    write_json(run_root / "reports" / REPORT_NAME, report)
    write_json(run_root / "reports" / "secondary-visual-assets-generation-report.json", report)
    for section, items in section_entries.items():
        write_json(run_root / "reports" / f"{sanitize_file_stem(section)}-generation-report.json", {
            "status": "pass" if all(item.get("status") == "success" for item in items) else status,
            "generated_at": utc_now(),
            "provider": "imagegen",
            "section": section,
            "entries": items,
        })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--accept-existing", action="store_true")
    args = parser.parse_args()
    report = dispatch_asset_imagegen_requests(
        Path(args.run_root).resolve(),
        overwrite=args.overwrite,
        accept_existing=args.accept_existing,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in {"fail", "needs_asset_imagegen"}:
        raise SystemExit(2 if report["status"] == "needs_asset_imagegen" else 1)


if __name__ == "__main__":
    main()
