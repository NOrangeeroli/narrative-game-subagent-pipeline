#!/usr/bin/env python3
"""Create a small run that exercises extended interaction.inspect_scene behavior."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pipeline_lib import ensure_run_layout, path_for, project_shared_state, write_json, write_text


def yarn_manifest(node_id: str, unit_id: str, title: str, outcome_id: str | None = None, edge_id: str | None = None) -> dict:
    exit_bindings = []
    if outcome_id and edge_id:
        exit_bindings.append({"outcome_id": outcome_id, "edge_id": edge_id})
    return {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "source_node_id": node_id,
        "realization_unit_id": unit_id,
        "yarn_node_title": title,
        "local_asset_refs": [],
        "command_refs": [],
        "exit_bindings": exit_bindings,
        "state_reads": [],
        "state_writes": [],
        "continuity_summary": "Fixture VN fragment.",
        "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.search"], "node_ids": [node_id], "edge_ids": [edge_id] if edge_id else [], "game_ir_ids": []},
    }


def create_fixture(run_root: Path, overwrite: bool = False) -> None:
    if run_root.exists() and overwrite:
        shutil.rmtree(run_root)
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "Create a tiny investigation scene with local evidence interaction.\n")

    requirements = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "prompt": "Create a tiny investigation scene with local evidence interaction.",
        "target_experience": "The player searches a library desk, spends limited focus, connects clues, and leaves with a deduction.",
        "requirements": [{"id": "req.core", "priority": "must", "text": "Player must inspect visual regions, manage focus, collect, use an item, combine evidence, and complete the scene.", "source_phrase": "local evidence interaction"}],
        "creative_constraints": {"genre": "investigation", "tone": "quiet suspense", "themes": ["attention"], "motifs": ["library", "hidden evidence"], "prohibited_content": []},
        "production_constraints": {"target_language": "en", "approximate_node_count": 3, "desired_endings": 1, "asset_budget_level": "low", "notes": []},
        "assumptions": [],
        "unknowns": [],
    }
    write_json(path_for(run_root, "requirements"), requirements)

    synopsis = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "title": "The Drawer Note",
        "summary": "A short investigation verifies that scene-local item use and evidence combination can drive progress.",
        "events": [{"id": "event.search", "summary": "Search the library desk, recover the torn page, and connect it to wet ink.", "purpose": "Exercise interaction extension.", "requirement_ids": ["req.core"]}],
        "cast": [{"id": "char.investigator", "name": "Investigator", "role": "player viewpoint"}],
        "locations": [{"id": "loc.library", "name": "Library", "description": "A dim study with a locked drawer."}],
        "pacing_notes": [],
    }
    write_json(path_for(run_root, "synopsis"), synopsis)

    branch_graph = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "title": "Interaction Extension Fixture",
        "graph_scope": "full_game",
        "clusters": [],
        "source_outline_ids": ["event.search"],
        "start_node_id": "node.intro",
        "nodes": [
            {"id": "node.intro", "node_type": "start", "title": "Arrival", "summary": "The investigator enters the library.", "body": "The old library waits in silence.", "is_terminal": False, "source_event_ids": ["event.search"]},
            {"id": "node.search", "node_type": "scene", "title": "Desk Search", "summary": "The player searches the desk for a hidden torn page and proves it was recently altered.", "body": "Inspect the desk and use what you find.", "is_terminal": False, "source_event_ids": ["event.search"]},
            {"id": "node.end", "node_type": "terminal", "title": "Deduction Secured", "summary": "The player leaves with proof of a recent forgery.", "body": "The page and ink point to a recent forgery.", "is_terminal": True, "source_event_ids": ["event.search"]},
        ],
        "edges": [
            {"id": "edge.intro_to_search", "from": "node.intro", "to": "node.search", "label": "Search the desk", "condition_type": "unconditional"},
            {"id": "edge.search_to_end", "from": "node.search", "to": "node.end", "label": "Leave with the torn page", "condition_type": "outcome"},
        ],
    }
    write_json(path_for(run_root, "branch_graph"), branch_graph)

    game_ir = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "design_brief": {
            "target_experience": "A short tactile investigation where observation creates a later option.",
            "tone": "quiet suspense",
            "themes": ["attention"],
            "must_keep_constraints": ["Use declarative interaction data only."],
            "production_constraints": {},
            "narrative_bible": {"cast": synopsis["cast"], "locations": synopsis["locations"], "timeline": [], "continuity_rules": []},
        },
        "world": {"summary": "A contained investigation fixture."},
        "entities": [{"id": "char.investigator", "kind": "character", "name": "Investigator", "description": "The viewpoint character."}],
        "global_state_variables": [
            {"id": "state.drawer_opened", "type": "boolean", "initial_value": False, "description": "Whether the drawer was opened."},
            {"id": "state.has_torn_page", "type": "boolean", "initial_value": False, "description": "Whether the player recovered the torn page."},
            {"id": "state.deduced_recent_forgery", "type": "boolean", "initial_value": False, "description": "Whether the player connected the torn page to the fresh ink."},
        ],
        "progression_stages": [{"id": "stage.fixture", "description": "Single interaction smoke test."}],
        "event_rules": [],
    }
    write_json(path_for(run_root, "game_ir"), game_ir)
    write_json(path_for(run_root, "shared_state"), project_shared_state(game_ir))

    plans = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "plans": [
            {
                "source_node_id": "node.intro",
                "realization_kind": "vn_yarn",
                "unit_id": "realization.node_intro",
                "entry_binding": {"type": "yarn_node", "node_title": "Node_Intro"},
                "exit_bindings": [{"outcome_id": "continue", "edge_id": "edge.intro_to_search"}],
                "required_state_reads": [],
                "state_writes": [],
                "required_assets": [],
                "continuity_summary": "Introduce the search.",
                "implementation_notes": [],
                "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.search"], "node_ids": ["node.intro"], "edge_ids": ["edge.intro_to_search"], "game_ir_ids": []},
            },
            {
                "source_node_id": "node.search",
                "realization_kind": "interaction",
                "unit_id": "realization.node_search",
                "entry_binding": {"type": "gameplay_unit", "adapter_id": "interaction.inspect_scene"},
                "exit_bindings": [{"outcome_id": "complete", "edge_id": "edge.search_to_end", "label": "Leave with the torn page"}],
                "required_state_reads": [],
                "state_writes": [],
                "required_assets": ["bg.library_night"],
                "continuity_summary": "The player finds the torn page and deduces it was recently altered.",
                "implementation_notes": ["Exercise overlay hotspot bounds, focus budget, inspect, collect, use, reveal, evidence combine, and completion requirements."],
                "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.search"], "node_ids": ["node.search"], "edge_ids": ["edge.search_to_end"], "game_ir_ids": ["state.drawer_opened", "state.has_torn_page", "state.deduced_recent_forgery"]},
            },
            {
                "source_node_id": "node.end",
                "realization_kind": "vn_yarn",
                "unit_id": "realization.node_end",
                "entry_binding": {"type": "yarn_node", "node_title": "Node_End"},
                "exit_bindings": [],
                "required_state_reads": [],
                "state_writes": [],
                "required_assets": [],
                "continuity_summary": "End the fixture.",
                "implementation_notes": [],
                "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.search"], "node_ids": ["node.end"], "edge_ids": [], "game_ir_ids": []},
            },
        ],
    }
    write_json(path_for(run_root, "realization_plans"), plans)

    interaction = {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "source_node_id": "node.search",
        "realization_unit_id": "realization.node_search",
        "realization_kind": "interaction",
        "adapter_id": "interaction.inspect_scene",
        "entry_text": "Search the desk. Focus is limited, so inspect what looks meaningful.",
        "exit_bindings": [{"outcome_id": "complete", "edge_id": "edge.search_to_end", "label": "Leave with the torn page", "state_writes": []}],
        "required_state_reads": [],
        "state_writes": [],
        "required_assets": ["bg.library_night", "prop.small_key", "prop.torn_page", "sfx.unlock"],
        "runtime_spec": {
            "prompt": "Inspect visual regions, collect evidence, and connect the clues.",
            "scene": {"background_asset_id": "bg.library_night", "layout": "overlay", "fallback_layout": "grid", "show_hotspot_labels": "hover"},
            "action_budget": {"id": "focus", "label": "Focus", "initial": 6, "inspect_cost": 1, "use_cost": 1, "wrong_use_cost": 1, "combine_cost": 1, "depleted_text": "You are out of focus. Leave with what you already understand."},
            "hotspots": [
                {
                    "id": "desk_mat",
                    "label": "Desk mat",
                    "kind": "object",
                    "initially_visible": True,
                    "verbs": ["inspect", "collect"],
                    "bounds": {"x": 0.16, "y": 0.58, "w": 0.26, "h": 0.16},
                    "reveal_text": "The mat lifts just enough to reveal a brass key.",
                    "collects": ["item.small_key"],
                    "asset_id": "prop.small_key",
                },
                {
                    "id": "ink_bottle",
                    "label": "Ink bottle",
                    "kind": "object",
                    "initially_visible": True,
                    "verbs": ["inspect", "collect"],
                    "bounds": {"x": 0.38, "y": 0.48, "w": 0.13, "h": 0.16},
                    "reveal_text": "The ink is still wet. A fresh smear stains your glove.",
                    "collects": ["item.wet_ink"],
                },
                {
                    "id": "locked_drawer",
                    "label": "Locked drawer",
                    "kind": "container",
                    "initially_visible": True,
                    "bounds": {"x": 0.59, "y": 0.56, "w": 0.25, "h": 0.16},
                    "requires_items": ["item.small_key"],
                    "blocked_text": "The drawer handle will not move without a key.",
                    "blocked_cost": 1,
                    "use_prompt": "The drawer has a tiny brass keyhole.",
                    "use_results": [
                        {
                            "item_id": "item.small_key",
                            "cost": 1,
                            "text": "The small key turns. Inside the drawer, a photo frame slips aside.",
                            "reveals_hotspots": ["photo_frame"],
                            "state_writes": [{"state_variable_id": "state.drawer_opened", "operation": "set", "value": True, "description": "The drawer was opened."}],
                            "sfx_asset_id": "sfx.unlock",
                        }
                    ],
                },
                {
                    "id": "photo_frame",
                    "label": "Photo frame",
                    "kind": "evidence",
                    "initially_visible": False,
                    "verbs": ["inspect", "collect"],
                    "bounds": {"x": 0.49, "y": 0.33, "w": 0.18, "h": 0.16},
                    "reveal_text": "A torn page is taped behind the photo.",
                    "collects": ["item.torn_page"],
                    "asset_id": "prop.torn_page",
                    "state_writes": [{"state_variable_id": "state.has_torn_page", "operation": "set", "value": True, "description": "The torn page was recovered."}],
                },
            ],
            "items": [
                {"id": "item.small_key", "label": "Small key", "description": "A brass key from under the desk mat.", "asset_id": "prop.small_key"},
                {"id": "item.wet_ink", "label": "Wet ink", "description": "A fresh smear from the ink bottle."},
                {"id": "item.torn_page", "label": "Torn page", "description": "Evidence recovered from behind the photo.", "asset_id": "prop.torn_page"},
                {"id": "evidence.recent_forgery", "label": "Recent forgery", "description": "The page and ink belong to the same fresh alteration."},
            ],
            "evidence_combinations": [
                {
                    "id": "deduce_recent_forgery",
                    "label": "Compare wet ink with torn page",
                    "item_ids": ["item.wet_ink", "item.torn_page"],
                    "creates_items": ["evidence.recent_forgery"],
                    "text": "The torn edge carries the same fresh ink. This page was altered tonight.",
                    "state_writes": [{"state_variable_id": "state.deduced_recent_forgery", "operation": "set", "value": True, "description": "The player deduced the recent forgery."}],
                }
            ],
            "completion": {"required_hotspots": ["photo_frame"], "required_items": ["evidence.recent_forgery"], "outcome_id": "complete", "label": "Leave with the deduction"},
        },
        "fail_forward": {"enabled": False},
        "continuity_summary": "The player recovers the torn page and deduces it was recently altered.",
        "source_trace": {"requirement_ids": ["req.core"], "event_ids": ["event.search"], "node_ids": ["node.search"], "edge_ids": ["edge.search_to_end"], "game_ir_ids": ["state.drawer_opened", "state.has_torn_page", "state.deduced_recent_forgery"]},
    }
    write_json(run_root / "workspace" / "realization" / "interactions" / "node.search.interaction.json", interaction)

    write_text(run_root / "workspace" / "vn" / "fragments" / "node.intro.yarn", """title: Node_Intro
---
// source_node: node.intro
Narrator: The old library waits in silence.
<<complete_activity outcome="continue">>
===
""")
    write_json(run_root / "workspace" / "vn" / "fragments" / "node.intro.manifest.json", yarn_manifest("node.intro", "realization.node_intro", "Node_Intro", "continue", "edge.intro_to_search"))

    write_text(run_root / "workspace" / "vn" / "fragments" / "node.end.yarn", """title: Node_End
---
// source_node: node.end
Narrator: The torn page and wet ink prove the page was altered tonight.
===
""")
    write_json(run_root / "workspace" / "vn" / "fragments" / "node.end.manifest.json", yarn_manifest("node.end", "realization.node_end", "Node_End"))

    write_json(path_for(run_root, "asset_direction"), {
        "metadata": {"schema_version": "0.1.0", "generated_by": "create_interaction_fixture.py", "notes": []},
        "style_pack": {"summary": "quiet investigation VN", "palette": ["#1c2528", "#f4c76b", "#76c5b6"], "lighting": "dim lamplight", "rendering": "clean illustrated props"},
        "asset_directions": [],
        "voice_profiles": {},
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create_fixture(run_root, overwrite=args.overwrite)
    print(str(run_root))


if __name__ == "__main__":
    main()
