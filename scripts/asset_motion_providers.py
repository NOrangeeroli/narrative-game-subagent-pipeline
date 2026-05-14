#!/usr/bin/env python3
"""Small motion-asset providers for RPG runtime media."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from pipeline_lib import Json, ensure_dir
from asset_image_providers import (
    append_asset_log_event,
    parse_json_env,
    parse_json_or_throw,
    redact_headers,
    request_text,
    timestamp,
)


MOCK_MP4_BYTES = base64.b64decode(
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAGbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAB9AAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAACF0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAA+gAAAAAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAgAAAAAAACRlZHRzAAAAHGVsc3QAAAAAAAAAAQAAB9AAAAQAAAABAAAAAAKFbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAyAAAAMgBVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABf21pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAT9zdGJsAAAAr3N0c2QAAAAAAAAAAQAAAJ9hdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAgACABIAAAASAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGP//AAAANWF2Y0MBQsAf/+EAGGdkAB6s2UFB+//AwAAAMAAAMAAAwDxHixckAQAGaOvjyyLA/fj4AAAAABBwYXNwAAAAAQAAAAEAAAAUc3R0cwAAAAAAAAABAAAAAQAABAAAAAAUc3RzcwAAAAAAAAABAAAAAQAAABRzdHN6AAAAAAAAAAAAAAABAAAB7AAAABRzdGNvAAAAAAAAAAEAAAC0AAAAZG1kYXQAAAAAAGXxHgAN//8AAAAAAA=="
)
PPIO_VIDEO_DEFAULT_BASE_URL = "https://api.ppio.com/v3/async"
PPIO_I2V_DEFAULT_MODEL = "veo-3.1-fast-generate-firstlastframe"
PPIO_ASYNC_TASK_RESULT_ENDPOINT = "https://api.ppio.com/v3/async/task-result"
I2V_CANONICAL_FRAME_SIZE = (1280, 720)
DEFAULT_LOOP_NEGATIVE_PROMPT = (
    "camera movement, zoom, pan, cuts, scene transition, text, watermark, logo, "
    "new characters, terrain warping, layout changes, first last frame mismatch, "
    "black bars, letterbox, pillarbox, side padding"
)


def write_tiny_animated_gif(output_path: Path) -> list[str]:
    """Write a valid transparent animated GIF without external image tools.

    This is the deterministic local fallback. Real providers can write richer
    GIFs through provider_hints or future API implementations while preserving
    the same manifest contract.
    """
    ensure_dir(output_path.parent)
    output_path.write_bytes(
        b"GIF89a"
        b"\x01\x00\x01\x00\x80\x00\x00"
        b"\x00\x00\x00\xff\xff\xff"
        b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
        b"\x21\xf9\x04\x09\x0a\x00\x00\x00"
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00"
        b"\x21\xf9\x04\x09\x0a\x00\x00\x00"
        b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00"
        b"\x3b"
    )
    return ["wrote local transparent animated gif fallback"]


def generate_character_gif(
    *,
    provider: str,
    motion: Json,
    source_path: Path,
    output_path: Path,
    run_root: Path | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    provider_id = provider or "local-gif"
    if provider_id == "provider-hint":
        hint = _first_existing_hint(motion, run_root)
        if hint:
            ensure_dir(output_path.parent)
            shutil.copy2(hint, output_path)
            notes.append(f"copied provider_hints source {hint}")
        else:
            notes.extend(write_tiny_animated_gif(output_path))
            provider_id = "local-gif"
    elif provider_id in {"local-gif", "mock", "none"}:
        notes.extend(write_tiny_animated_gif(output_path))
    else:
        notes.extend(write_tiny_animated_gif(output_path))
        notes.append(f"provider {provider_id} is not implemented locally; used fallback")
        provider_id = f"{provider_id}+local-gif-fallback"
    if source_path.exists():
        notes.append(f"source_image={source_path}")
    return {"provider": provider_id, "model": "local-motion-gif", "notes": notes}


def generate_background_video(
    *,
    provider: str,
    video: Json,
    source_path: Path,
    output_path: Path,
    run_root: Path | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    provider_id = provider or "mock"
    if provider_id == "provider-hint":
        hint = _first_existing_hint(video, run_root)
        if hint:
            ensure_dir(output_path.parent)
            shutil.copy2(hint, output_path)
            notes.append(f"copied provider_hints source {hint}")
        else:
            provider_id = "mock"
            notes.append("provider_hints missing; used mock video fallback")
    if provider_id in {"openai_I2V_PPIO", "ppio-i2v", "openai-ppioVideo"}:
        prompt = str((video.get("spec") if isinstance(video.get("spec"), dict) else {}).get("prompt") or "")
        return generate_ppio_i2v_video(
            video=video,
            prompt=prompt,
            source_path=source_path,
            output_path=output_path,
        )
    if provider_id in {"mock", "local-mp4", "none"}:
        ensure_dir(output_path.parent)
        output_path.write_bytes(MOCK_MP4_BYTES)
        notes.append("wrote mock mp4 background loop")
    elif provider_id != "provider-hint":
        ensure_dir(output_path.parent)
        output_path.write_bytes(MOCK_MP4_BYTES)
        notes.append(f"provider {provider_id} is not implemented locally; used mock mp4 fallback")
        provider_id = f"{provider_id}+mock-fallback"
    if source_path.exists():
        notes.append(f"source_image={source_path}")
    return {"provider": provider_id, "model": "mock-video-provider", "notes": notes}


def generate_ppio_i2v_video(*, video: Json, prompt: str, source_path: Path, output_path: Path) -> dict[str, Any]:
    api_key = os.environ.get("I2V_API_KEY") or os.environ.get("VIDEO_API_KEY") or os.environ.get("PPIO_API_KEY")
    if not api_key:
        raise RuntimeError("PPIO I2V video generation requires I2V_API_KEY, VIDEO_API_KEY, or PPIO_API_KEY.")
    if not source_path.exists():
        raise RuntimeError(f"PPIO I2V source image is missing: {source_path}")
    model = os.environ.get("I2V_MODEL") or os.environ.get("VIDEO_MODEL") or PPIO_I2V_DEFAULT_MODEL
    base_url = os.environ.get("I2V_BASE_URL") or os.environ.get("VIDEO_BASE_URL") or PPIO_VIDEO_DEFAULT_BASE_URL
    url = build_endpoint_url(base_url, model)
    prepared_source_path = prepare_i2v_source_frame(source_path, output_path)
    source_image = image_data_url(prepared_source_path)
    payload = configure_ppio_video_payload(build_i2v_payload(model=model, prompt=prompt, source_image=source_image))
    asset_id = str(video.get("asset_id") or "background_video")
    output_root = output_path.parents[2] if len(output_path.parents) >= 3 else output_path.parent
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "openai_I2V_PPIO",
        "phase": "request",
        "context": {"assetKey": asset_id, "assetType": "video", "operation": "video.generate"},
        "url": url,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": redact_video_payload(payload),
    })
    status, response_headers, response_body = request_text(url, headers=headers, payload=payload)
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "openai_I2V_PPIO",
        "phase": "response",
        "context": {"assetKey": asset_id, "assetType": "video", "operation": "video.generate"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    if status < 200 or status >= 300:
        raise RuntimeError(f"PPIO I2V video generation failed ({status}): {response_body}")
    payload_response = parse_json_or_throw(response_body, "PPIO I2V video generation")
    if has_task_id(payload_response):
        payload_response = poll_ppio_video_task(
            task_id=extract_task_id(payload_response),
            api_key=api_key,
            output_root=output_root,
            asset_id=asset_id,
        )
    video_url = first_video_url(payload_response)
    if not video_url:
        raise RuntimeError("PPIO I2V response found no downloadable videos[].video_url/url field.")
    saved = download_video_file(video_url, output_path)
    return {
        "provider": "openai_I2V_PPIO",
        "model": model,
        "notes": [
            f"mime_type={saved['mime_type']}",
            f"bytes={saved['bytes']}",
            "downloaded provider video URL",
            f"source_image={source_path}",
            f"i2v_source_frame={prepared_source_path}",
        ],
    }


def build_endpoint_url(base_url: str, endpoint_or_model: str) -> str:
    endpoint = endpoint_or_model.strip().strip("/")
    base = base_url.rstrip("/")
    if endpoint.startswith(("http://", "https://")):
        return endpoint
    if base.lower().endswith(f"/{endpoint.lower()}"):
        return base
    return f"{base}/{urllib.parse.quote(endpoint)}"


def image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def prepare_i2v_source_frame(source_path: Path, output_path: Path) -> Path:
    if parse_bool_env("I2V_DISABLE_FRAME_PREP", False):
        return source_path
    target_width = int(float(os.environ.get("I2V_FRAME_WIDTH") or os.environ.get("VIDEO_FRAME_WIDTH") or I2V_CANONICAL_FRAME_SIZE[0]))
    target_height = int(float(os.environ.get("I2V_FRAME_HEIGHT") or os.environ.get("VIDEO_FRAME_HEIGHT") or I2V_CANONICAL_FRAME_SIZE[1]))
    frame_root = output_path.parents[2] if len(output_path.parents) >= 3 else output_path.parent
    frame_dir = frame_root / "intermediate" / "i2v-source-frames"
    ensure_dir(frame_dir)
    prepared_path = frame_dir / f"{source_path.stem}.i2v-{target_width}x{target_height}.png"
    with Image.open(source_path) as source:
        image = source.convert("RGB")
    if image.size == (target_width, target_height):
        image.save(prepared_path)
        return prepared_path

    target_ratio = target_width / target_height
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        fill_height = target_height
        fill_width = round(fill_height * source_ratio)
    else:
        fill_width = target_width
        fill_height = round(fill_width / source_ratio)
    fill = image.resize((fill_width, fill_height), Image.Resampling.LANCZOS)
    left = max(0, (fill_width - target_width) // 2)
    top = max(0, (fill_height - target_height) // 2)
    fill = fill.crop((left, top, left + target_width, top + target_height))
    fill = fill.filter(ImageFilter.GaussianBlur(radius=24))
    fill = fill.point(lambda value: int(value * 0.82))

    if source_ratio > target_ratio:
        contain_width = target_width
        contain_height = round(contain_width / source_ratio)
    else:
        contain_height = target_height
        contain_width = round(contain_height * source_ratio)
    foreground = image.resize((contain_width, contain_height), Image.Resampling.LANCZOS)
    x = (target_width - contain_width) // 2
    y = (target_height - contain_height) // 2
    fill.paste(foreground, (x, y))
    fill.save(prepared_path)
    return prepared_path


def build_i2v_payload(*, model: str, prompt: str, source_image: str) -> dict[str, Any]:
    normalized_model = model.lower()
    loop_prompt = ensure_loop_prompt(prompt)
    if "veo-3.1-fast-generate-firstlastframe" in normalized_model or "firstlastframe" in normalized_model:
        payload: dict[str, Any] = {
            "image": source_image,
            "last_image": source_image,
            "prompt": loop_prompt,
            "resolution": os.environ.get("I2V_RESOLUTION") or os.environ.get("VIDEO_RESOLUTION") or "720p",
            "aspect_ratio": os.environ.get("I2V_ASPECT_RATIO") or os.environ.get("VIDEO_ASPECT_RATIO") or "16:9",
            "sample_count": int(float(os.environ.get("I2V_SAMPLE_COUNT") or os.environ.get("VIDEO_SAMPLE_COUNT") or "1")),
            "duration_seconds": int(float(os.environ.get("I2V_DURATION_SECONDS") or os.environ.get("VIDEO_DURATION_SECONDS") or "4")),
            "generate_audio": parse_bool_env("I2V_GENERATE_AUDIO", parse_bool_env("VIDEO_GENERATE_AUDIO", False)),
            "person_generation": os.environ.get("I2V_PERSON_GENERATION")
            or os.environ.get("VIDEO_PERSON_GENERATION")
            or "disallow",
            "negative_prompt": os.environ.get("I2V_NEGATIVE_PROMPT")
            or os.environ.get("VIDEO_NEGATIVE_PROMPT")
            or DEFAULT_LOOP_NEGATIVE_PROMPT,
        }
        enhance_prompt = os.environ.get("I2V_ENHANCE_PROMPT") or os.environ.get("VIDEO_ENHANCE_PROMPT")
        if enhance_prompt is not None:
            payload["enhance_prompt"] = parse_bool_text(enhance_prompt)
        return payload
    if "seedance-v1.5-pro-i2v" in model.lower():
        return {
            "fps": 24,
            "image": source_image,
            "ratio": "16:9",
            "prompt": loop_prompt,
            "duration": 5,
            "watermark": False,
            "resolution": "720p",
            "camera_fixed": True,
            "generate_audio": False,
        }
    if "kling-v3.0-pro-i2v" in normalized_model:
        return {"prompt": loop_prompt, "image": source_image}
    if "startend2video" in normalized_model or "vidu-q2-pro-startend2video" in normalized_model:
        return {"prompt": loop_prompt, "images": [source_image, source_image], "n": 1}
    return {"prompt": loop_prompt, "image": source_image, "n": 1}


def ensure_loop_prompt(prompt: str) -> str:
    base = prompt.strip() or "subtle animated environmental game background"
    loop_guard = (
        "Use the supplied image as both the first and last frame. "
        "Create a seamless continuous loop with identical start and end composition, "
        "locked camera, and only subtle environmental motion. "
        "The frame is already a complete 16:9 game background; fill it edge to edge with no black bars, no letterbox, and no pillarbox."
    )
    if "seamless" in base.lower() and "loop" in base.lower():
        return base
    return f"{base}\n{loop_guard}"


def parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return parse_bool_text(raw_value)


def parse_bool_text(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def configure_ppio_video_payload(payload: dict[str, Any]) -> dict[str, Any]:
    extra = parse_json_env("I2V_EXTRA_PARAMS", None)
    if extra is None:
        extra = parse_json_env("VIDEO_EXTRA_PARAMS", {})
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key != "expected_count":
                payload[key] = value
        count = extra.get("expected_count")
        if isinstance(count, int) and count > 0 and "n" in payload:
            payload["n"] = count
    rules = parse_json_env("I2V_REWRITE_RULES", None)
    if rules is None:
        rules = parse_json_env("VIDEO_REWRITE_RULES", {})
    if isinstance(rules, dict):
        apply_rewrite_rules(payload, rules)
    return payload


def poll_ppio_video_task(*, task_id: str, api_key: str, output_root: Path, asset_id: str) -> Any:
    endpoint = os.environ.get("I2V_TASK_RESULT_ENDPOINT") or os.environ.get("VIDEO_TASK_RESULT_ENDPOINT") or PPIO_ASYNC_TASK_RESULT_ENDPOINT
    poll_interval_ms = int(float(os.environ.get("I2V_TASK_POLL_INTERVAL_MS") or os.environ.get("VIDEO_TASK_POLL_INTERVAL_MS") or "3000"))
    max_polls = int(float(os.environ.get("I2V_TASK_MAX_POLLS") or os.environ.get("VIDEO_TASK_MAX_POLLS") or "120"))
    url = f"{endpoint}?task_id={urllib.parse.quote(task_id)}"
    headers = {"Authorization": f"Bearer {api_key}"}
    for _ in range(max_polls):
        append_asset_log_event(output_root, asset_id, {
            "timestamp": timestamp(),
            "provider": "openai_I2V_PPIO",
            "phase": "request",
            "context": {"assetKey": asset_id, "assetType": "video_task", "operation": "task-result.poll"},
            "url": url,
            "method": "GET",
            "headers": redact_headers(headers),
        })
        status, response_headers, response_body = request_text(url, headers=headers, payload=None, method="GET")
        append_asset_log_event(output_root, asset_id, {
            "timestamp": timestamp(),
            "provider": "openai_I2V_PPIO",
            "phase": "response",
            "context": {"assetKey": asset_id, "assetType": "video_task", "operation": "task-result.poll"},
            "status": status,
            "headers": response_headers,
            "body": response_body,
        })
        if status < 200 or status >= 300:
            raise RuntimeError(f"PPIO I2V task-result query failed ({status}): {response_body}")
        payload = parse_json_or_throw(response_body, "PPIO I2V task-result")
        if first_video_url(payload):
            return payload
        task_status = get_task_status(payload)
        if task_status and any(token in task_status.upper() for token in ("FAIL", "ERROR", "REJECT")):
            raise RuntimeError(f"PPIO I2V async task failed ({task_status}): {get_task_reason(payload)}")
        time.sleep(poll_interval_ms / 1000)
    raise RuntimeError(f"PPIO I2V async task timed out after {max_polls} polls: {task_id}")


def download_video_file(url: str, output_path: Path) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "narrative-game-asset-pipeline/1.0"}, method="GET")
    timeout = int(float(os.environ.get("VIDEO_HTTP_TIMEOUT_MS") or os.environ.get("IMAGE_HTTP_TIMEOUT_MS") or "90000")) / 1000
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - generated provider URL
        data = response.read()
        ensure_dir(output_path.parent)
        output_path.write_bytes(data)
        return {"mime_type": response.headers.get("content-type", "video/mp4"), "bytes": len(data)}


def first_video_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    videos = payload.get("videos")
    if not isinstance(videos, list):
        return None
    for video in videos:
        if isinstance(video, str) and video:
            return video
        if isinstance(video, dict):
            candidate = video.get("video_url") or video.get("url")
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def has_task_id(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and (
            (isinstance(payload.get("task_id"), str) and bool(payload["task_id"].strip()))
            or (isinstance(payload.get("id"), str) and bool(payload["id"].strip()))
        )
    )


def extract_task_id(payload: Any) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("task_id"), str) and payload["task_id"].strip():
        return payload["task_id"].strip()
    if isinstance(payload, dict) and isinstance(payload.get("id"), str) and payload["id"].strip():
        return payload["id"].strip()
    raise RuntimeError("PPIO async video response does not contain task_id.")


def get_task_status(payload: Any) -> str | None:
    if isinstance(payload, dict):
        task = payload.get("task")
        if isinstance(task, dict) and isinstance(task.get("status"), str):
            return task["status"]
        if isinstance(payload.get("status"), str):
            return payload["status"]
    return None


def get_task_reason(payload: Any) -> str:
    if isinstance(payload, dict):
        task = payload.get("task")
        if isinstance(task, dict) and isinstance(task.get("reason"), str):
            return task["reason"]
        if isinstance(payload.get("reason"), str):
            return payload["reason"]
    return "unknown reason"


def apply_rewrite_rules(payload: dict[str, Any], rules: dict[str, Any]) -> None:
    for path, value in (rules.get("set") or {}).items():
        set_path(payload, str(path), value)
    for path in (rules.get("unset") or []) + (rules.get("delete") or []):
        delete_path(payload, str(path))
    for to_path, from_path in (rules.get("copy") or {}).items():
        value = get_path(payload, str(from_path))
        if value is not None:
            set_path(payload, str(to_path), value)
    for to_path, from_path in {**(rules.get("move") or {}), **(rules.get("rename") or {})}.items():
        value = get_path(payload, str(from_path))
        if value is not None:
            set_path(payload, str(to_path), value)
            delete_path(payload, str(from_path))


def get_path(root: Any, path: str) -> Any:
    current = root
    for segment in path.split("."):
        if isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current


def set_path(root: dict[str, Any], path: str, value: Any) -> None:
    current = root
    parts = path.split(".")
    for segment in parts[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[parts[-1]] = value


def delete_path(root: dict[str, Any], path: str) -> None:
    current = root
    parts = path.split(".")
    for segment in parts[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            return
        current = next_value
    current.pop(parts[-1], None)


def redact_video_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: redact_video_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_video_payload(item) for item in payload]
    if isinstance(payload, str) and payload.startswith("data:image/") and len(payload) > 256:
        return f"<base64 image data: {len(payload)} chars>"
    return payload


def _first_existing_hint(asset: Json, run_root: Path | None = None) -> Path | None:
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    for raw_hint in spec.get("provider_hints") or asset.get("provider_hints") or []:
        if not isinstance(raw_hint, str):
            continue
        hint = Path(raw_hint)
        if not hint.is_absolute() and run_root is not None:
            hint = run_root / hint
        if hint.exists() and hint.is_file():
            return hint
    return None
