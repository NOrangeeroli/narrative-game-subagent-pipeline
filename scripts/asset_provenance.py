#!/usr/bin/env python3
"""Small provenance helpers for generated runtime assets."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from pipeline_lib import Json, ensure_dir, load_optional_json, write_json


REPORT_REF = Path("reports") / "asset-provenance-report.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def report_path(run_root: Path) -> Path:
    return run_root / REPORT_REF


def load_report(run_root: Path) -> Json:
    return load_optional_json(report_path(run_root)) or {
        "status": "pass",
        "generated_at": utc_now(),
        "assets": [],
    }


def write_report(run_root: Path, report: Json) -> Path:
    assets = report.get("assets") if isinstance(report.get("assets"), list) else []
    if any(asset.get("status") == "fail" for asset in assets if isinstance(asset, dict)):
        report["status"] = "fail"
    elif any(asset.get("status") == "needs_imagegen" for asset in assets if isinstance(asset, dict)):
        report["status"] = "needs_imagegen"
    else:
        report["status"] = "pass"
    report["updated_at"] = utc_now()
    return write_json(report_path(run_root), report)


def record_asset_result(run_root: Path, result: Json) -> Json:
    report = load_report(run_root)
    assets = [asset for asset in report.get("assets", []) if isinstance(asset, dict)]
    asset_id = str(result.get("asset_id") or "").strip()
    if not asset_id:
        raise ValueError("asset provenance result requires asset_id")
    result = dict(result)
    result.setdefault("updated_at", utc_now())
    replaced = False
    for index, existing in enumerate(assets):
        if existing.get("asset_id") == asset_id:
            assets[index] = {**existing, **result}
            replaced = True
            break
    if not replaced:
        assets.append(result)
    report["assets"] = assets
    write_report(run_root, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-kind", default="asset")
    parser.add_argument("--requested-provider", required=True)
    parser.add_argument("--final-provider", required=True)
    parser.add_argument("--status", choices=("success", "fail", "needs_imagegen"), default="success")
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--error", default=None)
    args = parser.parse_args()
    result: Json = {
        "asset_id": args.asset_id,
        "asset_kind": args.asset_kind,
        "requested_provider": args.requested_provider,
        "final_provider": args.final_provider,
        "status": args.status,
    }
    if args.output_file:
        result["output_file"] = args.output_file
    if args.error:
        result["error"] = args.error
    report = record_asset_result(Path(args.run_root).resolve(), result)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
