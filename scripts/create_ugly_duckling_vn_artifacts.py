#!/usr/bin/env python3
"""Create a complete Web VN run for The Ugly Duckling."""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent

from pipeline_lib import ensure_run_layout, path_for, write_json, write_text


NODES = [
    ("node.reed_nest", "芦苇窝的清晨", "最后破壳的小鸟被鸭群嘲笑，母鸭仍试图保护它。"),
    ("node.farmyard", "院子里的目光", "它在农家院寻找容身之处，却被鸡、猫和孩子们推开。"),
    ("node.winter_marsh", "冰封沼泽", "冬天到来，丑小鸭在寒风和冰面边缘坚持活下去。"),
    ("node.spring_lake", "春天的湖", "冰雪融化，它靠近湖面，看见一群优雅的白天鹅。"),
    ("node.true_reflection", "真正的倒影", "它在水中认出自己的模样，不再把别人的嘲笑当作命运。"),
]

EDGES = [
    ("edge.nest.farmyard", "node.reed_nest", "node.farmyard", "离开芦苇窝"),
    ("edge.farmyard.winter", "node.farmyard", "node.winter_marsh", "逃向荒野"),
    ("edge.winter.spring", "node.winter_marsh", "node.spring_lake", "等到春天"),
    ("edge.spring.reflection", "node.spring_lake", "node.true_reflection", "靠近湖心"),
]


def write_design_layer(run_root: Path) -> None:
    write_json(path_for(run_root, "requirements"), {
        "prompt": "《丑小鸭》改编成短篇中文剧情游戏。",
        "requirements": [
            {"id": "req.public_domain", "text": "基于公版童话《丑小鸭》，不引用现代影视改编设计。"},
            {"id": "req.playable", "text": "浏览器可游玩的短篇剧情游戏，玩家通过选择推进五幕故事。"},
            {"id": "req.theme", "text": "突出孤独、误解、坚持、自我认识和温柔的成长。"},
            {"id": "req.language", "text": "所有游戏正文使用中文。"},
        ],
    })
    write_json(path_for(run_root, "synopsis"), {
        "title": "丑小鸭",
        "events": [
            {"id": "event.hatch", "summary": "一只与众不同的小鸟在芦苇窝里最后破壳。"},
            {"id": "event.mocked", "summary": "鸭群、鸡和猫用外貌判断它，它被迫离开。"},
            {"id": "event.winter", "summary": "漫长冬天几乎夺走它的力气，但它没有放弃。"},
            {"id": "event.swans", "summary": "春天的湖面出现白天鹅，它第一次被美吸引而不是被恐惧驱赶。"},
            {"id": "event.reflection", "summary": "它在倒影中发现自己已经成为天鹅。"},
        ],
    })
    write_json(path_for(run_root, "branch_graph"), {
        "title": "丑小鸭",
        "start_node_id": "node.reed_nest",
        "nodes": [
            {"id": node_id, "title": title, "summary": summary, **({"is_terminal": True} if node_id == "node.true_reflection" else {})}
            for node_id, title, summary in NODES
        ],
        "edges": [
            {"id": edge_id, "from": source, "to": target, "condition_type": "unconditional", "label": label}
            for edge_id, source, target, label in EDGES
        ],
    })
    write_json(path_for(run_root, "game_ir"), {
        "metadata": {"schema_version": "0.1.0"},
        "title": "丑小鸭",
        "design_brief": {
            "logline": "一只被误认为丑陋的小鸟穿过嘲笑和寒冬，最终在湖面认出真正的自己。",
            "narrative_bible": {
                "themes": ["被误解的孤独", "坚持活下去", "自我认识", "温柔成长"],
                "cast": [
                    {"id": "char.duckling", "name": "小灰鸟"},
                    {"id": "char.mother_duck", "name": "母鸭"},
                    {"id": "char.hen", "name": "花母鸡"},
                    {"id": "char.cat", "name": "老猫"},
                    {"id": "char.swan", "name": "白天鹅"},
                    {"id": "char.narrator", "name": "旁白"},
                ],
            },
        },
        "global_state_variables": [
            {"id": "state.left_nest", "type": "boolean", "initial_value": False, "description": "小灰鸟是否离开芦苇窝。"},
            {"id": "state.survived_winter", "type": "boolean", "initial_value": False, "description": "是否撑过冰封冬天。"},
            {"id": "state.accepted_self", "type": "boolean", "initial_value": False, "description": "是否认出并接纳真正的自己。"},
        ],
        "progression_rules": [
            {"id": "rule.departure", "summary": "离开芦苇窝后进入农家院。"},
            {"id": "rule.winter", "summary": "经历农家院误解后进入冬天沼泽。"},
            {"id": "rule.ending", "summary": "春湖倒影揭示成长后的身份。"},
        ],
    })


def write_realization_plans(run_root: Path) -> None:
    outgoing = {source: [] for _, source, _, _ in EDGES}
    for edge_id, source, _, label in EDGES:
        outgoing.setdefault(source, []).append((edge_id, label))
    node_titles = {node_id: title for node_id, title, _ in NODES}
    assets_by_node = {
        "node.reed_nest": ["bg.reed_nest", "portrait.duckling.small", "portrait.mother_duck.concerned"],
        "node.farmyard": ["bg.farmyard", "portrait.duckling.small", "portrait.hen.proud", "portrait.cat.cool"],
        "node.winter_marsh": ["bg.winter_marsh", "portrait.duckling.tired"],
        "node.spring_lake": ["bg.spring_lake", "portrait.duckling.grown", "portrait.swan.gentle"],
        "node.true_reflection": ["bg.spring_lake", "portrait.duckling.grown", "portrait.swan.gentle"],
    }
    state_writes = {
        "edge.nest.farmyard": [{"state_variable_id": "state.left_nest", "operation": "set", "value": True}],
        "edge.winter.spring": [{"state_variable_id": "state.survived_winter", "operation": "set", "value": True}],
        "edge.spring.reflection": [{"state_variable_id": "state.accepted_self", "operation": "set", "value": True}],
    }
    plans = []
    for node_id, title, _ in NODES:
        plans.append({
            "source_node_id": node_id,
            "unit_id": f"vn.{node_id.removeprefix('node.')}",
            "realization_kind": "vn_yarn",
            "entry_binding": {"type": "yarn_node", "node_title": node_titles[node_id]},
            "exit_bindings": [
                {
                    "edge_id": edge_id,
                    "label": label,
                    "outcome_id": edge_id.removeprefix("edge."),
                    "state_writes": state_writes.get(edge_id, []),
                }
                for edge_id, label in outgoing.get(node_id, [])
            ],
            "required_assets": assets_by_node[node_id],
            "required_state_reads": [],
            "state_writes": [],
        })
    write_json(path_for(run_root, "realization_plans"), {"plans": plans})


def yarn(title: str, source_node_id: str, body: str) -> str:
    return dedent(f"""\
    title: {title}
    // source_node: {source_node_id}
    ---
    {body.strip()}
    ===
    """)


def write_vn_fragments(run_root: Path) -> None:
    fragments = {
        "node.reed_nest": yarn("芦苇窝的清晨", "node.reed_nest", """
        旁白: 芦苇轻轻摇晃，窝里的蛋一个接一个裂开。
        母鸭: 孩子们，别挤，太阳才刚照到水面。
        旁白: 最后一枚蛋特别大，壳也特别沉。等它终于裂开，探出的不是金黄的小脑袋，而是一只灰扑扑、笨拙又安静的小鸟。
        小灰鸟: 我也可以跟大家一起游吗？
        小鸭甲: 它怎么这么大？羽毛也乱糟糟的。
        母鸭: 它只是来得晚些。水会告诉我们它能不能游。
        旁白: 小灰鸟下水时溅起很大的水花，却没有沉下去。它游得慢，但每一下都很认真。
        [[离开芦苇窝|院子里的目光]]
        """),
        "node.farmyard": yarn("院子里的目光", "node.farmyard", """
        旁白: 农家院比池塘热闹，也比池塘吵闹。
        花母鸡: 你会下蛋吗？不会？那你在这里有什么用？
        老猫: 你会拱背、发出威风的声音吗？也不会？真可惜。
        小灰鸟: 我只是想找一个不被赶走的角落。
        旁白: 孩子们追着它跑，鹅群伸长脖子叫嚷，连风都像在推它离开。
        小灰鸟: 如果这里没有我的位置，我就去更远的地方。
        [[逃向荒野|冰封沼泽]]
        """),
        "node.winter_marsh": yarn("冰封沼泽", "node.winter_marsh", """
        旁白: 秋天从树梢落下，冬天从水面升起。沼泽结了冰，芦苇变成灰白色。
        小灰鸟: 只要还能呼吸，就再往前一步。
        旁白: 它躲过猎狗的脚步，避开冰面裂缝，在风里把头埋进翅膀。
        旁白: 有一天黄昏，它看见几只洁白的大鸟从天空掠过。那一刻，寒冷像被短暂忘记。
        小灰鸟: 世界上竟然有这样美的鸟。
        旁白: 它不知道自己为什么想哭，只知道还想等到春天。
        [[等到春天|春天的湖]]
        """),
        "node.spring_lake": yarn("春天的湖", "node.spring_lake", """
        旁白: 冰裂成碎银，柳枝垂到湖面。小灰鸟已经不再像从前那样矮小。
        白天鹅: 你为什么站得那么远？
        小灰鸟: 我怕靠近你们。大家都说我难看、笨拙、不该出现。
        白天鹅: 湖水不会重复别人的话。你可以自己看看。
        旁白: 小灰鸟颤抖着走向湖心，水面安静得像一面完整的镜子。
        [[靠近湖心|真正的倒影]]
        """),
        "node.true_reflection": yarn("真正的倒影", "node.true_reflection", """
        旁白: 倒影里没有那只被嘲笑的丑小鸭。
        旁白: 水中是一只年轻的白天鹅，羽毛明亮，脖颈修长，眼睛里仍保留着熬过冬天的温柔。
        小灰鸟: 原来我不是走错了生命，只是还没有长成自己。
        白天鹅: 欢迎回到湖上。
        旁白: 它张开翅膀。风托住它，像曾经所有寒冷都变成了向上的力量。
        旁白: 结局：真正的名字，不由嘲笑者决定。
        """),
    }
    fragments_root = run_root / "workspace" / "vn" / "fragments"
    for node_id, text in fragments.items():
        write_text(fragments_root / f"{node_id}.yarn", text)
        write_json(fragments_root / f"{node_id}.manifest.json", {
            "source_node_id": node_id,
            "realization_kind": "vn_yarn",
            "yarn_path": f"{node_id}.yarn",
        })


def write_asset_direction(run_root: Path) -> None:
    assets = [
        ("bg.reed_nest", "background", "清晨芦苇池塘，鸭窝、柔光、水草和刚裂开的蛋壳。"),
        ("bg.farmyard", "background", "乡村农家院，木栅栏、鸡窝、谷粒、温暖但拥挤的空间。"),
        ("bg.winter_marsh", "background", "冰封沼泽，灰蓝色天空、结冰水面、枯芦苇和远处脚印。"),
        ("bg.spring_lake", "background", "春天湖泊，柳枝、新绿、清澈倒影和远处白天鹅。"),
        ("portrait.duckling.small", "portrait", "灰色小鸟，瘦弱、局促、眼神好奇。"),
        ("portrait.duckling.tired", "portrait", "冬天里的小灰鸟，羽毛蓬乱但眼神坚韧。"),
        ("portrait.duckling.grown", "portrait", "年轻白天鹅，仍带一点羞怯但姿态舒展。"),
        ("portrait.mother_duck.concerned", "portrait", "母鸭，温柔担心，守在芦苇窝旁。"),
        ("portrait.hen.proud", "portrait", "花母鸡，昂头、挑剔、农家院角色。"),
        ("portrait.cat.cool", "portrait", "老猫，冷静懒散，坐在木门边。"),
        ("portrait.swan.gentle", "portrait", "白天鹅，平和、优雅、接纳的神情。"),
        ("ui.storybook_panel", "ui", "温柔童话绘本风对话面板。"),
    ]
    write_json(path_for(run_root, "asset_direction"), {
        "style_pack": {
            "summary": "温柔北欧童话绘本风，水彩质感，情绪克制，适合儿童文学但不幼稚。",
            "rendering": "soft watercolor storybook visual novel illustration",
            "lighting": "misty natural light, winter blue shadows, spring lake glow",
            "palette": ["#8aa6a3", "#d8c9a7", "#52616b", "#f0efe6", "#b88f6a"],
        },
        "asset_directions": [
            {"asset_id": asset_id, "kind": kind, "description": description}
            for asset_id, kind, description in assets
        ],
    })


def create(run_root: Path) -> None:
    ensure_run_layout(run_root)
    write_text(path_for(run_root, "prompt"), "《丑小鸭》中文剧情游戏：一只被误解的小鸟穿过嘲笑和寒冬，在春天湖面认出真正的自己。\n")
    write_design_layer(run_root)
    write_realization_plans(run_root)
    write_vn_fragments(run_root)
    write_asset_direction(run_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default="runs/ugly-duckling-vn")
    args = parser.parse_args()
    run_root = Path(args.run_root).resolve()
    create(run_root)
    print(str(run_root))


if __name__ == "__main__":
    main()
