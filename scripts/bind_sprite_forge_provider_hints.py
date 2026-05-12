#!/usr/bin/env python3
"""Bind conventionally named Sprite Forge assets into asset-direction.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SEARCH_DIRS = (
    "maps",
    "battle-backgrounds",
    "sprites",
    "icons",
    "rpg-ui",
    "ui",
    "processed",
)
EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg")
VISUAL_PREFIXES = (
    "map.",
    "tileset.",
    "sprite.",
    "enemy.",
    "battlebg.",
    "icon.",
    "ui.",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def candidate_keys(asset_id: str) -> set[str]:
    parts = asset_id.split(".")
    keys = {normalize(asset_id), normalize(asset_id.replace(".", "-")), normalize(asset_id.replace(".", "_"))}
    if len(parts) > 1:
        keys.add(normalize(parts[-1]))
        keys.add(normalize("-".join(parts[1:])))
    return keys


def discover_sources(run_root: Path) -> dict[str, Path]:
    root = run_root / "workspace" / "sprite-forge-assets"
    sources: dict[str, Path] = {}
    if not root.exists():
        return sources
    for folder in SEARCH_DIRS:
        base = root / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix.lower() not in EXTENSIONS or not path.is_file():
                continue
            if path.name.startswith(".") or path.name.endswith(".palette.png"):
                continue
            rel = path.relative_to(root)
            keys = {normalize(path.stem), normalize(rel.with_suffix("").as_posix())}
            parent = path.parent.name
            if parent != folder:
                keys.add(normalize(parent))
                keys.add(normalize(f"{parent}-{path.stem}"))
            for key in keys:
                sources.setdefault(key, path)
    return sources


def bind(run_root: Path, overwrite: bool) -> dict[str, Any]:
    asset_direction_path = run_root / "workspace" / "asset-direction.json"
    if not asset_direction_path.exists():
        raise FileNotFoundError(asset_direction_path)
    payload = read_json(asset_direction_path)
    directions = payload.get("asset_directions", [])
    if not isinstance(directions, list):
        raise ValueError("asset-direction.json must contain asset_directions list")

    sources = discover_sources(run_root)
    bound: list[dict[str, str]] = []
    missing: list[str] = []
    for item in directions:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or "")
        if not asset_id:
            continue
        if not asset_id.startswith(VISUAL_PREFIXES):
            continue
        if item.get("provider_hints") and not overwrite:
            continue
        source = None
        for key in candidate_keys(asset_id):
            source = sources.get(key)
            if source:
                break
        if source is None:
            missing.append(asset_id)
            continue
        item["provider_hints"] = [str(source.relative_to(run_root))]
        item.setdefault("source_trace", {})["visual_source"] = "sprite_forge_skill"
        bound.append({"asset_id": asset_id, "provider_hint": str(source.relative_to(run_root))})

    write_json(asset_direction_path, payload)
    report = {
        "status": "pass",
        "run_root": str(run_root),
        "source_count": len(sources),
        "bound_count": len(bound),
        "bound": bound,
        "missing_count": len(missing),
        "missing": missing,
    }
    write_json(run_root / "reports" / "sprite-forge-provider-hints-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = bind(Path(args.run_root).resolve(), overwrite=args.overwrite)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
