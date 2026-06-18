"""SELECTING_HAND 阶段的出牌策略。

第一版策略只做一件事：枚举当前手牌所有 1 到 5 张组合，
选择基础估分最高的一组牌打出。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from balatro_state_reader import area_cards
from card_utils import parse_hand_cards
from hand_evaluator import EvaluatedHand, best_play, best_play_from_state


JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlayDecision:
    """一次 SELECTING_HAND 阶段的出牌决策。"""

    cards: list[int]
    reason: str
    evaluation: EvaluatedHand | None

    def log_text(self) -> str:
        """生成一行适合命令行输出的决策说明。"""

        if self.evaluation is None:
            return f"cards={self.cards} reason={self.reason}"

        return (
            f"cards={self.cards} "
            f"hand_type={self.evaluation.hand_type!r} "
            f"estimated_score={self.evaluation.estimated_score} "
            f"reason={self.reason}"
        )


def choose_play_action(
    state: JsonObject,
    *,
    max_cards: int = 5,
) -> PlayDecision:
    """选择当前最推荐打出的手牌索引。"""

    if max_cards <= 0:
        raise ValueError("max_cards 必须大于 0。")
    max_cards = min(max_cards, 5)

    evaluation = best_play_from_state(state)
    if evaluation is not None:
        # 如果调用方限制了最多出牌数量，则重新评估这个限制下的最佳组合。
        if max_cards != 5:
            hand_cards = area_cards(state, "hand")
            evaluation = best_play(
                parse_hand_cards(hand_cards),
                hands_info=state.get("hands") if isinstance(state.get("hands"), dict) else {},
                max_cards=max_cards,
            )

        if evaluation is not None:
            return PlayDecision(
                cards=evaluation.cards,
                reason="选择当前基础估分最高的牌型",
                evaluation=evaluation,
            )

    fallback = _fallback_cards(state, max_cards=max_cards)
    return PlayDecision(
        cards=fallback,
        reason="无法解析手牌，回退为打出前几张牌",
        evaluation=None,
    )


def _fallback_cards(state: JsonObject, *, max_cards: int) -> list[int]:
    """解析失败时的保底策略，避免 bot 卡死在 SELECTING_HAND。"""

    hand_size = len(area_cards(state, "hand"))
    return list(range(min(max_cards, hand_size)))
