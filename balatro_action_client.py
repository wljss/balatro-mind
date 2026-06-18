"""封装 BalatroBot 动作 API，让 AI 可以操作《小丑牌》。

`balatro_state_reader.py` 负责“看见状态”，本文件负责“执行动作”。
这些方法本身不做策略判断，只把 BalatroBot JSON-RPC 方法包装成
更清晰的 Python 调用。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from balatro_state_reader import (
    BalatroBotClient,
    BalatroBotProtocolError,
    GameState,
    JsonObject,
)


def _clean_params(params: JsonObject) -> JsonObject:
    """去掉 None 参数，避免给 BalatroBot 传入无意义字段。"""

    return {key: value for key, value in params.items() if value is not None}


def _require_exactly_one(params: JsonObject, names: Sequence[str]) -> None:
    """校验一组互斥参数里必须且只能提供一个。"""

    provided = [name for name in names if params.get(name) is not None]
    if len(provided) != 1:
        joined = ", ".join(names)
        raise ValueError(f"必须且只能提供一个参数：{joined}")


def _indices(values: Sequence[int]) -> list[int]:
    """把索引序列转成普通 list，方便 JSON 序列化。"""

    return [int(value) for value in values]


@dataclass(slots=True)
class BalatroActionClient(BalatroBotClient):
    """BalatroBot 动作客户端。

    继承 `BalatroBotClient` 的连接配置和 `rpc()` 方法，并为常用动作
    提供带参数名的包装方法。
    """

    def _game_state_action(
        self,
        method: str,
        params: JsonObject | None = None,
    ) -> GameState:
        """调用一个预期返回 GameState 的动作。"""

        result = self.rpc(method, params)
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"{method} returned {result!r}")
        return result

    def menu(self) -> GameState:
        """返回主菜单。"""

        return self._game_state_action("menu")

    def start(
        self,
        *,
        deck: str = "RED",
        stake: str = "WHITE",
        seed: str | None = None,
    ) -> GameState:
        """开始一局新游戏。"""

        params = _clean_params({"deck": deck, "stake": stake, "seed": seed})
        return self._game_state_action("start", params)

    def select(self) -> GameState:
        """选择当前盲注并开始本轮。"""

        return self._game_state_action("select")

    def skip(self) -> GameState:
        """跳过当前小盲或大盲，Boss 盲不能跳过。"""

        return self._game_state_action("skip")

    def buy(
        self,
        *,
        card: int | None = None,
        voucher: int | None = None,
        pack: int | None = None,
    ) -> GameState:
        """从商店购买一张卡、优惠券或补充包，索引从 0 开始。"""

        params = _clean_params({"card": card, "voucher": voucher, "pack": pack})
        _require_exactly_one(params, ("card", "voucher", "pack"))
        return self._game_state_action("buy", params)

    def pack(
        self,
        *,
        card: int | None = None,
        targets: Sequence[int] | None = None,
        skip: bool = False,
    ) -> GameState:
        """处理已打开的补充包：选择一张牌，或跳过补充包。"""

        params: JsonObject = {}
        if card is not None:
            params["card"] = int(card)
        if targets is not None:
            params["targets"] = _indices(targets)
        if skip:
            params["skip"] = True

        # targets 只是 card 的附加参数，真正互斥的是 card 和 skip。
        _require_exactly_one(params, ("card", "skip"))
        return self._game_state_action("pack", params)

    def skip_pack(self) -> GameState:
        """跳过当前打开的补充包。"""

        return self.pack(skip=True)

    def sell(
        self,
        *,
        joker: int | None = None,
        consumable: int | None = None,
    ) -> GameState:
        """卖出小丑牌或消耗牌，索引从 0 开始。"""

        params = _clean_params({"joker": joker, "consumable": consumable})
        _require_exactly_one(params, ("joker", "consumable"))
        return self._game_state_action("sell", params)

    def reroll(self) -> GameState:
        """重掷商店商品。"""

        return self._game_state_action("reroll")

    def cash_out(self) -> GameState:
        """结算当前回合奖励并进入商店。"""

        return self._game_state_action("cash_out")

    def next_round(self) -> GameState:
        """离开商店，进入下一轮盲注选择。"""

        return self._game_state_action("next_round")

    def play(self, cards: Sequence[int]) -> GameState:
        """打出手牌中的若干张牌，索引从 0 开始。"""

        return self._game_state_action("play", {"cards": _indices(cards)})

    def discard(self, cards: Sequence[int]) -> GameState:
        """弃掉手牌中的若干张牌，索引从 0 开始。"""

        return self._game_state_action("discard", {"cards": _indices(cards)})

    def rearrange(
        self,
        *,
        hand: Sequence[int] | None = None,
        jokers: Sequence[int] | None = None,
        consumables: Sequence[int] | None = None,
    ) -> GameState:
        """重新排列手牌、小丑牌或消耗牌。"""

        params: JsonObject = _clean_params(
            {
                "hand": _indices(hand) if hand is not None else None,
                "jokers": _indices(jokers) if jokers is not None else None,
                "consumables": _indices(consumables)
                if consumables is not None
                else None,
            }
        )
        _require_exactly_one(params, ("hand", "jokers", "consumables"))
        return self._game_state_action("rearrange", params)

    def use(
        self,
        *,
        consumable: int,
        cards: Sequence[int] | None = None,
    ) -> GameState:
        """使用一张消耗牌，可选指定目标手牌索引。"""

        params = _clean_params(
            {
                "consumable": int(consumable),
                "cards": _indices(cards) if cards is not None else None,
            }
        )
        return self._game_state_action("use", params)

    def add(
        self,
        *,
        key: str,
        seal: str | None = None,
        edition: str | None = None,
        enhancement: str | None = None,
        eternal: bool | None = None,
        perishable: int | None = None,
        rental: bool | None = None,
    ) -> GameState:
        """调试用：向游戏里添加一张牌或一个物品。"""

        params = _clean_params(
            {
                "key": key,
                "seal": seal,
                "edition": edition,
                "enhancement": enhancement,
                "eternal": eternal,
                "perishable": perishable,
                "rental": rental,
            }
        )
        return self._game_state_action("add", params)

    def set_values(
        self,
        **values: Any,
    ) -> GameState:
        """调试用：设置金钱、筹码、手数等游戏数值。"""

        params = _clean_params(dict(values))
        if not params:
            raise ValueError("set_values 至少需要一个要设置的字段。")
        return self._game_state_action("set", params)

    def save(self, path: str) -> JsonObject:
        """保存当前 run。"""

        result = self.rpc("save", {"path": path})
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"save returned {result!r}")
        return result

    def load(self, path: str) -> JsonObject:
        """读取保存的 run。"""

        result = self.rpc("load", {"path": path})
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"load returned {result!r}")
        return result

    def screenshot(self, path: str) -> JsonObject:
        """保存游戏截图到指定路径。"""

        result = self.rpc("screenshot", {"path": path})
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"screenshot returned {result!r}")
        return result
