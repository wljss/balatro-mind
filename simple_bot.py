"""一个最小闭环 Balatro bot。

这个 bot 的目标不是完整模拟高手策略，而是验证整条链路：

1. 从 BalatroBot 读取当前 GameState。
2. 根据 `state` 选择一个合法动作。
3. 调用 BalatroBot 动作 API。
4. 重复直到 GAME_OVER 或达到步数上限。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass

from balatro_action_client import BalatroActionClient
from balatro_state_reader import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    GameState,
    area_cards,
    compact_game_state,
)
from strategy_play import choose_play_action


@dataclass(slots=True)
class SimpleBotConfig:
    """最小 bot 的运行配置。"""

    deck: str = "RED"
    stake: str = "WHITE"
    seed: str | None = None
    max_steps: int = 3000
    play_count: int = 5
    interval_seconds: float = 0.1
    new_run: bool = False
    print_final_json: bool = False


@dataclass(slots=True)
class SimpleBot:
    """按游戏阶段行动的 baseline bot。"""

    client: BalatroActionClient
    config: SimpleBotConfig

    def run(self) -> GameState:
        """运行 bot，直到游戏结束或达到步数上限。"""

        state = self._initial_state()

        for step in range(1, self.config.max_steps + 1):
            print(f"[{step:03d}] {self._describe_state(state)}")

            if state.get("state") == "GAME_OVER":
                self._print_game_over(state)
                return state

            state = self.step(state)
            time.sleep(self.config.interval_seconds)

        raise RuntimeError(f"达到 max_steps={self.config.max_steps}，bot 停止运行。")

    def step(self, state: GameState) -> GameState:
        """根据当前游戏阶段执行一个最朴素的合法动作。"""

        state_name = state.get("state")

        if state_name == "MENU":
            print("      action=start")
            return self.client.start(
                deck=self.config.deck,
                stake=self.config.stake,
                seed=self.config.seed,
            )

        if state_name == "BLIND_SELECT":
            print("      action=select")
            return self.client.select()

        if state_name == "SELECTING_HAND":
            decision = choose_play_action(state, max_cards=self.config.play_count)
            if not decision.cards:
                print("      action=refresh_state (no hand cards)")
                return self.client.get_game_state()
            print(f"      action=play {decision.log_text()}")
            return self.client.play(decision.cards)

        if state_name == "ROUND_EVAL":
            print("      action=cash_out")
            return self.client.cash_out()

        if state_name == "SHOP":
            print("      action=next_round")
            return self.client.next_round()

        if state_name == "SMODS_BOOSTER_OPENED":
            print("      action=skip_pack")
            return self.client.skip_pack()

        # 未知或过渡状态先刷新，避免在错误阶段乱发动作。
        print(f"      action=refresh_state (unknown state {state_name!r})")
        return self.client.get_game_state()

    def _initial_state(self) -> GameState:
        """决定从当前 run 继续，还是强制回菜单开新 run。"""

        if self.config.new_run:
            print("准备开始新 run：menu -> start")
            self.client.menu()
            return self.client.start(
                deck=self.config.deck,
                stake=self.config.stake,
                seed=self.config.seed,
            )

        state = self.client.get_game_state()
        if state.get("state") == "MENU":
            print("当前在 MENU，自动 start")
            return self.client.start(
                deck=self.config.deck,
                stake=self.config.stake,
                seed=self.config.seed,
            )

        return state

    def _describe_state(self, state: GameState) -> str:
        """生成一行适合命令行观察的状态摘要。"""

        round_info = state.get("round")
        chips = round_info.get("chips") if isinstance(round_info, dict) else None
        hand_size = len(area_cards(state, "hand"))
        return (
            f"state={state.get('state')} "
            f"ante={state.get('ante_num')} "
            f"round={state.get('round_num')} "
            f"money={state.get('money')} "
            f"chips={chips} "
            f"hand={hand_size}"
        )

    def _print_game_over(self, state: GameState) -> None:
        """打印最终结果。"""

        result = "胜利" if state.get("won") else "失败"
        print(
            f"游戏结束：{result}，"
            f"ante={state.get('ante_num')}，round={state.get('round_num')}"
        )
        if self.config.print_final_json:
            print(json.dumps(compact_game_state(state), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行一个最小闭环 Balatro bot。")
    parser.add_argument("--host", default=os.getenv("BALATROBOT_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("BALATROBOT_PORT", str(DEFAULT_PORT))),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("BALATROBOT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))),
    )
    parser.add_argument("--deck", default="RED", help="新 run 使用的牌组。")
    parser.add_argument("--stake", default="WHITE", help="新 run 使用的难度。")
    parser.add_argument("--seed", default=None, help="可选随机种子。")
    parser.add_argument(
        "--new-run",
        action="store_true",
        help="先回到 MENU，再开始新 run。未启用时会优先接管当前状态。",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=300,
        help="最多执行多少个动作步，防止无限循环。",
    )
    parser.add_argument(
        "--play-count",
        type=int,
        default=5,
        help="SELECTING_HAND 阶段最多允许策略打出几张手牌，最大有效值为 5。",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="动作之间的等待秒数。",
    )
    parser.add_argument(
        "--final-json",
        action="store_true",
        help="GAME_OVER 后额外打印压缩状态 JSON。",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    client = BalatroActionClient(host=args.host, port=args.port, timeout=args.timeout)
    config = SimpleBotConfig(
        deck=args.deck,
        stake=args.stake,
        seed=args.seed,
        max_steps=args.max_steps,
        play_count=args.play_count,
        interval_seconds=args.interval,
        new_run=args.new_run,
        print_final_json=args.final_json,
    )
    SimpleBot(client=client, config=config).run()


if __name__ == "__main__":
    main()
