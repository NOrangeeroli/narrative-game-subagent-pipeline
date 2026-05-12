#!/usr/bin/env python3
"""Generate background assets as a dedicated workflow stage.

This script handles script-callable providers. For IMAGE_PROVIDER=imagegen it
writes broker request files and returns a needs_imagegen status because Codex
image generation is a client-side tool, not a Python provider.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from asset_image_providers import generate_provider_images, resolve_provider_model
from asset_manifest_probe import probe_asset_manifest
from asset_motion_providers import generate_background_video
from asset_provenance import record_asset_result
from compile_rpg_manifest import compile_rpg_manifest
from export_boundary_previews import export_boundary_previews
from generate_rpg_boundaries_from_masks import generate_boundaries as generate_rpg_boundaries
from generate_assets import (
    build_background_prompt,
    build_rpg_asset_prompt,
    render_rpg_svg,
    remote_rpg_asset_shape,
    write_image_as_png,
    write_png_from_svg,
)
from pipeline_lib import Json, ensure_dir, load_optional_json, path_for, write_json, write_text
from validate_boundaries import validate as validate_boundaries


REMOTE_IMAGE_PROVIDER_ALIASES = {
    "ppio": "openai-ppioImage",
    "openai-ppioimage": "openai-ppioImage",
    "openai-ppioImage": "openai-ppioImage",
}

VIDEO_PROVIDER_ALIASES = {
    "ppio": "openai_I2V_PPIO",
    "openai_i2v_ppio": "openai_I2V_PPIO",
    "openai-ppiovideo": "openai_I2V_PPIO",
    "openai-ppioVideo": "openai_I2V_PPIO",
    "none": "none",
    "skip": "none",
    "": "none",
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_background_env(run_root: Path, env_file: str | None) -> None:
    candidates: list[Path] = []
    if env_file:
        candidates.append(Path(env_file))
    candidates.extend([run_root / ".env", Path.cwd() / ".env"])
    for candidate in candidates:
        load_dotenv(candidate)


def normalize_image_provider(value: str | None) -> str:
    provider = (value or os.environ.get("BACKGROUND_IMAGE_PROVIDER") or os.environ.get("IMAGE_PROVIDER") or "local-svg").strip()
    return REMOTE_IMAGE_PROVIDER_ALIASES.get(provider.lower(), provider)


def normalize_video_provider(value: str | None) -> str:
    provider = (value or os.environ.get("BACKGROUND_VIDEO_PROVIDER") or os.environ.get("VIDEO_PROVIDER") or "none").strip()
    return VIDEO_PROVIDER_ALIASES.get(provider.lower(), provider)


def prompt_for_asset(asset: Json, manifest: Json) -> str:
    section = asset["section"]
    if section == "backgrounds":
        return build_background_prompt({"asset_id": asset["asset_id"], "spec": asset.get("spec", {})}, manifest)
    role = "map_asset" if section == "map_assets" else "battle_background"
    return build_rpg_asset_prompt({"asset_id": asset["asset_id"], "spec": asset.get("spec", {})}, role, manifest)


def output_path_for_asset(run_root: Path, asset: Json) -> Path:
    file_ref = asset.get("file_ref")
    if not isinstance(file_ref, str) or not file_ref:
        raise RuntimeError(f"Background asset {asset.get('asset_id')} is missing file_ref.")
    return run_root / "workspace" / "generated-assets" / file_ref


def write_local_svg(asset: Json, output_path: Path) -> list[str]:
    section = asset["section"]
    role = "background" if section == "backgrounds" else ("map_asset" if section == "map_assets" else "battle_background")
    source_svg = output_path.parents[2] / "sources" / f"{asset['asset_id']}.svg"
    return write_png_from_svg(render_rpg_svg({"asset_id": asset["asset_id"], "spec": asset.get("spec", {})}, role), output_path, source_svg)


def imagegen_request(run_root: Path, asset: Json, prompt: str, output_path: Path) -> Path:
    request_path = run_root / "workspace" / "generated-assets" / "imagegen-requests" / f"{asset['asset_id']}.json"
    write_json(request_path, {
        "asset_id": asset["asset_id"],
        "asset_kind": asset["background_type"],
        "prompt": prompt,
        "output_file": str(output_path.relative_to(run_root)),
        "note": "Codex agent must call image_gen, save/copy the generated image to output_file, then rerun postprocessing/provenance.",
    })
    return request_path


def generate_static_image(
    *,
    run_root: Path,
    manifest: Json,
    asset: Json,
    provider: str,
    model: str | None,
    overwrite: bool,
) -> Json:
    output_path = output_path_for_asset(run_root, asset)
    prompt = prompt_for_asset(asset, manifest)
    prompt_path = run_root / "workspace" / "generated-assets" / "prompts" / f"{asset['asset_id']}.txt"
    write_text(prompt_path, prompt + "\n")
    requested_provider = provider

    if output_path.exists() and not overwrite:
        final_provider = {
            "imagegen": "imagegen",
            "openai-ppioImage": "ppio-image",
            "local-svg": "local-svg",
            "local_svg": "local-svg",
        }.get(provider, str(asset.get("existing_provider") or "existing"))
        return {
            "asset_id": asset["asset_id"],
            "asset_kind": asset["background_type"],
            "requested_provider": requested_provider,
            "final_provider": final_provider,
            "status": "success",
            "output_file": str(output_path.relative_to(run_root)),
            "prompt_ref": str(prompt_path.relative_to(run_root)),
            "notes": [f"used existing static background as {final_provider}"],
        }

    if provider == "imagegen":
        request_path = imagegen_request(run_root, asset, prompt, output_path)
        return {
            "asset_id": asset["asset_id"],
            "asset_kind": asset["background_type"],
            "requested_provider": "imagegen",
            "final_provider": "imagegen",
            "status": "needs_imagegen",
            "output_file": str(output_path.relative_to(run_root)),
            "prompt_ref": str(prompt_path.relative_to(run_root)),
            "request_ref": str(request_path.relative_to(run_root)),
            "notes": ["imagegen requires Codex agent tool execution"],
        }

    try:
        if provider in {"openai-ppioImage"}:
            role = "background" if asset["section"] == "backgrounds" else ("map_asset" if asset["section"] == "map_assets" else "battle_background")
            image_type, aspect_ratio = ("background", "16:9") if role == "background" else remote_rpg_asset_shape(role)
            images = generate_provider_images(
                provider=provider,
                model=model,
                asset_id=str(asset["asset_id"]),
                output_root=run_root / "workspace" / "generated-assets",
                prompt=prompt,
                image_type=image_type,
                aspect_ratio=aspect_ratio,
                expected_count=1,
            )
            if not images:
                raise RuntimeError("provider returned no images")
            notes = write_image_as_png(output_path, images[0])
            final_provider = "ppio-image"
        elif provider in {"local-svg", "local_svg"}:
            notes = write_local_svg(asset, output_path)
            final_provider = "local-svg"
        else:
            raise RuntimeError(f"Unsupported IMAGE_PROVIDER for background workflow: {provider}")
        return {
            "asset_id": asset["asset_id"],
            "asset_kind": asset["background_type"],
            "requested_provider": requested_provider,
            "final_provider": final_provider,
            "status": "success",
            "model": resolve_provider_model(provider, model) if provider == "openai-ppioImage" else None,
            "output_file": str(output_path.relative_to(run_root)),
            "prompt_ref": str(prompt_path.relative_to(run_root)),
            "notes": notes,
        }
    except Exception as exc:  # noqa: BLE001
        notes = write_local_svg(asset, output_path)
        return {
            "asset_id": asset["asset_id"],
            "asset_kind": asset["background_type"],
            "requested_provider": requested_provider,
            "final_provider": "local-svg",
            "status": "success",
            "output_file": str(output_path.relative_to(run_root)),
            "prompt_ref": str(prompt_path.relative_to(run_root)),
            "error": str(exc),
            "notes": [*notes, "fell back to local-svg static background"],
        }


def generate_video_if_enabled(run_root: Path, asset: Json, static_result: Json, provider: str, overwrite: bool) -> Json | None:
    if provider == "none" or static_result.get("status") != "success":
        return None
    source_path = run_root / str(static_result["output_file"])
    output_path = run_root / "workspace" / "generated-assets" / "generated" / "videos" / f"bgv.{asset['asset_id']}.loop.mp4"
    if output_path.exists() and not overwrite:
        return {
            "provider": "openai_I2V_PPIO" if provider == "openai_I2V_PPIO" else "existing-video",
            "output_file": str(output_path.relative_to(run_root)),
            "notes": ["skipped existing dynamic background"],
        }
    prompt = " ".join([
        f"Create a seamless looping background video from {asset['asset_id']}.",
        "Animate only subtle environmental motion.",
        "Keep camera locked, preserve all gameplay paths and terrain boundaries.",
        "No characters, no UI, no labels, no readable text.",
    ])
    video = {
        "asset_id": f"bgv.{asset['asset_id']}.loop",
        "kind": "background_video",
        "spec": {"prompt": prompt},
    }
    try:
        result = generate_background_video(
            provider=provider,
            video=video,
            source_path=source_path,
            output_path=output_path,
            run_root=run_root,
        )
        result["output_file"] = str(output_path.relative_to(run_root))
        return result
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "video-failed",
            "error": str(exc),
            "notes": ["kept static image as runtime background"],
        }


def selected_assets(probe: Json, scope: str) -> list[Json]:
    assets = [asset for asset in probe.get("background_assets", []) if isinstance(asset, dict)]
    if scope == "all":
        return assets
    return [asset for asset in assets if asset.get("scope") == scope]


def generate_backgrounds(
    *,
    run_root: Path,
    scope: str,
    image_provider: str | None,
    video_provider: str | None,
    image_model: str | None,
    overwrite: bool,
    env_file: str | None,
) -> Json:
    load_background_env(run_root, env_file)
    manifest = load_optional_json(path_for(run_root, "asset_manifest")) or {}
    probe = probe_asset_manifest(run_root)
    assets = selected_assets(probe, scope)
    provider = normalize_image_provider(image_provider)
    video = normalize_video_provider(video_provider)
    entries: list[Json] = []
    static_entries: list[tuple[Json, Json]] = []
    status = "pass"

    for asset in assets:
        static_result = generate_static_image(
            run_root=run_root,
            manifest=manifest,
            asset=asset,
            provider=provider,
            model=image_model,
            overwrite=overwrite,
        )
        if static_result["status"] == "needs_imagegen":
            status = "needs_imagegen"
            entries.append(static_result)
            record_asset_result(run_root, static_result)
            continue
        static_entries.append((asset, static_result))
        entries.append(static_result)
        record_asset_result(run_root, static_result)

    boundary_report = None
    boundary_validation_report = None
    if status == "pass" and scope in ("rpg", "all") and any(asset.get("scope") == "rpg" for asset in assets):
        try:
            boundary_report = generate_rpg_boundaries(run_root=run_root, provider=provider, env_file=env_file, overwrite=overwrite)
            if boundary_report.get("status") == "needs_boundary_imagegen":
                status = "needs_boundary_imagegen"
            elif boundary_report.get("status") == "fail":
                status = "fail"
            else:
                _, compile_report = compile_rpg_manifest(run_root)
                if compile_report.get("status") == "fail":
                    status = "fail"
                    boundary_validation_report = {"status": "fail", "stage": "compile_rpg_manifest", "report": compile_report}
                else:
                    preview_report = export_boundary_previews(run_root)
                    validation_report = validate_boundaries(run_root)
                    boundary_report = {**boundary_report, "preview_report": preview_report}
                    boundary_validation_report = validation_report
                    if validation_report.get("status") == "fail":
                        status = "fail"
        except Exception as exc:  # noqa: BLE001
            status = "fail"
            boundary_report = {"status": "fail", "error": str(exc)}

    if status == "pass":
        video_entries: list[Json] = []
        for asset, static_result in static_entries:
            video_result = generate_video_if_enabled(run_root, asset, static_result, video, overwrite)
            final_result = dict(static_result)
            if video_result and video_result.get("provider") not in (None, "video-failed"):
                final_result["final_provider"] = "ppio-video" if video_result.get("provider") == "openai_I2V_PPIO" else str(video_result.get("provider"))
                final_result["video"] = video_result
                final_result["output_file"] = video_result.get("output_file", final_result["output_file"])
                final_result["static_file"] = static_result.get("output_file")
            elif video_result:
                final_result["video"] = video_result
            record_asset_result(run_root, final_result)
            video_entries.append(final_result)
        entries = video_entries

    elif status != "needs_imagegen":
        for _, static_result in static_entries:
            record_asset_result(run_root, static_result)

    if status == "pass" and boundary_report is None and scope in ("rpg", "all") and any(asset.get("scope") == "rpg" for asset in assets):
        try:
            boundary_report = export_boundary_previews(run_root)
        except Exception as exc:  # noqa: BLE001
            if status == "pass":
                status = "fail"
            boundary_report = {"status": "fail", "error": str(exc)}

    report = {
        "status": status,
        "scope": scope,
        "image_provider": provider,
        "video_provider": video,
        "background_count": len(assets),
        "entries": entries,
        "boundary_report": boundary_report,
        "boundary_validation_report": boundary_validation_report,
    }
    report_name = {
        "rpg": "rpg-background-generation-report.json",
        "vn": "vn-background-generation-report.json",
        "all": "background-generation-report.json",
    }[scope]
    write_json(run_root / "reports" / report_name, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--scope", choices=("rpg", "vn", "all"), default="all")
    parser.add_argument("--image-provider", default=None)
    parser.add_argument("--video-provider", default=None)
    parser.add_argument("--image-model", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = generate_backgrounds(
        run_root=Path(args.run_root).resolve(),
        scope=args.scope,
        image_provider=args.image_provider,
        video_provider=args.video_provider,
        image_model=args.image_model,
        overwrite=args.overwrite,
        env_file=args.env_file,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] in ("fail", "needs_imagegen", "needs_boundary_imagegen"):
        raise SystemExit(2 if report["status"] in ("needs_imagegen", "needs_boundary_imagegen") else 1)


if __name__ == "__main__":
    main()
