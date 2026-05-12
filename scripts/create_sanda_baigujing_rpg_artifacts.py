#!/usr/bin/env python3
"""Create a complete Web RPG run for the Journey to the West episode 三打白骨精."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


Json = dict[str, Any]


def grid(width: int, height: int, fill: str = "grass") -> list[list[str]]:
    return [[fill for _ in range(width)] for _ in range(height)]


def collision(width: int, height: int) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def make_path_layer(width: int, height: int, points: list[tuple[int, int]]) -> list[list[str]]:
    layer = grid(width, height, "grass")
    for x, y in points:
        if 0 <= x < width and 0 <= y < height:
            layer[y][x] = "path"
    return layer


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "三打白骨精改编成中文神话短篇 Web RPG。",
        "requirements": [
            {"id": "req.theme", "text": "改编《西游记》中三打白骨精，突出识破伪装、师徒信任和护送取经的主题。"},
            {"id": "req.playable", "text": "产出浏览器可运行的短篇 RPG，包含探索、对白、任务、休息点、道具和三场回合制战斗。"},
            {"id": "req.language", "text": "游戏内主要文本使用中文。"},
            {"id": "req.scope", "text": "流程控制在三个地图内，十分钟内可完成。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "三打白骨精",
        "events": [
            {"id": "event.ridge_warning", "summary": "孙悟空在白虎岭护送唐僧，发现山路妖气与饥民幻象。"},
            {"id": "event.first_form", "summary": "白骨精化作送饭少女，悟空以火眼金睛识破并第一次击退。"},
            {"id": "event.second_form", "summary": "妖怪化作老妇追问女儿下落，师徒信任受到动摇。"},
            {"id": "event.third_form", "summary": "妖怪化作老翁引唐僧责怪悟空，最终露出白骨真身。"},
            {"id": "event.cave_resolution", "summary": "悟空在白骨洞击败白骨夫人，师徒重新上路。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "三打白骨精 RPG Branch Graph",
        "start_node_id": "node.ridge_start",
        "nodes": [
            {"id": "node.ridge_start", "title": "白虎岭起行", "summary": "悟空护送唐僧进入白虎岭。"},
            {"id": "node.first_strike", "title": "少女送饭", "summary": "悟空识破白骨精第一次变化。"},
            {"id": "node.second_strike", "title": "老妇寻女", "summary": "白骨精借亲情伪装离间师徒。"},
            {"id": "node.third_strike", "title": "老翁问罪", "summary": "白骨精第三次变化逼出信任危机。"},
            {"id": "node.bone_cave", "title": "白骨洞决战", "summary": "悟空击破妖雾，击败白骨夫人。"},
            {"id": "node.road_continues", "title": "师徒再行", "summary": "师徒离开白虎岭，继续西行。", "is_terminal": True},
        ],
        "edges": [
            {"id": "edge.start.first", "from": "node.ridge_start", "to": "node.first_strike", "condition_type": "unconditional"},
            {"id": "edge.first.second", "from": "node.first_strike", "to": "node.second_strike", "condition_type": "unconditional"},
            {"id": "edge.second.third", "from": "node.second_strike", "to": "node.third_strike", "condition_type": "unconditional"},
            {"id": "edge.third.cave", "from": "node.third_strike", "to": "node.bone_cave", "condition_type": "unconditional"},
            {"id": "edge.cave.end", "from": "node.bone_cave", "to": "node.road_continues", "condition_type": "terminal_resolution"},
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "三打白骨精",
        "design_brief": {
            "logline": "孙悟空在白虎岭三次识破白骨精伪装，保护唐僧穿过妖雾。",
            "narrative_bible": {
                "themes": ["识破伪装", "师徒信任", "护送取经"],
                "cast": [
                    {"id": "char.sun_wukong", "name": "孙悟空"},
                    {"id": "char.tang_monk", "name": "唐僧"},
                    {"id": "char.zhu_bajie", "name": "猪八戒"},
                    {"id": "char.sha_seng", "name": "沙僧"},
                    {"id": "char.baigujing", "name": "白骨精"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.first_form_defeated", "type": "boolean", "initial_value": False, "description": "是否击退少女变化。"},
            {"id": "state.second_form_defeated", "type": "boolean", "initial_value": False, "description": "是否击退老妇变化。"},
            {"id": "state.third_form_defeated", "type": "boolean", "initial_value": False, "description": "是否击退老翁变化。"},
            {"id": "state.trust_restored", "type": "boolean", "initial_value": False, "description": "师徒信任是否恢复。"},
        ],
        "progression_rules": [
            {"id": "rule.start", "summary": "从白虎岭山路开始。"},
            {"id": "rule.three_strikes", "summary": "依次识破少女、老妇、老翁三重变化。"},
            {"id": "rule.finish", "summary": "击败白骨洞中的白骨夫人后完成结局。"},
        ],
    })


def write_rpg_tables(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "rpg-campaign.json", {
        "title": "三打白骨精",
        "start_map_id": "map.white_tiger_ridge",
        "start_position": {"x": 2, "y": 5},
        "party": ["actor.sun_wukong"],
        "entry_title": "进入《三打白骨精》",
        "entry_text": "以孙悟空视角护送唐僧穿过白虎岭，三次识破白骨精的变化。",
        "entry_points": [
            {
                "id": "entry.wukong",
                "title": "火眼护师",
                "description": "扮演孙悟空，从白虎岭山道开始护送唐僧。",
                "start_map_id": "map.white_tiger_ridge",
                "start_position": {"x": 2, "y": 5},
                "party": ["actor.sun_wukong"],
                "initial_quests": ["quest.protect_tang"],
                "initial_flags": {"route.wukong": True},
                "initial_inventory": {"item.peach": 2, "item.alms_bowl": 1},
            }
        ],
        "goal": "识破白骨精三次变化并保护唐僧离开白虎岭。",
        "major_quest_ids": ["quest.protect_tang", "quest.three_strikes", "quest.defeat_baigu"],
        "final_quest_id": "quest.defeat_baigu",
        "ending_title": "妖雾散尽",
        "ending_text": "白骨洞前妖雾散去，唐僧终于明白三次棒下皆非凡人。师徒重整行囊，继续西行。",
        "endings": [
            {
                "id": "trust_restored",
                "title": "结局：火眼未误",
                "text": "悟空收起金箍棒，唐僧合掌致歉。白虎岭的风吹散骨灰，只剩西行路向前延伸。",
                "conditions": {"flags": {"ending:trust_restored": True}},
            }
        ],
        "required_assets": [
            "map.white_tiger_ridge",
            "map.abandoned_hamlet",
            "map.bone_cave",
            "tileset.bone_mountain",
            "sprite.sun_wukong",
            "sprite.tang_monk",
            "sprite.zhu_bajie",
            "sprite.sha_seng",
            "sprite.baigujing_maiden",
            "sprite.baigujing_old_woman",
            "sprite.baigujing_old_man",
            "enemy.bone_maiden",
            "enemy.bone_matron",
            "enemy.white_bone_demon",
            "battlebg.ridge_mist",
            "battlebg.bone_cave",
            "icon.item.peach",
            "icon.item.alms_bowl",
            "icon.skill.golden_cudgel",
            "ui.ink_panel",
        ],
    })
    write_json(rpg / "world-map.json", {
        "title": "白虎岭",
        "start_map_id": "map.white_tiger_ridge",
        "maps": [
            {"id": "map.white_tiger_ridge", "title": "白虎岭山路", "role": "field"},
            {"id": "map.abandoned_hamlet", "title": "荒村幻舍", "role": "deception"},
            {"id": "map.bone_cave", "title": "白骨洞", "role": "finale"},
        ],
    })
    write_json(rpg / "actors.json", {
        "actors": [
            {
                "id": "actor.sun_wukong",
                "name": "孙悟空",
                "class_id": "class.great_sage",
                "stats": {"hp": 62, "attack": 16, "defense": 6, "speed": 7},
                "sprite_asset_id": "sprite.sun_wukong",
                "skills": ["skill.golden_cudgel", "skill.fiery_eyes", "skill.cloud_guard"],
            }
        ]
    })
    write_json(rpg / "classes.json", {"classes": [{"id": "class.great_sage", "name": "齐天大圣", "growth": "高速强攻"}]})
    write_json(rpg / "items.json", {
        "items": [
            {"id": "item.peach", "name": "山桃", "description": "恢复体力的山桃。", "icon_asset_id": "icon.item.peach"},
            {"id": "item.alms_bowl", "name": "紫金钵", "description": "唐僧化缘所用的钵盂。", "icon_asset_id": "icon.item.alms_bowl"},
            {"id": "item.truth_talisman", "name": "照妖符", "description": "能短暂照出妖气的符纸。", "icon_asset_id": "icon.skill.golden_cudgel"},
        ]
    })
    write_json(rpg / "equipment.json", {"equipment": [{"id": "equip.tiger_skin", "name": "虎皮裙", "slot": "body", "defense": 2, "asset_id": "icon.item.peach"}]})
    write_json(rpg / "skills.json", {
        "skills": [
            {"id": "skill.golden_cudgel", "name": "金箍棒", "power": 8, "focus_cost": 0, "icon_asset_id": "icon.skill.golden_cudgel"},
            {"id": "skill.fiery_eyes", "name": "火眼金睛", "power": 12, "focus_cost": 2, "icon_asset_id": "icon.skill.golden_cudgel"},
            {"id": "skill.cloud_guard", "name": "筋斗云护身", "power": 1, "focus_cost": 0, "effect": "guard_focus", "icon_asset_id": "icon.skill.golden_cudgel"},
            {"id": "skill.bone_claw", "name": "白骨爪", "power": 6, "focus_cost": 0, "icon_asset_id": "icon.skill.golden_cudgel"},
            {"id": "skill.demon_mist", "name": "妖雾迷心", "power": 8, "focus_cost": 0, "icon_asset_id": "icon.skill.golden_cudgel"},
        ]
    })
    write_json(rpg / "enemies.json", {
        "enemies": [
            {"id": "enemy.bone_maiden", "name": "送饭少女", "stats": {"hp": 24, "attack": 7, "defense": 2, "speed": 5}, "sprite_asset_id": "enemy.bone_maiden", "skills": ["skill.bone_claw"], "pattern": ["attack", "skill", "guard"]},
            {"id": "enemy.bone_matron", "name": "寻女老妇", "stats": {"hp": 30, "attack": 8, "defense": 3, "speed": 4}, "sprite_asset_id": "enemy.bone_matron", "skills": ["skill.demon_mist"], "pattern": ["skill", "attack", "guard", "attack"]},
            {"id": "enemy.white_bone_demon", "name": "白骨夫人", "stats": {"hp": 46, "attack": 10, "defense": 4, "speed": 5}, "sprite_asset_id": "enemy.white_bone_demon", "skills": ["skill.bone_claw", "skill.demon_mist"], "pattern": ["guard", "skill", "attack", "skill"]},
        ]
    })
    write_json(rpg / "encounter-tables.json", {"encounter_tables": [{"id": "encounter.bone_mist", "enemies": ["enemy.bone_maiden", "enemy.bone_matron"]}]})
    write_json(rpg / "quests.json", {
        "quests": [
            {"id": "quest.protect_tang", "title": "护送唐僧", "description": "保护唐僧穿过白虎岭。"},
            {"id": "quest.three_strikes", "title": "三打白骨精", "description": "识破白骨精三次变化。"},
            {"id": "quest.defeat_baigu", "title": "白骨洞决战", "description": "击败白骨夫人，驱散妖雾。"},
        ]
    })
    write_json(rpg / "npc-dialogue.json", {
        "npc_dialogue": [
            {"id": "dialogue.tang_warning", "lines": [{"speaker": "唐僧", "text": "悟空，此岭荒寒，若遇饥民，切不可轻动杀心。"}, {"speaker": "孙悟空", "text": "师父放心。俺老孙先看妖气，再论善恶。"}]},
            {"id": "dialogue.bajie_tease", "lines": [{"speaker": "猪八戒", "text": "猴哥，若真有人送饭，老猪先替师父尝一口。"}, {"speaker": "孙悟空", "text": "呆子，越是香气扑鼻，越要小心白骨冷风。"}]},
            {"id": "dialogue.sha_seng_calm", "lines": [{"speaker": "沙僧", "text": "大师兄，师父一时不明，你莫急。妖气未散，我们先守住路口。"}]},
            {"id": "dialogue.maiden", "lines": [{"speaker": "送饭少女", "text": "长老远行辛苦，小女子带了斋饭。"}, {"speaker": "孙悟空", "text": "斋饭有香，影子却无生气。妖怪，现形！"}]},
            {"id": "dialogue.old_woman", "lines": [{"speaker": "寻女老妇", "text": "谁见了我那送饭的女儿？"}, {"speaker": "孙悟空", "text": "你哭声像人，脚下骨影却骗不过俺老孙。"}]},
            {"id": "dialogue.old_man", "lines": [{"speaker": "问罪老翁", "text": "你这和尚纵徒行凶，还我妻女命来！"}, {"speaker": "孙悟空", "text": "三番变化，只为乱我师徒。白骨精，出来受棒！"}]},
            {"id": "dialogue.cave_echo", "lines": [{"speaker": "白骨洞回声", "text": "皮相可换，贪念不灭。若师徒离心，白骨便有路可走。"}]},
        ]
    })
    write_json(rpg / "events.json", {"events": [{"id": "event.baigu_defeated", "title": "白骨精伏诛", "quest_id": "quest.defeat_baigu"}]})
    write_json(rpg / "shops.json", {"shops": []})
    write_json(rpg / "rest-points.json", {
        "rest_points": [
            {"id": "rest.ridge_shrine", "name": "山路石龛", "cost": 0},
            {"id": "rest.cave_mouth", "name": "洞口清风", "cost": 0},
        ]
    })
    write_json(rpg / "progression-rules.json", {
        "progression_rules": [
            {"id": "progression.first", "quest_id": "quest.three_strikes", "effect": "第一次识破少女变化。"},
            {"id": "progression.final", "quest_id": "quest.defeat_baigu", "effect": "击败白骨夫人并触发结局。"},
        ]
    })


def write_maps(run_root: Path) -> None:
    maps_root = run_root / "workspace" / "rpg" / "maps"
    ridge_path = [(x, 5) for x in range(1, 13)] + [(6, y) for y in range(2, 8)] + [(3, 4), (9, 4), (11, 6)]
    hamlet_path = [(x, 5) for x in range(1, 13)] + [(4, y) for y in range(2, 8)] + [(8, y) for y in range(2, 8)] + [(10, 4)]
    cave_path = [(x, 5) for x in range(1, 13)] + [(7, y) for y in range(1, 8)] + [(4, 4), (10, 3), (11, 6)]
    write_json(maps_root / "white_tiger_ridge.map.json", {
        "id": "map.white_tiger_ridge",
        "title": "白虎岭山路",
        "width": 14,
        "height": 9,
        "asset_id": "map.white_tiger_ridge",
        "boundary_file": "../boundaries/white_tiger_ridge.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, ridge_path), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.tang_monk", "type": "npc", "x": 3, "y": 5, "name": "唐僧", "dialogue_id": "dialogue.tang_warning", "sprite_asset_id": "sprite.tang_monk", "quest_id": "quest.protect_tang"},
            {"id": "npc.bajie", "type": "npc", "x": 5, "y": 6, "name": "猪八戒", "dialogue_id": "dialogue.bajie_tease", "sprite_asset_id": "sprite.zhu_bajie"},
            {"id": "pickup.truth_talisman", "type": "pickup", "x": 6, "y": 3, "item_id": "item.truth_talisman", "log": "拾得一张照妖符。"},
            {"id": "battle.maiden_form", "type": "battle", "x": 9, "y": 5, "enemy_id": "enemy.bone_maiden", "once": True, "quest_id": "quest.three_strikes", "dialogue_id": "dialogue.maiden", "battle_background_asset_id": "battlebg.ridge_mist", "win_outcomes": [{"id": "first.strike", "lines": [{"speaker": "孙悟空", "text": "第一棒打散的是皮相，不是人命。"}], "set_flags": {"first_form_defeated": True}}]},
            {"id": "rest.ridge_shrine", "type": "rest", "x": 11, "y": 6, "rest_point_id": "rest.ridge_shrine"},
            {"id": "exit.to_hamlet", "type": "transfer", "x": 12, "y": 5, "target_map_id": "map.abandoned_hamlet", "target_x": 1, "target_y": 5},
        ],
    })
    write_json(maps_root / "abandoned_hamlet.map.json", {
        "id": "map.abandoned_hamlet",
        "title": "荒村幻舍",
        "width": 14,
        "height": 9,
        "asset_id": "map.abandoned_hamlet",
        "boundary_file": "../boundaries/abandoned_hamlet.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, hamlet_path), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.old_woman", "type": "npc", "x": 4, "y": 3, "name": "寻女老妇", "dialogue_id": "dialogue.old_woman", "sprite_asset_id": "sprite.baigujing_old_woman"},
            {"id": "battle.matron_form", "type": "battle", "x": 8, "y": 5, "enemy_id": "enemy.bone_matron", "once": True, "quest_id": "quest.three_strikes", "battle_background_asset_id": "battlebg.ridge_mist", "win_outcomes": [{"id": "second.strike", "lines": [{"speaker": "猪八戒", "text": "这哭声怎也化成了白烟？猴哥，莫非真有妖？"}], "set_flags": {"second_form_defeated": True}}]},
            {"id": "pickup.peach", "type": "pickup", "x": 10, "y": 4, "item_id": "item.peach", "log": "在破篮中找到一个山桃。"},
            {"id": "exit.back_ridge", "type": "transfer", "x": 1, "y": 5, "target_map_id": "map.white_tiger_ridge", "target_x": 11, "target_y": 5},
            {"id": "exit.to_cave", "type": "transfer", "x": 12, "y": 5, "target_map_id": "map.bone_cave", "target_x": 1, "target_y": 5},
        ],
    })
    write_json(maps_root / "bone_cave.map.json", {
        "id": "map.bone_cave",
        "title": "白骨洞",
        "width": 14,
        "height": 9,
        "asset_id": "map.bone_cave",
        "boundary_file": "../boundaries/bone_cave.boundaries.json",
        "layers": {"ground": make_path_layer(14, 9, cave_path), "collision": collision(14, 9)},
        "events": [
            {"id": "npc.sha_seng", "type": "npc", "x": 4, "y": 4, "name": "沙僧", "dialogue_id": "dialogue.sha_seng_calm", "sprite_asset_id": "sprite.sha_seng"},
            {"id": "npc.old_man", "type": "npc", "x": 7, "y": 3, "name": "问罪老翁", "dialogue_id": "dialogue.old_man", "sprite_asset_id": "sprite.baigujing_old_man"},
            {"id": "npc.cave_echo", "type": "npc", "x": 10, "y": 3, "name": "白骨洞回声", "dialogue_id": "dialogue.cave_echo", "sprite_asset_id": "sprite.baigujing_old_man"},
            {"id": "battle.white_bone_demon", "type": "battle", "x": 11, "y": 5, "enemy_id": "enemy.white_bone_demon", "once": True, "quest_id": "quest.defeat_baigu", "battle_background_asset_id": "battlebg.bone_cave", "win_outcomes": [{"id": "third.strike", "lines": [{"speaker": "白骨精", "text": "三副皮囊皆碎，仍拦不住你这双火眼。"}, {"speaker": "孙悟空", "text": "俺老孙打的是妖心，不是凡身。"}], "set_flags": {"third_form_defeated": True, "trust_restored": True, "ending:trust_restored": True}, "complete_quest_id": "quest.defeat_baigu"}]},
            {"id": "rest.cave_mouth", "type": "rest", "x": 7, "y": 6, "rest_point_id": "rest.cave_mouth"},
            {"id": "exit.back_hamlet", "type": "transfer", "x": 1, "y": 5, "target_map_id": "map.abandoned_hamlet", "target_x": 11, "target_y": 5},
        ],
    })


def write_boundaries(run_root: Path) -> None:
    root = run_root / "workspace" / "rpg" / "boundaries"
    write_json(root / "white_tiger_ridge.boundaries.json", {
        "map_id": "map.white_tiger_ridge",
        "coordinate_system": "pixels",
        "description": "粗粒度边界：中部山路可走，北侧密林、南侧断崖、溪沟和巨石不可走。",
        "collision_shapes": [
            {"id": "north_forest", "type": "polygon", "points": [[0, 0], [14, 0], [14, 1.3], [10, 1.1], [7, 1.4], [4, 1.1], [0, 1.5]]},
            {"id": "south_cliff", "type": "polygon", "points": [[0, 7.5], [3, 7.1], [7, 7.4], [10, 7.0], [14, 7.2], [14, 9], [0, 9]]},
            {"id": "west_rock", "type": "polygon", "points": [[0, 1.4], [1.4, 1.5], [1.2, 4.2], [0, 4.8]]},
            {"id": "east_thicket", "type": "polygon", "points": [[12.8, 1.2], [14, 1.0], [14, 7.3], [13.0, 7.0], [12.7, 4.0]]},
            {"id": "ridge_boulder", "type": "rect", "x": 7.2, "y": 2.0, "w": 1.4, "h": 1.5},
        ],
        "walkable_hint": {"x": 6, "y": 5},
    })
    write_json(root / "abandoned_hamlet.boundaries.json", {
        "map_id": "map.abandoned_hamlet",
        "coordinate_system": "pixels",
        "description": "粗粒度边界：破村主路可走，倒塌屋舍、枯井和围墙不可走。",
        "collision_shapes": [
            {"id": "north_wall", "type": "polygon", "points": [[0, 0], [14, 0], [14, 1.1], [9, 1.3], [5, 1.0], [0, 1.4]]},
            {"id": "south_ruins", "type": "polygon", "points": [[0, 7.4], [4, 7.0], [8, 7.3], [14, 7.1], [14, 9], [0, 9]]},
            {"id": "west_house", "type": "rect", "x": 1.0, "y": 2.0, "w": 2.3, "h": 2.0},
            {"id": "east_house", "type": "rect", "x": 10.8, "y": 2.0, "w": 2.0, "h": 2.3},
            {"id": "dry_well", "type": "rect", "x": 6.0, "y": 2.2, "w": 1.2, "h": 1.2},
        ],
        "walkable_hint": {"x": 6, "y": 5},
    })
    write_json(root / "bone_cave.boundaries.json", {
        "map_id": "map.bone_cave",
        "coordinate_system": "pixels",
        "description": "粗粒度边界：洞中主路可走，骨墙、深坑和石笋不可走。",
        "collision_shapes": [
            {"id": "cave_ceiling", "type": "polygon", "points": [[0, 0], [14, 0], [14, 1.0], [10, 1.4], [7, 1.0], [3, 1.3], [0, 1.0]]},
            {"id": "cave_floor_pit", "type": "polygon", "points": [[0, 7.6], [5, 7.0], [9, 7.4], [14, 7.1], [14, 9], [0, 9]]},
            {"id": "west_bone_wall", "type": "polygon", "points": [[0, 1.0], [1.2, 1.3], [1.0, 4.2], [0, 5.0]]},
            {"id": "east_bone_wall", "type": "polygon", "points": [[12.7, 1.0], [14, 1.0], [14, 7.0], [12.8, 6.7], [12.5, 3.4]]},
            {"id": "bone_pillar", "type": "rect", "x": 5.5, "y": 2.0, "w": 1.0, "h": 1.5},
        ],
        "walkable_hint": {"x": 7, "y": 5},
    })


def write_asset_direction(run_root: Path) -> None:
    directions = [
        ("map.white_tiger_ridge", "map_asset", "白虎岭山路俯视地图，山林、岩壁、曲折土路和淡淡妖雾。"),
        ("map.abandoned_hamlet", "map_asset", "荒村幻舍俯视地图，破屋、枯井、主路和不自然的冷光。"),
        ("map.bone_cave", "map_asset", "白骨洞俯视地图，洞壁、骨堆、石笋和幽蓝妖雾。"),
        ("tileset.bone_mountain", "tileset", "白虎岭山石、枯草、骨墙、破屋和洞穴地表瓦片。"),
        ("sprite.sun_wukong", "sprite", "孙悟空，金甲红披风，手持金箍棒，灵动警觉。"),
        ("sprite.tang_monk", "sprite", "唐僧，白净僧袍，神情慈悲而犹疑。"),
        ("sprite.zhu_bajie", "sprite", "猪八戒，钉耙和宽大僧衣，贪嘴但可爱。"),
        ("sprite.sha_seng", "sprite", "沙僧，深色僧衣，沉稳护队。"),
        ("sprite.baigujing_maiden", "sprite", "白骨精少女变化，篮中斋饭，笑容过于苍白。"),
        ("sprite.baigujing_old_woman", "sprite", "白骨精老妇变化，拄杖哭诉，影子泛白。"),
        ("sprite.baigujing_old_man", "sprite", "白骨精老翁变化，怒目问罪，衣摆如骨烟。"),
        ("enemy.bone_maiden", "enemy_sprite", "送饭少女妖形，半透明白骨纹与饭篮妖气。"),
        ("enemy.bone_matron", "enemy_sprite", "寻女老妇妖形，骨爪藏在袖中，灰白妖雾。"),
        ("enemy.white_bone_demon", "enemy_sprite", "白骨夫人真身，白骨王冠、妖雾披帛和冷蓝眼火。"),
        ("battlebg.ridge_mist", "battle_background", "白虎岭山路战斗背景，枯树、岩石和妖雾。"),
        ("battlebg.bone_cave", "battle_background", "白骨洞决战背景，骨墙、幽火和洞口冷光。"),
        ("icon.item.peach", "item_icon", "红润山桃图标。"),
        ("icon.item.alms_bowl", "item_icon", "紫金钵图标。"),
        ("icon.skill.golden_cudgel", "skill_icon", "金箍棒发光图标。"),
        ("ui.ink_panel", "rpg_ui", "西游水墨风对话面板和战斗 UI 装饰。"),
        ("bgm.white_tiger_ridge", "bgm", "白虎岭山路 BGM，紧张但克制的中国打击乐与笛声。"),
        ("bgm.abandoned_hamlet", "bgm", "荒村幻舍 BGM，空屋回声、低弦和冷风。"),
        ("bgm.bone_cave", "bgm", "白骨洞 BGM，幽暗鼓点和妖雾氛围。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {
            "summary": "中国古典神魔绘本风格，西游记人物、荒山妖雾、手绘 RPG 俯视地图。",
            "rendering": "hand-painted Chinese myth RPG asset",
            "lighting": "cold mountain mist with warm monk-road highlights",
            "palette": ["#25313a", "#765f44", "#c9a14a", "#e8dcc2", "#b9c7cf"],
        },
        "asset_directions": [
            {
                "asset_id": asset_id,
                "kind": kind,
                "description": description,
                **({"mood": "looping map ambience"} if kind == "bgm" else {}),
            }
            for asset_id, kind, description in directions
        ],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "三打白骨精 Web RPG：玩家扮演孙悟空，在白虎岭识破白骨精三次变化，保护唐僧并完成取经队伍的信任抉择。\n")
    write_design_layer(run_root)
    write_rpg_tables(run_root)
    write_maps(run_root)
    write_boundaries(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/sanda-baigujing-rpg")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
