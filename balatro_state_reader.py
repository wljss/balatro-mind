"""从 BalatroBot JSON-RPC API 读取《小丑牌》当前游戏状态。

先启动 BalatroBot，例如：

    uvx balatrobot serve

再读取当前游戏状态：

    uv run python balatro_state_reader.py
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request


JsonObject = dict[str, Any]
GameState = JsonObject

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12346
DEFAULT_TIMEOUT_SECONDS = 20.0


class BalatroBotError(RuntimeError):
    """BalatroBot 客户端错误的基类。"""


class BalatroBotConnectionError(BalatroBotError):
    """无法连接 BalatroBot HTTP 服务时抛出。"""


class BalatroBotTimeoutError(BalatroBotConnectionError):
    """BalatroBot 请求超时时抛出，动作可能已经被游戏接收。"""


class BalatroBotProtocolError(BalatroBotError):
    """BalatroBot 返回的 JSON-RPC 响应格式不符合预期时抛出。"""


class BalatroBotRPCError(BalatroBotError):
    """BalatroBot 返回 JSON-RPC error 对象时抛出。"""

    def __init__(self, code: Any, message: str, data: Any | None = None) -> None:
        super().__init__(f"BalatroBot RPC error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


@dataclass(slots=True)
class BalatroBotClient:
    """访问本机 BalatroBot 服务的小型 JSON-RPC 客户端。"""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "BalatroBotClient":
        """从 BALATROBOT_HOST、BALATROBOT_PORT、BALATROBOT_TIMEOUT 创建客户端。"""

        host = os.getenv("BALATROBOT_HOST", DEFAULT_HOST)
        port = int(os.getenv("BALATROBOT_PORT", str(DEFAULT_PORT)))
        timeout = float(os.getenv("BALATROBOT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
        return cls(host=host, port=port, timeout=timeout)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def rpc(self, method: str, params: JsonObject | None = None) -> Any:
        """调用 BalatroBot JSON-RPC 方法，并返回 result 字段。"""

        # BalatroBot 文档要求使用 JSON-RPC 2.0 格式提交 HTTP POST 请求。
        payload: JsonObject = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1,
        }
        if params is not None:
            payload["params"] = params

        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                raw_response = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BalatroBotConnectionError(
                f"BalatroBot returned HTTP {exc.code}: {details}"
            ) from exc
        except TimeoutError as exc:
            raise BalatroBotTimeoutError(
                f"BalatroBot request to {self.url} timed out after "
                f"{self.timeout:g} seconds."
            ) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise BalatroBotTimeoutError(
                    f"BalatroBot request to {self.url} timed out after "
                    f"{self.timeout:g} seconds."
                ) from exc
            raise BalatroBotConnectionError(
                f"Could not connect to BalatroBot at {self.url}. "
                "Start it with `uvx balatrobot serve` or set BALATROBOT_PORT."
            ) from exc
        except OSError as exc:
            raise BalatroBotConnectionError(
                f"Could not connect to BalatroBot at {self.url}. "
                "Start it with `uvx balatrobot serve` or set BALATROBOT_PORT."
            ) from exc

        try:
            response_data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise BalatroBotProtocolError(
                f"BalatroBot returned non-JSON data: {raw_response!r}"
            ) from exc

        if not isinstance(response_data, dict):
            raise BalatroBotProtocolError(
                f"BalatroBot returned a non-object response: {response_data!r}"
            )

        if "error" in response_data:
            rpc_error = response_data["error"]
            if isinstance(rpc_error, dict):
                raise BalatroBotRPCError(
                    rpc_error.get("code"),
                    str(rpc_error.get("message", "unknown error")),
                    rpc_error.get("data"),
                )
            raise BalatroBotRPCError(None, str(rpc_error))

        if "result" not in response_data:
            raise BalatroBotProtocolError(
                f"BalatroBot response did not contain a result: {response_data!r}"
            )

        return response_data["result"]

    def health(self) -> JsonObject:
        """返回 BalatroBot 健康检查结果，通常是 {'status': 'ok'}。"""

        result = self.rpc("health")
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"health returned {result!r}")
        return result

    def get_game_state(self) -> GameState:
        """读取并返回完整的当前游戏状态。"""

        result = self.rpc("gamestate")
        if not isinstance(result, dict):
            raise BalatroBotProtocolError(f"gamestate returned {result!r}")
        return result

    def wait_until_ready(
        self,
        *,
        attempts: int = 30,
        interval_seconds: float = 1.0,
    ) -> None:
        """轮询 health，直到 BalatroBot 可访问或重试次数耗尽。"""

        last_error: BalatroBotError | None = None
        for _ in range(attempts):
            try:
                self.health()
                return
            except BalatroBotError as exc:
                last_error = exc
                time.sleep(interval_seconds)

        if last_error is not None:
            raise last_error
        raise BalatroBotConnectionError("BalatroBot did not become ready.")

    def iter_game_states(
        self,
        *,
        interval_seconds: float = 0.25,
    ):
        """持续轮询并产出游戏状态，用于观察游戏状态变化。"""

        while True:
            yield self.get_game_state()
            time.sleep(interval_seconds)


def card_summary(card: JsonObject) -> JsonObject:
    """提取 AI 决策早期实验中最常用的卡牌字段。"""

    value = card.get("value")
    modifier = card.get("modifier")
    state = card.get("state")
    cost = card.get("cost")

    return {
        "id": card.get("id"),
        "key": card.get("key"),
        "set": card.get("set"),
        "label": card.get("label"),
        "value": value if isinstance(value, dict) else {},
        "modifier": modifier if isinstance(modifier, dict) else {},
        "state": state if isinstance(state, dict) else {},
        "cost": cost if isinstance(cost, dict) else {},
    }


def area_cards(state: GameState, area_name: str) -> list[JsonObject]:
    """读取某个牌区的 cards，例如 hand、jokers、shop。"""

    # BalatroBot 的牌区通常是 {"count": ..., "limit": ..., "cards": [...]}。
    area = state.get(area_name)
    if isinstance(area, dict):
        cards = area.get("cards", [])
        if isinstance(cards, list):
            return [card for card in cards if isinstance(card, dict)]
    return []


def current_blind(state: GameState) -> JsonObject:
    """返回当前正在打或可选择的盲注；没有时返回空字典。"""

    blinds = state.get("blinds")
    if not isinstance(blinds, dict):
        return {}

    # 优先取 CURRENT，其次取 BLIND_SELECT 阶段可点的 SELECT。
    # 如果一轮刚结束，可能只剩 DEFEATED，可作为最近一次盲注的兜底信息。
    for expected_status in ("CURRENT", "SELECT", "DEFEATED"):
        for blind in blinds.values():
            if not isinstance(blind, dict):
                continue
            if blind.get("status") == expected_status:
                return blind

    return {}


def compact_game_state(state: GameState) -> JsonObject:
    """构造一个更小的状态快照，方便后续 AI 策略直接消费。"""

    round_info = state.get("round")
    return {
        "state": state.get("state"),
        "round_num": state.get("round_num"),
        "ante_num": state.get("ante_num"),
        "money": state.get("money"),
        "deck": state.get("deck"),
        "stake": state.get("stake"),
        "seed": state.get("seed"),
        "won": state.get("won"),
        "round": round_info if isinstance(round_info, dict) else {},
        "blind": current_blind(state),
        "hand": [card_summary(card) for card in area_cards(state, "hand")],
        "jokers": [card_summary(card) for card in area_cards(state, "jokers")],
        "consumables": [card_summary(card) for card in area_cards(state, "consumables")],
        "shop": [card_summary(card) for card in area_cards(state, "shop")],
        "pack": [card_summary(card) for card in area_cards(state, "pack")],
    }


def read_game_state(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> GameState:
    """便捷函数：只需要读取一次完整游戏状态时直接调用。"""

    return BalatroBotClient(host=host, port=port, timeout=timeout).get_game_state()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 BalatroBot 读取游戏状态。")
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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="打印完整 GameState，而不是压缩后的摘要。",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="持续轮询并打印游戏状态。",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="启用 --watch 时的轮询间隔，单位为秒。",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    client = BalatroBotClient(host=args.host, port=args.port, timeout=args.timeout)

    if args.watch:
        for state in client.iter_game_states(interval_seconds=args.interval):
            output = state if args.raw else compact_game_state(state)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            print()
        return

    state = client.get_game_state()
    output = state if args.raw else compact_game_state(state)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
