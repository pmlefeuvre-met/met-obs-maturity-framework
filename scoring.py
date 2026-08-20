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


def compute_sub_domain_score(sub_domain: SubDomain, declared_level: int, is_checked: IsCheckedFn) -> ScoreResult:
    """
    The assessor directly declares which level's description currently matches
    reality (declared_level, 0-4) as a single judgement call -- not something
    derived by ticking every box at every lower level. The checklist is only
    used as evidence of progress toward the *next* level: how many of its
    criteria are already satisfied becomes partial credit toward advancing.
    """
    declared_level = max(0, min(4, declared_level))
    next_score = declared_level + 1 if declared_level < 4 else None

    partial_credit = 0.0
    level_ratios: dict[int, float] = {}
    checked_total = 0
    items_total = 0

    if next_score is not None:
        next_level = next((lvl for lvl in sub_domain.levels if lvl.score == next_score), None)
        if next_level is not None:
            total = len(next_level.criteria)
            checked = sum(1 for idx in range(total) if is_checked(next_score, idx))
            items_total = total
            checked_total = checked
            ratio = (checked / total) if total else 0.0
            level_ratios[next_score] = ratio
            partial_credit = ratio

    final_score = min(4.0, round(declared_level + partial_credit, 2))

    return ScoreResult(
        achieved_level=declared_level,
        partial_credit=partial_credit,
        final_score=final_score,
        checked_count=checked_total,
        total_count=items_total,
        level_ratios=level_ratios,
    )
