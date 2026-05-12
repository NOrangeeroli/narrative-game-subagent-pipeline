#!/usr/bin/env python3
"""Audio provider adapters for narrative-game-subagent-pipeline assets."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import math
import os
import random
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_dir

try:
    import requests
except ImportError:  # pragma: no cover - urllib fallback keeps the skill dependency-light.
    requests = None  # type: ignore[assignment]


PPIO_AUDIO_DEFAULT_BASE_URL = "https://api.ppio.com/v3"
MINIMAX_MUSIC_ENDPOINT = "minimax-music"
MINIMAX_TTS_ENDPOINT = "minimax-speech-2.8-hd"
MINIMAX_VOICE_DESIGN_ENDPOINT = "minimax-voice-design"
MINIMAX_MUSIC_DEFAULT_MODEL = "music-2.5+"
MINIMAX_MUSIC_ALLOWED_FORMATS = {"mp3", "wav", "pcm"}
MINIMAX_MUSIC_ALLOWED_BITRATES = {32000, 64000, 128000, 256000}
MINIMAX_MUSIC_ALLOWED_SAMPLE_RATES = {16000, 24000, 32000, 44100}
MINIMAX_TTS_ALLOWED_EMOTIONS = {"happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "fluent", "whisper"}
MINIMAX_DEFAULT_VOICE_ID = "Chinese (Mandarin)_ExplorativeGirl"
MINIMAX_VOICE_DESIGN_DEFAULT_ENABLED = True
VOICE_DESIGN_CACHE_NAME = "voice-design-cache.json"
VOICE_DESIGN_LOCK = threading.Lock()
MINIMAX_VOICE_PROFILE_MAP: dict[str, str] = {}


@dataclass
class GeneratedAudio:
    bytes: bytes
    mime_type: str
    source_url: str | None = None


def normalize_audio_provider_id(provider: str | None) -> str:
    normalized = (provider or "").strip()
    if normalized.lower() in {"ppio", "openai-ppioaudio", "openai_ppioaudio"}:
        return "minimax-ppio"
    return normalized


def resolve_audio_provider_model(provider: str, model: str | None = None, audio_kind: str | None = None) -> str:
    provider = normalize_audio_provider_id(provider)
    if model:
        return model
    if provider in ("mock", "local-procedural"):
        return "local-procedural-audio-v1" if provider == "local-procedural" else "mock-audio-provider"
    if provider == "minimax-ppio":
        if normalize_audio_kind(audio_kind) == "voice":
            return os.environ.get("MINIMAX_TTS_ENDPOINT") or MINIMAX_TTS_ENDPOINT
        return os.environ.get("AUDIO_MODEL") or os.environ.get("MINIMAX_MUSIC_MODEL") or MINIMAX_MUSIC_DEFAULT_MODEL
    return provider or "unknown-audio-provider"


def generate_provider_audio(
    *,
    provider: str,
    model: str | None,
    asset: dict[str, Any],
    output_root: Path,
    prompt: str,
    audio_kind: str,
    expected_format: str,
) -> GeneratedAudio:
    provider = normalize_audio_provider_id(provider)
    kind = normalize_audio_kind(audio_kind)
    if provider in ("mock", "local-procedural"):
        return GeneratedAudio(generate_mock_wav_bytes(str(asset.get("asset_id") or "audio"), kind), "audio/wav")
    if provider == "minimax-ppio":
        if kind == "voice":
            return generate_minimax_voice_audio(
                model=resolve_audio_provider_model(provider, model, kind),
                asset=asset,
                output_root=output_root,
                text=prompt,
                expected_format=expected_format,
            )
        return generate_minimax_music_audio(
            model=resolve_audio_provider_model(provider, model, kind),
            asset=asset,
            output_root=output_root,
            prompt=prompt,
            audio_kind=kind,
            expected_format=expected_format,
        )
    raise ValueError(f"Provider {provider} is not a supported audio provider.")


def generate_audio_file(
    *,
    provider: str,
    asset: dict[str, Any],
    output_path: Path,
    prompt: str,
    audio_kind: str | None = None,
    model: str | None = None,
    expected_format: str | None = None,
    output_root: Path | None = None,
    fallback_provider: str | None = None,
) -> dict[str, Any]:
    """Generate one audio asset and write it to disk.

    This is the stable programmatic entry point for callers that need a single
    BGM/SFX/voice file without running the full asset pipeline.
    """
    kind = normalize_audio_kind(audio_kind or str(asset.get("kind") or ""))
    output_root = output_root or output_path.parent
    expected_format = expected_format or audio_format_for_output_path(output_path)
    provider_used = normalize_audio_provider_id(provider)
    fallback_from: str | None = None
    primary_error: str | None = None
    try:
        audio = generate_provider_audio(
            provider=provider_used,
            model=model,
            asset=asset,
            output_root=output_root,
            prompt=prompt,
            audio_kind=kind,
            expected_format=expected_format,
        )
    except Exception as exc:  # noqa: BLE001 - preserve provider error for reports
        if not fallback_provider:
            raise
        fallback_from = provider_used
        primary_error = str(exc)
        provider_used = fallback_provider
        audio = generate_provider_audio(
            provider=provider_used,
            model=model,
            asset=asset,
            output_root=output_root,
            prompt=prompt,
            audio_kind=kind,
            expected_format=expected_format,
        )
    audio = normalize_generated_audio(asset_id=str(asset.get("asset_id") or output_path.stem), kind=kind, audio=audio)
    ensure_dir(output_path.parent)
    output_path.write_bytes(audio.bytes)
    return {
        "asset_id": str(asset.get("asset_id") or output_path.stem),
        "kind": kind,
        "provider": provider_used,
        "model": resolve_audio_provider_model(provider_used, model, kind),
        "output_file": str(output_path),
        "bytes": len(audio.bytes),
        "mime_type": audio.mime_type,
        "source_url_present": bool(audio.source_url),
        "fallback_from": fallback_from,
        "primary_error": primary_error,
    }


def normalize_generated_audio(*, asset_id: str, kind: str, audio: GeneratedAudio) -> GeneratedAudio:
    if kind != "sfx":
        return audio
    max_seconds = sfx_max_duration_seconds()
    if max_seconds <= 0:
        return audio
    trimmed = trim_wav_bytes(audio.bytes, max_seconds)
    if trimmed is None:
        return audio
    return GeneratedAudio(trimmed, audio.mime_type, audio.source_url)


def trim_wav_bytes(audio_bytes: bytes, max_seconds: float) -> bytes | None:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as source:
            params = source.getparams()
            max_frames = int(source.getframerate() * max_seconds)
            if source.getnframes() <= max_frames:
                return None
            frames = source.readframes(max_frames)
    except (wave.Error, EOFError):
        return None
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams(params)
        target.writeframes(frames)
    return output.getvalue()


def generate_minimax_music_audio(
    *,
    model: str,
    asset: dict[str, Any],
    output_root: Path,
    prompt: str,
    audio_kind: str,
    expected_format: str,
) -> GeneratedAudio:
    asset_id = str(asset.get("asset_id") or "audio")
    api_key = require_audio_api_key()
    endpoint = build_ppio_audio_endpoint(os.environ.get("MINIMAX_MUSIC_ENDPOINT") or MINIMAX_MUSIC_ENDPOINT)
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    lyrics = first_text(spec.get("lyrics"), asset.get("lyrics"))
    audio_format = normalize_audio_format(
        os.environ.get("AUDIO_BGM_FORMAT")
        or os.environ.get("AUDIO_MUSIC_FORMAT")
        or expected_format
    )
    if audio_format not in MINIMAX_MUSIC_ALLOWED_FORMATS:
        audio_format = "mp3"
    bitrate = env_int("AUDIO_BGM_BITRATE") or env_int("AUDIO_MUSIC_BITRATE") or env_int("AUDIO_BITRATE") or 128000
    sample_rate = env_int("AUDIO_BGM_SAMPLE_RATE") or env_int("AUDIO_MUSIC_SAMPLE_RATE") or env_int("AUDIO_SAMPLE_RATE") or 44100
    if bitrate not in MINIMAX_MUSIC_ALLOWED_BITRATES:
        bitrate = 128000
    if sample_rate not in MINIMAX_MUSIC_ALLOWED_SAMPLE_RATES:
        sample_rate = 44100
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "is_instrumental": parse_bool_env("AUDIO_IS_INSTRUMENTAL", lyrics is None),
        "lyrics_optimizer": parse_bool_env("AUDIO_LYRICS_OPTIMIZER", False),
        "output_format": "url",
        "aigc_watermark": parse_bool_env("AUDIO_AIGC_WATERMARK", False),
        "audio_setting": compact_dict({
            "format": audio_format,
            "bitrate": bitrate,
            "sample_rate": sample_rate,
        }),
    }
    if lyrics:
        payload["lyrics"] = lyrics
    configure_audio_payload(payload, "AUDIO_MUSIC_EXTRA_PARAMS")
    headers = audio_headers(api_key)
    append_audio_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "request",
        "context": {"assetKey": asset_id, "assetType": audio_kind, "operation": "audio.music.generate"},
        "url": endpoint,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": payload,
    })
    status, response_headers, response_body = request_text(endpoint, headers=headers, payload=payload)
    append_audio_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "response",
        "context": {"assetKey": asset_id, "assetType": audio_kind, "operation": "audio.music.generate"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    if status < 200 or status >= 300:
        raise RuntimeError(f"MiniMax music generation failed ({status}): {response_body}")
    return extract_audio_from_response(response_body, asset_id, output_root)


def generate_minimax_voice_audio(
    *,
    model: str,
    asset: dict[str, Any],
    output_root: Path,
    text: str,
    expected_format: str,
) -> GeneratedAudio:
    asset_id = str(asset.get("asset_id") or "voice")
    api_key = require_audio_api_key()
    endpoint = build_ppio_audio_endpoint(model)
    spec = asset.get("spec") if isinstance(asset.get("spec"), dict) else {}
    minimax_binding = provider_binding_for(spec, "minimax-ppio")
    audio_format = normalize_audio_format(expected_format)
    voice_setting = compact_dict({
        "voice_id": resolve_minimax_voice_id(spec, asset, output_root=output_root, preview_text=text),
        "vol": env_float("AUDIO_VOICE_VOL") or 1.0,
        "pitch": env_int("AUDIO_VOICE_PITCH") if os.environ.get("AUDIO_VOICE_PITCH") is not None else 0,
        "speed": env_float("AUDIO_VOICE_SPEED") or 1.0,
        "latex_read": parse_bool_env("AUDIO_VOICE_LATEX_READ", False),
        "text_normalization": parse_bool_env("AUDIO_TEXT_NORMALIZATION", True),
        "emotion": normalize_minimax_tts_emotion(
            first_text(
                minimax_binding.get("voice_emotion"),
                minimax_binding.get("emotion"),
                spec.get("voice_emotion"),
                asset.get("voice_emotion"),
                os.environ.get("AUDIO_VOICE_EMOTION"),
                spec.get("emotion"),
                asset.get("emotion"),
            )
        ),
    })
    payload: dict[str, Any] = {
        "text": text,
        "stream": False,
        "audio_setting": compact_dict({
            "format": audio_format,
            "bitrate": env_int("AUDIO_BITRATE") or 128000,
            "channel": env_int("AUDIO_CHANNEL") or 1,
            "sample_rate": env_int("AUDIO_SAMPLE_RATE") or 32000,
        }),
        "output_format": "url",
        "voice_setting": voice_setting,
        "aigc_watermark": parse_bool_env("AUDIO_AIGC_WATERMARK", False),
        "subtitle_enable": parse_bool_env("AUDIO_SUBTITLE_ENABLE", False),
        "continuous_sound": parse_bool_env("AUDIO_CONTINUOUS_SOUND", False),
    }
    language_boost = first_text(spec.get("language_boost"), os.environ.get("AUDIO_LANGUAGE_BOOST"), infer_language_boost(text))
    if language_boost:
        payload["language_boost"] = language_boost
    for env_name, payload_key in (
        ("AUDIO_VOICE_MODIFY", "voice_modify"),
        ("AUDIO_PRONUNCIATION_DICT", "pronunciation_dict"),
    ):
        extra = parse_json_env(env_name, None)
        if extra is not None:
            payload[payload_key] = extra
    configure_audio_payload(payload, "AUDIO_TTS_EXTRA_PARAMS")
    headers = audio_headers(api_key)
    provider_emotion = voice_setting.get("emotion")
    request_context = {
        "assetKey": asset_id,
        "assetType": "voice",
        "operation": "audio.tts.generate",
    }
    delivery_context = compact_dict({
        "speaker": spec.get("speaker") or asset.get("speaker"),
        "authored_emotion": spec.get("emotion") or asset.get("emotion"),
        "authored_tone": spec.get("tone") or asset.get("tone"),
        "provider_voice_emotion": provider_emotion,
        "voice_profile_id": minimax_binding.get("voice_profile_id") or spec.get("voice_id") or asset.get("voice_id"),
    })
    if delivery_context:
        request_context["delivery"] = delivery_context
    append_audio_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "request",
        "context": request_context,
        "url": endpoint,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": {**payload, "text": text[:500]},
    })
    status, response_headers, response_body = request_text(endpoint, headers=headers, payload=payload)
    append_audio_log_event(output_root, asset_id, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "response",
        "context": {"assetKey": asset_id, "assetType": "voice", "operation": "audio.tts.generate"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    if status < 200 or status >= 300:
        raise RuntimeError(f"MiniMax TTS generation failed ({status}): {response_body}")
    return extract_audio_from_response(response_body, asset_id, output_root)


def extract_audio_from_response(response_text: str, asset_id: str, output_root: Path) -> GeneratedAudio:
    payload = parse_json_or_throw(response_text, "MiniMax audio generation")
    assert_minimax_success_response(payload)
    candidates = collect_audio_candidates(payload)
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        value = candidate.strip()
        if value.startswith(("http://", "https://")):
            append_audio_log_event(output_root, asset_id, {
                "timestamp": timestamp(),
                "provider": "minimax-ppio",
                "phase": "request",
                "context": {"assetKey": asset_id, "operation": "audio.download"},
                "url": value,
                "method": "GET",
            })
            audio = download_audio_bytes(value)
            append_audio_log_event(output_root, asset_id, {
                "timestamp": timestamp(),
                "provider": "minimax-ppio",
                "phase": "response",
                "context": {"assetKey": asset_id, "operation": "audio.download"},
                "source_url": value,
                "mime_type": audio.mime_type,
                "bytes": len(audio.bytes),
            })
            return audio
        decoded = maybe_decode_audio_payload(value)
        if decoded:
            return decoded
    raise RuntimeError("MiniMax audio response did not contain a usable audio URL or inline audio payload.")


def assert_minimax_success_response(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, dict):
        return
    status_code = base_resp.get("status_code")
    if status_code in (None, 0, "0"):
        return
    status_msg = base_resp.get("status_msg") or "unknown error"
    raise RuntimeError(f"MiniMax audio generation failed with base_resp {status_code}: {status_msg}")


def collect_audio_candidates(value: Any) -> list[str]:
    candidates: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            candidates.append(item)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if not isinstance(item, dict):
            return
        for key in ("audio", "audio_url", "url", "download_url", "source_url", "clip_url"):
            candidate = item.get(key)
            if isinstance(candidate, str):
                candidates.append(candidate)
        for key in ("audios", "urls", "audio_urls", "outputs", "data", "result"):
            if key in item:
                visit(item[key])

    visit(value)
    return candidates


def maybe_decode_audio_payload(value: str) -> GeneratedAudio | None:
    if value.startswith("data:audio/") and ";base64," in value:
        header, data = value.split(";base64,", 1)
        mime_type = header.removeprefix("data:")
        return GeneratedAudio(base64.b64decode(data), mime_type)
    compact = "".join(value.split())
    if len(compact) >= 32 and len(compact) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in compact):
        return GeneratedAudio(bytes.fromhex(compact), "audio/mpeg")
    try:
        decoded = base64.b64decode(compact, validate=True)
    except binascii.Error:
        return None
    return GeneratedAudio(decoded, "audio/mpeg") if decoded else None


def download_audio_bytes(url: str) -> GeneratedAudio:
    request = urllib.request.Request(url, headers={"User-Agent": "narrative-game-asset-pipeline/1.0"}, method="GET")
    timeout = audio_http_timeout_seconds()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if audio_no_proxy() else None
    open_url = opener.open if opener else urllib.request.urlopen
    last_error: Exception | None = None
    for attempt in range(resolve_audio_retry_count() + 1):
        try:
            with open_url(request, timeout=timeout) as response:  # noqa: S310 - generated provider URL
                return GeneratedAudio(response.read(), response.headers.get("content-type", "audio/mpeg"), source_url=url)
        except Exception as exc:  # noqa: BLE001 - provider downloads can transiently fail.
            last_error = exc
            if attempt >= resolve_audio_retry_count():
                break
            time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(f"Audio download failed: {last_error}")


def request_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: Any = None,
    method: str = "POST",
) -> tuple[int, dict[str, str], str]:
    timeout = audio_http_timeout_seconds()
    last_error: Exception | None = None
    no_proxy = audio_no_proxy_for_url(url)
    if requests is not None:
        session = requests.Session()
        if no_proxy:
            session.trust_env = False
        for attempt in range(resolve_audio_retry_count() + 1):
            try:
                if method.upper() == "GET":
                    response = session.get(url, headers=headers or {}, timeout=timeout)
                else:
                    response = session.request(method.upper(), url, json=payload, headers=headers or {}, timeout=timeout)
                return response.status_code, dict(response.headers.items()), response.text
            except Exception as exc:  # noqa: BLE001 - surface provider/network detail to caller
                last_error = exc
                if attempt >= resolve_audio_retry_count():
                    break
                time.sleep(1.25 * (attempt + 1))
        raise RuntimeError(f"HTTP request failed: {last_error}")

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if no_proxy else None
    open_url = opener.open if opener else urllib.request.urlopen
    for attempt in range(resolve_audio_retry_count() + 1):
        request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with open_url(request, timeout=timeout) as response:  # noqa: S310 - user-configured provider URL
                body = response.read().decode("utf-8", errors="replace")
                return response.status, dict(response.headers.items()), body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, dict(exc.headers.items()), body
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= resolve_audio_retry_count():
                break
            time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(f"HTTP request failed: {last_error}")


def generate_mock_wav_bytes(asset_id: str, audio_kind: str) -> bytes:
    sample_rate = env_int("AUDIO_MOCK_SAMPLE_RATE") or 22050
    kind = normalize_audio_kind(audio_kind)
    duration = {"bgm": 8.0, "sfx": 1.2, "voice": 0.8}.get(kind, 0.6)
    digest = hashlib.sha256(asset_id.encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    base_frequency = 180 + digest[0] % 260
    frame_count = int(sample_rate * duration)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frame_count):
            progress = index / max(frame_count - 1, 1)
            t = index / sample_rate
            if kind == "sfx":
                sample = procedural_sfx_sample(asset_id, t, progress, base_frequency, rng)
                envelope = procedural_sfx_envelope(asset_id, progress)
            elif kind == "bgm":
                sample = procedural_bgm_sample(t, progress, base_frequency)
                envelope = min(progress * 5, (1 - progress) * 5, 1)
            else:
                sample = math.sin(2 * math.pi * base_frequency * t)
                envelope = min(progress * 8, (1 - progress) * 8, 1)
            wav.writeframes(struct.pack("<h", int(sample * envelope * 0.22 * 32767)))
    return output.getvalue()


def procedural_bgm_sample(t: float, progress: float, base_frequency: float) -> float:
    chord_roots = [0, 5, 7, 3]
    chord = chord_roots[int((progress * len(chord_roots)) % len(chord_roots))]
    root = base_frequency * (2 ** (chord / 12))
    pad = (
        math.sin(2 * math.pi * root * t) * 0.35
        + math.sin(2 * math.pi * root * 1.5 * t) * 0.22
        + math.sin(2 * math.pi * root * 2.0 * t) * 0.16
    )
    bell = math.sin(2 * math.pi * (root * 4) * t) * max(0, math.sin(2 * math.pi * 0.5 * t)) * 0.18
    shimmer = math.sin(2 * math.pi * (root * 6.01) * t) * 0.05
    return max(-1, min(1, pad + bell + shimmer))


def procedural_sfx_sample(asset_id: str, t: float, progress: float, base_frequency: float, rng: random.Random) -> float:
    token = asset_id.lower()
    if "gear" in token:
        tick = 1.0 if (int(t * 24) % 6) == 0 else -0.3
        whirr = math.sin(2 * math.pi * (base_frequency * 0.7 + 60 * progress) * t)
        return 0.55 * whirr + 0.25 * tick
    if "memory" in token:
        noise = rng.uniform(-1, 1) * (1 - progress)
        pulse = math.sin(2 * math.pi * (base_frequency * 1.5) * t)
        return 0.35 * noise + 0.65 * pulse
    if "tide" in token:
        sweep = math.sin(2 * math.pi * (base_frequency + 180 * progress) * t)
        reverse = math.sin(2 * math.pi * (base_frequency * 2.7) * t + progress * math.pi)
        return 0.6 * sweep + 0.25 * reverse
    if "prism" in token or "choice" in token:
        partials = [1.0, 1.5, 2.25, 3.0]
        return sum(math.sin(2 * math.pi * base_frequency * partial * t) / (index + 2) for index, partial in enumerate(partials))
    if "station" in token:
        hum = math.sin(2 * math.pi * 92 * t) + 0.3 * math.sin(2 * math.pi * 184 * t)
        pulse = 0.65 + 0.35 * math.sin(2 * math.pi * 2.2 * t)
        return hum * pulse
    return math.sin(2 * math.pi * base_frequency * t) + 0.35 * math.sin(2 * math.pi * base_frequency * 2.01 * t)


def procedural_sfx_envelope(asset_id: str, progress: float) -> float:
    token = asset_id.lower()
    if "station" in token:
        return min(progress * 4, (1 - progress) * 4, 1) * 0.7
    if "gear" in token or "memory" in token:
        return min(progress * 10, (1 - progress) * 3, 1)
    return math.exp(-4.5 * progress) * min(progress * 18, 1)


def build_ppio_audio_endpoint(endpoint: str) -> str:
    cleaned = endpoint.strip("/")
    base = (os.environ.get("AUDIO_BASE_URL") or PPIO_AUDIO_DEFAULT_BASE_URL).rstrip("/")
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    for known in (MINIMAX_MUSIC_ENDPOINT, MINIMAX_TTS_ENDPOINT):
        if base.lower().endswith(f"/{known}".lower()):
            return base[: -len(known)] + cleaned
    if base.lower().endswith(f"/{cleaned}".lower()):
        return base
    return f"{base}/{cleaned}"


def normalize_audio_kind(value: str | None) -> str:
    kind = str(value or "").strip().lower()
    if kind.startswith("voice"):
        return "voice"
    if kind.startswith("sfx") or kind in {"sound", "sound_effect"}:
        return "sfx"
    return "bgm" if kind.startswith("bgm") or kind in {"music", "background_music"} else kind or "bgm"


def normalize_minimax_tts_emotion(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    token = value.strip().lower()
    if token in MINIMAX_TTS_ALLOWED_EMOTIONS:
        return token
    return None


def normalize_audio_format(value: str | None) -> str:
    cleaned = str(value or "").strip().lower().lstrip(".")
    if cleaned in {"mpeg", "mpga"}:
        return "mp3"
    return cleaned or os.environ.get("AUDIO_FORMAT") or "wav"


def audio_format_for_output_path(output_path: Path) -> str:
    suffix = output_path.suffix.lower().lstrip(".")
    return normalize_audio_format(suffix or os.environ.get("AUDIO_FORMAT"))


def require_audio_api_key() -> str:
    api_key = os.environ.get("AUDIO_API_KEY") or os.environ.get("PPIO_API_KEY")
    if not api_key:
        raise RuntimeError("PPIO audio generation requires AUDIO_API_KEY or PPIO_API_KEY.")
    return api_key


def audio_headers(api_key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}


def configure_audio_payload(payload: dict[str, Any], scoped_extra_env: str) -> None:
    extra = parse_json_env("AUDIO_EXTRA_PARAMS", {})
    if isinstance(extra, dict):
        deep_merge(payload, extra)
    scoped_extra = parse_json_env(scoped_extra_env, {})
    if isinstance(scoped_extra, dict):
        deep_merge(payload, scoped_extra)


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


def compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def provider_binding_for(spec: dict[str, Any], provider: str) -> dict[str, Any]:
    bindings = spec.get("provider_bindings")
    if not isinstance(bindings, dict):
        return {}
    binding = bindings.get(provider)
    return binding if isinstance(binding, dict) else {}


def resolve_minimax_voice_id(
    spec: dict[str, Any],
    asset: dict[str, Any],
    *,
    output_root: Path | None = None,
    preview_text: str | None = None,
) -> str:
    profile_map = dict(MINIMAX_VOICE_PROFILE_MAP)
    configured_map = parse_json_env("MINIMAX_VOICE_PROFILE_MAP", {})
    if isinstance(configured_map, dict):
        profile_map.update({str(key): str(value) for key, value in configured_map.items() if value})

    minimax_binding = provider_binding_for(spec, "minimax-ppio")
    raw_voice_id = first_text(
        minimax_binding.get("voice_id"),
        minimax_binding.get("voice_profile_id"),
        spec.get("voice_id"),
        asset.get("voice_id"),
    )
    if raw_voice_id:
        profile = voice_profile_spec(raw_voice_id, spec=spec, asset=asset)
        if raw_voice_id.startswith("voice_profile.") and should_use_minimax_voice_design() and output_root is not None:
            return resolve_designed_minimax_voice_id(raw_voice_id, output_root, preview_text or "", profile)
        mapped = profile_map.get(raw_voice_id)
        if mapped:
            validate_minimax_voice_gender(raw_voice_id, mapped, profile)
            return mapped
        if raw_voice_id.startswith("voice_profile."):
            fallback = first_text(os.environ.get("MINIMAX_DEFAULT_VOICE_ID"), os.environ.get("AUDIO_VOICE_ID")) or MINIMAX_DEFAULT_VOICE_ID
            validate_minimax_voice_gender(raw_voice_id, fallback, profile)
            return fallback
        return raw_voice_id
    return first_text(os.environ.get("MINIMAX_VOICE_ID"), os.environ.get("AUDIO_VOICE_ID")) or MINIMAX_DEFAULT_VOICE_ID


def should_use_minimax_voice_design() -> bool:
    return parse_bool_env("MINIMAX_USE_VOICE_DESIGN", MINIMAX_VOICE_DESIGN_DEFAULT_ENABLED)


def resolve_designed_minimax_voice_id(profile_id: str, output_root: Path, preview_text: str, profile: dict[str, Any]) -> str:
    with VOICE_DESIGN_LOCK:
        cache = read_voice_design_cache(output_root)
        cached = cache.get(profile_id)
        profile_prompt = str(profile["prompt"])
        if (
            isinstance(cached, dict)
            and isinstance(cached.get("voice_id"), str)
            and cached["voice_id"].strip()
            and cached.get("prompt") == profile_prompt
        ):
            return cached["voice_id"].strip()

        voice_id = generate_minimax_designed_voice(
            profile_id=profile_id,
            output_root=output_root,
            prompt=profile_prompt,
            preview_text=preview_text[:500] or str(profile.get("preview_text") or "This is a short voice preview."),
        )
        cache[profile_id] = {
            "voice_id": voice_id,
            "gender": profile.get("gender", "unknown"),
            "prompt": profile["prompt"],
            "created_at": timestamp(),
        }
        write_voice_design_cache(output_root, cache)
        return voice_id


def generate_minimax_designed_voice(*, profile_id: str, output_root: Path, prompt: str, preview_text: str) -> str:
    api_key = require_audio_api_key()
    endpoint = build_ppio_audio_endpoint(os.environ.get("MINIMAX_VOICE_DESIGN_ENDPOINT") or MINIMAX_VOICE_DESIGN_ENDPOINT)
    payload: dict[str, Any] = {
        "prompt": prompt,
        "preview_text": preview_text[:500],
    }
    configure_audio_payload(payload, "AUDIO_VOICE_DESIGN_EXTRA_PARAMS")
    headers = audio_headers(api_key)
    log_key = f"voice_design.{profile_id}"
    append_audio_log_event(output_root, log_key, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "request",
        "context": {"assetKey": profile_id, "assetType": "voice_design", "operation": "audio.voice-design"},
        "url": endpoint,
        "method": "POST",
        "headers": redact_headers(headers),
        "payload": payload,
    })
    status, response_headers, response_body = request_text(endpoint, headers=headers, payload=payload)
    append_audio_log_event(output_root, log_key, {
        "timestamp": timestamp(),
        "provider": "minimax-ppio",
        "phase": "response",
        "context": {"assetKey": profile_id, "assetType": "voice_design", "operation": "audio.voice-design"},
        "status": status,
        "headers": response_headers,
        "body": response_body,
    })
    if status < 200 or status >= 300:
        raise RuntimeError(f"MiniMax voice design failed ({status}): {response_body}")
    payload_obj = parse_json_or_throw(response_body, "MiniMax voice design")
    assert_minimax_success_response(payload_obj)
    voice_id = collect_first_key(payload_obj, "voice_id")
    if not voice_id:
        raise RuntimeError(f"MiniMax voice design did not return voice_id: {response_body[:500]}")
    return voice_id


def voice_profile_spec(profile_id: str, *, spec: dict[str, Any] | None = None, asset: dict[str, Any] | None = None) -> dict[str, Any]:
    configured_specs = parse_json_env("MINIMAX_VOICE_PROFILE_SPECS", {})
    specs: dict[str, Any] = {}
    if isinstance(configured_specs, dict):
        for key, value in configured_specs.items():
            if isinstance(value, dict):
                merged = dict(specs.get(str(key), {}))
                merged.update(value)
                specs[str(key)] = merged
    profile: dict[str, Any] = dict(specs.get(profile_id, {}))
    spec = spec or {}
    asset = asset or {}
    for source in (asset.get("voice_design"), spec.get("voice_design")):
        if isinstance(source, dict):
            profile.update(source)
    for key in ("voice_gender", "gender", "age", "persona", "timbre", "style", "preview_text"):
        for source in (asset, spec):
            if key in source and source[key] not in (None, ""):
                normalized_key = "gender" if key == "voice_gender" else key
                profile[normalized_key] = source[key]
                break
    base_prompt = first_text(
        profile.get("prompt"),
        spec.get("voice_design_prompt"),
        asset.get("voice_design_prompt"),
    )
    prompt = build_voice_design_prompt(profile_id, spec=spec, asset=asset, profile=profile, base_prompt=base_prompt)
    profile["prompt"] = prompt
    profile.setdefault("gender", "unknown")
    return profile


def build_voice_design_prompt(
    profile_id: str,
    *,
    spec: dict[str, Any],
    asset: dict[str, Any],
    profile: dict[str, Any],
    base_prompt: str | None = None,
) -> str:
    speaker = first_text(
        spec.get("speaker"),
        asset.get("speaker"),
        profile.get("speaker"),
        profile.get("name"),
        profile.get("display_name"),
        profile_id.removeprefix("voice_profile.").replace("_", " "),
    )
    gender = first_text(profile.get("gender"))
    age = first_text(profile.get("age"), profile.get("age_impression"))
    persona = first_text(profile.get("persona"))
    timbre = first_text(profile.get("timbre"))
    style = first_text(profile.get("style"))
    critical_constraints: list[str] = []
    gender_token = str(gender or "").lower()
    age_token = str(age or "").lower()
    timbre_token = str(timbre or "").lower()
    if (
        any(token in gender_token for token in ("female", "girl", "woman"))
        and any(token in f"{age_token} {timbre_token}" for token in ("child", "girl", "8", "9", "10", "11", "young"))
    ):
        critical_constraints.append(
            "Critical casting constraint: the resulting voice must clearly sound like a young Mandarin-speaking girl, "
            "with a bright higher-pitched child timbre; it must not sound male, like a teenage boy, or like an adult."
        )
    parts = [
        base_prompt or "",
        f"Create a natural character voice for speaker {speaker}.",
        f"Gender: {gender}." if gender else "",
        f"Age or age impression: {age}." if age else "",
        f"Personality: {persona}." if persona else "",
        f"Timbre: {timbre}." if timbre else "",
        f"Speaking style: {style}." if style else "",
        *critical_constraints,
        "Keep the voice suitable for the provided dialogue and maintain this character identity across lines.",
    ]
    return " ".join(part for part in parts if part)


def read_voice_design_cache(output_root: Path) -> dict[str, Any]:
    cache_path = output_root / VOICE_DESIGN_CACHE_NAME
    if not cache_path.exists():
        return {}
    try:
        value = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def write_voice_design_cache(output_root: Path, cache: dict[str, Any]) -> None:
    ensure_dir(output_root)
    (output_root / VOICE_DESIGN_CACHE_NAME).write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_first_key(value: Any, key_name: str) -> str | None:
    if isinstance(value, dict):
        candidate = value.get(key_name)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        for child in value.values():
            found = collect_first_key(child, key_name)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = collect_first_key(child, key_name)
            if found:
                return found
    return None


def validate_minimax_voice_gender(profile_id: str, voice_id: str, profile: dict[str, Any]) -> None:
    expected = str(profile.get("gender") or "unknown").lower()
    if expected not in {"male", "female"}:
        return
    inferred = infer_system_voice_gender(voice_id)
    if inferred and inferred != expected:
        raise RuntimeError(
            f"Voice profile {profile_id} expects {expected}, but mapped MiniMax voice_id {voice_id!r} looks {inferred}."
        )


def infer_system_voice_gender(voice_id: str) -> str | None:
    token = voice_id.lower()
    female_tokens = ("girl", "woman", "female", "miss", "bestie")
    male_tokens = ("boy", "man", "male", "gentleman", "youth", "executive", "elder")
    if any(item in token for item in female_tokens):
        return "female"
    if any(item in token for item in male_tokens):
        return "male"
    return None


def infer_language_boost(text: str) -> str:
    return "Chinese" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "auto"


def parse_bool_env(name: str, fallback: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def audio_no_proxy() -> bool:
    return parse_bool_env("AUDIO_NO_PROXY", False)


def audio_no_proxy_for_url(url: str) -> bool:
    if audio_no_proxy():
        return True
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if host == "api.ppio.com" and path.endswith(f"/v3/{MINIMAX_MUSIC_ENDPOINT}"):
        return parse_bool_env("PPIO_MINIMAX_MUSIC_NO_PROXY", True)
    return False


def env_int(name: str) -> int | None:
    value = os.environ.get(name)
    try:
        return int(value) if value is not None and value.strip() else None
    except ValueError:
        return None


def env_float(name: str) -> float | None:
    value = os.environ.get(name)
    try:
        return float(value) if value is not None and value.strip() else None
    except ValueError:
        return None


def parse_json_or_throw(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned invalid JSON: {text[:500]}") from exc


def append_audio_log_event(output_root: Path, asset_id: str, event: dict[str, Any]) -> None:
    log_dir = output_root / "log"
    ensure_dir(log_dir)
    log_path = log_dir / f"{sanitize_asset_name(asset_id)}.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        redacted[key] = "<redacted>" if key.lower() == "authorization" else value
    return redacted


def sanitize_asset_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "unknown_asset"


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def resolve_audio_retry_count() -> int:
    value = os.environ.get("AUDIO_ASSET_RETRY_COUNT")
    try:
        parsed = int(value) if value is not None else 2
    except ValueError:
        return 2
    return max(0, parsed)


def audio_http_timeout_seconds() -> float:
    return (env_float("AUDIO_HTTP_TIMEOUT_MS") or 300000) / 1000


def sfx_max_duration_seconds() -> float:
    return (env_float("AUDIO_SFX_MAX_DURATION_MS") or 2200) / 1000
