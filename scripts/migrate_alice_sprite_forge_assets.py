#!/usr/bin/env python3
"""Bind Sprite Forge generated Alice in Wonderland assets into the RPG pipeline."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


RUN_ROOT = Path("runs/alice-wonderland-rpg")
ASSET_ROOT = RUN_ROOT / "workspace" / "sprite-forge-assets"
RAW_ROOT = ASSET_ROOT / "raw"


MAP_PANELS = [
    ("map.rabbit_hole_garden", "rabbit-hole-garden.png"),
    ("map.mad_tea_party", "mad-tea-party.png"),
    ("map.queen_court", "queen-court.png"),
]

BATTLE_PANELS = [
    ("battlebg.tea_table", "tea-table.png"),
    ("battlebg.queen_court", "queen-court.png"),
]

SPRITE_CELLS = [
    ("sprite.alice", "sprites/alice.png"),
    ("sprite.white_rabbit", "sprites/white-rabbit.png"),
    ("sprite.cheshire_cat", "sprites/cheshire-cat.png"),
    ("sprite.mad_hatter", "sprites/mad-hatter.png"),
    ("sprite.dormouse", "sprites/dormouse.png"),
    ("sprite.queen_hearts", "sprites/queen-hearts.png"),
    ("sprite.card_guard", "sprites/card-guard.png"),
    ("enemy.card_guard", "sprites/enemy-card-guard.png"),
    ("enemy.mad_teapot", "sprites/mad-teapot.png"),
    ("enemy.queen_hearts", "sprites/enemy-queen-hearts.png"),
    ("icon.item.drink_me", "icons/drink-me.png"),
    ("icon.item.eat_me", "icons/eat-me.png"),
]

ICON_UI_CELLS = [
    ("icon.skill.curiosity", "icons/curiosity.png"),
    ("ui.storybook_panel", "icons/storybook-panel.png"),
]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_size(source: Path) -> tuple[int, int]:
    raw = subprocess.check_output(["magick", "identify", "-format", "%w %h", str(source)], text=True).strip()
    width, height = [int(value) for value in raw.split()]
    return width, height


def split_vertical_atlas(source: Path, rows: int, output_dir: Path, panels: list[tuple[str, str]], resize: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = image_size(source)
    cell_h = height // rows
    hints: dict[str, str] = {}
    for index, (asset_id, filename) in enumerate(panels):
        output = output_dir / filename
        run([
            "magick",
            str(source),
            "-crop",
            f"{width}x{cell_h}+0+{index * cell_h}",
            "+repage",
            "-resize",
            resize,
            str(output),
        ])
        hints[asset_id] = str(output.relative_to(RUN_ROOT))
    return hints


def process_single(raw_cell: Path, asset_id: str, final_relative: str, cell_size: int) -> str:
    output_dir = ASSET_ROOT / "processed" / asset_id
    run([
        "python3",
        "scripts/sprite_forge/generate2dsprite.py",
        "process",
        "--input",
        str(raw_cell),
        "--target",
        "asset",
        "--mode",
        "single",
        "--rows",
        "1",
        "--cols",
        "1",
        "--cell-size",
        str(cell_size),
        "--single-size",
        "256",
        "--output-dir",
        str(output_dir),
        "--fit-scale",
        "0.9",
        "--align",
        "feet",
        "--component-mode",
        "largest",
        "--component-padding",
        "8",
        "--min-component-area",
        "80",
        "--threshold",
        "95",
        "--edge-threshold",
        "140",
        "--edge-clean-depth",
        "2",
    ])
    final_output = ASSET_ROOT / final_relative
    final_output.parent.mkdir(parents=True, exist_ok=True)
    source_asset = output_dir / "single-1.png"
    if not source_asset.exists():
        source_asset = output_dir / "sheet-transparent.png"
    if not source_asset.exists():
        raise FileNotFoundError(f"Sprite processor did not produce an output for {asset_id}")
    shutil.copy2(source_asset, final_output)
    return str(final_output.relative_to(RUN_ROOT))


def split_sheet(source: Path, rows: int, cols: int, cells: list[tuple[str, str]], raw_dir_name: str) -> dict[str, str]:
    cell_root = RAW_ROOT / raw_dir_name
    cell_root.mkdir(parents=True, exist_ok=True)
    width, height = image_size(source)
    cell_w = width // cols
    cell_h = height // rows
    cell_size = max(cell_w, cell_h)
    hints: dict[str, str] = {}
    for index, (asset_id, relative_output) in enumerate(cells):
        row = index // cols
        col = index % cols
        raw_cell = cell_root / f"{asset_id}.png"
        run([
            "magick",
            str(source),
            "-crop",
            f"{cell_w}x{cell_h}+{col * cell_w}+{row * cell_h}",
            "+repage",
            str(raw_cell),
        ])
        hints[asset_id] = process_single(raw_cell, asset_id, relative_output, cell_size)
    return hints


def process_walk_sheet() -> dict[str, str]:
    source = RAW_ROOT / "alice-walk-4x4.png"
    if not source.exists():
        return {}
    output_dir = ASSET_ROOT / "processed" / "sprite.alice_walk"
    run([
        "python3",
        "scripts/sprite_forge/generate2dsprite.py",
        "process",
        "--input",
        str(source),
        "--target",
        "player",
        "--mode",
        "walk",
        "--rows",
        "4",
        "--cols",
        "4",
        "--label-prefix",
        "walk",
        "--output-dir",
        str(output_dir),
        "--fit-scale",
        "0.9",
        "--align",
        "feet",
        "--component-mode",
        "largest",
        "--component-padding",
        "24",
        "--min-component-area",
        "80",
        "--threshold",
        "95",
        "--edge-threshold",
        "140",
        "--edge-clean-depth",
        "2",
        "--shared-scale",
    ])
    hints: dict[str, str] = {}
    sheet = output_dir / "sheet-transparent.png"
    if sheet.exists():
        final_sheet = ASSET_ROOT / "sprites" / "alice-walk-4x4.png"
        final_sheet.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sheet, final_sheet)
        hints["sprite.alice.walk_sheet"] = str(final_sheet.relative_to(RUN_ROOT))
    directions = ("down", "left", "right", "up")
    for index in range(1, 17):
        source_frame = output_dir / f"walk-{index}.png"
        if not source_frame.exists():
            continue
        direction = directions[(index - 1) // 4]
        frame = ((index - 1) % 4) + 1
        frame_output = ASSET_ROOT / "sprites" / "alice-walk-frames" / f"{direction}-{frame}.png"
        frame_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_frame, frame_output)
        hints[f"sprite.alice.walk.{direction}.{frame}"] = str(frame_output.relative_to(RUN_ROOT))
    return hints


def attach_provider_hints(hints: dict[str, str]) -> None:
    path = RUN_ROOT / "workspace" / "asset-direction.json"
    payload = read_json(path)
    for asset in payload.get("asset_directions", []):
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("asset_id")
        if asset_id in hints:
            asset["provider_hints"] = [hints[asset_id]]
            asset.setdefault("source_trace", {})["visual_source"] = "sprite_forge_skill_imagegen"
    write_json(path, payload)


def main() -> None:
    hints: dict[str, str] = {}
    hints.update(split_vertical_atlas(RAW_ROOT / "alice-map-atlas.png", 3, ASSET_ROOT / "maps", MAP_PANELS, "1280x720!"))
    hints.update(split_vertical_atlas(RAW_ROOT / "alice-battle-atlas.png", 2, ASSET_ROOT / "battle-backgrounds", BATTLE_PANELS, "1280x720!"))
    hints.update(split_sheet(RAW_ROOT / "alice-sprite-sheet.png", 4, 3, SPRITE_CELLS, "sprite-cells"))
    hints.update(split_sheet(RAW_ROOT / "alice-icon-ui-sheet.png", 1, 2, ICON_UI_CELLS, "icon-ui-cells"))
    walk_hints = process_walk_sheet()
    attach_provider_hints(hints)
    report = {
        "status": "pass",
        "asset_count": len(hints),
        "walk_asset_count": len(walk_hints),
        "provider_hints": hints,
        "walk_outputs": walk_hints,
        "source": "generate2dmap and generate2dsprite skills via built-in image_gen",
    }
    write_json(ASSET_ROOT / "metadata" / "sprite-forge-binding-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
