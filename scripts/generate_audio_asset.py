#!/usr/bin/env python3
"""Generate one audio asset through the configured provider.

This CLI is intentionally narrow: it lets the controller or a future agent
debug BGM/SFX/TTS generation without running the full VN asset pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_audio_providers import generate_audio_file


def read_text_arg(value: str | None, path_value: str | None) -> str:
    if path_value:
        return Path(path_value).read_text(encoding="utf-8").strip()
    return (value or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock", help="mock or minimax-ppio")
    parser.add_argument("--fallback-provider", default=None, help="Optional provider to use if the primary provider fails.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--kind", choices=("bgm", "sfx", "voice"), required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prompt", default=None, help="Music/SFX prompt, or voice text when --kind voice.")
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument("--text", default=None, help="Explicit TTS text; overrides --prompt for voice assets.")
    parser.add_argument("--text-file", default=None)
    parser.add_argument("--voice-id", default=None)
    parser.add_argument("--emotion", default=None)
    parser.add_argument("--format", default=None, help="Audio format requested from the provider; defaults to output suffix.")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    prompt = read_text_arg(args.prompt, args.prompt_file)
    text = read_text_arg(args.text, args.text_file)
    if args.kind == "voice":
        prompt = text or prompt
    if not prompt:
        raise SystemExit("Provide --prompt/--prompt-file, or --text/--text-file for voice assets.")

    spec: dict[str, object] = {}
    if args.kind == "voice":
        spec["text"] = prompt
    if args.voice_id:
        spec["voice_id"] = args.voice_id
    if args.emotion:
        spec["emotion"] = args.emotion

    result = generate_audio_file(
        provider=args.provider,
        fallback_provider=args.fallback_provider,
        model=args.model,
        asset={"asset_id": args.asset_id, "kind": args.kind, "spec": spec},
        output_path=output_path,
        output_root=output_path.parent,
        prompt=prompt,
        audio_kind=args.kind,
        expected_format=args.format,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
