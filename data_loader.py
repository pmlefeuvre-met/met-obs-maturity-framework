"""YAML -> unified maturity model parsing. No scoring or UI logic here."""

from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st
import yaml

FA_FILES: dict[str, str] = {
    "FA1": "fa1.yaml",
    "FA2": "fa2.yaml",
    "FA3": "fa3.yaml",
}


@dataclass(frozen=True)
class Criterion:
    text: str


@dataclass(frozen=True)
class Level:
    score: int
    label: str
    criteria: tuple[Criterion, ...]
    standards_ref: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gate:
    """Cross-element prerequisite: this element cannot be declared at
    `applies_at_level` unless `requires` (another element's id in the same
    sub-domain) has been declared at least at `min_level`."""
    requires: str
    min_level: int
    applies_at_level: int


@dataclass(frozen=True)
class Element:
    """One independently-progressing theme/track within a sub-domain (e.g.
    'Traceability' vs 'Calibration Interval Management'). Elements can sit at
    different levels simultaneously -- unlike the single sub-domain ladder,
    non-conflicting parts of a sub-domain can advance independently. Gates
    express real prerequisites between elements where the source content
    justifies one ('foreign keys' between tracks)."""
    id: str
    title: str
    weight: float
    level_text: dict[int, str]  # only keys for levels where this element has distinct content
    gates: tuple[Gate, ...] = ()

    @property
    def applicable_levels(self) -> tuple[int, ...]:
        return tuple(sorted(self.level_text.keys()))


@dataclass(frozen=True)
class SubDomain:
    name: str
    sequence: int  # position (1..12) in the end-to-end Observation Chain
    chain_stage: str  # narrative grouping shared across Focus Areas
    levels: tuple[Level, ...]  # sorted by score, 0..4 -- labels/standards_ref
    elements: tuple[Element, ...] = ()  # optional theme split; empty = single-ladder sub-domain


@dataclass(frozen=True)
class FocusArea:
    id: str
    title: str
    description: str
    sub_domains: tuple[SubDomain, ...]


@st.cache_data
def load_model() -> list[FocusArea]:
    focus_areas: list[FocusArea] = []
    for fa_id, file_path in FA_FILES.items():
        if not os.path.exists(file_path):
            continue
        with open(file_path) as f:
            doc = yaml.safe_load(f)

        sub_domains = []
        for sd in doc["sub_domains"]:
            levels = tuple(
                Level(
                    score=lvl["score"],
                    label=lvl["label"],
                    criteria=tuple(Criterion(text=c) for c in lvl.get("criteria", [])),
                    standards_ref=tuple(lvl.get("standards_ref", [])),
                )
                for lvl in sorted(sd["levels"], key=lambda lvl: lvl["score"])
            )
            elements = tuple(
                Element(
                    id=el["id"],
                    title=el["title"],
                    weight=el.get("weight", 1.0),
                    level_text={int(k): v for k, v in el["level_text"].items()},
                    gates=tuple(
                        Gate(
                            requires=g["requires"],
                            min_level=g["min_level"],
                            applies_at_level=g["applies_at_level"],
                        )
                        for g in el.get("gates", [])
                    ),
                )
                for el in sd.get("elements", [])
            )
            sub_domains.append(
                SubDomain(
                    name=sd["name"],
                    sequence=sd["sequence"],
                    chain_stage=sd["chain_stage"],
                    levels=levels,
                    elements=elements,
                )
            )

        focus_areas.append(
            FocusArea(
                id=doc.get("id", fa_id),
                title=doc["title"],
                description=doc["description"],
                sub_domains=tuple(sub_domains),
            )
        )
    return focus_areas


def chain_items(model: list[FocusArea]) -> list[tuple[FocusArea, SubDomain]]:
    """Flatten the model into a single (FocusArea, SubDomain) list ordered by
    `sequence`, i.e. the whole evaluation as one connected Observation Chain
    rather than three independent Focus Areas."""
    pairs = [(fa, sd) for fa in model for sd in fa.sub_domains]
    return sorted(pairs, key=lambda pair: pair[1].sequence)


