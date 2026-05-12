#!/usr/bin/env python3
"""Create a complete Web RPG run for the Meng Mu San Qian story."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


MAP_W = 1280
MAP_H = 720


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "《孟母三迁》改编成中文短篇 Web RPG。",
        "requirements": [
            {"id": "req.classic", "text": "基于中国传统典故《孟母三迁》，突出择邻而居、环境塑造和劝学主题。"},
            {"id": "req.playable", "text": "浏览器可游玩的短篇 RPG，包含探索、NPC 对话、道具、休息点、三场轻量战斗和结局。"},
            {"id": "req.maps", "text": "三次迁居对应墓园旁、市集旁、学宫旁三张主地图，并以家宅书房作为结局空间。"},
            {"id": "req.language", "text": "游戏文本使用中文。"},
            {"id": "req.skill_plan", "text": "地图按项目 Sprite Forge/generate2dmap 的 top-down Web RPG 合同规划；角色、敌人、图标按 clean HD RPG 资产束规划。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "孟母三迁：择邻成志",
        "events": [
            {"id": "event.graveyard", "summary": "孟母发现孟轲在墓园旁模仿丧葬，决定寻找更合适的居处。"},
            {"id": "event.market", "summary": "市集繁华却浮躁，孟轲被叫卖与讨价还价吸引。"},
            {"id": "event.school", "summary": "学宫旁书声琅琅，孟轲开始跟随礼乐与读书节奏。"},
            {"id": "event.loom", "summary": "孟轲一度懈怠，孟母以断机之喻劝其不可半途而废。"},
            {"id": "event.resolve", "summary": "孟轲立下求学志，邻里环境与母亲教诲共同成就新的起点。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "Meng Mu San Qian RPG Branch Graph",
        "start_node_id": "node.graveyard_home",
        "nodes": [
            {"id": "node.graveyard_home", "title": "墓园旁旧居", "summary": "孟母观察孩子模仿丧仪，收拾行囊。"},
            {"id": "node.market_home", "title": "市集旁新居", "summary": "市声热闹却扰乱心性，孟母再次迁居。"},
            {"id": "node.school_home", "title": "学宫旁安居", "summary": "礼乐书声引导孟轲向学。"},
            {"id": "node.loom_lesson", "title": "断机劝学", "summary": "孟母用织布机上的断线说明学习不可中断。"},
            {"id": "node.scholar_path", "title": "立志成学", "summary": "孟轲立下志向，故事抵达温和结局。", "is_terminal": True},
        ],
        "edges": [
            {"id": "edge.graveyard.market", "from": "node.graveyard_home", "to": "node.market_home", "condition_type": "quest_complete"},
            {"id": "edge.market.school", "from": "node.market_home", "to": "node.school_home", "condition_type": "quest_complete"},
            {"id": "edge.school.loom", "from": "node.school_home", "to": "node.loom_lesson", "condition_type": "quest_complete"},
            {"id": "edge.loom.resolve", "from": "node.loom_lesson", "to": "node.scholar_path", "condition_type": "terminal_resolution"},
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "孟母三迁：择邻成志",
        "design_brief": {
            "logline": "孟母带着年幼孟轲在墓园、市集与学宫之间迁居，辨明环境对心性的影响，并以断机之喻坚定求学之志。",
            "narrative_bible": {
                "themes": ["择邻而居", "母教", "勤学不辍", "环境与自我修养"],
                "cast": [
                    {"id": "char.meng_mu", "name": "孟母"},
                    {"id": "char.meng_ke", "name": "孟轲"},
                    {"id": "char.old_neighbor", "name": "旧邻老者"},
                    {"id": "char.vendor", "name": "市集商贩"},
                    {"id": "char.teacher", "name": "学宫先生"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.has_bamboo_slips", "type": "boolean", "initial_value": False, "description": "是否取得竹简。"},
            {"id": "state.moved_from_graveyard", "type": "boolean", "initial_value": False, "description": "是否离开墓园旁旧居。"},
            {"id": "state.market_lesson", "type": "boolean", "initial_value": False, "description": "是否理解市集浮躁之扰。"},
            {"id": "state.school_settled", "type": "boolean", "initial_value": False, "description": "是否在学宫旁安居。"},
            {"id": "state.resolve_made", "type": "boolean", "initial_value": False, "description": "是否立下求学志。"},
        ],
        "progression_rules": [
            {"id": "rule.graveyard", "source_edge_id": "edge.graveyard.market", "summary": "在墓园旁理解环境影响后迁往市集。"},
            {"id": "rule.market", "source_edge_id": "edge.market.school", "summary": "在市集中辨明喧嚣诱惑后迁往学宫。"},
            {"id": "rule.school", "source_edge_id": "edge.school.loom", "summary": "在学宫旁完成入学礼，取得竹简。"},
            {"id": "rule.loom", "summary": "完成断机劝学事件后触发结局。"},
        ],
    })


def write_rpg_tables(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "rpg-campaign.json", {
        "title": "孟母三迁：择邻成志",
        "start_map_id": "map.graveyard_lane",
        "start_position": {"x": 160, "y": 530},
        "party": ["actor.meng_mu"],
        "entry_title": "启程择邻",
        "entry_text": "墓园旁的风吹过旧屋。孟母牵起孟轲的手，决定为孩子寻找能安放心志的邻里。",
        "entry_points": [{
            "id": "entry.meng_mu",
            "title": "孟母",
            "description": "探索墓园、市集、学宫与书房，完成三迁与断机劝学。",
            "start_map_id": "map.graveyard_lane",
            "start_position": {"x": 160, "y": 530},
            "party": ["actor.meng_mu"],
            "initial_quests": ["quest.leave_graveyard"],
            "initial_inventory": {"item.steam_bun": 2},
        }],
        "goal": "为孟轲寻找合宜的成长环境，并让他明白学习不可半途而废。",
        "major_quest_ids": ["quest.leave_graveyard", "quest.leave_market", "quest.enter_school", "quest.loom_lesson"],
        "final_quest_id": "quest.loom_lesson",
        "ending_title": "书声入户",
        "ending_text": "窗外传来学宫晨读声，孟轲收好竹简，向母亲郑重行礼。迁居的路停下了，求学的路才刚开始。",
        "endings": [{"id": "scholar_path", "title": "结局：择邻成志", "text": "孟母择邻而居，孟轲在书声与母教中立下求学志。", "conditions": {"flags": {"ending:scholar_path": True}}}],
        "required_assets": [
            "map.graveyard_lane", "map.market_lane", "map.school_courtyard", "map.loom_room",
            "tileset.warring_states_town",
            "sprite.meng_mu", "sprite.meng_ke", "sprite.old_neighbor", "sprite.vendor", "sprite.teacher",
            "enemy.mournful_habit", "enemy.market_noise", "enemy.laziness_shadow",
            "battlebg.graveyard_lane", "battlebg.market_lane", "battlebg.school_courtyard", "battlebg.loom_room",
            "icon.item.steam_bun", "icon.item.calm_tea", "icon.item.bamboo_slips", "icon.item.loom_shuttle",
            "icon.skill.mother_teaching", "icon.skill.calm_words", "icon.skill.cut_thread",
            "ui.bamboo_scroll_panel",
        ],
        "battle_ui_showcase": {
            "title": "劝学回合",
            "text": "战斗不是伤害他人，而是用决心、礼仪和母亲教诲化解坏习气、喧嚣诱惑与懈怠影子。",
            "flow": ["探索邻里", "对话判断", "劝导战斗", "完成迁居", "触发断机劝学"],
            "features": ["中文典故剧情", "四张地图", "三场象征性战斗", "道具恢复与地图传送"],
        },
    })
    write_json(rpg / "world-map.json", {"title": "鲁地三迁小镇", "start_map_id": "map.graveyard_lane", "maps": [
        {"id": "map.graveyard_lane", "title": "墓园旁旧巷", "role": "field"},
        {"id": "map.market_lane", "title": "市集旁新居", "role": "town"},
        {"id": "map.school_courtyard", "title": "学宫旁庭院", "role": "hub"},
        {"id": "map.loom_room", "title": "孟家织室", "role": "finale"},
    ]})
    write_json(rpg / "actors.json", {"actors": [{
        "id": "actor.meng_mu", "name": "孟母", "class_id": "class.wise_mother",
        "stats": {"hp": 72, "attack": 11, "defense": 8, "speed": 6},
        "sprite_asset_id": "sprite.meng_mu",
        "walk_sheet_asset_id": "sprite.meng_mu.walksheet",
        "skills": ["skill.mother_teaching", "skill.calm_words", "skill.cut_thread"],
    }]})
    write_json(rpg / "classes.json", {"classes": [{"id": "class.wise_mother", "name": "贤母", "growth": "防御与专注均衡，擅长化解负面习气。"}]})
    write_json(rpg / "items.json", {"items": [
        {"id": "item.steam_bun", "name": "热馍", "description": "市集中买来的热馍，战斗中恢复生命。", "icon_asset_id": "icon.item.steam_bun", "heal": 18},
        {"id": "item.calm_tea", "name": "清心茶", "description": "茶棚的淡茶，提醒人从喧嚣里收心。", "icon_asset_id": "icon.item.calm_tea", "heal": 12},
        {"id": "item.bamboo_slips", "name": "启蒙竹简", "description": "学宫先生赠予孟轲的启蒙竹简。", "icon_asset_id": "icon.item.bamboo_slips"},
        {"id": "item.loom_shuttle", "name": "织机梭", "description": "孟母织布所用的木梭，象征持之以恒。", "icon_asset_id": "icon.item.loom_shuttle"},
    ]})
    write_json(rpg / "equipment.json", {"equipment": [{"id": "equip.cloth_satchel", "name": "布书袋", "slot": "body", "defense": 2, "asset_id": "icon.item.bamboo_slips"}]})
    write_json(rpg / "skills.json", {"skills": [
        {"id": "skill.mother_teaching", "name": "慈训", "power": 10, "focus_cost": 0, "icon_asset_id": "icon.skill.mother_teaching"},
        {"id": "skill.calm_words", "name": "定心言", "power": 14, "focus_cost": 2, "icon_asset_id": "icon.skill.calm_words"},
        {"id": "skill.cut_thread", "name": "断机喻", "power": 18, "focus_cost": 3, "icon_asset_id": "icon.skill.cut_thread"},
        {"id": "skill.bad_habit", "name": "旧习牵引", "power": 7, "focus_cost": 0, "icon_asset_id": "icon.skill.mother_teaching"},
        {"id": "skill.noisy_bargain", "name": "喧哗讨价", "power": 9, "focus_cost": 0, "icon_asset_id": "icon.skill.mother_teaching"},
        {"id": "skill.drowsy_pull", "name": "懈怠拖拽", "power": 12, "focus_cost": 0, "icon_asset_id": "icon.skill.mother_teaching"},
    ]})
    write_json(rpg / "enemies.json", {"enemies": [
        {"id": "enemy.mournful_habit", "name": "旧习影", "stats": {"hp": 28, "attack": 7, "defense": 2, "speed": 5}, "sprite_asset_id": "enemy.mournful_habit", "skills": ["skill.bad_habit"], "pattern": ["attack", "skill", "guard"]},
        {"id": "enemy.market_noise", "name": "市声乱流", "stats": {"hp": 38, "attack": 9, "defense": 3, "speed": 7}, "sprite_asset_id": "enemy.market_noise", "skills": ["skill.noisy_bargain"], "pattern": ["skill", "attack", "skill"]},
        {"id": "enemy.laziness_shadow", "name": "懈怠影", "stats": {"hp": 62, "attack": 12, "defense": 5, "speed": 4}, "sprite_asset_id": "enemy.laziness_shadow", "skills": ["skill.drowsy_pull", "skill.bad_habit"], "pattern": ["guard", "skill", "attack", "skill"]},
    ]})
    write_json(rpg / "encounter-tables.json", {"encounter_tables": [{"id": "encounter.habits", "enemies": ["enemy.mournful_habit", "enemy.market_noise"]}]})
    write_json(rpg / "quests.json", {"quests": [
        {"id": "quest.leave_graveyard", "title": "离开墓园旁", "description": "确认这里不适合孩子久居，收拾行囊。"},
        {"id": "quest.leave_market", "title": "离开市集旁", "description": "辨明喧嚣与逐利会扰乱心性。"},
        {"id": "quest.enter_school", "title": "学宫入礼", "description": "在学宫旁安居，取得启蒙竹简。"},
        {"id": "quest.loom_lesson", "title": "断机劝学", "description": "用织布不可断线的道理劝孟轲坚持读书。"},
    ]})
    write_json(rpg / "npc-dialogue.json", {"npc_dialogue": [
        {"id": "dialogue.old_neighbor", "lines": [
            {"speaker": "孟母", "text": "老丈，轲儿日日在巷口学哭拜，我心里不安。"},
            {"speaker": "旧邻老者", "text": "这里靠近墓地，出入所见就是这些。孩子眼快，学得也快。"},
            {"speaker": "孟轲", "text": "母亲，他们伏地叩首，我学得像不像？"},
            {"speaker": "孟母", "text": "礼有敬意，不能只学哀声。若日日只见送别，心也会被送别牵住。"},
            {"speaker": "旧邻老者", "text": "你若要他学活人的志气，确该换一处能见生计与读书的地方。"},
        ]},
        {"id": "dialogue.meng_ke_graveyard", "lines": [
            {"speaker": "孟轲", "text": "母亲，我这样哭拜，邻人会不会夸我有礼？"},
            {"speaker": "孟母", "text": "他们夸的是你懂事，我担心的是你只记住了哭声。"},
            {"speaker": "孟轲", "text": "礼不就是照着大人的样子做吗？"},
            {"speaker": "孟母", "text": "先有敬心，后有仪容。只学形貌，便像影子跟着风走。"},
            {"speaker": "孟轲", "text": "那我们离开这里，是为了让我学真的礼吗？"},
            {"speaker": "孟母", "text": "是。我们去找一个能让你心里长出志向的邻里。"},
        ]},
        {"id": "dialogue.vendor", "lines": [
            {"speaker": "孟母", "text": "掌柜，市声如此喧闹，孩子在这里日日听见的都是价钱。"},
            {"speaker": "市集商贩", "text": "夫人，讨价还价也是本事。小郎君学会吆喝，将来也不愁饭吃。"},
            {"speaker": "孟轲", "text": "母亲，我能不能也学他喊？一喊，大家都看过来。"},
            {"speaker": "孟母", "text": "会谋生是好事，可若心只追着热闹跑，书卷就拿不稳了。"},
            {"speaker": "市集商贩", "text": "话是这么说，街上热气最能留人，也最能分人的心。"},
            {"speaker": "孟母", "text": "多谢提醒。轲儿，懂得生计，也要懂得何处能安放心志。"},
        ]},
        {"id": "dialogue.teacher", "lines": [
            {"speaker": "孟母", "text": "先生，孩子从市井喧哗中来，先该学什么才能收心？"},
            {"speaker": "学宫先生", "text": "先正衣冠，再正坐席。身体安了，心才有地方落下。"},
            {"speaker": "孟轲", "text": "若我听见外头叫卖，还想跑出去看呢？"},
            {"speaker": "孟母", "text": "想看并不可耻，能把眼光收回来，才是今日的功课。"},
            {"speaker": "学宫先生", "text": "取一卷竹简，从第一行读起。读书不是躲开世界，是学会不被世界牵走。"},
            {"speaker": "孟轲", "text": "我愿试一试，先读完这一卷。"},
        ]},
        {"id": "dialogue.meng_ke_loom", "lines": [
            {"speaker": "孟轲", "text": "母亲，今日的书太难，我想明日再读。"},
            {"speaker": "孟母", "text": "你看这匹布，若我织到一半剪断，明日还能接成原来的样子吗？"},
            {"speaker": "孟轲", "text": "线断了，就算接上，也会留下结。"},
            {"speaker": "孟母", "text": "学问也是这样。停一日，看似只少一日，心里的线却先松了。"},
            {"speaker": "孟轲", "text": "可我怕自己读不懂，越读越羞。"},
            {"speaker": "孟母", "text": "不懂便问，慢便慢读。只要今日不断，明日就有可续之处。"},
        ]},
    ]})
    write_json(rpg / "events.json", {"events": [{"id": "event.resolve_made", "title": "立志成学", "quest_id": "quest.loom_lesson"}]})
    write_json(rpg / "shops.json", {"shops": [{
        "id": "shop.market_stall",
        "name": "市集茶食摊",
        "inventory": ["item.steam_bun", "item.calm_tea"],
        "lines": ["小摊上热气腾腾。孟母买下热馍，也提醒孟轲：市井谋生值得尊重，喧嚣逐利却不可乱了心。"],
    }]})
    write_json(rpg / "rest-points.json", {"rest_points": [
        {"id": "rest.old_well", "name": "旧井石阶", "cost": 0},
        {"id": "rest.market_tea", "name": "市集茶棚", "cost": 0},
        {"id": "rest.school_pine", "name": "学宫松荫", "cost": 0},
        {"id": "rest.loom_bench", "name": "织室木凳", "cost": 0},
    ]})
    write_json(rpg / "progression-rules.json", {"progression_rules": [
        {"id": "progression.graveyard", "quest_id": "quest.leave_graveyard", "effect": "迁往市集旁。"},
        {"id": "progression.market", "quest_id": "quest.leave_market", "effect": "迁往学宫旁。"},
        {"id": "progression.school", "quest_id": "quest.enter_school", "effect": "取得启蒙竹简并回到织室。"},
        {"id": "progression.loom", "quest_id": "quest.loom_lesson", "effect": "孟轲立志并触发结局。"},
    ]})


def map_payload(map_id: str, title: str, asset_id: str, boundary_file: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": map_id,
        "title": title,
        "coordinate_system": "pixels",
        "width": MAP_W,
        "height": MAP_H,
        "asset_id": asset_id,
        "boundary_file": f"../boundaries/{boundary_file}",
        "layers": {"ground": [], "collision": []},
        "events": events,
    }


def write_maps(run_root: Path) -> None:
    maps = run_root / "workspace" / "rpg" / "maps"
    write_json(maps / "graveyard_lane.map.json", map_payload("map.graveyard_lane", "墓园旁旧巷", "map.graveyard_lane", "graveyard_lane.boundaries.json", [
        {"id": "npc.old_neighbor", "type": "npc", "x": 345, "y": 490, "name": "旧邻老者", "dialogue_id": "dialogue.old_neighbor", "sprite_asset_id": "sprite.old_neighbor"},
        {"id": "npc.meng_ke_graveyard", "type": "npc", "x": 535, "y": 515, "name": "孟轲", "dialogue_id": "dialogue.meng_ke_graveyard", "sprite_asset_id": "sprite.meng_ke", "quest_id": "quest.leave_graveyard"},
        {"id": "battle.old_habit", "type": "battle", "x": 780, "y": 430, "enemy_id": "enemy.mournful_habit", "once": True, "quest_id": "quest.leave_graveyard", "battle_background_asset_id": "battlebg.graveyard_lane", "win_outcomes": [{"id": "move.market", "lines": [{"speaker": "孟母", "text": "此处不是久居之所。收拾书箱，我们再走一程。"}], "set_flags": {"moved_from_graveyard": True}, "complete_quest_id": "quest.leave_graveyard"}]},
        {"id": "rest.old_well", "type": "rest", "x": 450, "y": 590, "rest_point_id": "rest.old_well"},
        {"id": "exit.to_market", "type": "transfer", "x": 1135, "y": 495, "target_map_id": "map.market_lane", "target_x": 145, "target_y": 510},
    ]))
    write_json(maps / "market_lane.map.json", map_payload("map.market_lane", "市集旁新居", "map.market_lane", "market_lane.boundaries.json", [
        {"id": "npc.vendor", "type": "npc", "x": 410, "y": 420, "name": "市集商贩", "dialogue_id": "dialogue.vendor", "sprite_asset_id": "sprite.vendor", "quest_id": "quest.leave_market"},
        {"id": "shop.market_stall", "type": "shop", "x": 535, "y": 455, "shop_id": "shop.market_stall", "name": "市集茶食摊", "sprite_asset_id": "sprite.vendor"},
        {"id": "pickup.steam_bun", "type": "pickup", "x": 620, "y": 560, "item_id": "item.steam_bun", "quantity": 2, "log": "你收起两份热馍。"},
        {"id": "battle.market_noise", "type": "battle", "x": 820, "y": 430, "enemy_id": "enemy.market_noise", "once": True, "quest_id": "quest.leave_market", "battle_background_asset_id": "battlebg.market_lane", "win_outcomes": [{"id": "move.school", "lines": [{"speaker": "孟母", "text": "买卖喧闹自有其处，孩子读书要有能静心的邻里。"}], "set_flags": {"market_lesson": True}, "complete_quest_id": "quest.leave_market"}]},
        {"id": "rest.market_tea", "type": "rest", "x": 545, "y": 520, "rest_point_id": "rest.market_tea"},
        {"id": "exit.back_graveyard", "type": "transfer", "x": 95, "y": 510, "target_map_id": "map.graveyard_lane", "target_x": 1085, "target_y": 495},
        {"id": "exit.to_school", "type": "transfer", "x": 1145, "y": 500, "target_map_id": "map.school_courtyard", "target_x": 155, "target_y": 525},
    ]))
    write_json(maps / "school_courtyard.map.json", map_payload("map.school_courtyard", "学宫旁庭院", "map.school_courtyard", "school_courtyard.boundaries.json", [
        {"id": "npc.teacher", "type": "npc", "x": 575, "y": 350, "name": "学宫先生", "dialogue_id": "dialogue.teacher", "sprite_asset_id": "sprite.teacher", "quest_id": "quest.enter_school"},
        {"id": "pickup.bamboo_slips", "type": "pickup", "x": 675, "y": 420, "item_id": "item.bamboo_slips", "quantity": 1, "log": "你取得启蒙竹简。"},
        {"id": "quest.school_settled", "type": "quest", "x": 850, "y": 430, "quest_id": "quest.enter_school", "name": "入学礼", "lines": [{"speaker": "学宫先生", "text": "能在喧嚣之后收心，便已经踏入学门。"}], "set_flags": {"school_settled": True}, "complete_quest_id": "quest.enter_school"},
        {"id": "rest.school_pine", "type": "rest", "x": 430, "y": 545, "rest_point_id": "rest.school_pine"},
        {"id": "exit.back_market", "type": "transfer", "x": 95, "y": 525, "target_map_id": "map.market_lane", "target_x": 1090, "target_y": 500},
        {"id": "exit.to_loom", "type": "transfer", "x": 1145, "y": 470, "target_map_id": "map.loom_room", "target_x": 170, "target_y": 525},
    ]))
    write_json(maps / "loom_room.map.json", map_payload("map.loom_room", "孟家织室", "map.loom_room", "loom_room.boundaries.json", [
        {"id": "npc.meng_ke_loom", "type": "npc", "x": 520, "y": 405, "name": "孟轲", "dialogue_id": "dialogue.meng_ke_loom", "sprite_asset_id": "sprite.meng_ke", "quest_id": "quest.loom_lesson"},
        {"id": "pickup.loom_shuttle", "type": "pickup", "x": 610, "y": 515, "item_id": "item.loom_shuttle", "quantity": 1, "log": "你拾起织机木梭。"},
        {"id": "battle.laziness_shadow", "type": "battle", "x": 650, "y": 410, "enemy_id": "enemy.laziness_shadow", "once": True, "quest_id": "quest.loom_lesson", "battle_background_asset_id": "battlebg.loom_room", "win_outcomes": [{"id": "resolve.made", "lines": [{"speaker": "孟轲", "text": "我明白了。学问如织布，一日断线，便少一寸成匹的功夫。"}, {"speaker": "孟母", "text": "能续上今日，才有明日。"}], "set_flags": {"resolve_made": True, "ending:scholar_path": True}, "complete_quest_id": "quest.loom_lesson"}]},
        {"id": "rest.loom_bench", "type": "rest", "x": 455, "y": 565, "rest_point_id": "rest.loom_bench"},
        {"id": "exit.back_school", "type": "transfer", "x": 95, "y": 525, "target_map_id": "map.school_courtyard", "target_x": 1090, "target_y": 470},
    ]))


def write_boundaries(run_root: Path) -> None:
    root = run_root / "workspace" / "rpg" / "boundaries"
    edge_blocks = [
        {"id": "north_block", "type": "rect", "x": 0, "y": 0, "w": MAP_W, "h": 90},
        {"id": "south_block", "type": "rect", "x": 0, "y": 650, "w": MAP_W, "h": 70},
        {"id": "west_block", "type": "rect", "x": 0, "y": 0, "w": 70, "h": MAP_H},
        {"id": "east_block", "type": "rect", "x": 1210, "y": 0, "w": 70, "h": MAP_H},
    ]
    payloads = [
        ("map.graveyard_lane", "graveyard_lane.boundaries.json", "旧巷主路、井边和东侧迁居出口可走；坟丘、松柏墙和旧屋墙不可走。", edge_blocks + [
            {"id": "grave_mounds", "type": "polygon", "points": [[125, 110], [500, 105], [465, 305], [190, 325], [90, 235]]},
            {"id": "old_house", "type": "rect", "x": 650, "y": 115, "w": 330, "h": 190},
            {"id": "pine_cluster", "type": "polygon", "points": [[960, 95], [1210, 95], [1210, 330], [1050, 285], [920, 185]]},
        ], {"x": 510, "y": 535}),
        ("map.market_lane", "market_lane.boundaries.json", "市集街道中央、茶棚前和东西出口可走；摊棚、货箱和水渠不可走。", edge_blocks + [
            {"id": "left_stalls", "type": "rect", "x": 170, "y": 120, "w": 270, "h": 210},
            {"id": "right_stalls", "type": "rect", "x": 800, "y": 110, "w": 300, "h": 220},
            {"id": "crate_line", "type": "polygon", "points": [[690, 535], [1010, 555], [1015, 635], [665, 615]]},
        ], {"x": 590, "y": 510}),
        ("map.school_courtyard", "school_courtyard.boundaries.json", "庭院石路、松荫休息点和讲席前可走；学宫台基、回廊柱与水池不可走。", edge_blocks + [
            {"id": "school_hall", "type": "rect", "x": 420, "y": 95, "w": 450, "h": 210},
            {"id": "left_gallery", "type": "rect", "x": 115, "y": 130, "w": 170, "h": 320},
            {"id": "pond", "type": "polygon", "points": [[900, 500], [1070, 470], [1160, 540], [1095, 630], [910, 615]]},
        ], {"x": 575, "y": 455}),
        ("map.loom_room", "loom_room.boundaries.json", "织室中央、书案前和织机旁可走；墙壁、织机主体、柜架和屏风不可走。", edge_blocks + [
            {"id": "loom_frame", "type": "rect", "x": 700, "y": 190, "w": 245, "h": 265},
            {"id": "book_desk", "type": "rect", "x": 390, "y": 160, "w": 200, "h": 120},
            {"id": "cabinet", "type": "rect", "x": 995, "y": 135, "w": 145, "h": 360},
        ], {"x": 520, "y": 500}),
    ]
    for map_id, filename, desc, shapes, hint in payloads:
        write_json(root / filename, {
            "map_id": map_id,
            "coordinate_system": "pixels",
            "description": desc,
            "collision_shapes": shapes,
            "walkable_hint": hint,
            "boundary_source": {
                "kind": "manual_skill_scaffold",
                "source_skill": "project narrative-game-subagent-pipeline + generate2dmap contract",
                "map_mode": "scene_mode",
                "collision_model": "coarse_shapes",
                "visual_asset_source": "final_quality_provider_or_accepted_provider_hints",
            },
        })


def write_asset_direction(run_root: Path) -> None:
    directions = [
        ("map.graveyard_lane", "map_asset", "战国鲁地墓园旁旧巷俯视 RPG 地图，青石路、低矮旧屋、松柏、墓丘远置但不阴森，主路清晰连通。"),
        ("map.market_lane", "map_asset", "战国市集旁街巷俯视 RPG 地图，布棚、陶罐、米袋、叫卖摊，中央街道宽阔可走。"),
        ("map.school_courtyard", "map_asset", "学宫旁庭院俯视 RPG 地图，礼乐讲席、松树、石阶、书院门廊，明亮宁静。"),
        ("map.loom_room", "map_asset", "孟家织室俯视 RPG 室内地图，织布机、书案、竹简、暖窗光，中心走位清楚。"),
        ("tileset.warring_states_town", "tileset", "战国鲁地小镇 RPG 地表、青石路、泥土、院墙、木屋、书院石阶、室内木地板。"),
        ("sprite.meng_mu", "sprite", "孟母，朴素深青汉服，温和坚定，top-down clean HD RPG 角色。"),
        ("sprite.meng_mu.walksheet", "sprite_animation", "孟母 4x4 四方向行走图，透明背景，行顺序 down/left/right/up，每行四帧，同一服装与脚点。"),
        ("sprite.meng_ke", "sprite", "幼年孟轲，束发童子，布衣书袋，好奇神情，top-down clean HD RPG 角色。"),
        ("sprite.old_neighbor", "sprite", "旧邻老者，灰衣、竹杖、亲切提醒。"),
        ("sprite.vendor", "sprite", "市集商贩，短褐衣、布幡、陶罐货担。"),
        ("sprite.teacher", "sprite", "学宫先生，儒雅长衫、竹简、端正站姿。"),
        ("enemy.mournful_habit", "enemy_sprite", "象征旧习的灰蓝影子，像被风吹散的礼器剪影，不恐怖。"),
        ("enemy.market_noise", "enemy_sprite", "市声乱流敌人，布幡、铜钱、声波形状组成的旋涡。"),
        ("enemy.laziness_shadow", "enemy_sprite", "懈怠影敌人，柔软暗影拖着断开的线头与未卷起的竹简。"),
        ("battlebg.graveyard_lane", "battle_background", "墓园旁青石旧巷战斗背景，松柏、远处旧屋、温和灰绿色光。"),
        ("battlebg.market_lane", "battle_background", "市集街道战斗背景，布棚、米袋、陶器、暖色人间烟火。"),
        ("battlebg.school_courtyard", "battle_background", "学宫庭院战斗背景，松荫、书案、礼乐台、清晨阳光。"),
        ("battlebg.loom_room", "battle_background", "孟家织室最终战背景，织布机、断线、竹简与暖窗光，构图清晰。"),
        ("icon.item.steam_bun", "item_icon", "热馍图标，白色蒸汽、竹叶垫底，无文字。"),
        ("icon.item.calm_tea", "item_icon", "清心茶图标，陶盏淡茶和一缕热气，无文字。"),
        ("icon.item.bamboo_slips", "item_icon", "启蒙竹简图标，无文字。"),
        ("icon.item.loom_shuttle", "item_icon", "木质织机梭图标，无文字。"),
        ("icon.skill.mother_teaching", "skill_icon", "母教技能图标，暖色灯光、竹简和细线，无文字。"),
        ("icon.skill.calm_words", "skill_icon", "定心言技能图标，平静水纹、竹简和柔和声波，无文字。"),
        ("icon.skill.cut_thread", "skill_icon", "断机喻技能图标，织线被剪断又重新接续的象征图标，无文字。"),
        ("ui.bamboo_scroll_panel", "rpg_ui", "竹简与素布边框 RPG 对话面板。"),
        ("bgm.graveyard_lane", "bgm", "墓园旁旧巷 BGM，古琴、低笛、缓慢但温柔。"),
        ("bgm.market_lane", "bgm", "市集 BGM，轻快笙笛、木鱼点缀、热闹但不过吵。"),
        ("bgm.school_courtyard", "bgm", "学宫 BGM，古琴、钟磬、清晨读书氛围。"),
        ("bgm.loom_room", "bgm", "织室 BGM，织机节奏、古琴泛音、温暖室内感。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {
            "summary": "战国鲁地历史绘本风，clean HD top-down RPG，温润水墨色与清晰游戏读图结合。",
            "rendering": "clean hand-painted HD 2D RPG asset, Chinese historical picture-book style, readable silhouettes",
            "rendering_mode": "clean hand-painted HD 2D RPG asset, Chinese historical picture-book style, not pixel art",
            "lighting": "soft daylight, warm lamplight, school courtyard morning light",
            "palette": ["#2f4a3e", "#c6a15b", "#8b3f2f", "#e8dfc8", "#506f7a"],
            "map_pipeline": {
                "source_skill": "generate2dmap",
                "map_mode": "scene_mode",
                "visual_model": "layered_raster-compatible 16:9 top-down map",
                "runtime_object_model": "interactive_scene_objects + scene_hooks",
                "collision_model": "coarse_shapes",
                "visual_asset_source": "final-quality provider or accepted Sprite Forge/provider_hints; local-svg only for explicit low-tier fallback",
            },
            "sprite_pipeline": {"source_skill": "generate2dsprite", "view": "topdown", "art_style": "clean_hd", "bundle": "unit_bundle"},
        },
        "asset_directions": [{"asset_id": a, "kind": k, "description": d, **({"mood": "looping historical RPG ambience"} if k == "bgm" else {})} for a, k, d in directions],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "《孟母三迁》Web RPG：孟母带孟轲从墓园旁迁到市集旁，再迁到学宫旁，并用断机之喻劝学。\n")
    write_design_layer(run_root)
    write_rpg_tables(run_root)
    write_maps(run_root)
    write_boundaries(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/mengmu-sanqian-rpg")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
