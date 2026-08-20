"""Pure hierarchical (gated-ladder) scoring logic. No Streamlit imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from data_loader import FocusArea, SubDomain, chain_items

IsCheckedFn = Callable[[int, int], bool]  # (level_score, bullet_idx) -> bool
StateGet = Callable[[str, Any], Any]  # dict.get / st.session_state.get

# Short display labels for chain_stage, used only where space is tight
# (sidebar dropdown, chart legend). Full names remain the source of truth
# in the data and are still shown in headers/captions.
SHORT_STAGE_LABELS = {
    "Physical and Metrological Foundation": "Foundation",
    "Network Infrastructure and Field Maintenance": "Field Maintenance",
    "Real-Time Data Ingestion and Processing": "Data Ingestion",
    "Automated Data Quality Checkpoints": "Automated QC",
    "Manual Data Quality Control and Expert Review": "Expert Review",
    "Siting, Exposure, and Environmental Classification": "Siting & Exposure",
    "Metadata Lifecycle and System Synchronization": "Metadata",
    "Network Design and Strategic Lifecycle Planning": "Network Design",
}


def short_stage(stage: str) -> str:
    return SHORT_STAGE_LABELS.get(stage, stage)


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


@dataclass(frozen=True)
class ElementOutcome:
    element_id: str
    declared_level: int   # what the assessor picked
    effective_level: int  # after gate capping (== declared_level if no gate applies)
    gated: bool            # True if a gate capped this element below its declared level


@dataclass(frozen=True)
class ElementBasedScoreResult:
    final_score: float
    outcomes: dict[str, ElementOutcome] = field(default_factory=dict)


def compute_sub_domain_element_score(
    sub_domain: SubDomain, declared_levels: dict[str, int]
) -> ElementBasedScoreResult:
    """
    Some sub-domains split into independent theme tracks (`elements`) rather
    than a single ladder: non-conflicting parts can sit at different levels
    at once (e.g. Traceability at Level 3 while Records Management is still
    at Level 1). Each element's level is declared directly by the assessor.
    A `Gate` caps an element's effective level when the source content makes
    it depend on another element (e.g. "adjusted... while maintaining
    traceability" implies interval optimization needs traceability in place
    first). The sub-domain's overall score is the weight-adjusted mean of its
    elements' effective levels.
    """
    outcomes: dict[str, ElementOutcome] = {}
    for element in sub_domain.elements:
        applicable = element.applicable_levels
        declared = declared_levels.get(element.id, applicable[0] if applicable else 0)
        declared = min(applicable, key=lambda lvl: abs(lvl - declared)) if applicable else declared

        effective = declared
        gated = False
        for gate in element.gates:
            if effective >= gate.applies_at_level and declared_levels.get(gate.requires, 0) < gate.min_level:
                effective = gate.applies_at_level - 1
                gated = True

        outcomes[element.id] = ElementOutcome(
            element_id=element.id,
            declared_level=declared,
            effective_level=effective,
            gated=gated,
        )

    total_weight = sum(el.weight for el in sub_domain.elements)
    weighted_sum = sum(outcomes[el.id].effective_level * el.weight for el in sub_domain.elements)
    final_score = round(weighted_sum / total_weight, 2) if total_weight else 0.0

    return ElementBasedScoreResult(final_score=final_score, outcomes=outcomes)


def score_all(model: list[FocusArea], institute: str, get: StateGet) -> list[dict]:
    """
    Compute the full chain scores_summary table for one institute from any
    flat key/value store (`st.session_state.get` while live, or a loaded
    `SavedAssessment.answers.get` for a saved one). Scores are never persisted
    to disk -- they're cheap to recompute from `answers` alone, so both the
    live app and the read-only Saved Assessments page share this single
    implementation instead of duplicating the key formulas.
    """
    rows = []
    for fa, sd in chain_items(model):
        if sd.elements:
            declared_levels = {
                el.id: get(f"{institute}::{fa.id}::{sd.name}::{el.id}::declared_level", el.applicable_levels[0])
                for el in sd.elements
            }
            final_score = compute_sub_domain_element_score(sd, declared_levels).final_score
            completion_pct = 0.0
        else:
            declared = int(get(f"{institute}::{fa.id}::{sd.name}::declared_level", 0))
            is_checked = lambda score, idx, fa=fa, sd=sd: bool(
                get(f"{institute}::{fa.id}::{sd.name}::L{score}::{idx}", False)
            )
            sd_result = compute_sub_domain_score(sd, declared, is_checked)
            final_score = sd_result.final_score
            completion_pct = sd_result.completion_pct
        rows.append({
            "Sequence": sd.sequence,
            "Chain Stage": sd.chain_stage,
            "Stage (short)": short_stage(sd.chain_stage),
            "Focus Area": fa.id,
            "Sub-Domain": sd.name,
            "Achieved Score": final_score,
            "Target Score": 3.0,  # Best Practice Target
            "Progress to Next %": f"{completion_pct}%",
        })
    return rows
