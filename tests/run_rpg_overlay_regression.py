#!/usr/bin/env python3
"""Regression checks for narrative-first RPG overlay stages."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run(args: list[str], expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if expect_success and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Command failed: {' '.join(args)}")
    if not expect_success and result.returncode == 0:
        print(result.stdout)
        raise SystemExit(f"Command unexpectedly passed: {' '.join(args)}")
    return result


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_fixture(name: str, destination: Path) -> Path:
    target = destination / name
    shutil.copytree(FIXTURES / name, target)
    return target


def write_overlay_plan(run_root: Path) -> None:
    write_json(run_root / "workspace" / "design_layer_rpg" / "rpg-overlay-plan.json", {
        "metadata": {
            "schema_version": "0.1.0",
            "generated_by": "RPGSystemPlanner",
            "mode": "narrative_first_overlay",
        },
        "source_story_levels": ["level_01", "level_02"],
        "story_slices": [
            {
                "id": "slice.archive",
                "title": "Archive Investigation",
                "source_story_unit_ids": ["story.l1.ch01", "story.l1.ch02"],
                "criticality": "critical",
                "required_story_beats": [
                    "The player enters the archive investigation.",
                    "The player resolves the archive pressure without changing the ending.",
                ],
                "character_arc_beats": ["The protagonist moves from uncertainty to committed action."],
                "emotional_turns": ["curiosity_to_resolve"],
                "canon_constraints": ["Preserve the V3 public graph outcomes."],
                "forbidden_changes": ["Do not add a new ending."],
                "map_intent_ids": ["map_intent.archive"],
                "questline_intent_ids": ["questline.archive"],
                "combat_intent_ids": [],
                "equipment_intent_ids": ["equipment_intent.archive_key"],
                "progression_axis_ids": ["progression.focus"],
            }
        ],
        "region_intents": [],
        "map_intents": [
            {
                "id": "map_intent.archive",
                "story_slice_ids": ["slice.archive"],
                "narrative_function": "exploration",
                "story_obligations": ["Stage the investigation as a playable archive space."],
                "forbidden_changes": ["Do not split the public route."],
            }
        ],
        "questline_intents": [
            {
                "id": "questline.archive",
                "story_slice_ids": ["slice.archive"],
                "narrative_function": "reveal",
                "story_obligations": ["Turn the two story units into quest stages."],
                "forbidden_changes": ["Do not invent a new canonical culprit."],
            }
        ],
        "combat_intents": [],
        "equipment_intents": [
            {
                "id": "equipment_intent.archive_key",
                "story_slice_ids": ["slice.archive"],
                "narrative_function": "access",
                "story_obligations": ["Represent archive access without changing edge conditions."],
                "forbidden_changes": ["Do not add a new locked route."],
            }
        ],
        "progression_axes": [
            {
                "id": "progression.focus",
                "story_slice_ids": ["slice.archive"],
                "narrative_function": "relationship_shift",
                "story_obligations": ["Track growing focus as flavor and pacing only."],
                "forbidden_changes": ["Do not create a grind gate for the V3 ending."],
            }
        ],
        "postdesign_scope": [],
        "repair_notes": [],
    })


def write_minimal_rpg(run_root: Path) -> None:
    write_json(run_root / "workspace" / "design_layer" / "branch_graph.json", {
        "title": "Old RPG",
        "graph_scope": "full_game",
        "start_node_id": "node.start",
        "nodes": [{"id": "node.start", "title": "Start", "summary": "Start.", "is_terminal": True}],
        "edges": [],
    })
    write_json(run_root / "workspace" / "design_layer" / "game_ir.json", {
        "design_brief": {"target_experience": "Old RPG compatibility"},
        "global_state_variables": [],
        "event_rules": [],
    })
    write_json(run_root / "workspace" / "rpg" / "rpg-campaign.json", {
        "title": "Old RPG",
        "start_map_id": "map.home",
        "start_position": {"x": 100, "y": 100},
        "party": ["actor.hero"],
    })
    write_json(run_root / "workspace" / "rpg" / "world-map.json", {
        "title": "World",
        "start_map_id": "map.home",
        "maps": [{"id": "map.home", "title": "Home", "role": "start"}],
    })
    write_json(run_root / "workspace" / "rpg" / "maps" / "home.map.json", {
        "id": "map.home",
        "title": "Home",
        "width": 1280,
        "height": 720,
        "layers": {"ground": [], "collision": []},
        "events": [
            {"id": "npc.guide", "type": "npc", "x": 360, "y": 360, "name": "Guide", "dialogue_id": "dialogue.guide"},
        ],
    })
    write_json(run_root / "workspace" / "rpg" / "actors.json", {
        "actors": [{"id": "actor.hero", "name": "Hero", "stats": {"hp": 30, "attack": 8, "defense": 3}}],
    })
    write_json(run_root / "workspace" / "rpg" / "npc-dialogue.json", {
        "npc_dialogue": [{"id": "dialogue.guide", "lines": [{"speaker": "Guide", "text": "Stay close."}]}],
    })


def write_scene_script_rpg(run_root: Path) -> None:
    write_minimal_rpg(run_root)
    write_json(run_root / "workspace" / "rpg" / "quests.json", {
        "quests": [{"id": "quest.opening", "title": "Opening", "description": "Watch the opening scene."}],
    })
    write_json(run_root / "workspace" / "rpg" / "scene-scripts.json", {
        "scene_scripts": [
            {
                "id": "scene.opening",
                "map_id": "map.home",
                "trigger": {"kind": "on_entry", "map_id": "map.home", "once": True},
                "blocking": True,
                "actors": [
                    {"actor_id": "player", "x": 180, "y": 520},
                    {"actor_id": "actor.guide", "event_id": "npc.guide", "x": 360, "y": 360},
                ],
                "beats": [
                    {"kind": "dialogue", "speaker_actor_id": "actor.guide", "text": "The road is moving before you touch the keys."},
                    {"kind": "move_actor", "actor_id": "player", "to": {"x": 260, "y": 520}, "speed": 200},
                    {"kind": "activate_quest", "quest_id": "quest.opening"},
                    {"kind": "set_flag", "flag": "scene.opening.done", "value": True},
                ],
            }
        ],
    })


def test_overlay_flow(tmp: Path) -> None:
    run_root = copy_fixture("v3_hierarchical_minimal", tmp)
    run([sys.executable, "scripts/run_pipeline.py", "compile-design", "--run-root", str(run_root), "--design-layer", "v3"])
    write_overlay_plan(run_root)
    run([sys.executable, "scripts/run_pipeline.py", "validate-rpg-overlay", "--run-root", str(run_root)])
    run([sys.executable, "scripts/run_pipeline.py", "freeze-narrative", "--run-root", str(run_root)])
    freeze = read_json(run_root / "workspace" / "design_layer_rpg" / "narrative-freeze.json")
    assert freeze["branch_graph_hash"]
    assert "v3.l1.ch01.entry" in freeze["public_node_ids"]

    run([sys.executable, "scripts/run_pipeline.py", "prepare-rpg-postdesign-slices", "--run-root", str(run_root)])
    slices = read_json(run_root / "workspace" / "design_layer_rpg" / "rpg-postdesign-slices.json")
    assert slices["slice_count"] == 1
    assert slices["public_node_count"] > slices["slice_count"]
    packet = read_json(run_root / "workspace" / "controller-packets" / "postdesign" / "rpg" / "slice.archive.json")
    assert packet["public_node_ids"] == ["v3.l1.ch01.entry", "v3.l1.ch02.resolve"]
    assert packet["map_intents"][0]["id"] == "map_intent.archive"

    branch_graph = read_json(run_root / "workspace" / "design_layer" / "branch_graph.json")
    branch_graph["title"] = "Changed After Freeze"
    write_json(run_root / "workspace" / "design_layer" / "branch_graph.json", branch_graph)
    run([sys.executable, "scripts/run_pipeline.py", "freeze-narrative", "--run-root", str(run_root), "--verify"], expect_success=False)


def test_old_rpg_compatibility(tmp: Path) -> None:
    run_root = tmp / "old_rpg"
    write_minimal_rpg(run_root)
    run([sys.executable, "scripts/validate_rpg.py", "--run-root", str(run_root)])
    report = read_json(run_root / "reports" / "rpg-validation.json")
    assert report["status"] == "pass"
    coverage = read_json(run_root / "reports" / "rpg-coverage.json")
    assert coverage["rpg_overlay_trace"]["status"] == "not_applicable"


def test_scene_scripts_compile_and_export(tmp: Path) -> None:
    run_root = tmp / "scene_script_rpg"
    write_scene_script_rpg(run_root)
    run([sys.executable, "scripts/validate_rpg.py", "--run-root", str(run_root)])
    manifest = read_json(run_root / "workspace" / "rpg" / "rpg-manifest.json")
    assert manifest["scene_scripts"][0]["id"] == "scene.opening"
    coverage = read_json(run_root / "reports" / "rpg-coverage.json")
    assert coverage["scene_script_count"] == 1

    run([sys.executable, "scripts/export_web_rpg.py", "--run-root", str(run_root)])
    game_data = (run_root / "build" / "web-rpg" / "game-data.js").read_text(encoding="utf-8")
    assert '"scene_scripts"' in game_data
    assert '"scene.opening"' in game_data


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        test_overlay_flow(tmp)
        test_old_rpg_compatibility(tmp)
        test_scene_scripts_compile_and_export(tmp)
    print("rpg overlay regression: pass")


if __name__ == "__main__":
    main()
