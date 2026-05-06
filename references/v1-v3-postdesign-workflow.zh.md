# V1 / V3 + Post-Design 工作流程说明

这个系统的目标是把一个故事想法或一段原文，变成一个可玩的分支叙事游戏。

整条流程可以分成三层：

```text
Design Layer
设计剧情结构、分支、状态和结局
        |
        v
Post-Design
把设计变成玩家可见、可点击、可玩的内容
        |
        v
Runtime / Export
组装成 Web VN 或 Unity scaffold
```

Design layer 有两个平行模块：V1 和 V3。它们前面的设计方式不同，但最后都会产出同一套公共接口：

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

`branch_graph.json` 是剧情图：有哪些节点、从哪里走到哪里、每条边代表什么选择或跳转。

`game_ir.json` 是语义层：有哪些状态变量、状态如何改变、条件如何判断、结局如何解析。

Post-design 不关心这些公共接口来自 V1 还是 V3。它只负责把公共图和状态语义实现成玩家能看到的内容。

## Controller 和 Subagents

Controller 是总调度。它负责：

- 初始化 run 目录。
- 准备输入和 source material。
- 为每个 subagent 准备 clean-context packet。
- 保存 subagent 返回的 typed payload。
- 校验 artifact。
- 合并 shard。
- 编译 design layer。
- 调度 post-design、build 和 export。

Subagent 是具体作者。每个 subagent 只读自己的 role card 和 controller 给的 packet，不自己浏览整个 run，也不决定 artifact 是否通过。

换句话说：controller 管流程和文件，subagent 管当前这一步的创作。

## V1：直接设计模块

V1 是较直接的 design layer，适合从一个 prompt 或简单设定开始生成游戏结构。

V1 的流程是：

```text
PromptAnalyst
        |
        v
LinearSynopsisDesigner
        |
        v
BranchGraphDesigner
        |
        v
BaseGameIRDesigner
        |
        v
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

### 1. PromptAnalyst

`PromptAnalyst` 理解用户需求，输出：

```text
workspace/design_layer/user_requirements.json
```

它提取目标体验、题材、语气、限制、必须满足的需求等。

### 2. LinearSynopsisDesigner

`LinearSynopsisDesigner` 先写一条基础线性故事，输出：

```text
workspace/design_layer/chapter_linear_synopsis.json
```

这一步不是最终游戏图，而是给后续分支设计提供基础剧情骨架。

### 3. BranchGraphDesigner

`BranchGraphDesigner` 把线性故事改成分支图，输出：

```text
workspace/design_layer/branch_graph.json
```

它负责设计：

- 节点。
- 边。
- 起点。
- 终点。
- 玩家选择。
- 边上的 `conditions` 和 `effects`。

V1 里，`branch_graph.edges[*].conditions` 和 `branch_graph.edges[*].effects` 就是公共 runtime transition interface。后续 runtime 会直接使用这些条件和效果。

### 4. BaseGameIRDesigner

`BaseGameIRDesigner` 设计状态和语义规则，输出：

```text
workspace/design_layer/game_ir.json
```

它负责声明状态变量，并把重要边的语义同步到 `game_ir.event_rules`。

V1 的特点是短、直接、快。它不做多层原文抽象，而是直接生成公共剧情图和状态语义。

## V3：层级化改编模块

V3 适合改编小说、长文本或复杂剧情。它不是直接从 prompt 写一个图，而是先理解原文结构，再做层级化设计。

V3 有两个方向相反的流程：

```text
story extraction:   从细到粗
graph/state design: 从粗到细
```

先从原文里提取多层 story units，再从全局层向细节层设计状态和剧情图。

## V3 第一阶段：准备原文

如果是 source-adaptation，controller 先准备：

```text
inputs/source_material/full_text.txt
inputs/source_material/source_index.json
inputs/source_material/chunks/*.txt
inputs/source_material/extraction_report.json
```

这些文件说明原文在哪里、分成哪些 chunk、每个 chunk 的顺序和来源是什么。

后续 subagent 不直接拿完整 run。controller 会把当前任务需要的 source chunk 或 story slice 放进 packet。

## V3 第二阶段：StoryLevelExtractor

`StoryLevelExtractor` 从细到粗提取 story levels。

典型输出是：

```text
workspace/design_layer_v3/story_levels/level_01/linear_story.json
workspace/design_layer_v3/story_levels/level_02/linear_story.json
workspace/design_layer_v3/story_levels/level_03/linear_story.json
workspace/design_layer_v3/facts/*
```

`level_01` 是最细层，通常接近章节、场景或短剧情片段。

更高层是对低层的总结和凝练，比如 arc、act、全局故事。高层不是低层的简单拼接。

每个 story unit 应该说明：

- 这一段发生了什么。
- 主角做了什么具体动作。
- 这个动作造成了什么影响。
- 涉及哪些人物、地点、物件、问题。
- 这一段来自哪些原文 source refs。

对于长文本，`level_01` 可以分 shard 并行。但所有 shard 加起来必须覆盖完整 `source_index.json`，不能只抽代表章节。

最粗层 story level 必须由一个全局 worker 处理所有直接子 story units。这样后续 policy 和全局 graph/state design 才有一致的全局 story view。

`StoryLevelExtractor` 也会捕获 facts，例如人物、地点、事件、关系、世界规则和主题。controller 最后汇总成：

```text
workspace/design_layer_v3/facts/canonical_fact_graph.json
```

## V3 第三阶段：AdaptationPolicyDesigner

`AdaptationPolicyDesigner` 根据最粗层 story view 和 canonical facts，输出：

```text
workspace/design_layer_v3/adaptation/global_policy.json
```

它只设计全局改编方向，不设计完整剧情图。

它负责说明：

- 目标风格和语气。
- route families。
- 哪些 canon 内容必须保留。
- 哪些地方允许发明、变体、失败、延迟、重访或重排。
- 哪些主题、人物关系和结局方向需要强化。

具体节点怎么分支、状态变量怎么设计、玩家选择怎么改变剧情，交给 `LevelStateGraphDesigner`。

## V3 第四阶段：LevelStateGraphDesigner

`LevelStateGraphDesigner` 从粗到细设计 graph/state。

每一层输出：

```text
workspace/design_layer_v3/design_levels/level_<NN>/state_model.json
workspace/design_layer_v3/design_levels/level_<NN>/story_graph.json
workspace/design_layer_v3/design_levels/level_<NN>/contracts.json
workspace/design_layer_v3/design_levels/level_<NN>/parent_state_settlements.json
```

最粗层必须只有一个全局 designer。它负责全局一致性：

- 全局剧情空间。
- 全局 route-family state。
- 多结局 resolution state。
- 跨层 route memory。
- 给子层的 contracts。

更细层可以按 parent packet 并行设计。

这一层最重要的原则是 state-first。设计顺序是：

1. 先确定本层需要维护哪些状态变量。
2. 再说明不同状态值会怎样改变剧情体验。
3. 再设计玩家可以做出的外在行为选择。
4. 再设计 graph nodes 和 edges。
5. 最后写 contracts 和 parent settlements。

玩家选择必须是可见行为，例如：

- 走向某处。
- 说出某句话。
- 检查某个物件。
- 使用某个道具。
- 等待。
- 拒绝。
- 帮助。
- 打断。

心理倾向可以作为状态记录，但不应该直接成为玩家看到的 choice label。

## V3 如何产生网状剧情

V3 不要求一个 story unit 严格对应一个 graph node。

当前规则是：

- 每个 story unit 至少要被一个同层 graph node 引用。
- 每个 graph node 必须引用一个或多个同层 story units。
- 不能发明完全没有 source anchor 的 graph node。
- 可以把一个 story unit 扩展成多个状态依赖的 graph nodes。

也就是说，designer 可以发明新的剧情片段，但这些片段必须从原文功能和状态变化中派生出来。

设计时可以问：

```text
这段剧情为什么会发生？
如果前面状态不同，它会怎样改变？
它会失败吗？
会延迟吗？
会被跳过吗？
会在之后以另一种形式回来吗？
会导致不同结局压力吗？
```

一个原文事件可以被扩展成：

- canon version。
- failure version。
- delayed version。
- revisit version。
- consequence version。
- bridge version。

这就是 V3 的网状剧情核心：不是简单把原文线性搬进游戏，而是把原文事件变成状态驱动的事件空间。

## V3 的状态、边和结局

`story_graph.json` 里的 edge 承载分支语义：

```text
conditions: 什么时候能走这条边
effects:    走这条边后写入什么状态
```

一个分支要有意义，必须至少做到一件事：

- 改变后续节点顺序。
- 改变后续节点可访问性。
- 让玩家 skip、delay 或 revisit 某些内容。
- 写入后续节点会读取的状态。
- 改变 parent_state_settlement。
- 改变 terminal variant 或 ending resolution。

如果两个选择只是换句话说，最后去同一个节点，后续也不读状态，那就是假分支。

## V3 Compile

V3 私有设计完成后，运行：

```bash
python3 scripts/run_pipeline.py compile-design --run-root <run> --design-layer v3
```

编译后得到和 V1 一样的公共接口：

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
```

这里有一个重要边界：

- runtime-visible `branch_graph.json` 只来自最细 enabled design level，通常是 `level_01`。
- 更高层的 V3 `story_graph` 是设计上下文，不直接变成玩家可见节点或选择。
- 更高层状态和 parent settlements 可以进入 `game_ir.json`，影响后续语义。

所以 post-design 看到的是统一后的公共 runtime graph，而不是 V3 的所有私有层级文件。

## Post-Design：共同落地流程

V1 和 V3 到这里就汇合了。

Post-design 只依赖：

```text
workspace/design_layer/branch_graph.json
workspace/design_layer/game_ir.json
workspace/state/shared-state.schema.json
```

它的任务是把设计实现成玩家能看到和操作的内容。

## Post-Design 第一步：Validate + Project Shared State

先运行：

```bash
python3 scripts/validate_artifacts.py --run-root <run> --write-projections
```

这一步会检查：

- branch graph 是否连通、节点和边是否合法。
- game_ir 是否声明了状态变量。
- edge conditions/effects 是否引用了已声明状态。
- graph 和 game_ir 是否互相引用了不存在的 id。

同时生成：

```text
workspace/state/shared-state.schema.json
```

后续 writer 只能引用这里或 `game_ir.json` 里已经声明的状态。

## Post-Design 第二步：NodeRealizationPlanner

`NodeRealizationPlanner` 为每个 branch graph node 生成一个实现计划：

```text
workspace/realization/node-realization-plans.json
```

它不写正文。它负责把抽象设计翻译成“这个节点应该怎么实现”。

它要决定：

- 每个节点是 `vn_yarn`、`cutscene_yarn`，还是 battle / puzzle / interaction / exploration。
- 每个 outgoing edge 对应哪个 outcome。
- 玩家选择在场景的哪里出现。
- 每个选择对应什么外在行为。
- 每个 outcome 读写哪些状态。
- 多入边节点如何写 entry variants。
- terminal node 如何根据状态生成 terminal variants。

如果 design graph 说有分支，但后续没有任何状态读取或可见 payoff，`NodeRealizationPlanner` 应该暴露这个问题，而不是把它包装成有效分支。

## Post-Design 第三步：NodeSceneWriter

`NodeSceneWriter` 根据 realization plan 写玩家可见的 VN fragment：

```text
workspace/vn/fragments/<source_node_id>.yarn
workspace/vn/fragments/<source_node_id>.manifest.json
```

它负责：

- 正文。
- 对白。
- 独白。
- 场景节奏。
- 玩家看到的 choice labels。
- 结局文本。
- Yarn commands。
- fragment manifest。

它不能：

- 改 branch graph 拓扑。
- 发明新状态变量。
- 删除 planned outcomes。
- 把多出口节点写成一段线性 prose。
- 直接使用 designer fallback label 当最终 choice label。

对于多出口节点，SceneWriter 必须写出玩家可见的 `->` choice label，并用 `<<complete_activity outcome="...">>` 连接到 plan 中的 outcome。

对于 V3 run，场景写完后应运行：

```bash
python3 scripts/run_pipeline.py check-v3-scene-choice-labels --run-root <run>
```

这个检查确认玩家看到的选择文本来自 SceneWriter 写的 Yarn，而不是 designer 或 planner 的 fallback。

## Post-Design 第四步：Gameplay Writers

如果某些节点不是 VN 场景，而是玩法单元，controller 会分发给对应 writer：

```text
BattleRealizationWriter
InteractionRealizationWriter
PuzzleRealizationWriter
ExplorationRealizationWriter
```

它们输出 declarative gameplay artifacts：

```text
workspace/realization/battles/*.battle.json
workspace/realization/interactions/*.interaction.json
workspace/realization/puzzles/*.puzzle.json
workspace/realization/explorations/*.exploration.json
```

这些 writer 不写 runtime code。runtime 支持什么 adapter，由 controller 和 exporter 决定。

## Post-Design 第五步：AssetDirector

`AssetDirector` 在文本和玩法基本确定后运行，输出：

```text
workspace/asset-direction.json
```

它整理视觉和音频方向，例如：

- 背景。
- 角色立绘。
- 表情。
- BGM。
- SFX。
- voice。

它不重新设计场景，也不覆盖 SceneWriter 已经安排好的 staging。它只是把已有 asset intents 整合成更一致的资产方向。

## Build / Export

最终运行：

```bash
python3 scripts/run_pipeline.py build --run-root <run>
```

build 会做这些事：

1. 再次 validate design artifacts。
2. 编译 gameplay manifest。
3. 组装 Yarn fragments。
4. 生成 StoryIR 并校验跳转和 outcome。
5. 规划和生成 assets。
6. 导出 Web VN。
7. 可选导出 Unity scaffold。
8. 写 final report。

主要输出：

```text
build/web-vn/
build/unity-project/
reports/final-report.json
```

## 玩家选择如何影响剧情

玩家看到的是 SceneWriter 写出的 choice label。

玩家点击选择后，Yarn 会触发：

```text
<<complete_activity outcome="...">>
```

runtime 用这个 outcome 找到：

```text
realization plan exit_binding
        |
        v
branch_graph edge
        |
        v
edge conditions/effects
```

然后：

- `conditions` 决定选项是否可用。
- `effects` 写入状态变量。
- 后续节点、边、entry variant、terminal variant 再读取这些状态。

所以真实影响链路是：

```text
玩家选择
-> outcome
-> branch_graph edge
-> effects 写状态
-> 后续内容读状态
-> 后续剧情或结局变化
```

如果一个选择没有写状态，或者写了状态但后面没人读，它通常就是假分支。

## Source of Truth

| 内容 | 权威来源 |
| --- | --- |
| V1 用户需求 | `workspace/design_layer/user_requirements.json` |
| V1 线性故事骨架 | `workspace/design_layer/chapter_linear_synopsis.json` |
| V3 story anchors | `workspace/design_layer_v3/story_levels/*/linear_story.json` |
| V3 facts | `workspace/design_layer_v3/facts/canonical_fact_graph.json` |
| V3 改编方向 | `workspace/design_layer_v3/adaptation/global_policy.json` |
| V3 私有层级设计 | `workspace/design_layer_v3/design_levels/*` |
| runtime 剧情图 | `workspace/design_layer/branch_graph.json` |
| runtime 状态语义 | `workspace/design_layer/game_ir.json` |
| shared state schema | `workspace/state/shared-state.schema.json` |
| 节点实现计划 | `workspace/realization/node-realization-plans.json` |
| 玩家可见 VN 内容 | `workspace/vn/fragments/*.yarn` |
| VN fragment metadata | `workspace/vn/fragments/*.manifest.json` |
| 资产方向 | `workspace/asset-direction.json` |
| 可玩导出 | `build/web-vn/` |

## 如何判断分支是否真实

检查一个 run 是否有真实网状剧情，可以问：

1. 两个玩家是否可能看到不同节点顺序？
2. 玩家是否可以 skip、delay 或 revisit 某些内容？
3. 早期选择是否写入后续会读取的状态？
4. 收束节点是否保留 route memory？
5. 结局是否由之前状态自动解析，而不是最后手动选择？
6. SceneWriter 是否实现了每个 planned outcome？
7. 玩家看到的 choice label 是否是目标语言，并且描述外在行为？

如果答案大多是否定的，问题通常出在：

- designer 没有设计真实 state-gated graph。
- planner 没有把分支变成可见 realization plan。
- SceneWriter 把分支写成了线性文本。
- edge effects 写入的状态没有被后续读取。

## 最短心智模型

可以把系统理解成：

```text
V1 / V3 design layer:
决定游戏有哪些剧情可能、有哪些状态、玩家选择会造成什么后果。

Post-design:
把这些设计写成玩家能看到的场景、对白、选择和玩法。

Runtime / export:
让玩家点击选择，并根据状态推进到不同后续内容和结局。
```

