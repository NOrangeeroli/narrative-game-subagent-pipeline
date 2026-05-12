#!/usr/bin/env python3
"""Create a small Web RPG run that uses pixel-native map coordinates."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "生成一个精简资产模式的像素坐标 Web RPG，用于验证逐像素地图坐标。",
        "requirements": [
            {"id": "req.pixel_coords", "text": "地图坐标必须使用 pixels，事件、边界和起点与 1280x720 背景像素一致。"},
            {"id": "req.playable", "text": "包含探索、对话、拾取、休息和一场战斗。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "星灯林地",
        "events": [
            {"id": "event.arrive", "summary": "巡林人进入星灯林地。"},
            {"id": "event.clear", "summary": "她点亮灯塔并驱散影子。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "Pixel Coordinate Smoke RPG",
        "start_node_id": "node.grove",
        "nodes": [
            {"id": "node.grove", "title": "星灯林地", "summary": "像素坐标地图验证场景。", "is_terminal": True}
        ],
        "edges": [],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "星灯林地",
        "design_brief": {
            "logline": "巡林人在 1280x720 的像素坐标地图中收集星露并击退影子。",
            "narrative_bible": {
                "themes": ["导航验证", "轻量战斗"],
                "cast": [{"id": "char.ranger", "name": "巡林人"}, {"id": "char.lantern_keeper", "name": "灯塔守望者"}],
            },
        },
        "global_state_variables": [
            {"id": "state.lamp_lit", "type": "boolean", "initial_value": False, "description": "星灯是否已点亮。"}
        ],
        "progression_rules": [{"id": "rule.finish", "summary": "击败影子后完成验证。"}],
    })


def write_rpg(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    maps = rpg / "maps"
    boundaries = rpg / "boundaries"
    maps.mkdir(parents=True, exist_ok=True)
    boundaries.mkdir(parents=True, exist_ok=True)

    write_json(rpg / "rpg-campaign.json", {
        "title": "星灯林地",
        "start_map_id": "map.starlamp_grove",
        "start_position": {"x": 180, "y": 520},
        "party": ["actor.ranger"],
        "entry_points": [{
            "id": "entry.ranger",
            "title": "巡林人",
            "description": "像素坐标验证路线。",
            "start_map_id": "map.starlamp_grove",
            "start_position": {"x": 180, "y": 520},
            "party": ["actor.ranger"],
            "initial_inventory": {"item.star_dew": 1},
        }],
        "goal": "点亮林地中心的星灯。",
        "final_quest_id": "quest.light_lamp",
        "ending_title": "验证完成",
        "ending_text": "星灯重新亮起，像素坐标、事件、边界和战斗流程都能运行。",
        "endings": [{"id": "lamp_lit", "title": "结局：星灯亮起", "text": "林地恢复了清晰的道路。", "conditions": {"flags": {"ending:lamp_lit": True}}}],
        "required_assets": ["map.starlamp_grove", "sprite.ranger", "sprite.keeper", "enemy.shadow_wisp", "battlebg.starlamp_grove", "icon.item.star_dew", "icon.skill.lamp_flash"],
    })
    write_json(rpg / "world-map.json", {"title": "星灯林地", "start_map_id": "map.starlamp_grove", "map_ids": ["map.starlamp_grove"]})
    write_json(maps / "starlamp_grove.map.json", {
        "id": "map.starlamp_grove",
        "title": "星灯林地",
        "coordinate_system": "pixels",
        "width": 1280,
        "height": 720,
        "asset_id": "map.starlamp_grove",
        "boundary_file": "../boundaries/starlamp_grove.boundaries.json",
        "layers": {"ground": [], "collision": []},
        "events": [
            {"id": "npc.keeper", "type": "npc", "x": 710, "y": 300, "name": "灯塔守望者", "dialogue_id": "dialogue.keeper", "sprite_asset_id": "sprite.keeper"},
            {"id": "pickup.star_dew", "type": "pickup", "x": 450, "y": 420, "item_id": "item.star_dew", "quantity": 1, "once": True},
            {"id": "rest.moss_bench", "type": "rest", "x": 1110, "y": 560, "rest_point_id": "rest.moss_bench"},
            {"id": "battle.shadow_wisp", "type": "battle", "x": 1010, "y": 205, "enemy_id": "enemy.shadow_wisp", "battle_background_asset_id": "battlebg.starlamp_grove", "once": True, "win_outcomes": [{"id": "lamp_lit", "lines": [{"speaker": "巡林人", "text": "星灯的路已经重新清楚了。"}], "set_flags": {"ending:lamp_lit": True}, "complete_quest_id": "quest.light_lamp"}]},
        ],
    })
    write_json(boundaries / "starlamp_grove.boundaries.json", {
        "map_id": "map.starlamp_grove",
        "coordinate_system": "pixels",
        "description": "像素坐标边界：地图边缘、池塘和暗石不可走，中心路径保持连通。",
        "collision_shapes": [
            {"id": "north_edge", "type": "rect", "x": 0, "y": 0, "w": 1280, "h": 64},
            {"id": "south_edge", "type": "rect", "x": 0, "y": 660, "w": 1280, "h": 60},
            {"id": "west_edge", "type": "rect", "x": 0, "y": 0, "w": 70, "h": 720},
            {"id": "east_edge", "type": "rect", "x": 1210, "y": 0, "w": 70, "h": 720},
            {"id": "moon_pond", "type": "polygon", "points": [[230, 120], [430, 95], [560, 180], [500, 270], [280, 260], [190, 190]]},
            {"id": "dark_stones", "type": "rect", "x": 800, "y": 420, "w": 230, "h": 120},
        ],
        "walkable_hint": {"x": 180, "y": 520},
    })

    write_json(rpg / "actors.json", {"actors": [{"id": "actor.ranger", "name": "巡林人", "sprite_asset_id": "sprite.ranger", "stats": {"hp": 32, "attack": 8, "defense": 3, "speed": 5}, "skills": ["skill.lamp_flash"]}]})
    write_json(rpg / "enemies.json", {"enemies": [{"id": "enemy.shadow_wisp", "name": "影火", "sprite_asset_id": "enemy.shadow_wisp", "stats": {"hp": 18, "attack": 5, "defense": 1, "speed": 3}, "pattern": ["attack", "guard", "skill"], "skills": ["skill.shadow_pulse"]}]})
    write_json(rpg / "skills.json", {"skills": [{"id": "skill.lamp_flash", "name": "星灯闪光", "power": 6, "focus_cost": 1}, {"id": "skill.shadow_pulse", "name": "暗影脉冲", "power": 3, "focus_cost": 0}]})
    write_json(rpg / "items.json", {"items": [{"id": "item.star_dew", "name": "星露", "description": "恢复用的微光露珠。"}]})
    write_json(rpg / "quests.json", {"quests": [{"id": "quest.light_lamp", "title": "点亮星灯", "description": "与守望者交谈并击退影火。"}]})
    write_json(rpg / "npc-dialogue.json", {"npc_dialogue": [{"id": "dialogue.keeper", "lines": [{"speaker": "灯塔守望者", "text": "这里的路以像素计算，靠近星灯时要避开池塘和暗石。"}, {"speaker": "巡林人", "text": "我会沿着亮路前进。"}]}]})
    write_json(rpg / "rest-points.json", {"rest_points": [{"id": "rest.moss_bench", "name": "苔藓长椅", "cost": 0}]})
    for filename in ("classes.json", "equipment.json", "encounter-tables.json", "events.json", "shops.json", "progression-rules.json"):
        write_json(rpg / filename, {})

    write_json(run_root / "workspace" / "asset-direction.json", {
        "style_pack": {
            "summary": "精简资产模式，清晰低成本 Web RPG 占位美术。",
            "rendering": "clean simple 2D RPG placeholder art with readable shapes",
            "lighting": "soft twilight",
            "palette": ["#23433b", "#6fa37a", "#d8bd77", "#5f9ca9"],
        },
        "asset_directions": [
            {"asset_id": "map.starlamp_grove", "kind": "map_asset", "description": "16:9 星灯林地俯视地图，清楚路径、池塘、暗石和边界。"},
            {"asset_id": "sprite.ranger", "kind": "sprite", "description": "巡林人小角色，斗篷和提灯。"},
            {"asset_id": "sprite.keeper", "kind": "sprite", "description": "灯塔守望者，温和长袍。"},
            {"asset_id": "enemy.shadow_wisp", "kind": "enemy_sprite", "description": "小型暗影火焰敌人。"},
            {"asset_id": "battlebg.starlamp_grove", "kind": "battle_background", "description": "星灯林地战斗背景。"},
            {"asset_id": "icon.item.star_dew", "kind": "item_icon", "description": "星露道具图标。"},
            {"asset_id": "icon.skill.lamp_flash", "kind": "skill_icon", "description": "星灯闪光技能图标。"},
            {"asset_id": "bgm.starlamp_grove", "kind": "bgm", "description": "星灯林地循环 BGM。", "mood": "looping twilight ambience"},
        ],
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "生成一个精简资产模式的像素坐标 Web RPG。\n")
    write_design_layer(run_root)
    write_rpg(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
