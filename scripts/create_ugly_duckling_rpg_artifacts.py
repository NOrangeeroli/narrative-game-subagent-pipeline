#!/usr/bin/env python3
"""Create a complete Web RPG run for The Ugly Duckling."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


def grid(width: int, height: int, fill: str = "grass") -> list[list[str]]:
    return [[fill for _ in range(width)] for _ in range(height)]


def collision(width: int, height: int) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def make_path_layer(width: int, height: int, points: list[tuple[int, int]], fill: str = "grass") -> list[list[str]]:
    layer = grid(width, height, fill)
    for x, y in points:
        if 0 <= x < width and 0 <= y < height:
            layer[y][x] = "path"
    return layer


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "《丑小鸭》改编成短篇 Web RPG。",
        "requirements": [
            {"id": "req.public_domain", "text": "基于公版童话《丑小鸭》，采用温柔北欧绘本风，不引用现代影视改编设计。"},
            {"id": "req.playable", "text": "浏览器可游玩的短篇 RPG，包含探索、对白、道具、休息点和三场轻量战斗。"},
            {"id": "req.theme", "text": "突出孤独、误解、坚持、自我认识和温柔的成长。"},
            {"id": "req.language", "text": "游戏文本使用中文。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "丑小鸭",
        "events": [
            {"id": "event.hatch", "summary": "一只灰色小鸟在芦苇窝最后破壳，被鸭群误解。"},
            {"id": "event.farmyard", "summary": "它穿过农家院，被鸡、猫和追逐声逼向荒野。"},
            {"id": "event.winter", "summary": "冰封沼泽中，寒风和孤独几乎夺走它的力气。"},
            {"id": "event.spring", "summary": "春天湖面出现白天鹅，它终于看见真正的倒影。"},
            {"id": "event.acceptance", "summary": "它接纳自己，展开翅膀加入湖上的天鹅。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "Ugly Duckling RPG Branch Graph",
        "start_node_id": "node.reed_marsh",
        "nodes": [
            {"id": "node.reed_marsh", "title": "芦苇窝", "summary": "灰色小鸟从芦苇窝醒来，学习在嘲笑中前进。"},
            {"id": "node.farmyard", "title": "农家院", "summary": "农家院的目光和追逐声让它寻找真正的去处。"},
            {"id": "node.winter_lake", "title": "冰封湖", "summary": "它撑过寒冬，并在湖边看见春天的白影。"},
            {"id": "node.spring_lake", "title": "春湖倒影", "summary": "水面揭示它已经成为白天鹅。"},
            {"id": "node.first_flight", "title": "第一次飞行", "summary": "它不再由嘲笑者命名。", "is_terminal": True},
        ],
        "edges": [
            {"id": "edge.marsh.farmyard", "from": "node.reed_marsh", "to": "node.farmyard", "condition_type": "unconditional"},
            {"id": "edge.farmyard.winter", "from": "node.farmyard", "to": "node.winter_lake", "condition_type": "unconditional"},
            {"id": "edge.winter.spring", "from": "node.winter_lake", "to": "node.spring_lake", "condition_type": "unconditional"},
            {"id": "edge.spring.flight", "from": "node.spring_lake", "to": "node.first_flight", "condition_type": "terminal_resolution"},
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "丑小鸭",
        "design_brief": {
            "logline": "被误解的小灰鸟穿过农家院和冰封湖，在春天认出真正的自己。",
            "narrative_bible": {
                "themes": ["孤独", "坚持", "自我认识", "温柔成长"],
                "cast": [
                    {"id": "char.duckling", "name": "小灰鸟"},
                    {"id": "char.mother_duck", "name": "母鸭"},
                    {"id": "char.hen", "name": "花母鸡"},
                    {"id": "char.cat", "name": "老猫"},
                    {"id": "char.swan", "name": "白天鹅"},
                    {"id": "char.winter_wind", "name": "冬风"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.left_nest", "type": "boolean", "initial_value": False, "description": "是否离开芦苇窝。"},
            {"id": "state.survived_winter", "type": "boolean", "initial_value": False, "description": "是否撑过冰封冬天。"},
            {"id": "state.accepted_self", "type": "boolean", "initial_value": False, "description": "是否接纳真正的自己。"},
        ],
        "progression_rules": [
            {"id": "rule.start", "summary": "从芦苇窝开始。"},
            {"id": "rule.winter", "summary": "通过农家院后进入冰封湖。"},
            {"id": "rule.end", "summary": "春湖倒影后完成第一次飞行。"},
        ],
    })


def write_rpg_tables(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "rpg-campaign.json", {
        "title": "丑小鸭",
        "start_map_id": "map.reed_marsh",
        "start_position": {"x": 2, "y": 5},
        "party": ["actor.duckling"],
        "entry_title": "选择进入《丑小鸭》的角度",
        "entry_text": "同一个湖岸，可以从被误解者、旁观者和归来者三个角度进入。",
        "entry_points": [
            {
                "id": "entry.duckling",
                "title": "小灰鸟出走",
                "description": "从芦苇窝出发，穿过农家院和冰封湖，寻找自己的名字。",
                "start_map_id": "map.reed_marsh",
                "start_position": {"x": 2, "y": 5},
                "party": ["actor.duckling"],
                "initial_quests": ["quest.leave_nest"],
                "initial_flags": {"route.duckling": True},
                "initial_inventory": {"item.reed_seed": 1},
            },
            {
                "id": "entry.farm_sparrow",
                "title": "檐下麻雀",
                "description": "从农家院旁观误解如何形成，并帮助小灰鸟避开追逐。",
                "start_map_id": "map.farmyard",
                "start_position": {"x": 2, "y": 5},
                "party": ["actor.farm_sparrow"],
                "initial_quests": ["quest.cross_farmyard"],
                "initial_flags": {"route.sparrow": True},
                "initial_inventory": {"item.bread_crumb": 1},
            },
            {
                "id": "entry.young_swan",
                "title": "春湖白影",
                "description": "从春湖边见证小灰鸟归来，完成最后的接纳。",
                "start_map_id": "map.spring_lake",
                "start_position": {"x": 2, "y": 5},
                "party": ["actor.young_swan"],
                "initial_quests": ["quest.find_reflection"],
                "initial_flags": {"route.swan": True, "state.survived_winter": True},
                "initial_inventory": {"item.warm_feather": 1},
            },
        ],
        "goal": "撑过误解与寒冬，在春湖倒影中认出真正的自己。",
        "major_quest_ids": ["quest.leave_nest", "quest.cross_farmyard", "quest.find_reflection"],
        "final_quest_id": "quest.find_reflection",
        "ending_title": "真正的名字",
        "ending_text": "湖水没有重复嘲笑声。小灰鸟在倒影中看见白天鹅，第一次展开了属于自己的翅膀。",
        "endings": [{
            "id": "first_flight",
            "title": "结局：第一次飞行",
            "text": "它不再需要别人允许自己美丽。",
            "conditions": {"flags": {"ending:first_flight": True}},
        }],
        "required_assets": [
            "map.reed_marsh", "map.farmyard", "map.spring_lake", "tileset.lake_storybook",
            "sprite.duckling", "sprite.mother_duck", "sprite.hen", "sprite.cat", "sprite.swan", "sprite.farm_sparrow",
            "enemy.mocking_gaggle", "enemy.farmyard_chaser", "enemy.winter_wind",
            "battlebg.reed_marsh", "battlebg.farmyard", "battlebg.winter_lake",
            "icon.item.reed_seed", "icon.item.bread_crumb", "icon.item.warm_feather", "icon.skill.brave_peep",
            "ui.watercolor_panel",
        ],
    })
    write_json(rpg / "world-map.json", {"title": "湖岸与农家院", "start_map_id": "map.reed_marsh", "maps": [
        {"id": "map.reed_marsh", "title": "芦苇窝", "role": "field"},
        {"id": "map.farmyard", "title": "农家院", "role": "town"},
        {"id": "map.spring_lake", "title": "春湖", "role": "finale"},
    ]})
    write_json(rpg / "actors.json", {"actors": [
        {"id": "actor.duckling", "name": "小灰鸟", "class_id": "class.wanderer", "stats": {"hp": 58, "attack": 13, "defense": 6, "speed": 6}, "sprite_asset_id": "sprite.duckling", "skills": ["skill.brave_peep", "skill.keep_warm", "skill.reflect"]},
        {"id": "actor.farm_sparrow", "name": "檐下麻雀", "class_id": "class.guide", "stats": {"hp": 50, "attack": 12, "defense": 5, "speed": 8}, "sprite_asset_id": "sprite.farm_sparrow", "skills": ["skill.brave_peep", "skill.quick_flutter"]},
        {"id": "actor.young_swan", "name": "年轻白天鹅", "class_id": "class.wanderer", "stats": {"hp": 62, "attack": 14, "defense": 6, "speed": 7}, "sprite_asset_id": "sprite.swan", "skills": ["skill.reflect", "skill.wingbeat"]},
    ]})
    write_json(rpg / "classes.json", {"classes": [
        {"id": "class.wanderer", "name": "湖岸旅人", "growth": "均衡成长，重视韧性。"},
        {"id": "class.guide", "name": "檐下向导", "growth": "速度较高，擅长引路。"},
    ]})
    write_json(rpg / "items.json", {"items": [
        {"id": "item.reed_seed", "name": "芦苇籽", "description": "芦苇窝边落下的小种子，提醒你还有来处。", "icon_asset_id": "icon.item.reed_seed"},
        {"id": "item.bread_crumb", "name": "面包屑", "description": "农家院角落捡到的食物，可以恢复一点体力。", "icon_asset_id": "icon.item.bread_crumb"},
        {"id": "item.warm_feather", "name": "暖羽", "description": "春湖边拾到的羽毛，像一段温柔的回答。", "icon_asset_id": "icon.item.warm_feather"},
    ]})
    write_json(rpg / "equipment.json", {"equipment": [{"id": "equip.soft_down", "name": "柔软绒羽", "slot": "body", "defense": 1, "asset_id": "icon.item.warm_feather"}]})
    write_json(rpg / "skills.json", {"skills": [
        {"id": "skill.brave_peep", "name": "勇敢鸣叫", "power": 9, "focus_cost": 0, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.keep_warm", "name": "蜷身取暖", "power": 1, "focus_cost": 0, "effect": "guard_focus", "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.reflect", "name": "看清倒影", "power": 13, "focus_cost": 2, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.quick_flutter", "name": "急速振翅", "power": 11, "focus_cost": 1, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.wingbeat", "name": "湖风振翼", "power": 14, "focus_cost": 2, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.mocking_noise", "name": "嘲笑声浪", "power": 6, "focus_cost": 0, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.chase", "name": "追逐脚步", "power": 8, "focus_cost": 0, "icon_asset_id": "icon.skill.brave_peep"},
        {"id": "skill.cold_gust", "name": "寒风扑面", "power": 10, "focus_cost": 0, "icon_asset_id": "icon.skill.brave_peep"},
    ]})
    write_json(rpg / "enemies.json", {"enemies": [
        {"id": "enemy.mocking_gaggle", "name": "嘲笑的鸭群", "stats": {"hp": 24, "attack": 7, "defense": 2, "speed": 5}, "sprite_asset_id": "enemy.mocking_gaggle", "skills": ["skill.mocking_noise"], "pattern": ["attack", "guard", "skill"]},
        {"id": "enemy.farmyard_chaser", "name": "农家院追逐声", "stats": {"hp": 32, "attack": 8, "defense": 3, "speed": 6}, "sprite_asset_id": "enemy.farmyard_chaser", "skills": ["skill.chase"], "pattern": ["skill", "attack", "guard"]},
        {"id": "enemy.winter_wind", "name": "冰湖冬风", "stats": {"hp": 44, "attack": 10, "defense": 4, "speed": 5}, "sprite_asset_id": "enemy.winter_wind", "skills": ["skill.cold_gust"], "pattern": ["guard", "skill", "attack", "skill"]},
    ]})
    write_json(rpg / "encounter-tables.json", {"encounter_tables": [{"id": "encounter.lake_trials", "enemies": ["enemy.mocking_gaggle", "enemy.farmyard_chaser", "enemy.winter_wind"]}]})
    write_json(rpg / "quests.json", {"quests": [
        {"id": "quest.leave_nest", "title": "离开芦苇窝", "description": "在嘲笑声中找到离开的勇气。"},
        {"id": "quest.cross_farmyard", "title": "穿过农家院", "description": "避开追逐，抵达通往荒野的小路。"},
        {"id": "quest.find_reflection", "title": "寻找真正的倒影", "description": "撑过寒冬，在春湖边看清自己。"},
    ]})
    write_json(rpg / "npc-dialogue.json", {"npc_dialogue": [
        {"id": "dialogue.mother_duck", "lines": [{"speaker": "母鸭", "text": "你来得晚些，也长得不同些，但水会接住认真游的人。"}, {"speaker": "小灰鸟", "text": "如果大家都笑我，我还可以往前游吗？"}]},
        {"id": "dialogue.hen", "lines": [{"speaker": "花母鸡", "text": "不会下蛋，也不会咯咯叫，你到底算什么？"}, {"speaker": "小灰鸟", "text": "也许我还没有知道答案。"}]},
        {"id": "dialogue.cat", "lines": [{"speaker": "老猫", "text": "院子里只欢迎有用的本领。"}, {"speaker": "檐下麻雀", "text": "有些本领要到远处才会长出来。"}]},
        {"id": "dialogue.sparrow", "lines": [{"speaker": "檐下麻雀", "text": "沿着篱笆影子走，孩子们就追不上你。"}]},
        {"id": "dialogue.swan", "lines": [{"speaker": "白天鹅", "text": "湖水不会重复别人的话。靠近些，自己看看。"}, {"speaker": "小灰鸟", "text": "如果倒影也讨厌我呢？"}]},
        {"id": "dialogue.lake_echo", "lines": [{"speaker": "湖面回声", "text": "名字会改变，伤口会愈合，翅膀会记得天空。"}]},
    ]})
    write_json(rpg / "events.json", {"events": [{"id": "event.first_flight", "title": "第一次飞行", "quest_id": "quest.find_reflection"}]})
    write_json(rpg / "shops.json", {"shops": []})
    write_json(rpg / "rest-points.json", {"rest_points": [
        {"id": "rest.reed_bed", "name": "芦苇窝", "cost": 0},
        {"id": "rest.hay_corner", "name": "干草角落", "cost": 0},
        {"id": "rest.sunlit_shore", "name": "春湖浅滩", "cost": 0},
    ]})
    write_json(rpg / "progression-rules.json", {"progression_rules": [
        {"id": "progression.leave", "quest_id": "quest.leave_nest", "effect": "离开芦苇窝。"},
        {"id": "progression.cross", "quest_id": "quest.cross_farmyard", "effect": "穿过农家院。"},
        {"id": "progression.reflect", "quest_id": "quest.find_reflection", "effect": "接纳真正的自己。"},
    ]})


def write_maps(run_root: Path) -> None:
    maps = run_root / "workspace" / "rpg" / "maps"
    marsh_path = [(x, 5) for x in range(1, 13)] + [(5, y) for y in range(2, 8)] + [(3, 4), (8, 4), (10, 6)]
    farm_path = [(x, 5) for x in range(1, 13)] + [(4, y) for y in range(2, 8)] + [(9, y) for y in range(2, 8)] + [(6, 3)]
    lake_path = [(x, 5) for x in range(1, 13)] + [(7, y) for y in range(1, 8)] + [(4, 4), (10, 4), (11, 6)]
    write_json(maps / "reed_marsh.map.json", {
        "id": "map.reed_marsh", "title": "芦苇窝", "width": 14, "height": 9, "asset_id": "map.reed_marsh", "boundary_file": "../boundaries/reed_marsh.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, marsh_path, "grass"), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.mother_duck", "type": "npc", "x": 3, "y": 5, "name": "母鸭", "dialogue_id": "dialogue.mother_duck", "sprite_asset_id": "sprite.mother_duck", "quest_id": "quest.leave_nest"},
            {"id": "pickup.reed_seed", "type": "pickup", "x": 8, "y": 4, "item_id": "item.reed_seed", "log": "你捡起一粒芦苇籽。"},
            {"id": "battle.mocking_gaggle", "type": "battle", "x": 10, "y": 5, "enemy_id": "enemy.mocking_gaggle", "once": True, "quest_id": "quest.leave_nest", "battle_background_asset_id": "battlebg.reed_marsh", "win_outcomes": [{"id": "leave.nest", "lines": [{"speaker": "小灰鸟", "text": "我听见了嘲笑，但脚下还有水路。"}], "set_flags": {"left_nest": True}, "complete_quest_id": "quest.leave_nest"}]},
            {"id": "rest.reed_bed", "type": "rest", "x": 10, "y": 6, "rest_point_id": "rest.reed_bed"},
            {"id": "exit.to_farmyard", "type": "transfer", "x": 12, "y": 5, "target_map_id": "map.farmyard", "target_x": 1, "target_y": 5},
        ],
    })
    write_json(maps / "farmyard.map.json", {
        "id": "map.farmyard", "title": "农家院", "width": 14, "height": 9, "asset_id": "map.farmyard", "boundary_file": "../boundaries/farmyard.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, farm_path, "path"), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.hen", "type": "npc", "x": 4, "y": 3, "name": "花母鸡", "dialogue_id": "dialogue.hen", "sprite_asset_id": "sprite.hen"},
            {"id": "npc.cat", "type": "npc", "x": 7, "y": 4, "name": "老猫", "dialogue_id": "dialogue.cat", "sprite_asset_id": "sprite.cat"},
            {"id": "npc.sparrow", "type": "npc", "x": 9, "y": 3, "name": "檐下麻雀", "dialogue_id": "dialogue.sparrow", "sprite_asset_id": "sprite.farm_sparrow"},
            {"id": "pickup.bread_crumb", "type": "pickup", "x": 6, "y": 3, "item_id": "item.bread_crumb", "log": "你找到一小块面包屑。"},
            {"id": "battle.chaser", "type": "battle", "x": 9, "y": 5, "enemy_id": "enemy.farmyard_chaser", "once": True, "quest_id": "quest.cross_farmyard", "battle_background_asset_id": "battlebg.farmyard", "win_outcomes": [{"id": "cross.farmyard", "lines": [{"speaker": "檐下麻雀", "text": "就是现在，穿过篱笆影子！"}], "set_flags": {"crossed_farmyard": True}, "complete_quest_id": "quest.cross_farmyard"}]},
            {"id": "rest.hay_corner", "type": "rest", "x": 10, "y": 4, "rest_point_id": "rest.hay_corner"},
            {"id": "exit.back_marsh", "type": "transfer", "x": 1, "y": 5, "target_map_id": "map.reed_marsh", "target_x": 11, "target_y": 5},
            {"id": "exit.to_lake", "type": "transfer", "x": 12, "y": 5, "target_map_id": "map.spring_lake", "target_x": 1, "target_y": 5},
        ],
    })
    write_json(maps / "spring_lake.map.json", {
        "id": "map.spring_lake", "title": "春湖", "width": 14, "height": 9, "asset_id": "map.spring_lake", "boundary_file": "../boundaries/spring_lake.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, lake_path, "path"), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.swan", "type": "npc", "x": 7, "y": 3, "name": "白天鹅", "dialogue_id": "dialogue.swan", "sprite_asset_id": "sprite.swan", "quest_id": "quest.find_reflection"},
            {"id": "npc.lake_echo", "type": "npc", "x": 10, "y": 4, "name": "湖面回声", "dialogue_id": "dialogue.lake_echo", "sprite_asset_id": "sprite.swan"},
            {"id": "pickup.warm_feather", "type": "pickup", "x": 4, "y": 4, "item_id": "item.warm_feather", "log": "你拾起一枚暖羽。"},
            {"id": "battle.winter_wind", "type": "battle", "x": 11, "y": 5, "enemy_id": "enemy.winter_wind", "once": True, "quest_id": "quest.find_reflection", "battle_background_asset_id": "battlebg.winter_lake", "win_outcomes": [{"id": "first.flight", "lines": [{"speaker": "小灰鸟", "text": "我不是走错了生命，只是还没有长成自己。"}, {"speaker": "白天鹅", "text": "欢迎回到湖上。"}], "set_flags": {"survived_winter": True, "accepted_self": True, "ending:first_flight": True}, "complete_quest_id": "quest.find_reflection"}]},
            {"id": "rest.sunlit_shore", "type": "rest", "x": 11, "y": 6, "rest_point_id": "rest.sunlit_shore"},
            {"id": "exit.back_farmyard", "type": "transfer", "x": 1, "y": 5, "target_map_id": "map.farmyard", "target_x": 11, "target_y": 5},
        ],
    })


def write_boundaries(run_root: Path) -> None:
    root = run_root / "workspace" / "rpg" / "boundaries"
    common = [
        {"id": "north_block", "type": "polygon", "points": [[0, 0], [14, 0], [14, 1.2], [9, 1.1], [5, 1.3], [0, 1.2]]},
        {"id": "south_block", "type": "polygon", "points": [[0, 7.5], [5, 7.2], [9, 7.4], [14, 7.1], [14, 9], [0, 9]]},
        {"id": "west_block", "type": "polygon", "points": [[0, 1], [1.2, 1.2], [1.0, 7.2], [0, 7.5]]},
        {"id": "east_block", "type": "polygon", "points": [[13.15, 1.1], [14, 1], [14, 7.2], [13.1, 7.0]]},
        {"id": "center_prop", "type": "rect", "x": 6.2, "y": 2.0, "w": 1.4, "h": 1.5},
    ]
    for map_id, filename, desc in [
        ("map.reed_marsh", "reed_marsh.boundaries.json", "芦苇窝主路可走，深水、密芦苇和窝外堤岸不可走。"),
        ("map.farmyard", "farmyard.boundaries.json", "院中小路可走，鸡窝、栅栏、柴堆和屋檐不可走。"),
        ("map.spring_lake", "spring_lake.boundaries.json", "春湖浅滩可走，深水、柳树根和冰裂边缘不可走。"),
    ]:
        write_json(root / filename, {"map_id": map_id, "coordinate_system": "pixels", "description": desc, "collision_shapes": common, "walkable_hint": {"x": 7, "y": 5}})


def write_asset_direction(run_root: Path) -> None:
    directions = [
        ("map.reed_marsh", "map_asset", "芦苇窝俯视 RPG 地图，浅水、芦苇、鸭窝、蛋壳和曲折水路。"),
        ("map.farmyard", "map_asset", "农家院俯视 RPG 地图，木栅栏、鸡窝、谷粒、柴堆和通往荒野的小路。"),
        ("map.spring_lake", "map_asset", "春湖俯视 RPG 地图，浅滩、柳枝、倒影水面、残冰和白天鹅。"),
        ("tileset.lake_storybook", "tileset", "湖岸、芦苇、农家院、冰面、浅水、柳树和童话地砖。"),
        ("sprite.duckling", "sprite", "灰色小鸟，小而倔强，绘本风可爱但不滑稽。"),
        ("sprite.mother_duck", "sprite", "母鸭，温柔担心，守在芦苇窝旁。"),
        ("sprite.hen", "sprite", "花母鸡，昂头、挑剔、农家院角色。"),
        ("sprite.cat", "sprite", "老猫，冷静懒散，坐在木门边。"),
        ("sprite.swan", "sprite", "白天鹅，平和优雅，带接纳的神情。"),
        ("sprite.farm_sparrow", "sprite", "檐下麻雀，机敏小向导。"),
        ("enemy.mocking_gaggle", "enemy_sprite", "嘲笑的鸭群，夸张声浪和围成半圈的剪影。"),
        ("enemy.farmyard_chaser", "enemy_sprite", "农家院追逐声，脚步、扫帚影子和混乱尘土。"),
        ("enemy.winter_wind", "enemy_sprite", "冰湖冬风，蓝白旋风、雪粒和冷光。"),
        ("battlebg.reed_marsh", "battle_background", "芦苇窝战斗背景，浅水和围观鸭群。"),
        ("battlebg.farmyard", "battle_background", "农家院战斗背景，木栅栏、谷粒和追逐尘土。"),
        ("battlebg.winter_lake", "battle_background", "冰封湖战斗背景，裂冰、寒风和远处春光。"),
        ("icon.item.reed_seed", "item_icon", "芦苇籽图标，温柔童话质感。"),
        ("icon.item.bread_crumb", "item_icon", "面包屑图标，农家院小补给。"),
        ("icon.item.warm_feather", "item_icon", "暖羽图标，白色羽毛和春光。"),
        ("icon.skill.brave_peep", "skill_icon", "勇敢鸣叫技能图标，小小声波和羽毛。"),
        ("ui.watercolor_panel", "rpg_ui", "水彩绘本风 RPG 对话面板。"),
        ("bgm.reed_marsh", "bgm", "芦苇窝 BGM，柔和木管、水声和清晨弦乐。"),
        ("bgm.farmyard", "bgm", "农家院 BGM，轻快拨弦、木头敲击和忙碌节奏。"),
        ("bgm.spring_lake", "bgm", "春湖 BGM，温柔钢片琴、弦乐和湖面风声。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {
            "summary": "温柔北欧童话绘本风，水彩质感，情绪克制，适合短篇 RPG 探索。",
            "rendering": "soft watercolor storybook 2D RPG asset",
            "lighting": "misty morning reeds, winter blue shadows, spring lake glow",
            "palette": ["#8aa6a3", "#d8c9a7", "#52616b", "#f0efe6", "#b88f6a"],
        },
        "asset_directions": [{"asset_id": asset_id, "kind": kind, "description": desc, **({"mood": "looping gentle storybook ambience"} if kind == "bgm" else {})} for asset_id, kind, desc in directions],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "《丑小鸭》Web RPG：小灰鸟穿过芦苇窝、农家院和春湖，在误解与寒冬之后认出真正的自己。\n")
    write_design_layer(run_root)
    write_rpg_tables(run_root)
    write_maps(run_root)
    write_boundaries(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/ugly-duckling-rpg")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
