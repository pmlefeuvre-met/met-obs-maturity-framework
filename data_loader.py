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
class SubDomain:
    name: str
    sequence: int  # position (1..12) in the end-to-end Observation Chain
    chain_stage: str  # narrative grouping shared across Focus Areas
    levels: tuple[Level, ...]  # sorted by score, 0..4


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
                    criteria=tuple(Criterion(text=c) for c in lvl["criteria"]),
                    standards_ref=tuple(lvl.get("standards_ref", [])),
                )
                for lvl in sorted(sd["levels"], key=lambda lvl: lvl["score"])
            )
            sub_domains.append(
                SubDomain(
                    name=sd["name"],
                    sequence=sd["sequence"],
                    chain_stage=sd["chain_stage"],
                    levels=levels,
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


