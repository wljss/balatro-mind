# balatro-mind 后续开发路线

本文档记录项目接下来怎么从“能读取游戏状态”推进到“能自动玩一局”，再逐步变成更聪明的 AI。

## 当前基础

已经有几块基础能力：

| 文件 | 作用 |
| --- | --- |
| `balatro_state_reader.py` | 读取 BalatroBot 的 `gamestate`，并提供压缩状态摘要 |
| `balatro_action_client.py` | 封装 BalatroBot 的动作 API，让程序可以操作游戏 |
| `card_utils.py` | 解析普通扑克牌的花色、点数和基础筹码 |
| `hand_evaluator.py` | 枚举出牌组合，识别基础牌型并估分 |
| `strategy_play.py` | SELECTING_HAND 阶段的基础出牌策略 |
| `simple_bot.py` | 最小闭环 bot，按当前游戏阶段执行动作 |

当前目标不是马上训练模型，而是先把“观察、行动、反馈”这条闭环打通。

## 阶段 1：稳定闭环

目标：让 bot 可以从菜单开始，自动走完整局。

已经覆盖的基础流程：

```text
MENU -> start
BLIND_SELECT -> select
SELECTING_HAND -> play 基础估分最高的牌
ROUND_EVAL -> cash_out
SHOP -> next_round
SMODS_BOOSTER_OPENED -> skip_pack
GAME_OVER -> 结束
```

下一步要确认：

1. `simple_bot.py` 是否能稳定跑到 `GAME_OVER`。
2. 各阶段返回的 GameState 是否和文档一致。
3. BalatroBot 有动画或过渡状态时，是否需要增加等待或刷新逻辑。
4. 出错时是否能记录当前状态和动作。
5. 动作请求超时时，是否能避免重复发送动作并恢复读取最新状态。

## 阶段 2：动作合法性与日志

目标：减少无效动作，并让每次决策都可以回放。

建议新增：

| 模块 | 作用 |
| --- | --- |
| `game_logger.py` | 记录每一步的状态、动作、结果 |
| `action_policy.py` | 定义“某个 state 下允许哪些动作” |
| `logs/runs/` | 保存 bot 运行样本 |

每一步建议记录：

```text
step
state
ante_num
round_num
money
hand
jokers
action
action_params
next_state
error
```

这会为后续调试和训练数据收集打地基。

## 阶段 3：手牌评估器

目标：让 AI 不再“打前 5 张”，而是能挑出更合理的牌。

第一版已经新增：

| 模块 | 作用 |
| --- | --- |
| `hand_evaluator.py` | 根据当前手牌枚举可打组合，识别基础牌型 |
| `card_utils.py` | 解析 `H_A`、`S_T` 等 card key，转换花色和点数 |
| `strategy_play.py` | SELECTING_HAND 阶段的基础出牌策略 |

第一版支持普通扑克牌基础牌型：

```text
High Card
Pair
Two Pair
Three of a Kind
Straight
Flush
Full House
Four of a Kind
Straight Flush
```

它会用 BalatroBot 返回的 `hands` 字段读取当前牌型的 chips/mult，并加上计分牌的基础筹码做粗略估分。

当前仍未覆盖：

1. 小丑牌完整效果。
2. 增强牌、蜡封、版本的完整计分。
3. 弃牌找牌策略。
4. Boss 盲注的全部特殊限制。

## 阶段 4：商店策略

目标：让 AI 在商店阶段做一些基本判断。

第一版规则可以很简单：

1. 有空小丑位时，优先购买买得起的小丑牌。
2. 钱少时不重掷。
3. 补充包先跳过，等后续实现 pack 策略。
4. 小丑栏满时暂时不卖牌，避免破坏已有组合。

后续再扩展：

| 策略点 | 说明 |
| --- | --- |
| 小丑牌估值 | 根据 `label`、`key`、`cost` 粗略判断价值 |
| 消耗牌使用 | 判断塔罗牌、星球牌什么时候用 |
| 补充包选择 | 根据 pack 内容选择奖励 |
| 优惠券购买 | 判断经济类或容量类 voucher 是否值得买 |

## 阶段 5：启发式 baseline

目标：形成一个比随机和“前 5 张”更强的规则 bot。

可以拆成几个策略函数：

```text
decide_blind(state)
decide_hand_action(state)
decide_shop_action(state)
decide_pack_action(state)
```

每个函数输入完整或压缩状态，输出一个动作：

```python
{
    "method": "play",
    "params": {"cards": [0, 2, 4]}
}
```

这样后续无论是规则、搜索还是模型，都可以复用同一套动作执行层。

## 阶段 6：数据与模型

等 baseline 能稳定跑大量局之后，再考虑机器学习。

可选路线：

| 路线 | 说明 |
| --- | --- |
| 监督学习 | 用人类或规则 bot 的记录训练策略模型 |
| 强化学习 | 让 bot 自己跑局，用胜负、Ante、分数做奖励 |
| 搜索/规划 | 在单个阶段枚举动作，选择短期收益最高的动作 |

不建议太早直接上深度强化学习。Balatro 的规则和组合很多，先用规则系统把动作空间缩小，会更稳。

## 近期建议任务

推荐下一批任务顺序：

1. 跑 `simple_bot.py`，观察基础出牌策略能否稳定过第一轮。
2. 增加运行日志，把每一步状态和动作保存下来。
3. 增加简单弃牌策略：分数明显不够时弃掉低价值孤张。
4. 把增强牌、蜡封、版本逐步纳入估分。
5. 再开始做商店策略。

## 开发约定

后续新增模块时继续保持：

1. 复杂逻辑旁边写简短中文注释。
2. README 记录如何运行。
3. `docs/` 记录字段含义、策略假设和阶段性计划。
4. 先写能验证的小闭环，再追求策略强度。
