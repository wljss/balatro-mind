# balatro-mind

这个项目的目标是做一个会玩《Balatro / 小丑牌》的 AI。当前阶段先解决几个基础问题：

1. 通过 BalatroBot mod 读取游戏状态。
2. 把游戏状态整理成后续 AI 决策容易使用的数据结构。
3. 封装 BalatroBot 动作 API，跑通一个最小自动 bot。

部分思路参考了 [balatro-agent](https://github.com/Arcadi4/balatro-agent)。

## 环境准备

请先安装 [uv](https://www.runoob.com/python3/uv-tutorial.html)。

```powershell
uv python install 3.14
uv venv --python 3.14
.venv\Scripts\activate
uv pip install balatrobot
```

如果已经创建过 `.venv`，以后只需要进入环境：

```powershell
.venv\Scripts\activate
```

退出虚拟环境：

```powershell
deactivate
```

## 启动 BalatroBot

BalatroBot 会启动游戏，并在本机开一个 JSON-RPC HTTP API。默认地址是：

```text
http://127.0.0.1:12346
```

启动方式：

```powershell
balatrobot serve
```

也可以使用 uvx：

```powershell
uvx balatrobot serve
```

如果端口被占用，可以换一个端口：

```powershell
balatrobot serve --port 8080
```

## 读取游戏状态

项目里的 `balatro_state_reader.py` 用来读取 BalatroBot 的 `gamestate` 接口。

读取压缩后的状态摘要：

```powershell
uv run python balatro_state_reader.py
```

读取完整 GameState：

```powershell
uv run python balatro_state_reader.py --raw
```

持续观察状态变化：

```powershell
uv run python balatro_state_reader.py --watch --interval 0.25
```

连接其他端口：

```powershell
uv run python balatro_state_reader.py --port 8080
```

也可以通过环境变量配置：

```powershell
$env:BALATROBOT_HOST = "127.0.0.1"
$env:BALATROBOT_PORT = "12346"
$env:BALATROBOT_TIMEOUT = "5"
uv run python balatro_state_reader.py
```

## 在代码中使用

读取一次完整游戏状态：

```python
from balatro_state_reader import BalatroBotClient

client = BalatroBotClient()
state = client.get_game_state()
```

读取更适合早期 AI 决策实验的压缩状态：

```python
from balatro_state_reader import BalatroBotClient, compact_game_state

client = BalatroBotClient()
state = client.get_game_state()
observation = compact_game_state(state)
```

持续轮询：

```python
from balatro_state_reader import BalatroBotClient

client = BalatroBotClient()

for state in client.iter_game_states(interval_seconds=0.25):
    print(state["state"])
```

## 当前状态读取内容

压缩状态里会保留这些常用信息：

- 当前游戏阶段：`state`
- 回合与底注：`round_num`、`ante_num`
- 金钱、牌组、难度、种子：`money`、`deck`、`stake`、`seed`
- 当前回合信息：`round`
- 当前盲注信息：`blind`
- 手牌、小丑牌、消耗牌、商店、补充包里的卡牌摘要：`hand`、`jokers`、`consumables`、`shop`、`pack`

完整字段以 BalatroBot 返回的 GameState 为准，相关离线文档在 `BalatroBot-html/` 目录。

更详细的返回字段说明见 [docs/balatro_state_reader_returns.md](docs/balatro_state_reader_returns.md)。

## 操作游戏动作

`balatro_action_client.py` 封装了 BalatroBot 的动作接口，例如：

```python
from balatro_action_client import BalatroActionClient

client = BalatroActionClient()
state = client.select()
state = client.play([0, 1, 2, 3, 4])
state = client.cash_out()
```

常用动作包括：

- `start()`：开始新 run
- `select()` / `skip()`：选择或跳过盲注
- `play(cards)` / `discard(cards)`：打出或弃掉手牌
- `cash_out()`：结算本轮
- `next_round()`：离开商店进入下一轮
- `buy(...)` / `sell(...)` / `reroll()`：商店相关动作
- `pack(...)` / `skip_pack()`：补充包相关动作

## 运行最小 bot

`simple_bot.py` 是当前的最小闭环 bot。它只按游戏阶段执行最朴素的合法动作，用来验证“读取状态 -> 执行动作 -> 再读取状态”的链路。

从当前状态接管：

```powershell
uv run python simple_bot.py
```

强制回到菜单并开始新 run：

```powershell
uv run python simple_bot.py --new-run
```

指定牌组、难度和种子：

```powershell
uv run python simple_bot.py --new-run --deck RED --stake WHITE --seed TEST123
```

常用调试参数：

```powershell
uv run python simple_bot.py --max-steps 100 --interval 0.2 --final-json
```

当前 bot 的策略非常简单：

- `MENU`：开始新 run
- `BLIND_SELECT`：直接选择当前盲注
- `SELECTING_HAND`：打出手牌最前面的 5 张
- `ROUND_EVAL`：结算奖励
- `SHOP`：直接进入下一轮
- `SMODS_BOOSTER_OPENED`：跳过补充包

后续开发路线见 [docs/development_plan.md](docs/development_plan.md)。

## 常见问题

如果提示无法连接 `127.0.0.1:12346`，先确认 BalatroBot 已启动：

```powershell
balatrobot serve
```

如果你使用了自定义端口，读取状态时也要传同一个端口：

```powershell
uv run python balatro_state_reader.py --port 8080
```

如果需要确认 BalatroBot 是否正常，可以调用：

```powershell
uvx balatrobot api health
uvx balatrobot api gamestate
```

## 后续开发约定

后续新增功能时，尽量同步补充两件事：

1. 在复杂或容易误解的代码旁写简短中文注释。
2. 在 README 中补充运行方式、输入输出、重要参数或新模块用途。
