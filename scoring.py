"""Pure hierarchical (gated-ladder) scoring logic. No Streamlit imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from data_loader import SubDomain

IsCheckedFn = Callable[[int, int], bool]  # (level_score, bullet_idx) -> bool


@dataclass(frozen=True)
class ScoreResult:
    achieved_level: int
    partial_credit: float
    final_score: float
    checked_count: int
    total_count: int
    level_ratios: dict[int, float]

    @property
    def completion_pct(self) -> float:
        return round((self.checked_count / self.total_count * 100), 1) if self.total_count else 0.0


def compute_sub_domain_score(sub_domain: SubDomain, is_checked: IsCheckedFn) -> ScoreResult:
    """
    Levels combine sequentially, not additively:
      1. Walk levels 1 -> 4 in order.
      2. A level is achieved only if ratio == 1.0 AND every lower level is achieved.
      3. The first non-fully-achieved level contributes partial credit toward the
         next rung; levels beyond that gate do not affect the score.
    """
    achieved_level = 0
    partial_credit = 0.0
    level_ratios: dict[int, float] = {}
    checked_total = 0
    items_total = 0

    for level in sorted(sub_domain.levels, key=lambda lvl: lvl.score):
        if level.score == 0:
            continue

        total = len(level.criteria)
        checked = sum(1 for idx in range(total) if is_checked(level.score, idx))
        items_total += total
        checked_total += checked

        ratio = (checked / total) if total else 0.0
        level_ratios[level.score] = ratio

        if achieved_level == level.score - 1:
            if ratio >= 1.0:
                achieved_level = level.score
            else:
                partial_credit = ratio

    final_score = min(4.0, round(achieved_level + partial_credit, 2))

    return ScoreResult(
        achieved_level=achieved_level,
        partial_credit=partial_credit,
        final_score=final_score,
        checked_count=checked_total,
        total_count=items_total,
        level_ratios=level_ratios,
    )
