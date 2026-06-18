# balatro_state_reader 返回字段说明

本文档说明 `balatro_state_reader.py` 会返回哪些字段，以及这些字段对应《Balatro / 小丑牌》游戏里的哪些信息。

## 两种返回层级

`balatro_state_reader.py` 里有两种常用返回：

| 调用方式 | 返回内容 | 用途 |
| --- | --- | --- |
| `BalatroBotClient().get_game_state()` | BalatroBot 原始 `GameState` | 字段最完整，适合调试、保存样本、研究 BalatroBot 返回结构 |
| `read_game_state()` | BalatroBot 原始 `GameState` | 读取一次状态的便捷函数 |
| `compact_game_state(state)` | 精简后的状态摘要 | 更适合早期 AI 决策实验，字段少、结构稳定 |
| `uv run python balatro_state_reader.py` | 默认打印 `compact_game_state()` | 人类观察或快速调试 |
| `uv run python balatro_state_reader.py --raw` | 打印完整 `GameState` | 查看 BalatroBot 原始返回 |

## 默认摘要输出

不加 `--raw` 时，脚本输出的是 `compact_game_state()` 的结果。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `state` | `str` | 当前游戏阶段，例如菜单、选盲注、出牌、商店等 |
| `round_num` | `int` | 当前局内第几轮 |
| `ante_num` | `int` | 当前 Ante，也就是底注层数 |
| `money` | `int` | 当前拥有的钱 |
| `deck` | `str` | 当前使用的牌组，例如 `RED`、`BLUE` |
| `stake` | `str` | 当前难度等级，例如 `WHITE` |
| `seed` | `str` | 当前 run 的随机种子 |
| `won` | `bool` | 当前 run 是否已经胜利 |
| `round` | `object` | 当前回合资源与分数信息，见 “Round 结构” |
| `blind` | `object` | 当前正在打、可选择或最近击败的盲注，见 “Blind 结构” |
| `hand` | `list[Card]` | 当前手牌区的卡牌摘要 |
| `jokers` | `list[Card]` | 当前拥有的小丑牌摘要 |
| `consumables` | `list[Card]` | 当前拥有的消耗牌摘要，例如塔罗牌、星球牌、幻灵牌 |
| `shop` | `list[Card]` | 当前商店中可购买的卡牌、补充包或商品摘要 |
| `pack` | `list[Card]` | 当前打开的补充包里可选择的卡牌摘要 |

### `blind` 的选择规则

`compact_game_state()` 会从完整 `blinds` 字段里选出一个最相关的盲注：

1. 优先返回 `status == "CURRENT"` 的盲注，表示正在进行。
2. 其次返回 `status == "SELECT"` 的盲注，表示当前可选择。
3. 最后返回 `status == "DEFEATED"` 的盲注，作为刚打完一轮时的兜底信息。

## 完整 GameState 顶层字段

`get_game_state()` 和 `read_game_state()` 返回 BalatroBot 的完整 `GameState`。字段会比默认摘要更多。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `state` | `str` | 当前游戏阶段 |
| `round_num` | `int` | 当前局内第几轮 |
| `ante_num` | `int` | 当前 Ante |
| `money` | `int` | 当前金钱 |
| `deck` | `str` | 当前牌组 |
| `stake` | `str` | 当前难度 |
| `seed` | `str` | 当前 run 的种子 |
| `won` | `bool` | 是否已经胜利 |
| `used_vouchers` | `object` 或 `list` | 已购买并生效的优惠券信息 |
| `hands` | `dict[str, PokerHand]` | 所有牌型的等级、筹码、倍率、已打出次数等信息 |
| `round` | `Round` | 当前回合剩余手数、弃牌数、已得分等信息 |
| `blinds` | `dict[str, Blind]` | 小盲、大盲、Boss 盲注的信息 |
| `jokers` | `Area` | 小丑牌区域 |
| `consumables` | `Area` | 消耗牌区域 |
| `cards` | `Area` | 牌库或完整卡牌区域，具体内容取决于当前状态 |
| `hand` | `Area` | 当前手牌区域 |
| `shop` | `Area` | 商店区域 |
| `vouchers` | `Area` | 商店中的优惠券区域 |
| `packs` | `Area` | 商店中的补充包区域 |
| `pack` | `Area` | 当前已打开补充包的可选牌区域 |

说明：BalatroBot 在不同游戏阶段返回的区域可能为空、缺失或内容不同，所以读取字段时要做好 `dict/list` 类型检查。

## 游戏阶段 `state`

| 值 | 游戏含义 | AI 通常要做什么 |
| --- | --- | --- |
| `MENU` | 主菜单 | 可以开始新 run，或等待人工操作 |
| `BLIND_SELECT` | 选择当前盲注，或跳过小盲/大盲 | 决定 `select` 还是 `skip` |
| `SELECTING_HAND` | 正在选择要打出或弃掉的手牌 | 决定 `play` 或 `discard` 的牌索引 |
| `ROUND_EVAL` | 一轮结束，等待结算奖励 | 调用 `cash_out` 进入商店 |
| `SHOP` | 商店阶段 | 买牌、卖牌、重掷、进入下一轮 |
| `SMODS_BOOSTER_OPENED` | 补充包已打开，正在选择奖励 | 选择补充包中的牌或跳过 |
| `GAME_OVER` | 游戏结束 | 记录结果，准备开始下一局 |

## Area 结构

`Area` 表示一个牌区，例如手牌、小丑牌、商店、补充包。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `count` | `int` | 当前区域里有多少张牌或商品 |
| `limit` | `int` | 该区域容量上限 |
| `highlighted_limit` | `int` | 可高亮或可选择的数量上限，例如最多选五张手牌 |
| `cards` | `list[Card]` | 该区域中的卡牌对象列表 |

常见 Area：

| Area 字段 | 游戏区域 |
| --- | --- |
| `hand` | 当前手牌 |
| `jokers` | 小丑牌栏 |
| `consumables` | 消耗牌栏 |
| `shop` | 商店商品 |
| `vouchers` | 商店优惠券 |
| `packs` | 商店补充包 |
| `pack` | 已打开补充包中的奖励选项 |

## Card 结构

`Card` 同时表示普通扑克牌、小丑牌、消耗牌、优惠券、补充包等对象。不同类型的卡牌可能缺少某些字段。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `id` | `int` | BalatroBot 给卡牌对象分配的 ID |
| `key` | `str` | 卡牌内部 key，例如 `H_A`、`j_joker`、`c_fool` |
| `set` | `str` | 卡牌所属集合，例如普通扑克牌、小丑牌、塔罗牌、星球牌 |
| `label` | `str` | 卡牌显示名称 |
| `value` | `object` | 普通扑克牌的花色、点数，或特殊卡牌的效果信息 |
| `modifier` | `object` | 卡牌上的额外修饰，如蜡封、版本、增强、永恒、租赁等 |
| `state` | `object` | 当前卡牌状态，如是否被 debuff、是否隐藏、是否高亮 |
| `cost` | `object` | 买入和卖出价格 |

### Card `value`

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `suit` | `str` | 花色。常见值：`H` 红桃、`D` 方片、`C` 梅花、`S` 黑桃 |
| `rank` | `str` | 点数。常见值：`A`、`K`、`Q`、`J`、`T`、`9` 到 `2` |
| `effect` | `str` | 特殊效果描述，主要出现在非普通扑克牌或增强牌上 |

### Card `modifier`

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `seal` | `str` 或 `null` | 蜡封效果 |
| `edition` | `str` 或 `null` | 版本效果，例如闪箔、镭射、多彩等 |
| `enhancement` | `str` 或 `null` | 增强效果，例如奖励牌、倍率牌、钢牌、玻璃牌等 |
| `eternal` | `bool` | 是否永恒，通常表示不能被卖出或摧毁 |
| `perishable` | `int` 或 `null` | 易腐剩余回合数，常见于小丑牌 |
| `rental` | `bool` | 是否租赁牌 |

### Card `state`

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `debuff` | `bool` | 是否被 Boss 盲注或其他效果禁用 |
| `hidden` | `bool` | 是否隐藏信息 |
| `highlight` | `bool` | 是否处于选中或高亮状态 |

### Card `cost`

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `buy` | `int` | 买入价格 |
| `sell` | `int` | 卖出价格 |

## Round 结构

`round` 描述当前回合内的资源和得分状态。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `hands_left` | `int` | 本轮剩余可出牌次数 |
| `hands_played` | `int` | 本轮已经出牌次数 |
| `discards_left` | `int` | 本轮剩余弃牌次数 |
| `discards_used` | `int` | 本轮已经弃牌次数 |
| `reroll_cost` | `int` | 当前商店重掷费用 |
| `chips` | `int` | 当前本轮已获得筹码分数 |

## Blind 结构

`Blind` 描述一个盲注，小盲、大盲和 Boss 盲注都使用这个结构。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `type` | `str` | 盲注类型：`SMALL`、`BIG`、`BOSS` |
| `status` | `str` | 当前盲注状态，见下表 |
| `name` | `str` | 盲注名称 |
| `effect` | `str` | 盲注特殊效果，Boss 盲注尤其重要 |
| `score` | `int` | 击败该盲注需要达到的目标分数 |
| `tag_name` | `str` | 跳过小盲或大盲时可获得的标签名 |
| `tag_effect` | `str` | 跳过后获得标签的效果说明 |

盲注类型：

| 值 | 游戏含义 |
| --- | --- |
| `SMALL` | 小盲，可以跳过拿标签 |
| `BIG` | 大盲，可以跳过拿标签 |
| `BOSS` | Boss 盲，不能跳过，并且通常有特殊限制 |

盲注状态：

| 值 | 游戏含义 |
| --- | --- |
| `SELECT` | 当前可选择 |
| `CURRENT` | 当前正在进行 |
| `UPCOMING` | 之后会出现 |
| `DEFEATED` | 已击败 |
| `SKIPPED` | 已跳过 |

## PokerHand 结构

`hands` 字段是一个字典，key 是牌型名称，例如 `Pair`、`Flush`、`Full House`。

| 字段 | 类型 | 游戏含义 |
| --- | --- | --- |
| `order` | `int` | 牌型排序 |
| `level` | `int` | 牌型等级，星球牌会提升它 |
| `chips` | `int` | 该牌型当前基础筹码 |
| `mult` | `int` | 该牌型当前基础倍率 |
| `played` | `int` | 本局累计打出该牌型的次数 |
| `played_this_round` | `int` | 当前回合打出该牌型的次数 |
| `example` | `list` | BalatroBot 给出的牌型示例，通常是 `[牌key, 是否计入牌型]` |

## 写 AI 时的读取建议

早期策略可以优先使用 `compact_game_state()`：

1. 用 `state` 判断当前阶段。
2. 在 `SELECTING_HAND` 阶段读取 `hand`，用列表索引决定 `play` 或 `discard`。
3. 在 `BLIND_SELECT` 阶段读取 `blind`，判断目标分数和跳过标签。
4. 在 `SHOP` 阶段读取 `money`、`shop`、`jokers`、`consumables`，决定买卖和重掷。
5. 需要更完整信息时，再读取原始 `GameState` 里的 `hands`、`blinds`、`vouchers`、`packs` 等字段。
