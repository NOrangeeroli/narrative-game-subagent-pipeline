#!/usr/bin/env python3
"""Create a complete Web RPG run for Alice's Adventures in Wonderland."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

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
        "prompt": "《爱丽丝奇遇记》改编成短篇 Web RPG。",
        "requirements": [
            {"id": "req.public_domain", "text": "基于公版《Alice's Adventures in Wonderland》，采用维多利亚奇幻绘本风，不引用现代影视设计。"},
            {"id": "req.playable", "text": "浏览器可游玩的短篇 RPG，包含探索、对白、道具、休息点和三场轻量战斗。"},
            {"id": "req.theme", "text": "突出好奇心、逻辑错位、体型变化和法庭荒诞。"},
            {"id": "req.language", "text": "游戏文本使用中文。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "爱丽丝奇遇记",
        "events": [
            {"id": "event.rabbit", "summary": "爱丽丝追逐怀表兔子，跌入奇异花园。"},
            {"id": "event.garden", "summary": "她用蛋糕与药水改变体型，穿过会说话的花丛。"},
            {"id": "event.tea", "summary": "疯帽匠茶会打乱时间，谜语与茶壶暴走。"},
            {"id": "event.court", "summary": "红心王后的纸牌法庭审判爱丽丝。"},
            {"id": "event.wake", "summary": "爱丽丝识破荒诞规则，从梦中醒来。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "Alice Wonderland RPG Branch Graph",
        "start_node_id": "node.rabbit_hole",
        "nodes": [
            {"id": "node.rabbit_hole", "title": "兔洞坠落", "summary": "爱丽丝追随白兔来到花园入口。"},
            {"id": "node.size_puzzle", "title": "变大与变小", "summary": "药水与蛋糕改变通路。"},
            {"id": "node.tea_party", "title": "永远六点钟", "summary": "疯帽匠茶会让时间停滞。"},
            {"id": "node.queen_court", "title": "红心法庭", "summary": "纸牌士兵和王后发起荒诞审判。"},
            {"id": "node.wake_up", "title": "醒来", "summary": "爱丽丝拒绝无意义的判决。", "is_terminal": True},
        ],
        "edges": [
            {"id": "edge.rabbit.size", "from": "node.rabbit_hole", "to": "node.size_puzzle", "condition_type": "unconditional"},
            {"id": "edge.size.tea", "from": "node.size_puzzle", "to": "node.tea_party", "condition_type": "unconditional"},
            {"id": "edge.tea.court", "from": "node.tea_party", "to": "node.queen_court", "condition_type": "unconditional"},
            {"id": "edge.court.wake", "from": "node.queen_court", "to": "node.wake_up", "condition_type": "terminal_resolution"},
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "爱丽丝奇遇记",
        "design_brief": {
            "logline": "爱丽丝在梦境国度穿过花园、茶会和红心法庭，用好奇心拆解荒诞规则。",
            "narrative_bible": {
                "themes": ["好奇心", "荒诞逻辑", "梦境成长"],
                "cast": [
                    {"id": "char.alice", "name": "爱丽丝"},
                    {"id": "char.white_rabbit", "name": "白兔先生"},
                    {"id": "char.cheshire_cat", "name": "柴郡猫"},
                    {"id": "char.mad_hatter", "name": "疯帽匠"},
                    {"id": "char.queen_hearts", "name": "红心王后"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.has_tiny_key", "type": "boolean", "initial_value": False, "description": "是否取得小金钥匙。"},
            {"id": "state.time_unstuck", "type": "boolean", "initial_value": False, "description": "茶会时间是否恢复流动。"},
            {"id": "state.trial_overturned", "type": "boolean", "initial_value": False, "description": "是否推翻荒诞判决。"},
        ],
        "progression_rules": [
            {"id": "rule.start", "summary": "从兔洞花园开始。"},
            {"id": "rule.tea", "summary": "解开茶会时间悖论后进入法庭。"},
            {"id": "rule.end", "summary": "击败红心王后的纸牌审判后醒来。"},
        ],
    })


def write_rpg_tables(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "rpg-campaign.json", {
        "title": "爱丽丝奇遇记",
        "start_map_id": "map.riverbank",
        "start_position": {"x": 420, "y": 520},
        "party": ["actor.alice"],
        "entry_title": "进入梦境国度",
        "entry_text": "追随怀表兔子，穿过越来越不讲道理的梦境。",
        "entry_points": [{
            "id": "entry.alice",
            "title": "好奇的爱丽丝",
            "description": "从河岸边的闲谈开始，追随白兔进入兔洞。",
            "start_map_id": "map.riverbank",
            "start_position": {"x": 420, "y": 520},
            "party": ["actor.alice"],
            "initial_inventory": {"item.drink_me": 1, "item.eat_me": 1},
        }],
        "goal": "追上白兔并推翻红心王后的荒诞审判。",
        "major_quest_ids": ["quest.follow_rabbit", "quest.unstick_time", "quest.overturn_trial"],
        "final_quest_id": "quest.overturn_trial",
        "ending_title": "梦醒之前",
        "ending_text": "纸牌飞散成秋叶，爱丽丝在树荫下醒来，怀里似乎还留着一枚小金钥匙。",
        "endings": [{"id": "wake", "title": "结局：这不过是一副纸牌", "text": "爱丽丝大声说出真相，红心法庭随梦境坍塌。", "conditions": {"flags": {"ending:wake": True}}}],
        "required_assets": [
            "map.riverbank", "map.rabbit_hole_garden", "map.mad_tea_party", "map.queen_court",
            "tileset.wonderland", "sprite.alice", "sprite.sister", "sprite.white_rabbit", "sprite.cheshire_cat",
            "sprite.mad_hatter", "sprite.queen_hearts", "sprite.dormouse",
            "enemy.card_guard", "enemy.mad_teapot", "enemy.queen_hearts",
            "battlebg.tea_table", "battlebg.queen_court",
            "icon.item.drink_me", "icon.item.eat_me", "icon.skill.curiosity", "ui.storybook_panel",
        ],
    })
    write_json(rpg / "world-map.json", {"title": "梦境国度", "start_map_id": "map.riverbank", "maps": [
        {"id": "map.riverbank", "title": "河岸边", "role": "opening"},
        {"id": "map.rabbit_hole_garden", "title": "兔洞花园", "role": "field"},
        {"id": "map.mad_tea_party", "title": "疯帽匠茶会", "role": "puzzle"},
        {"id": "map.queen_court", "title": "红心法庭", "role": "finale"},
    ]})
    write_json(rpg / "actors.json", {"actors": [{
        "id": "actor.alice", "name": "爱丽丝", "class_id": "class.dreamer",
        "stats": {"hp": 54, "attack": 12, "defense": 5, "speed": 6},
        "sprite_asset_id": "sprite.alice",
        "skills": ["skill.curiosity", "skill.logic_twist", "skill.size_shift"],
    }]})
    write_json(rpg / "classes.json", {"classes": [{"id": "class.dreamer", "name": "梦境旅人", "growth": "灵巧均衡"}]})
    write_json(rpg / "items.json", {"items": [
        {"id": "item.drink_me", "name": "喝我药水", "description": "让爱丽丝变小的蓝色小瓶。", "icon_asset_id": "icon.item.drink_me"},
        {"id": "item.eat_me", "name": "吃我蛋糕", "description": "让爱丽丝变大的小蛋糕。", "icon_asset_id": "icon.item.eat_me"},
        {"id": "item.tiny_key", "name": "小金钥匙", "description": "开启花园小门。", "icon_asset_id": "icon.skill.curiosity"},
    ]})
    write_json(rpg / "equipment.json", {"equipment": [{"id": "equip.blue_pinafore", "name": "蓝色围裙", "slot": "body", "defense": 1, "asset_id": "icon.item.eat_me"}]})
    write_json(rpg / "skills.json", {"skills": [
        {"id": "skill.curiosity", "name": "好奇一问", "power": 8, "focus_cost": 0, "icon_asset_id": "icon.skill.curiosity"},
        {"id": "skill.logic_twist", "name": "反问逻辑", "power": 12, "focus_cost": 2, "icon_asset_id": "icon.skill.curiosity"},
        {"id": "skill.size_shift", "name": "体型变换", "power": 1, "focus_cost": 0, "effect": "guard_focus", "icon_asset_id": "icon.skill.curiosity"},
        {"id": "skill.card_slash", "name": "纸牌切击", "power": 6, "focus_cost": 0, "icon_asset_id": "icon.skill.curiosity"},
        {"id": "skill.tea_splash", "name": "热茶泼洒", "power": 7, "focus_cost": 0, "icon_asset_id": "icon.skill.curiosity"},
        {"id": "skill.off_with_head", "name": "砍掉脑袋", "power": 10, "focus_cost": 0, "icon_asset_id": "icon.skill.curiosity"},
    ]})
    write_json(rpg / "enemies.json", {"enemies": [
        {"id": "enemy.card_guard", "name": "纸牌卫兵", "stats": {"hp": 24, "attack": 7, "defense": 2, "speed": 5}, "sprite_asset_id": "enemy.card_guard", "skills": ["skill.card_slash"], "pattern": ["attack", "guard", "skill"]},
        {"id": "enemy.mad_teapot", "name": "暴走茶壶", "stats": {"hp": 30, "attack": 8, "defense": 3, "speed": 4}, "sprite_asset_id": "enemy.mad_teapot", "skills": ["skill.tea_splash"], "pattern": ["skill", "attack", "guard"]},
        {"id": "enemy.queen_hearts", "name": "红心王后", "stats": {"hp": 46, "attack": 10, "defense": 4, "speed": 5}, "sprite_asset_id": "enemy.queen_hearts", "skills": ["skill.off_with_head", "skill.card_slash"], "pattern": ["guard", "skill", "attack", "skill"]},
    ]})
    write_json(rpg / "encounter-tables.json", {"encounter_tables": [{"id": "encounter.wonderland", "enemies": ["enemy.card_guard", "enemy.mad_teapot"]}]})
    write_json(rpg / "quests.json", {"quests": [
        {"id": "quest.follow_rabbit", "title": "追随白兔", "description": "找到通往花园深处的小门。"},
        {"id": "quest.unstick_time", "title": "让时间重新走动", "description": "解决疯帽匠茶会的时间悖论。"},
        {"id": "quest.overturn_trial", "title": "推翻审判", "description": "在红心法庭证明审判荒诞。"},
    ]})
    write_json(rpg / "npc-dialogue.json", {"npc_dialogue": [
        {"id": "dialogue.sister", "lines": [{"speaker": "姐姐", "text": "你若觉得闷，就自己编一个带图画和对话的故事吧。"}, {"speaker": "爱丽丝", "text": "也许故事会自己跑到我面前来。"}]},
        {"id": "dialogue.rabbit", "lines": [{"speaker": "白兔先生", "text": "迟到了，迟到了！公爵夫人会大发雷霆！"}, {"speaker": "爱丽丝", "text": "请等等，你的怀表为什么会在兔子口袋里？"}]},
        {"id": "dialogue.cat", "lines": [{"speaker": "柴郡猫", "text": "如果你不知道要去哪儿，哪条路都能到。"}, {"speaker": "爱丽丝", "text": "那我至少要去一个能讲清楚话的地方。"}]},
        {"id": "dialogue.hatter", "lines": [{"speaker": "疯帽匠", "text": "茶永远刚倒好，时间永远不肯走。"}, {"speaker": "爱丽丝", "text": "如果时间停了，杯子为什么还是空的？"}]},
        {"id": "dialogue.dormouse", "lines": [{"speaker": "睡鼠", "text": "井底有糖浆，糖浆里有故事，故事里还有井。"}]},
        {"id": "dialogue.queen", "lines": [{"speaker": "红心王后", "text": "先判刑，再审问！这是最快的法庭。"}, {"speaker": "爱丽丝", "text": "如果还没审问，判决就只是纸牌搭出来的塔。"}]},
        {"id": "dialogue.court_echo", "lines": [{"speaker": "法庭书记", "text": "证据是一首诗，诗意是有罪，押韵也是有罪。"}]},
    ]})
    write_json(rpg / "events.json", {"events": [{"id": "event.trial_overturned", "title": "纸牌飞散", "quest_id": "quest.overturn_trial"}]})
    write_json(rpg / "shops.json", {"shops": []})
    write_json(rpg / "rest-points.json", {"rest_points": [{"id": "rest.mushroom", "name": "蘑菇环", "cost": 0}, {"id": "rest.tea_chair", "name": "空茶椅", "cost": 0}]})
    write_json(rpg / "progression-rules.json", {"progression_rules": [
        {"id": "progression.key", "quest_id": "quest.follow_rabbit", "effect": "取得小金钥匙。"},
        {"id": "progression.time", "quest_id": "quest.unstick_time", "effect": "茶会时间恢复流动。"},
        {"id": "progression.trial", "quest_id": "quest.overturn_trial", "effect": "推翻红心法庭判决。"},
    ]})


def write_scene_scripts(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "scene-scripts.json", {"scene_scripts": [
        {
            "id": "scene.alice.riverbank_opening",
            "title": "河岸边的白兔",
            "map_id": "map.riverbank",
            "trigger": {"kind": "on_entry", "map_id": "map.riverbank", "once": True},
            "blocking": True,
            "actors": [
                {"actor_id": "player", "x": 420, "y": 520},
                {"actor_id": "actor.sister", "event_id": "npc.sister", "x": 560, "y": 500},
                {"actor_id": "actor.white_rabbit", "event_id": "npc.white_rabbit", "x": 1180, "y": 520},
            ],
            "beats": [
                {"kind": "dialogue", "speaker_actor_id": "actor.sister", "text": "这本书没有图画，也没有对话。你真的还想听吗？"},
                {"kind": "dialogue", "speaker_actor_id": "player", "text": "没有图画也没有对话，书还有什么用呢？"},
                {"kind": "wait", "seconds": 0.25},
                {"kind": "move_actor", "actor_id": "actor.white_rabbit", "to": {"x": 760, "y": 520}, "speed": 360},
                {"kind": "dialogue", "speaker_actor_id": "actor.white_rabbit", "text": "迟到了，迟到了！公爵夫人会要我的脑袋！"},
                {"kind": "face_actor", "actor_id": "player", "target_actor_id": "actor.white_rabbit"},
                {"kind": "dialogue", "speaker_actor_id": "player", "text": "一只会说话、还带怀表的兔子？我得弄明白。"},
                {"kind": "move_actor", "actor_id": "actor.white_rabbit", "to": {"x": 1185, "y": 420}, "speed": 420},
                {"kind": "hide_actor", "actor_id": "actor.white_rabbit"},
                {"kind": "move_actor", "actor_id": "player", "to": {"x": 875, "y": 500}, "speed": 240},
                {"kind": "activate_quest", "quest_id": "quest.follow_rabbit"},
                {"kind": "set_flag", "flag": "scene.riverbank_opening.done", "value": True},
                {"kind": "log", "text": "白兔钻进河岸尽头的洞口。"},
            ],
            "source_story_unit_ids": ["event.rabbit"],
            "public_node_ids": ["node.rabbit_hole"],
        }
    ]})


def write_maps(run_root: Path) -> None:
    maps = run_root / "workspace" / "rpg" / "maps"
    empty_layers = {"ground": [], "collision": []}
    write_json(maps / "riverbank.map.json", {
        "id": "map.riverbank", "title": "河岸边", "width": 1280, "height": 720,
        "asset_id": "map.riverbank", "boundary_file": "../boundaries/riverbank.boundaries.json",
        "layers": empty_layers,
        "events": [
            {"id": "npc.sister", "type": "npc", "x": 560, "y": 500, "name": "姐姐", "dialogue_id": "dialogue.sister", "sprite_asset_id": "sprite.sister"},
            {"id": "npc.white_rabbit", "type": "npc", "x": 1180, "y": 520, "name": "白兔先生", "dialogue_id": "dialogue.rabbit", "sprite_asset_id": "sprite.white_rabbit"},
            {"id": "exit.rabbit_hole", "type": "transfer", "x": 1170, "y": 420, "target_map_id": "map.rabbit_hole_garden", "target_x": 180, "target_y": 520, "conditions": {"flags": {"scene.riverbank_opening.done": True}}},
        ],
    })
    write_json(maps / "rabbit_hole_garden.map.json", {
        "id": "map.rabbit_hole_garden", "title": "兔洞花园", "width": 1280, "height": 720, "asset_id": "map.rabbit_hole_garden", "boundary_file": "../boundaries/rabbit_hole_garden.boundaries.json",
        "layers": empty_layers,
        "events": [
            {"id": "npc.white_rabbit.garden", "type": "npc", "x": 300, "y": 510, "name": "白兔先生", "dialogue_id": "dialogue.rabbit", "sprite_asset_id": "sprite.white_rabbit", "quest_id": "quest.follow_rabbit"},
            {"id": "npc.cheshire_cat", "type": "npc", "x": 610, "y": 300, "name": "柴郡猫", "dialogue_id": "dialogue.cat", "sprite_asset_id": "sprite.cheshire_cat"},
            {"id": "pickup.tiny_key", "type": "pickup", "x": 820, "y": 370, "item_id": "item.tiny_key", "log": "你找到了一枚小金钥匙。"},
            {"id": "battle.card_guard", "type": "battle", "x": 920, "y": 510, "enemy_id": "enemy.card_guard", "once": True, "quest_id": "quest.follow_rabbit", "battle_background_asset_id": "battlebg.queen_court", "win_outcomes": [{"id": "key.path", "lines": [{"speaker": "爱丽丝", "text": "你们只是一副会排队的纸牌。"}], "set_flags": {"has_tiny_key": True}}]},
            {"id": "rest.mushroom", "type": "rest", "x": 1040, "y": 590, "rest_point_id": "rest.mushroom"},
            {"id": "exit.to_tea", "type": "transfer", "x": 1130, "y": 510, "target_map_id": "map.mad_tea_party", "target_x": 170, "target_y": 510},
            {"id": "exit.back_riverbank", "type": "transfer", "x": 150, "y": 520, "target_map_id": "map.riverbank", "target_x": 1120, "target_y": 420},
        ],
    })
    write_json(maps / "mad_tea_party.map.json", {
        "id": "map.mad_tea_party", "title": "疯帽匠茶会", "width": 1280, "height": 720, "asset_id": "map.mad_tea_party", "boundary_file": "../boundaries/mad_tea_party.boundaries.json",
        "layers": empty_layers,
        "events": [
            {"id": "npc.hatter", "type": "npc", "x": 430, "y": 300, "name": "疯帽匠", "dialogue_id": "dialogue.hatter", "sprite_asset_id": "sprite.mad_hatter"},
            {"id": "npc.dormouse", "type": "npc", "x": 760, "y": 300, "name": "睡鼠", "dialogue_id": "dialogue.dormouse", "sprite_asset_id": "sprite.dormouse"},
            {"id": "battle.teapot", "type": "battle", "x": 760, "y": 510, "enemy_id": "enemy.mad_teapot", "once": True, "quest_id": "quest.unstick_time", "battle_background_asset_id": "battlebg.tea_table", "win_outcomes": [{"id": "time.unstuck", "lines": [{"speaker": "疯帽匠", "text": "杯子动了！时间终于肯换座位了。"}], "set_flags": {"time_unstuck": True}, "complete_quest_id": "quest.unstick_time"}]},
            {"id": "rest.tea_chair", "type": "rest", "x": 930, "y": 390, "rest_point_id": "rest.tea_chair"},
            {"id": "exit.back_garden", "type": "transfer", "x": 150, "y": 510, "target_map_id": "map.rabbit_hole_garden", "target_x": 1040, "target_y": 510},
            {"id": "exit.to_court", "type": "transfer", "x": 1130, "y": 510, "target_map_id": "map.queen_court", "target_x": 160, "target_y": 510},
        ],
    })
    write_json(maps / "queen_court.map.json", {
        "id": "map.queen_court", "title": "红心法庭", "width": 1280, "height": 720, "asset_id": "map.queen_court", "boundary_file": "../boundaries/queen_court.boundaries.json",
        "layers": empty_layers,
        "events": [
            {"id": "npc.queen", "type": "npc", "x": 640, "y": 290, "name": "红心王后", "dialogue_id": "dialogue.queen", "sprite_asset_id": "sprite.queen_hearts"},
            {"id": "npc.court_echo", "type": "npc", "x": 930, "y": 370, "name": "法庭书记", "dialogue_id": "dialogue.court_echo", "sprite_asset_id": "sprite.white_rabbit"},
            {"id": "battle.queen", "type": "battle", "x": 1040, "y": 510, "enemy_id": "enemy.queen_hearts", "once": True, "quest_id": "quest.overturn_trial", "battle_background_asset_id": "battlebg.queen_court", "win_outcomes": [{"id": "trial.overturned", "lines": [{"speaker": "红心王后", "text": "砍掉她的脑袋！"}, {"speaker": "爱丽丝", "text": "你们不过是一副纸牌。"}], "set_flags": {"trial_overturned": True, "ending:wake": True}, "complete_quest_id": "quest.overturn_trial"}]},
            {"id": "exit.back_tea", "type": "transfer", "x": 150, "y": 510, "target_map_id": "map.mad_tea_party", "target_x": 1040, "target_y": 510},
        ],
    })


def write_boundaries(run_root: Path) -> None:
    root = run_root / "workspace" / "rpg" / "boundaries"
    common = [
        {"id": "north_block", "type": "polygon", "points": [[0, 0], [1280, 0], [1280, 120], [820, 105], [460, 120], [0, 115]]},
        {"id": "south_block", "type": "polygon", "points": [[0, 640], [420, 620], [860, 635], [1280, 610], [1280, 720], [0, 720]]},
        {"id": "west_block", "type": "polygon", "points": [[0, 100], [105, 115], [95, 620], [0, 640]]},
        {"id": "east_block", "type": "polygon", "points": [[1190, 110], [1280, 95], [1280, 620], [1185, 605]]},
        {"id": "center_prop", "type": "rect", "x": 580, "y": 170, "w": 130, "h": 110},
    ]
    for map_id, filename, desc in [
        ("map.riverbank", "riverbank.boundaries.json", "河岸草地中央可走，河水、树根和远处灌木不可走。"),
        ("map.rabbit_hole_garden", "rabbit_hole_garden.boundaries.json", "花园主路可走，巨大蘑菇、篱笆、兔洞边缘不可走。"),
        ("map.mad_tea_party", "mad_tea_party.boundaries.json", "茶桌周围可走，长桌、树篱和堆叠茶具不可走。"),
        ("map.queen_court", "queen_court.boundaries.json", "法庭地毯可走，陪审席、王座、纸牌墙不可走。"),
    ]:
        write_json(root / filename, {"map_id": map_id, "coordinate_system": "pixels", "description": desc, "collision_shapes": common, "walkable_hint": {"x": 640, "y": 520}})


def write_asset_direction(run_root: Path) -> None:
    directions = [
        ("map.riverbank", "map_asset", "河岸边俯视地图，树荫、草地、书本、兔洞入口和远处河水。"),
        ("map.rabbit_hole_garden", "map_asset", "兔洞花园俯视地图，蘑菇环、小门、曲折小径和梦境植物。"),
        ("map.mad_tea_party", "map_asset", "疯帽匠茶会俯视地图，长茶桌、树下空椅、茶杯路径和停滞钟表。"),
        ("map.queen_court", "map_asset", "红心法庭俯视地图，棋盘地面、纸牌墙、王座和审判席。"),
        ("tileset.wonderland", "tileset", "梦境国度地表、蘑菇、茶具、纸牌和棋盘地砖。"),
        ("sprite.alice", "sprite", "公版维多利亚绘本风爱丽丝，蓝色裙装和白围裙。"),
        ("sprite.sister", "sprite", "爱丽丝的姐姐，维多利亚河岸读书装束，温和沉静。"),
        ("sprite.white_rabbit", "sprite", "白兔先生，怀表、马甲、焦急神情。"),
        ("sprite.cheshire_cat", "sprite", "柴郡猫，条纹猫身、神秘笑容、半透明边缘。"),
        ("sprite.mad_hatter", "sprite", "疯帽匠，高帽、茶杯、夸张礼服。"),
        ("sprite.queen_hearts", "sprite", "红心王后，纸牌王冠、红黑礼服。"),
        ("sprite.dormouse", "sprite", "睡鼠，小茶杯旁昏昏欲睡。"),
        ("enemy.card_guard", "enemy_sprite", "红心纸牌卫兵，长矛和扑克牌身体。"),
        ("enemy.mad_teapot", "enemy_sprite", "暴走茶壶，蒸汽、裂纹和茶水飞溅。"),
        ("enemy.queen_hearts", "enemy_sprite", "战斗版红心王后，怒气、扑克牌旋风。"),
        ("battlebg.tea_table", "battle_background", "疯帽匠茶桌战斗背景，茶杯、树影和停滞时钟。"),
        ("battlebg.queen_court", "battle_background", "红心法庭战斗背景，王座、纸牌士兵和棋盘地面。"),
        ("icon.item.drink_me", "item_icon", "写着 Drink Me 感觉但无可读文字的蓝色小瓶图标。"),
        ("icon.item.eat_me", "item_icon", "写着 Eat Me 感觉但无可读文字的小蛋糕图标。"),
        ("icon.skill.curiosity", "skill_icon", "好奇心技能图标，小钥匙、问号形光芒但无文字。"),
        ("ui.storybook_panel", "rpg_ui", "维多利亚故事书边框对话面板。"),
        ("bgm.riverbank", "bgm", "河岸开场 BGM，安静树影、轻柔弦乐和夏日空气感。"),
        ("bgm.rabbit_hole_garden", "bgm", "兔洞花园 BGM，轻快弦乐、木管和梦境钟声。"),
        ("bgm.mad_tea_party", "bgm", "疯帽匠茶会 BGM，错拍华尔兹、茶杯敲击和滑稽木管。"),
        ("bgm.queen_court", "bgm", "红心法庭 BGM，紧张进行曲、鼓点和荒诞铜管。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {"summary": "公版维多利亚奇幻绘本风，手绘 RPG，梦境色彩但保持可读性。", "rendering": "hand-painted Victorian storybook RPG asset", "lighting": "soft dreamlike garden light and theatrical court shadows", "palette": ["#28425a", "#e8d7aa", "#b7323a", "#f3f0d8", "#6d8b57"]},
        "asset_directions": [{"asset_id": a, "kind": k, "description": d, **({"mood": "looping dream ambience"} if k == "bgm" else {})} for a, k, d in directions],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "《爱丽丝奇遇记》Web RPG：爱丽丝追随白兔，穿过兔洞花园、疯帽匠茶会和红心法庭，在梦醒前推翻荒诞审判。\n")
    write_design_layer(run_root)
    write_rpg_tables(run_root)
    write_scene_scripts(run_root)
    write_maps(run_root)
    write_boundaries(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/alice-wonderland-rpg")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
