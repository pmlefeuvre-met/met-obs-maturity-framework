# AGENTS.md — Meteorological Maturity Assessment Tool (Streamlit)

## System Overview
This project is an interactive web-based capability assessment tool built with **Streamlit** and **Plotly**. It transforms structured maturity matrices into an interactive audit web app. National Meteorological and Hydrological Services (NMHSs) use this tool to evaluate their operational maturity across 12 sub-domains on a 0 to 4 CMMI-style scale.

The three YAML files remain the source of content, but they are parsed into a **single unified in-memory model** (not three parallel structures). Each Focus Area (FA1/FA2/FA3) is metadata — an `id`, `title` and `description` defined directly in its YAML file — attached to its sub-domains, not a separate code path. Levels within a sub-domain are **hierarchical, not independent**: Level *N* only counts as achieved once Levels 1..N-1 are substantially satisfied (see Scoring & Math Logic).

**The evaluation is one connected Observation Chain, not three independent audits.** FA1/FA2/FA3 are an ownership/authoring split (who leads which part), not a conceptual divide. Every sub-domain carries a `sequence` (1..12) and a `chain_stage` — a narrative grouping that can span Focus Area boundaries — so the app can present the whole assessment end-to-end (instrument foundations → maintenance → data ingestion → QC → review → siting → metadata → network design) instead of three disconnected drill-downs.

---

## Core Operational Domains (Data Sources)

The app ingests three YAML files located in the root directory, one per Focus Area:
1. `fa1.yaml` (id: `FA1`)
   * *Sub-domains:* Calibration and Traceability, Procurement, Lifecycle Mgmt and Replacement, Sensor and Station Maintenance, Staff Competence and Training
2. `fa2.yaml` (id: `FA2`)
   * *Sub-domains:* Data Processing, Quality Control, Expert Review & LTQM, Performance Monitoring
3. `fa3.yaml` (id: `FA3`)
   * *Sub-domains:* Site Management, Metadata and Data Stewardship, Network Design and Lifecycle

Each file has the shape:
```yaml
id: FA1
title: Instrument Lifecycle & Maintenance
description: One-line summary of this Focus Area.
sub_domains:
  - name: Calibration and Traceability
    sequence: 1
    chain_stage: Physical and Metrological Foundation
    levels:
      - score: 0
        label: Absent / Non-compliant
        criteria: ["...", "..."]
        standards_ref: ["...", "..."]
```
`criteria` and `standards_ref` are plain string lists — no bullet-character stripping or `\n`-splitting is required at parse time. `sequence` and `chain_stage` place the sub-domain in the end-to-end Observation Chain (see System Overview); `sequence` is unique 1..12 across all three files combined, and `chain_stage` values are shared across Focus Areas:
1. Physical and Metrological Foundation
2. Network Infrastructure and Field Maintenance
3. Real-Time Data Ingestion and Processing
4. Automated Data Quality Checkpoints
5. Manual Data Quality Control and Expert Review
6. Siting, Exposure, and Environmental Classification
7. Metadata Lifecycle and System Synchronization
8. Network Design and Strategic Lifecycle Planning

---

## Technical Constraints & Guidelines

### 1. Data Architecture (Unified Model)
* **YAML Parsing:** Load each `fa*.yaml` file with `yaml.safe_load`; no Excel/pandas dependency for content ingestion.
* **Unified Model:** Parsing must build one model, not three separate dicts per file. Use nested dataclasses:
  ```
  FocusArea(id, title, description) -> SubDomain(name, sequence, chain_stage) -> Level(score 0-4, label, standards_ref) -> Criterion(text)
  ```
  `standards_ref` lives on `Level` (references apply per-level, not per-bullet, matching the source content). Live in `data_loader.py`, cached with `@st.cache_data`, returning a single `list[FocusArea]`.
* **Chain Ordering:** `data_loader.chain_items(model)` flattens the model into one `list[tuple[FocusArea, SubDomain]]` sorted by `SubDomain.sequence`. This is the single source of navigation order — UI code must not re-derive ordering by iterating Focus Areas first.
* **Session State Management:** All user interactions (checked/unchecked criteria) **must** be stored in `st.session_state` using unique compound keys: `f"{fa_name}::{sub_domain}::L{level_score}::{bullet_index}"`. Do not rely on local variables for checkbox state across page re-runs.

### 2. Scoring & Math Logic (Declared Level + Next-Level Evidence)
* **Level Scale:** 
  * `0`: Absent / Non-compliant (Baseline)
  * `1`: Basic / Ad hoc
  * `2`: Structured / Partially Compliant
  * `3`: Compliant (**Best Practice Target**)
  * `4`: Optimized / Continual Improvement
* **The assessor directly declares their current level.** Levels are holistic, narrative descriptions of practice — not independent checklist items that must all be true simultaneously. Requiring an assessor to tick a Level 1 bullet describing inferior/ad-hoc practice they have already surpassed, just to "unlock" credit for Level 2/3 (which is where they actually are), is not meaningful. Instead, the assessor reads each level's paragraph as a whole and **selects the one that currently matches reality** (a single judgement call, like picking a rubric row), stored in `st.session_state` as `f"{fa_id}::{sub_domain}::declared_level"`.
* **Criteria checklists are evidence of progress toward the *next* level only.** Live in `scoring.py` as a pure function, independent of Streamlit:
  1. Take `declared_level` (0-4) as given, not derived.
  2. If `declared_level < 4`, compute `ratio = checked / total` for the criteria of level `declared_level + 1` only.
  3. Levels at or below `declared_level` and levels beyond `declared_level + 1` do not affect the score.
* **Calculation:** `final_score = min(4.0, round(declared_level + partial_credit, 2))`, where `partial_credit` is the `ratio` from the next level (0.0 if `declared_level == 4`).

### 3. UI & Visualization (Progressive Disclosure)
* **Scaffolding:** Sidebar navigation is a single flat, ordered selector across all 12 sub-domains (via `chain_items`), not a two-level Focus-Area-then-sub-domain drill-down. The Focus Area is shown only as an "owner" caption/badge next to the selection, never as the primary grouping.
* **Chain Overview:** Render a full-width chart (e.g. horizontal bar, ordered by `sequence`, colored by `chain_stage`) showing achieved score for all 12 sub-domains at once, with a dashed reference line at the Level 3 target — this is what makes a weak link anywhere in the chain visible at a glance.
* **Layout:** Use `st.columns` to present the summary table alongside the live Plotly radar chart.
* **Level Ladder:** Render a compact horizontal stepper (Level 0-4) at the top of each sub-domain view, highlighting the currently achieved level and the Level 3 target.
* **Progressive Disclosure:**
  * Levels at or below the declared level render collapsed and read-only (e.g. `✅ Level 2 — surpassed`, expandable to review the criteria as plain text, no checkboxes).
  * The next level (`declared_level + 1`) renders expanded by default with interactive checkboxes — this is the only level whose criteria affect the score.
  * Levels beyond that render collapsed/disabled ("locked") until the assessor declares the prior level.
* **Readability:** Inject custom CSS (`st.markdown(..., unsafe_allow_html=True)`) to increase font size and line-height for checkbox labels and headers — do not rely on Streamlit's default body text size.
* **Plotly Radar Chart:** 
  * Map `Sub-Domain` to `theta` and `Achieved Score` to `r`.
  * Fix `range_r` strictly between `[0, 4]`.
  * Always overlay a dashed benchmark line at `r = 3.0` (Level 3 Target).

### 4. Code Structure / Module Boundaries
* `data_loader.py` — YAML → unified `FocusArea` model, cached parsing only.
* `scoring.py` — pure hierarchical scoring functions (no Streamlit imports), unit-testable.
* `app.py` — Streamlit UI only: navigation, level ladder rendering, dashboard/radar chart. Consumes `data_loader` and `scoring`, contains no parsing or scoring math of its own.

---

## File Structure

```text
.
├── AGENTS.md
├── app.py
├── data_loader.py
├── scoring.py
├── requirements.txt
├── fa1.yaml
├── fa2.yaml
└── fa3.yaml
```

## Development Environment & Virtual Environment (.venv)

All development, script execution, and application testing **MUST** run inside a dedicated Python virtual environment named `.venv`.

### 1. Environment Setup Commands
For Unix/Linux/macOS (Bash/Zsh):
```bash
# Create virtual environment if it does not exist
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt
```