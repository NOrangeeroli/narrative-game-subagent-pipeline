#!/usr/bin/env python3
"""Accept one built-in imagegen output for a broker request."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from asset_provenance import record_asset_result
from pipeline_lib import Json, ensure_dir


def latest_generated_png(after: float | None = None) -> Path:
    root = Path.home() / ".codex" / "generated_images"
    candidates = [path for path in root.rglob("*.png") if after is None or path.stat().st_mtime >= after]
    if not candidates:
        raise SystemExit(f"No generated PNG found under {root}.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def request_target(run_root: Path, request: Json) -> Path:
    output_ref = request.get("source_output_file") if request.get("requires_chroma_key_removal") else request.get("output_file")
    if not isinstance(output_ref, str) or not output_ref:
        raise SystemExit("Request is missing output_file/source_output_file.")
    return run_root / output_ref


def accept_output(run_root: Path, request_path: Path, generated_path: Path) -> Json:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise SystemExit(f"Malformed request: {request_path}")
    target = request_target(run_root, request)
    ensure_dir(target.parent)
    shutil.copy2(generated_path, target)

    result: Json = {
        "asset_id": request.get("asset_id"),
        "asset_kind": request.get("asset_kind") or "asset",
        "requested_provider": "imagegen",
        "final_provider": "imagegen",
        "status": "success",
        "output_file": request.get("output_file"),
        "source_output_file": request.get("source_output_file"),
        "request_ref": str(request_path.relative_to(run_root)),
        "generated_source": str(generated_path),
    }
    if not request.get("requires_chroma_key_removal") and request.get("asset_id"):
        record_asset_result(run_root, result)
    return {
        "status": "pass",
        "asset_id": request.get("asset_id"),
        "copied_from": str(generated_path),
        "copied_to": str(target),
        "requires_chroma_key_removal": bool(request.get("requires_chroma_key_removal")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--generated", default=None)
    parser.add_argument("--latest-after", type=float, default=None)
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    request_path = Path(args.request)
    if not request_path.is_absolute():
        request_path = run_root / request_path
    generated_path = Path(args.generated).resolve() if args.generated else latest_generated_png(args.latest_after)
    report = accept_output(run_root, request_path.resolve(), generated_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
