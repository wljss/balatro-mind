"""卡牌解析工具。

BalatroBot 返回的 Card 里，普通扑克牌通常同时有：

- `key`: 例如 `H_A`、`S_T`
- `value.suit`: 花色
- `value.rank`: 点数

这里把这些字段整理成后续牌型评估更容易使用的结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]

SUIT_NAMES = {
    "H": "Hearts",
    "D": "Diamonds",
    "C": "Clubs",
    "S": "Spades",
}

RANK_VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}

RANK_CHIPS = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}


@dataclass(frozen=True, slots=True)
class ParsedCard:
    """后续牌型评估使用的普通扑克牌信息。"""

    index: int
    key: str
    suit: str
    rank: str
    rank_value: int
    chips: int
    label: str
    debuffed: bool


def parse_playing_card(card: JsonObject, index: int) -> ParsedCard | None:
    """把 BalatroBot 的 Card 解析成普通扑克牌；非扑克牌返回 None。"""

    suit = _card_suit(card)
    rank = _card_rank(card)
    if suit not in SUIT_NAMES or rank not in RANK_VALUES:
        return None

    key = card.get("key")
    label = card.get("label")
    return ParsedCard(
        index=index,
        key=str(key) if key is not None else f"{suit}_{rank}",
        suit=suit,
        rank=rank,
        rank_value=RANK_VALUES[rank],
        chips=RANK_CHIPS[rank],
        label=str(label) if label is not None else f"{rank} of {SUIT_NAMES[suit]}",
        debuffed=is_debuffed(card),
    )


def parse_hand_cards(cards: list[JsonObject]) -> list[ParsedCard]:
    """解析一个手牌列表，自动忽略不能识别为普通扑克牌的对象。"""

    parsed: list[ParsedCard] = []
    for index, card in enumerate(cards):
        parsed_card = parse_playing_card(card, index)
        if parsed_card is not None:
            parsed.append(parsed_card)
    return parsed


def is_debuffed(card: JsonObject) -> bool:
    """判断卡牌是否被当前 Boss 盲注或其他效果禁用。"""

    state = card.get("state")
    if not isinstance(state, dict):
        return False
    return bool(state.get("debuff"))


def _card_suit(card: JsonObject) -> str | None:
    """优先从 value.suit 读花色，没有时从 key 兜底解析。"""

    value = card.get("value")
    if isinstance(value, dict):
        suit = value.get("suit")
        if isinstance(suit, str):
            return suit

    key = card.get("key")
    if isinstance(key, str) and len(key) >= 3 and key[1] == "_":
        return key[0]
    return None


def _card_rank(card: JsonObject) -> str | None:
    """优先从 value.rank 读点数，没有时从 key 兜底解析。"""

    value = card.get("value")
    if isinstance(value, dict):
        rank = value.get("rank")
        if isinstance(rank, str):
            return rank

    key = card.get("key")
    if isinstance(key, str) and len(key) >= 3 and key[1] == "_":
        return key[2:]
    return None
