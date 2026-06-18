"""基础手牌评估器。

第一版目标：在不考虑小丑牌、复杂增强和完整计分动画的前提下，
从当前手牌中挑出一个“看起来分数最高”的出牌组合。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from card_utils import ParsedCard, parse_hand_cards


JsonObject = dict[str, Any]

DEFAULT_HAND_VALUES: dict[str, tuple[int, int]] = {
    "High Card": (5, 1),
    "Pair": (10, 2),
    "Two Pair": (20, 2),
    "Three of a Kind": (30, 3),
    "Straight": (30, 4),
    "Flush": (35, 4),
    "Full House": (40, 4),
    "Four of a Kind": (60, 7),
    "Straight Flush": (100, 8),
    "Five of a Kind": (120, 12),
    "Flush House": (140, 14),
    "Flush Five": (160, 16),
}

HAND_STRENGTH = {
    "High Card": 1,
    "Pair": 2,
    "Two Pair": 3,
    "Three of a Kind": 4,
    "Straight": 5,
    "Flush": 6,
    "Full House": 7,
    "Four of a Kind": 8,
    "Straight Flush": 9,
    "Five of a Kind": 10,
    "Flush House": 11,
    "Flush Five": 12,
}


@dataclass(frozen=True, slots=True)
class EvaluatedHand:
    """一次候选出牌的评估结果。"""

    hand_type: str
    cards: list[int]
    scoring_cards: list[int]
    card_keys: list[str]
    base_chips: int
    base_mult: int
    card_chips: int
    estimated_score: int

    def as_dict(self) -> JsonObject:
        """转成适合日志和调试输出的字典。"""

        return {
            "hand_type": self.hand_type,
            "cards": self.cards,
            "scoring_cards": self.scoring_cards,
            "card_keys": self.card_keys,
            "base_chips": self.base_chips,
            "base_mult": self.base_mult,
            "card_chips": self.card_chips,
            "estimated_score": self.estimated_score,
        }


def best_play_from_state(state: JsonObject) -> EvaluatedHand | None:
    """从完整 GameState 中选择当前最推荐打出的牌。"""

    hand_area = state.get("hand")
    if not isinstance(hand_area, dict):
        return None

    cards = hand_area.get("cards")
    if not isinstance(cards, list):
        return None

    parsed_cards = parse_hand_cards([card for card in cards if isinstance(card, dict)])
    hands_info = state.get("hands") if isinstance(state.get("hands"), dict) else {}
    return best_play(parsed_cards, hands_info=hands_info)


def best_play(
    cards: list[ParsedCard],
    *,
    hands_info: JsonObject | None = None,
    max_cards: int = 5,
) -> EvaluatedHand | None:
    """枚举所有 1 到 5 张的组合，返回估分最高的出牌。"""

    if not cards:
        return None

    candidates: list[EvaluatedHand] = []
    max_size = min(max_cards, len(cards))
    for size in range(1, max_size + 1):
        for combo in combinations(cards, size):
            candidates.append(evaluate_cards(list(combo), hands_info=hands_info))

    return max(candidates, key=_candidate_sort_key)


def evaluate_cards(
    cards: list[ParsedCard],
    *,
    hands_info: JsonObject | None = None,
) -> EvaluatedHand:
    """评估一个候选出牌组合。"""

    if not cards:
        raise ValueError("evaluate_cards 至少需要一张牌。")

    hand_type, scoring_cards = _detect_hand(cards)
    base_chips, base_mult = _hand_value(hand_type, hands_info)
    card_chips = sum(card.chips for card in scoring_cards if not card.debuffed)
    estimated_score = (base_chips + card_chips) * base_mult

    return EvaluatedHand(
        hand_type=hand_type,
        cards=[card.index for card in cards],
        scoring_cards=[card.index for card in scoring_cards],
        card_keys=[card.key for card in cards],
        base_chips=base_chips,
        base_mult=base_mult,
        card_chips=card_chips,
        estimated_score=estimated_score,
    )


def _detect_hand(cards: list[ParsedCard]) -> tuple[str, list[ParsedCard]]:
    """识别一个候选组合的最佳牌型，并返回真正计分的牌。"""

    by_rank = _cards_by_rank(cards) #将点数相同的牌分到一组里
    rank_counts = sorted((len(group) for group in by_rank.values()), reverse=True)
    is_flush = len(cards) == 5 and len({card.suit for card in cards}) == 1 #同花
    is_straight = len(cards) == 5 and _is_straight(cards) #顺子

    if len(cards) == 5:
        if rank_counts == [5] and is_flush:
            return "Flush Five", cards
        if rank_counts == [3, 2] and is_flush:
            return "Flush House", cards
        if rank_counts == [5]:
            return "Five of a Kind", cards
        if is_straight and is_flush:
            return "Straight Flush", cards

    four = _groups_of_size(by_rank, 4)
    if four:
        return "Four of a Kind", four[0]

    if len(cards) == 5 and rank_counts == [3, 2]:
        return "Full House", cards

    if is_flush:
        return "Flush", cards

    if is_straight:
        return "Straight", cards

    three = _groups_of_size(by_rank, 3)
    if three:
        return "Three of a Kind", three[0]

    pairs = _groups_of_size(by_rank, 2)
    if len(pairs) >= 2:
        return "Two Pair", pairs[0] + pairs[1]

    if pairs:
        return "Pair", pairs[0]

    return "High Card", [_highest_card(cards)]


def _hand_value(
    hand_type: str,
    hands_info: JsonObject | None,
) -> tuple[int, int]:
    """读取 BalatroBot 当前牌型等级对应的 chips/mult，缺失时用基础值。"""

    if isinstance(hands_info, dict):
        info = hands_info.get(hand_type)
        if isinstance(info, dict):
            chips = info.get("chips")
            mult = info.get("mult")
            if isinstance(chips, int) and isinstance(mult, int):
                return chips, mult

    return DEFAULT_HAND_VALUES[hand_type]


def _cards_by_rank(cards: list[ParsedCard]) -> dict[str, list[ParsedCard]]:
    """点数相同的牌分到一组里"""
    groups: dict[str, list[ParsedCard]] = {}
    for card in cards:
        groups.setdefault(card.rank, []).append(card)
    return groups


def _groups_of_size(
    groups: dict[str, list[ParsedCard]],
    size: int,
) -> list[list[ParsedCard]]:
    """按组内最高牌大小排序，返回指定数量的同点数组。"""

    matching = [group for group in groups.values() if len(group) == size]
    return sorted(matching, key=lambda group: _highest_card(group).rank_value, reverse=True)


def _highest_card(cards: list[ParsedCard]) -> ParsedCard:
    return max(cards, key=lambda card: card.rank_value)


def _is_straight(cards: list[ParsedCard]) -> bool:
    ranks = sorted({card.rank_value for card in cards})
    if len(ranks) != 5:
        return False

    # A2345 在 Balatro 中也算顺子，这里把 A 当作 1 做兜底判断。
    if ranks == [2, 3, 4, 5, 14]:
        return True

    return ranks[-1] - ranks[0] == 4


def _candidate_sort_key(candidate: EvaluatedHand) -> tuple[int, int, int, int, int]:
    """候选出牌排序：先看估分，再看牌型强度，最后少打无关牌。"""

    return (
        candidate.estimated_score,
        HAND_STRENGTH[candidate.hand_type],
        candidate.card_chips,
        -len(candidate.cards),
        len(candidate.scoring_cards),
    )
