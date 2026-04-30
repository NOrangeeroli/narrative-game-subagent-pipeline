#!/usr/bin/env python3
"""Image provider adapters for narrative-game-subagent-pipeline assets."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_dir, write_text


PPIO_IMAGE_DEFAULT_BASE_URL = "https://api.ppio.com/v3"
PPIO_IMAGE_DEFAULT_MODEL = "gpt-image-2-text-to-image"
PPIO_ASYNC_TASK_RESULT_ENDPOINT = "https://api.ppio.com/v3/async/task-result"
GEMINI_IMAGE_DEFAULT_MODEL = "gemini-2.5-flash-image"


@dataclass
class GeneratedImage:
    bytes: bytes
    mime_type: str


def resolve_provider_model(provider: str, model: str | None = None) -> str:
    if model:
        return model
    if provider == "gemini":
        return os.environ.get("GEMINI_IMAGE_MODEL") or os.environ.get("IMAGE_MODEL") or GEMINI_IMAGE_DEFAULT_MODEL
    if provider == "openai-ppioImage":
        return os.environ.get("IMAGE_MODEL") or PPIO_IMAGE_DEFAULT_MODEL
    if provider == "mock":
        return "mock-image-provider"
    return "deterministic-svg-v1"


def generate_provider_images(
    *,
    provider: str,
    model: str | None,
    asset_id: str,
    output_root: Path,
    prompt: str,
    image_type: str,
    aspect_ratio: str,
    expected_count: int = 1,
    reference_images: list[Path] | None = None,
) -> list[GeneratedImage]:
    if provider == "gemini":
        return generate_gemini_images(
            model=resolve_provider_model(provider, model),
            asset_id=asset_id,
            output_root=output_root,
            prompt=prompt,
            image_type=image_type,
            aspect_ratio=aspect_ratio,
            reference_images=reference_images,
        )
    if provider == "openai-ppioImage":
        return generate_ppio_images(
            model=resolve_provider_model(provider, model),
            asset_id=asset_id,
            output_root=output_root,
            prompt=prompt,
            image_type=image_type,
            aspect_ratio=aspect_ratio,
            expected_count=expected_count,
        )
    raise ValueError(f"Provider {provider} is not a remote image provider.")


def generate_gemini_images(
    *,
    model: str,
    asset_id: str,
    output_root: Path,
    prompt: str,
    image_type: str,
    aspect_ratio: str,
    reference_images: list[Path] | None = None,
) -> list[GeneratedImage]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini image generation requires GEMINI_API_KEY.")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent"
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for reference_image in reference_images or []:
        mime_type = mimetypes.guess_type(reference_image.name)[0] or "image/png"
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": base64.b64encode(reference_image.read_bytes()).decode("ascii"),
            },
        })
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": os.environ.get("GEMINI_IMAGE_SIZE", "1K"),
            },
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "gemini",
        "phase": "request",
        "context": {"assetKey": asset_id, "assetType": image_type, "operation": "image.generate"},
        "url": endpoint,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": redact_image_payload(payload),
    })
    status, response_headers, response_body = request_text(endpoint, headers=headers, payload=payload)
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "gemini",
        "phase": "response",
        "context": {"assetKey": asset_id, "assetType": image_type, "operation": "image.generate"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    parsed = parse_json_or_throw(response_body, "Gemini image generation")
    if status < 200 or status >= 300:
        message = parsed.get("error", {}).get("message") if isinstance(parsed, dict) else None
        raise RuntimeError(message or f"Gemini image generation failed with status {status}.")
    images = []
    for candidate in parsed.get("candidates", []) if isinstance(parsed, dict) else []:
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []) if isinstance(content, dict) else []:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            mime_type = inline.get("mimeType") or inline.get("mime_type")
            if isinstance(data, str) and isinstance(mime_type, str):
                images.append(GeneratedImage(base64.b64decode(data), mime_type))
    if not images:
        feedback = parsed.get("promptFeedback", {}) if isinstance(parsed, dict) else {}
        raise RuntimeError(feedback.get("blockReasonMessage") or "Gemini returned no image data.")
    return images


def generate_ppio_images(
    *,
    model: str,
    asset_id: str,
    output_root: Path,
    prompt: str,
    image_type: str,
    aspect_ratio: str,
    expected_count: int,
) -> list[GeneratedImage]:
    api_key = os.environ.get("IMAGE_API_KEY")
    if not api_key:
        raise RuntimeError("PPIO image generation requires IMAGE_API_KEY.")
    endpoint = build_ppio_endpoint(model)
    payload = configure_ppio_payload({
        "prompt": prompt,
        "size": resolve_image_size(aspect_ratio),
        "quality": os.environ.get("IMAGE_QUALITY", "medium"),
        "n": resolve_expected_count(expected_count),
        "output_format": "png",
    })
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "openai-ppioImage",
        "phase": "request",
        "context": {"assetKey": asset_id, "assetType": image_type, "operation": "image.generate"},
        "url": endpoint,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": payload,
    })
    status, response_headers, response_body = request_text(endpoint, headers=headers, payload=payload)
    append_asset_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "openai-ppioImage",
        "phase": "response",
        "context": {"assetKey": asset_id, "assetType": image_type, "operation": "image.generate"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    if status < 200 or status >= 300:
        raise RuntimeError(f"PPIO image generation failed ({status}): {response_body}")
    return extract_ppio_images_from_text(response_body, api_key, asset_id, output_root)


def build_ppio_endpoint(endpoint_or_model: str) -> str:
    endpoint = endpoint_or_model.strip("/")
    base = (os.environ.get("IMAGE_BASE_URL") or PPIO_IMAGE_DEFAULT_BASE_URL).rstrip("/")
    base = base.removesuffix("/openai/v1").removesuffix("/openai")
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    known = ("gpt-image-2-text-to-image", "gpt-image-2-edit")
    for known_endpoint in known:
        if base.lower().endswith(f"/{known_endpoint}".lower()):
            return base[: -len(known_endpoint)] + endpoint
    if base.lower().endswith(f"/{endpoint}".lower()):
        return base
    return f"{base}/{endpoint}"


def extract_ppio_images_from_text(response_text: str, api_key: str, asset_id: str, output_root: Path) -> list[GeneratedImage]:
    payload = parse_json_or_throw(response_text, "PPIO image generation")
    response_mode = os.environ.get("IMAGE_RESPONSE_TYPE", "auto").strip()
    if response_mode == "task_id" or (response_mode == "auto" and isinstance(payload, dict) and isinstance(payload.get("task_id"), str)):
        payload = poll_ppio_task_result(str(payload["task_id"]), api_key, asset_id, output_root)
        return extract_images_array_payload(payload)
    if response_mode == "images_url":
        return extract_url_array_payload(payload)
    if response_mode in ("images_array", "auto"):
        if isinstance(payload, dict) and isinstance(payload.get("images"), list):
            images = payload["images"]
            if images and all(isinstance(item, str) or isinstance(item, dict) for item in images):
                if any(resolve_image_url_field(item) for item in images):
                    return extract_url_array_payload(payload)
            return extract_images_array_payload(payload)
    return extract_images_array_payload(payload)


def extract_images_array_payload(payload: Any) -> list[GeneratedImage]:
    images = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError("PPIO image generation returned no images.")
    outputs: list[GeneratedImage] = []
    for image in images:
        if isinstance(image, str):
            decoded = maybe_decode_data_url(image)
            outputs.append(GeneratedImage(decoded, "image/png") if decoded else download_image_bytes(image))
            continue
        if not isinstance(image, dict):
            continue
        b64_json = image.get("b64_json")
        if isinstance(b64_json, str):
            outputs.append(GeneratedImage(base64.b64decode(b64_json), "image/png"))
            continue
        image_url = resolve_image_url_field(image)
        if image_url:
            decoded = maybe_decode_data_url(image_url)
            outputs.append(GeneratedImage(decoded, "image/png") if decoded else download_image_bytes(image_url))
    if not outputs:
        raise RuntimeError("PPIO images array mode returned no usable image fields.")
    return outputs


def extract_url_array_payload(payload: Any) -> list[GeneratedImage]:
    images = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError("PPIO URL mode expects non-empty images array.")
    outputs: list[GeneratedImage] = []
    for image in images:
        image_url = resolve_image_url_field(image)
        if not image_url:
            continue
        decoded = maybe_decode_data_url(image_url)
        outputs.append(GeneratedImage(decoded, "image/png") if decoded else download_image_bytes(image_url))
    if not outputs:
        raise RuntimeError("PPIO URL mode found no usable image URLs.")
    return outputs


def poll_ppio_task_result(task_id: str, api_key: str, asset_id: str, output_root: Path) -> Any:
    poll_interval = resolve_positive_number(os.environ.get("IMAGE_TASK_POLL_INTERVAL_MS")) or 3000
    timeout_ms = resolve_positive_number(os.environ.get("IMAGE_ASSET_TIMEOUT_MS")) or 180000
    query_url = f"{PPIO_ASYNC_TASK_RESULT_ENDPOINT}?task_id={urllib.parse.quote(task_id)}"
    started = time.time()
    headers = {"Authorization": f"Bearer {api_key}"}
    while True:
        if (time.time() - started) * 1000 > timeout_ms:
            raise RuntimeError(f"PPIO async task timed out. task_id={task_id}")
        append_asset_log_event(output_root, asset_id, {
            "timestamp": timestamp(),
            "provider": "openai-ppioImage",
            "phase": "request",
            "context": {"assetKey": asset_id, "assetType": "task", "operation": "task-result.poll"},
            "url": query_url,
            "method": "GET",
            "headers": redact_headers(headers),
        })
        status, response_headers, response_body = request_text(query_url, headers=headers, method="GET")
        append_asset_log_event(output_root, asset_id, {
            "timestamp": timestamp(),
            "provider": "openai-ppioImage",
            "phase": "response",
            "context": {"assetKey": asset_id, "assetType": "task", "operation": "task-result.poll"},
            "status": status,
            "headers": response_headers,
            "body": response_body,
        })
        if status < 200 or status >= 300:
            raise RuntimeError(f"PPIO task-result query failed ({status}): {response_body}")
        payload = parse_json_or_throw(response_body, "PPIO task-result")
        images = payload.get("images") if isinstance(payload, dict) else None
        if isinstance(images, list) and images:
            return payload
        status_text = get_task_status(payload)
        if status_text and any(flag in status_text.upper() for flag in ("FAIL", "ERROR", "REJECT")):
            raise RuntimeError(f"PPIO async task failed ({status_text}): {get_task_reason(payload)}")
        time.sleep(poll_interval / 1000)


def request_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: Any = None,
    method: str = "POST",
) -> tuple[int, dict[str, str], str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    timeout = (resolve_positive_number(os.environ.get("IMAGE_HTTP_TIMEOUT_MS")) or 90000) / 1000
    last_error: Exception | None = None
    for attempt in range(resolve_retry_count() + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-configured provider URL
                body = response.read().decode("utf-8", errors="replace")
                return response.status, dict(response.headers.items()), body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, dict(exc.headers.items()), body
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= resolve_retry_count():
                break
            time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(f"HTTP request failed: {last_error}")


def download_image_bytes(url: str) -> GeneratedImage:
    request = urllib.request.Request(url, headers={"User-Agent": "narrative-game-asset-pipeline/1.0"}, method="GET")
    timeout = (resolve_positive_number(os.environ.get("IMAGE_HTTP_TIMEOUT_MS")) or 90000) / 1000
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - generated provider URL
        return GeneratedImage(response.read(), response.headers.get("content-type", "image/png"))


def configure_ppio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    extra = parse_json_env("IMAGE_EXTRA_PARAMS", {})
    if isinstance(extra, dict):
        deep_merge(payload, {k: v for k, v in extra.items() if k not in ("expected_count", "size_map")})
    rules = parse_json_env("IMAGE_REWRITE_RULES", {})
    if isinstance(rules, dict):
        apply_rewrite_rules(payload, rules)
    return payload


def resolve_image_size(aspect_ratio: str) -> str:
    extra = parse_json_env("IMAGE_EXTRA_PARAMS", {})
    size_map = extra.get("size_map") if isinstance(extra, dict) else None
    default = {"16:9": "1536x1024", "3:2": "1536x1024", "2:3": "1024x1536", "default": "1024x1024"}
    if isinstance(size_map, dict):
        default.update({str(k): str(v) for k, v in size_map.items() if isinstance(v, str)})
    return default.get(aspect_ratio) or default["default"]


def resolve_expected_count(expected_count: int) -> int:
    extra = parse_json_env("IMAGE_EXTRA_PARAMS", {})
    if isinstance(extra, dict):
        candidate = extra.get("expected_count")
        if isinstance(candidate, int) and candidate > 0:
            return candidate
    return max(1, expected_count)


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


def parse_json_env(name: str, fallback: Any) -> Any:
    value = os.environ.get(name)
    if not value or not value.strip():
        return fallback
    return json.loads(value)


def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(target.get(key), dict) and isinstance(value, dict):
            deep_merge(target[key], value)
        else:
            target[key] = value


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


def resolve_image_url_field(image: Any) -> str | None:
    if isinstance(image, str):
        return image
    if isinstance(image, dict):
        value = image.get("image_url") or image.get("url")
        return value if isinstance(value, str) else None
    return None


def maybe_decode_data_url(value: str) -> bytes | None:
    marker = ";base64,"
    if not value.startswith("data:image/") or marker not in value:
        return None
    return base64.b64decode(value.split(marker, 1)[1])


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


def parse_json_or_throw(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned invalid JSON: {text[:500]}") from exc


def append_asset_log_event(output_root: Path, asset_id: str, event: dict[str, Any]) -> None:
    log_dir = output_root / "log"
    ensure_dir(log_dir)
    log_path = log_dir / f"{sanitize_asset_name(asset_id)}.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        redacted[key] = "<redacted>" if key.lower() in {"authorization", "x-goog-api-key"} else value
    return redacted


def redact_image_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "data" and isinstance(value, str) and len(value) > 256:
                redacted[key] = f"<base64 image data: {len(value)} chars>"
            else:
                redacted[key] = redact_image_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_image_payload(item) for item in payload]
    return payload


def sanitize_asset_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "unknown_asset"


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def resolve_positive_number(value: str | None) -> float | None:
    try:
        parsed = float(value) if value is not None else None
    except ValueError:
        return None
    return parsed if parsed and parsed > 0 else None


def resolve_retry_count() -> int:
    value = os.environ.get("IMAGE_ASSET_RETRY_COUNT")
    try:
        parsed = int(value) if value is not None else 1
    except ValueError:
        return 1
    return max(0, parsed)
