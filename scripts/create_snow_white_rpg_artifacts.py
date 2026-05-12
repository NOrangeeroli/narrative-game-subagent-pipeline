#!/usr/bin/env python3
"""Create a complete Web RPG run for a Snow White-inspired public-domain fairy tale."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


MAP_W = 1280
MAP_H = 720


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "《白雪公主》改编成中文短篇 Web RPG。",
        "requirements": [
            {"id": "req.public_domain", "text": "基于公版童话《白雪公主》，不引用现代影视造型、台词或专有设定。"},
            {"id": "req.playable", "text": "浏览器可游玩的短篇 RPG，包含探索、NPC 对话、道具、休息点、三场战斗和结局。"},
            {"id": "req.theme", "text": "突出纯真、嫉妒、伪装、森林庇护与自我拯救。"},
            {"id": "req.language", "text": "游戏文本使用中文。"},
            {"id": "req.skill_plan", "text": "地图按 generate2dmap 的 top-down RPG tile_mode/scene-hook 合同规划，角色和敌人按 generate2dsprite 的 topdown clean_hd 资产束规划。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "白雪公主：森林之心",
        "events": [
            {"id": "event.mirror", "summary": "魔镜泄露王后的嫉妒，白雪逃进黑森林。"},
            {"id": "event.cottage", "summary": "七位矿工在林中小屋收留白雪，请她修复守护炉火。"},
            {"id": "event.disguise", "summary": "王后派出影鸦与毒梳伪装，试图让森林陷入沉睡。"},
            {"id": "event.apple", "summary": "白雪识破毒苹果中的咒纹，在镜湖边反制王后的魔法。"},
            {"id": "event.dawn", "summary": "森林晨光击碎魔镜，城堡的嫉妒诅咒消散。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "Snow White RPG Branch Graph",
        "start_node_id": "node.forest_escape",
        "nodes": [
            {"id": "node.forest_escape", "title": "逃入黑森林", "summary": "白雪躲开猎人与影鸦，寻找安全的林间小路。"},
            {"id": "node.dwarfs_cottage", "title": "矿工小屋", "summary": "白雪帮助七位矿工点燃守护炉火。"},
            {"id": "node.glass_lake", "title": "镜湖毒苹果", "summary": "王后的伪装在镜湖边显形。"},
            {"id": "node.mirror_gate", "title": "魔镜门厅", "summary": "白雪进入城堡门厅，与嫉妒魔镜决战。"},
            {"id": "node.dawn_return", "title": "晨光归来", "summary": "森林恢复，白雪带回自由的黎明。", "is_terminal": True},
        ],
        "edges": [
            {"id": "edge.escape.cottage", "from": "node.forest_escape", "to": "node.dwarfs_cottage", "condition_type": "unconditional"},
            {"id": "edge.cottage.lake", "from": "node.dwarfs_cottage", "to": "node.glass_lake", "condition_type": "quest_complete"},
            {"id": "edge.lake.gate", "from": "node.glass_lake", "to": "node.mirror_gate", "condition_type": "quest_complete"},
            {"id": "edge.gate.dawn", "from": "node.mirror_gate", "to": "node.dawn_return", "condition_type": "terminal_resolution"},
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "白雪公主：森林之心",
        "design_brief": {
            "logline": "白雪公主在森林、矿工小屋、镜湖和城堡门厅中收集炉火碎片，击破王后的嫉妒魔镜。",
            "narrative_bible": {
                "themes": ["纯真与勇气", "伪装与识破", "森林庇护", "嫉妒的代价"],
                "cast": [
                    {"id": "char.snow_white", "name": "白雪公主"},
                    {"id": "char.huntsman", "name": "悔悟猎人"},
                    {"id": "char.dwarf_elder", "name": "矿工长者"},
                    {"id": "char.forest_deer", "name": "森林小鹿"},
                    {"id": "char.queen", "name": "王后"},
                    {"id": "char.magic_mirror", "name": "魔镜"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.has_lantern", "type": "boolean", "initial_value": False, "description": "是否取得矿灯。"},
            {"id": "state.hearth_restored", "type": "boolean", "initial_value": False, "description": "小屋炉火是否恢复。"},
            {"id": "state.apple_purified", "type": "boolean", "initial_value": False, "description": "是否净化毒苹果。"},
            {"id": "state.mirror_broken", "type": "boolean", "initial_value": False, "description": "是否击碎嫉妒魔镜。"},
        ],
        "progression_rules": [
            {"id": "rule.start", "summary": "从黑森林入口开始，取得矿灯后抵达小屋。"},
            {"id": "rule.cottage", "summary": "恢复小屋炉火后，镜湖道路开放。"},
            {"id": "rule.lake", "summary": "净化毒苹果后，城堡魔镜门厅开放。"},
            {"id": "rule.final", "summary": "击败魔镜后触发晨光结局。"},
        ],
    })


def write_rpg_tables(run_root: Path) -> None:
    rpg = run_root / "workspace" / "rpg"
    write_json(rpg / "rpg-campaign.json", {
        "title": "白雪公主：森林之心",
        "start_map_id": "map.dark_forest",
        "start_position": {"x": 170, "y": 540},
        "party": ["actor.snow_white"],
        "entry_title": "走入森林",
        "entry_text": "王后的魔镜在城堡里低语。白雪必须穿过森林，找到能照亮真相的炉火。",
        "entry_points": [{
            "id": "entry.snow_white",
            "title": "白雪公主",
            "description": "探索森林、小屋、镜湖和魔镜门厅，击破王后的嫉妒诅咒。",
            "start_map_id": "map.dark_forest",
            "start_position": {"x": 170, "y": 540},
            "party": ["actor.snow_white"],
            "initial_quests": ["quest.find_cottage"],
            "initial_inventory": {"item.forest_berry": 2},
        }],
        "goal": "恢复森林炉火，净化毒苹果，击碎嫉妒魔镜。",
        "major_quest_ids": ["quest.find_cottage", "quest.restore_hearth", "quest.purify_apple", "quest.break_mirror"],
        "final_quest_id": "quest.break_mirror",
        "ending_title": "晨光照进森林",
        "ending_text": "魔镜裂成无声的银片，森林里的炉火与晨光一起亮起。白雪没有等待谁来拯救她，而是亲手带回了黎明。",
        "endings": [{"id": "dawn", "title": "结局：森林之心", "text": "白雪净化毒苹果并击碎魔镜，王后的诅咒随晨光消散。", "conditions": {"flags": {"ending:dawn": True}}}],
        "required_assets": [
            "map.dark_forest", "map.dwarfs_cottage", "map.mirror_lake", "map.castle_mirror_hall",
            "tileset.snow_white_forest",
            "sprite.snow_white", "sprite.huntsman", "sprite.dwarf_elder", "sprite.forest_deer", "sprite.queen",
            "enemy.shadow_raven", "enemy.poison_comb", "enemy.magic_mirror",
            "battlebg.forest_path", "battlebg.mirror_lake", "battlebg.mirror_hall",
            "icon.item.forest_berry", "icon.item.miner_lantern", "icon.item.purified_apple", "icon.skill.kind_heart",
            "ui.fairy_tale_panel",
        ],
        "battle_ui_showcase": {
            "title": "战斗节奏",
            "text": "白雪用善意、炉火与识破伪装的勇气对抗王后的影鸦、毒梳和魔镜。",
            "flow": ["探索地图", "触发事件", "回合制战斗", "完成任务", "开放下一张地图"],
            "features": ["中文剧情对白", "三场轻量战斗", "道具治疗", "地图传送与休息点"],
        },
    })
    write_json(rpg / "world-map.json", {"title": "王后诅咒下的森林王国", "start_map_id": "map.dark_forest", "maps": [
        {"id": "map.dark_forest", "title": "黑森林入口", "role": "field"},
        {"id": "map.dwarfs_cottage", "title": "七矿工小屋", "role": "hub"},
        {"id": "map.mirror_lake", "title": "镜湖", "role": "puzzle"},
        {"id": "map.castle_mirror_hall", "title": "魔镜门厅", "role": "finale"},
    ]})
    write_json(rpg / "actors.json", {"actors": [{
        "id": "actor.snow_white", "name": "白雪公主", "class_id": "class.forest_heart",
        "stats": {"hp": 64, "attack": 12, "defense": 6, "speed": 7},
        "sprite_asset_id": "sprite.snow_white",
        "skills": ["skill.kind_heart", "skill.hearth_glow", "skill.truth_song"],
    }]})
    write_json(rpg / "classes.json", {"classes": [{"id": "class.forest_heart", "name": "森林之心", "growth": "生命与速度均衡"}]})
    write_json(rpg / "items.json", {"items": [
        {"id": "item.forest_berry", "name": "森林浆果", "description": "恢复少量生命的红浆果。", "icon_asset_id": "icon.item.forest_berry", "heal": 18},
        {"id": "item.miner_lantern", "name": "矿灯", "description": "七矿工交给白雪的黄铜矿灯。", "icon_asset_id": "icon.item.miner_lantern"},
        {"id": "item.purified_apple", "name": "净化苹果", "description": "被炉火净化后的苹果，可以反照伪装。", "icon_asset_id": "icon.item.purified_apple"},
    ]})
    write_json(rpg / "equipment.json", {"equipment": [{"id": "equip.blue_cloak", "name": "森林蓝披肩", "slot": "body", "defense": 2, "asset_id": "icon.item.miner_lantern"}]})
    write_json(rpg / "skills.json", {"skills": [
        {"id": "skill.kind_heart", "name": "善意之歌", "power": 9, "focus_cost": 0, "icon_asset_id": "icon.skill.kind_heart"},
        {"id": "skill.hearth_glow", "name": "炉火微光", "power": 13, "focus_cost": 2, "icon_asset_id": "icon.skill.kind_heart"},
        {"id": "skill.truth_song", "name": "真名回响", "power": 17, "focus_cost": 3, "icon_asset_id": "icon.skill.kind_heart"},
        {"id": "skill.shadow_peck", "name": "影喙", "power": 7, "focus_cost": 0, "icon_asset_id": "icon.skill.kind_heart"},
        {"id": "skill.poison_prick", "name": "毒梳刺", "power": 9, "focus_cost": 0, "icon_asset_id": "icon.skill.kind_heart"},
        {"id": "skill.jealous_reflection", "name": "嫉妒反照", "power": 12, "focus_cost": 0, "icon_asset_id": "icon.skill.kind_heart"},
    ]})
    write_json(rpg / "enemies.json", {"enemies": [
        {"id": "enemy.shadow_raven", "name": "影鸦", "stats": {"hp": 26, "attack": 7, "defense": 2, "speed": 7}, "sprite_asset_id": "enemy.shadow_raven", "skills": ["skill.shadow_peck"], "pattern": ["attack", "skill", "guard"]},
        {"id": "enemy.poison_comb", "name": "毒梳幻影", "stats": {"hp": 36, "attack": 9, "defense": 3, "speed": 5}, "sprite_asset_id": "enemy.poison_comb", "skills": ["skill.poison_prick"], "pattern": ["skill", "attack", "guard"]},
        {"id": "enemy.magic_mirror", "name": "嫉妒魔镜", "stats": {"hp": 58, "attack": 11, "defense": 5, "speed": 6}, "sprite_asset_id": "enemy.magic_mirror", "skills": ["skill.jealous_reflection", "skill.shadow_peck"], "pattern": ["guard", "skill", "attack", "skill"]},
    ]})
    write_json(rpg / "encounter-tables.json", {"encounter_tables": [{"id": "encounter.forest_curse", "enemies": ["enemy.shadow_raven", "enemy.poison_comb"]}]})
    write_json(rpg / "quests.json", {"quests": [
        {"id": "quest.find_cottage", "title": "找到林中小屋", "description": "穿过黑森林，找到七矿工留下的炉火。"},
        {"id": "quest.restore_hearth", "title": "恢复守护炉火", "description": "击退毒梳幻影，让小屋重新亮起。"},
        {"id": "quest.purify_apple", "title": "净化毒苹果", "description": "在镜湖边识破王后的伪装。"},
        {"id": "quest.break_mirror", "title": "击碎嫉妒魔镜", "description": "进入城堡门厅，终结魔镜诅咒。"},
    ]})
    write_json(rpg / "npc-dialogue.json", {"npc_dialogue": [
        {"id": "dialogue.huntsman", "lines": [{"speaker": "悔悟猎人", "text": "沿着苔藓最亮的路走，小屋的烟囱会在黄昏前出现。"}, {"speaker": "白雪", "text": "谢谢你。愿你以后不再听从恐惧。"}]},
        {"id": "dialogue.deer", "lines": [{"speaker": "森林小鹿", "text": "影鸦害怕炉火，也害怕有人唱出真话。"}]},
        {"id": "dialogue.dwarf_elder", "lines": [{"speaker": "矿工长者", "text": "炉火碎了，毒梳和冷灰堵住了烟道。"}, {"speaker": "白雪", "text": "那就让我们把火重新点起来。"}]},
        {"id": "dialogue.queen", "lines": [{"speaker": "陌生老妇", "text": "甜苹果给甜美的姑娘，咬一口，烦恼就会睡去。"}, {"speaker": "白雪", "text": "你的影子没有变老，王后。"}]},
        {"id": "dialogue.mirror", "lines": [{"speaker": "魔镜", "text": "世上最美的人，只能映出王后的名字。"}, {"speaker": "白雪", "text": "镜子若只会说谎，碎片也比整面更诚实。"}]},
    ]})
    write_json(rpg / "events.json", {"events": [{"id": "event.mirror_broken", "title": "魔镜碎裂", "quest_id": "quest.break_mirror"}]})
    write_json(rpg / "shops.json", {"shops": []})
    write_json(rpg / "rest-points.json", {"rest_points": [{"id": "rest.moss_bed", "name": "苔藓床", "cost": 0}, {"id": "rest.hearth", "name": "小屋炉火", "cost": 0}, {"id": "rest.lake_stone", "name": "镜湖石阶", "cost": 0}]})
    write_json(rpg / "progression-rules.json", {"progression_rules": [
        {"id": "progression.lantern", "quest_id": "quest.find_cottage", "effect": "取得矿灯并开启小屋道路。"},
        {"id": "progression.hearth", "quest_id": "quest.restore_hearth", "effect": "恢复小屋炉火并开启镜湖道路。"},
        {"id": "progression.apple", "quest_id": "quest.purify_apple", "effect": "净化苹果并开启城堡道路。"},
        {"id": "progression.mirror", "quest_id": "quest.break_mirror", "effect": "击碎魔镜并触发结局。"},
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
    write_json(maps / "dark_forest.map.json", map_payload("map.dark_forest", "黑森林入口", "map.dark_forest", "dark_forest.boundaries.json", [
        {"id": "npc.huntsman", "type": "npc", "x": 310, "y": 505, "name": "悔悟猎人", "dialogue_id": "dialogue.huntsman", "sprite_asset_id": "sprite.huntsman", "quest_id": "quest.find_cottage"},
        {"id": "npc.deer", "type": "npc", "x": 625, "y": 390, "name": "森林小鹿", "dialogue_id": "dialogue.deer", "sprite_asset_id": "sprite.forest_deer"},
        {"id": "battle.raven", "type": "battle", "x": 790, "y": 455, "enemy_id": "enemy.shadow_raven", "once": True, "quest_id": "quest.find_cottage", "battle_background_asset_id": "battlebg.forest_path", "win_outcomes": [{"id": "forest.clear", "lines": [{"speaker": "白雪", "text": "影子散开了，小路露出来了。"}], "set_flags": {"has_lantern": True}, "complete_quest_id": "quest.find_cottage", "grant_items": {"item.miner_lantern": 1}}]},
        {"id": "rest.moss_bed", "type": "rest", "x": 500, "y": 575, "rest_point_id": "rest.moss_bed"},
        {"id": "exit.to_cottage", "type": "transfer", "x": 1120, "y": 410, "target_map_id": "map.dwarfs_cottage", "target_x": 160, "target_y": 520},
    ]))
    write_json(maps / "dwarfs_cottage.map.json", map_payload("map.dwarfs_cottage", "七矿工小屋", "map.dwarfs_cottage", "dwarfs_cottage.boundaries.json", [
        {"id": "npc.dwarf_elder", "type": "npc", "x": 430, "y": 390, "name": "矿工长者", "dialogue_id": "dialogue.dwarf_elder", "sprite_asset_id": "sprite.dwarf_elder", "quest_id": "quest.restore_hearth"},
        {"id": "pickup.berry", "type": "pickup", "x": 690, "y": 520, "item_id": "item.forest_berry", "quantity": 2, "log": "你收起两枚森林浆果。"},
        {"id": "battle.comb", "type": "battle", "x": 835, "y": 390, "enemy_id": "enemy.poison_comb", "once": True, "quest_id": "quest.restore_hearth", "battle_background_asset_id": "battlebg.forest_path", "win_outcomes": [{"id": "hearth.restored", "lines": [{"speaker": "矿工长者", "text": "炉火回来了，镜湖上的雾也会让路。"}], "set_flags": {"hearth_restored": True}, "complete_quest_id": "quest.restore_hearth"}]},
        {"id": "rest.hearth", "type": "rest", "x": 590, "y": 395, "rest_point_id": "rest.hearth"},
        {"id": "exit.back_forest", "type": "transfer", "x": 120, "y": 530, "target_map_id": "map.dark_forest", "target_x": 1070, "target_y": 410},
        {"id": "exit.to_lake", "type": "transfer", "x": 1130, "y": 510, "target_map_id": "map.mirror_lake", "target_x": 150, "target_y": 500},
    ]))
    write_json(maps / "mirror_lake.map.json", map_payload("map.mirror_lake", "镜湖", "map.mirror_lake", "mirror_lake.boundaries.json", [
        {"id": "npc.queen_disguised", "type": "npc", "x": 610, "y": 360, "name": "陌生老妇", "dialogue_id": "dialogue.queen", "sprite_asset_id": "sprite.queen", "quest_id": "quest.purify_apple"},
        {"id": "battle.apple_curse", "type": "battle", "x": 790, "y": 420, "enemy_id": "enemy.poison_comb", "once": True, "quest_id": "quest.purify_apple", "battle_background_asset_id": "battlebg.mirror_lake", "win_outcomes": [{"id": "apple.purified", "lines": [{"speaker": "白雪", "text": "苹果里的咒纹被湖光照出来了。"}], "set_flags": {"apple_purified": True}, "complete_quest_id": "quest.purify_apple", "grant_items": {"item.purified_apple": 1}}]},
        {"id": "rest.lake_stone", "type": "rest", "x": 420, "y": 545, "rest_point_id": "rest.lake_stone"},
        {"id": "exit.back_cottage", "type": "transfer", "x": 105, "y": 500, "target_map_id": "map.dwarfs_cottage", "target_x": 1080, "target_y": 510},
        {"id": "exit.to_castle", "type": "transfer", "x": 1160, "y": 360, "target_map_id": "map.castle_mirror_hall", "target_x": 170, "target_y": 520},
    ]))
    write_json(maps / "castle_mirror_hall.map.json", map_payload("map.castle_mirror_hall", "魔镜门厅", "map.castle_mirror_hall", "castle_mirror_hall.boundaries.json", [
        {"id": "npc.mirror", "type": "npc", "x": 640, "y": 285, "name": "魔镜", "dialogue_id": "dialogue.mirror", "sprite_asset_id": "enemy.magic_mirror"},
        {"id": "battle.magic_mirror", "type": "battle", "x": 760, "y": 405, "enemy_id": "enemy.magic_mirror", "once": True, "quest_id": "quest.break_mirror", "battle_background_asset_id": "battlebg.mirror_hall", "win_outcomes": [{"id": "mirror.broken", "lines": [{"speaker": "魔镜", "text": "我只映出她想听的话。"}, {"speaker": "白雪", "text": "那就让森林听见真话。"}], "set_flags": {"mirror_broken": True, "ending:dawn": True}, "complete_quest_id": "quest.break_mirror"}]},
        {"id": "exit.back_lake", "type": "transfer", "x": 115, "y": 520, "target_map_id": "map.mirror_lake", "target_x": 1085, "target_y": 360},
    ]))


def write_boundaries(run_root: Path) -> None:
    root = run_root / "workspace" / "rpg" / "boundaries"
    common_edge_blocks = [
        {"id": "north_block", "type": "rect", "x": 0, "y": 0, "w": MAP_W, "h": 90},
        {"id": "south_block", "type": "rect", "x": 0, "y": 650, "w": MAP_W, "h": 70},
        {"id": "west_block", "type": "rect", "x": 0, "y": 0, "w": 70, "h": MAP_H},
        {"id": "east_block", "type": "rect", "x": 1210, "y": 0, "w": 70, "h": MAP_H},
    ]
    payloads = [
        ("map.dark_forest", "dark_forest.boundaries.json", "主路、苔藓休息点和小屋出口可走；密林、树根墙和深灌木不可走。", common_edge_blocks + [
            {"id": "tree_wall_left", "type": "polygon", "points": [[70, 90], [235, 110], [220, 335], [95, 385], [70, 360]]},
            {"id": "tree_wall_top", "type": "polygon", "points": [[250, 90], [930, 90], [820, 220], [520, 190], [270, 235]]},
            {"id": "root_cluster", "type": "rect", "x": 840, "y": 500, "w": 190, "h": 135},
        ], {"x": 520, "y": 500}),
        ("map.dwarfs_cottage", "dwarfs_cottage.boundaries.json", "小屋前空地和矿道可走；小屋墙、木柴堆和密树不可走。", common_edge_blocks + [
            {"id": "cottage", "type": "rect", "x": 455, "y": 155, "w": 360, "h": 190},
            {"id": "woodpile", "type": "rect", "x": 760, "y": 520, "w": 140, "h": 95},
            {"id": "mine_rocks", "type": "polygon", "points": [[940, 90], [1210, 90], [1210, 300], [1030, 260], [910, 170]]},
        ], {"x": 570, "y": 455}),
        ("map.mirror_lake", "mirror_lake.boundaries.json", "湖边石径、浅滩和城堡道路可走；深湖、芦苇墙和镜面深水不可走。", common_edge_blocks + [
            {"id": "deep_lake", "type": "polygon", "points": [[365, 225], [450, 155], [620, 145], [755, 215], [785, 310], [680, 375], [500, 365], [390, 300]]},
            {"id": "reed_wall", "type": "polygon", "points": [[70, 90], [380, 95], [300, 245], [70, 285]]},
            {"id": "cliff", "type": "polygon", "points": [[875, 95], [1210, 90], [1210, 270], [1000, 245], [920, 190]]},
        ], {"x": 500, "y": 510}),
        ("map.castle_mirror_hall", "castle_mirror_hall.boundaries.json", "红毯和门厅中央可走；柱廊、王座台阶和破镜边缘不可走。", common_edge_blocks + [
            {"id": "left_columns", "type": "rect", "x": 170, "y": 120, "w": 130, "h": 405},
            {"id": "right_columns", "type": "rect", "x": 980, "y": 120, "w": 130, "h": 405},
            {"id": "mirror_dais", "type": "rect", "x": 520, "y": 115, "w": 245, "h": 165},
        ], {"x": 640, "y": 520}),
    ]
    for map_id, filename, desc, shapes, hint in payloads:
        write_json(root / filename, {
            "map_id": map_id,
            "coordinate_system": "pixels",
            "description": desc,
            "collision_shapes": shapes,
            "walkable_hint": hint,
            "boundary_source": {"kind": "manual_skill_scaffold", "source_skill": "generate2dmap", "map_mode": "tile_mode", "collision_model": "coarse_shapes"},
        })


def write_asset_direction(run_root: Path) -> None:
    directions = [
        ("map.dark_forest", "map_asset", "黑森林入口俯视 RPG 地图，苔藓小径、银桦、荆棘、昏暗但可读的林间道路。"),
        ("map.dwarfs_cottage", "map_asset", "七矿工小屋俯视 RPG 地图，小木屋、烟囱、矿道入口、炉火空地、木柴堆。"),
        ("map.mirror_lake", "map_asset", "镜湖俯视 RPG 地图，月色湖面、石径、芦苇、通往城堡的冷色小路。"),
        ("map.castle_mirror_hall", "map_asset", "城堡魔镜门厅俯视 RPG 地图，红毯、柱廊、银镜高台、破碎反光。"),
        ("tileset.snow_white_forest", "tileset", "森林童话 RPG 地表、苔藓、石路、木屋、湖岸、城堡地砖。"),
        ("sprite.snow_white", "sprite", "公版童话白雪公主，黑发、蓝黄服饰、红披肩，top-down clean HD RPG 角色。"),
        ("sprite.huntsman", "sprite", "悔悟猎人，棕色猎装、短披风、低头歉意。"),
        ("sprite.dwarf_elder", "sprite", "七矿工长者，灰胡子、矿帽、黄铜矿灯。"),
        ("sprite.forest_deer", "sprite", "森林小鹿，温和、浅棕、童话风。"),
        ("sprite.queen", "sprite", "王后伪装成老妇但影子带王冠轮廓。"),
        ("enemy.shadow_raven", "enemy_sprite", "影鸦敌人，黑紫羽毛、红眼、雾状边缘。"),
        ("enemy.poison_comb", "enemy_sprite", "毒梳幻影敌人，银梳、绿色毒雾、尖刺光。"),
        ("enemy.magic_mirror", "enemy_sprite", "嫉妒魔镜敌人，银框、裂纹、冷蓝反光和王冠阴影。"),
        ("battlebg.forest_path", "battle_background", "森林小径战斗背景，树影、苔藓、远处小屋光。"),
        ("battlebg.mirror_lake", "battle_background", "镜湖战斗背景，湖面倒影、毒苹果、芦苇和月光。"),
        ("battlebg.mirror_hall", "battle_background", "魔镜门厅战斗背景，红毯、柱廊、破碎银镜。"),
        ("icon.item.forest_berry", "item_icon", "森林红浆果图标，无文字。"),
        ("icon.item.miner_lantern", "item_icon", "黄铜矿灯图标，无文字。"),
        ("icon.item.purified_apple", "item_icon", "发光净化苹果图标，无文字。"),
        ("icon.skill.kind_heart", "skill_icon", "善意之歌技能图标，炉火、心形光、森林叶片，无文字。"),
        ("ui.fairy_tale_panel", "rpg_ui", "古典童话书页边框 RPG 对话面板。"),
        ("bgm.dark_forest", "bgm", "黑森林 BGM，轻弦、木管、低声钟琴。"),
        ("bgm.dwarfs_cottage", "bgm", "矿工小屋 BGM，温暖炉火、木琴、轻快锤音。"),
        ("bgm.mirror_lake", "bgm", "镜湖 BGM，玻璃琴、水声、悬疑弦乐。"),
        ("bgm.castle_mirror_hall", "bgm", "魔镜门厅 BGM，管风琴、低鼓、冷色合唱垫。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {
            "summary": "公版欧洲童话绘本风，clean HD top-down RPG，可读轮廓，温暖森林色与冷银镜面对比。",
            "rendering": "clean hand-painted HD 2D RPG asset, storybook fairy-tale lighting",
            "lighting": "soft forest dusk, hearth glow, moonlit lake, cold mirror hall reflections",
            "palette": ["#253a2f", "#d9b45f", "#b8323a", "#eef0dc", "#657d93"],
            "map_pipeline": {"source_skill": "generate2dmap", "map_mode": "tile_mode", "visual_model": "layered_tilemap-compatible raster", "runtime_object_model": "interactive_scene_objects + scene_hooks", "collision_model": "coarse_shapes"},
            "sprite_pipeline": {"source_skill": "generate2dsprite", "view": "topdown", "art_style": "clean_hd", "bundle": "unit_bundle"},
        },
        "asset_directions": [{"asset_id": a, "kind": k, "description": d, **({"mood": "looping fairy-tale ambience"} if k == "bgm" else {})} for a, k, d in directions],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "《白雪公主》Web RPG：白雪穿过黑森林、七矿工小屋、镜湖和魔镜门厅，净化毒苹果并击碎嫉妒魔镜。\n")
    write_design_layer(run_root)
    write_rpg_tables(run_root)
    write_maps(run_root)
    write_boundaries(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/snow-white-rpg")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
