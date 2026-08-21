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
* **Session State Management:** All user interactions (checked/unchecked criteria, declared levels, free-text comments) **must** be stored in `st.session_state` using unique compound keys namespaced by the selected Met Institute: `f"{institute}::{fa_id}::{sub_domain}::L{level_score}::{bullet_index}"` (legacy checklist path), `f"{institute}::{fa_id}::{sub_domain}::{element_id}::declared_level"` (element path), or `f"{institute}::{fa_id}::{sub_domain}::{element_id}::comment"` (per-element/sub-domain comment, `element_id` is the literal `_subdomain` for the legacy path). Do not rely on local variables for checkbox/radio/text-area state across page re-runs, and never drop the `institute` prefix — it's what keeps different institutes' answers from clobbering each other. This prefix convention is also what lets Save/Export automatically pick up any new field (e.g. comments) with zero changes to `storage.py`.
* **Hydrate on every rerun + silent autosave:** `sidebar.hydrate_from_saved(institute)` merges `st.session_state` with `saved/<institute>.yaml` on *every* script rerun (not just once), and `sidebar.autosave(institute, assessor_name, answers)` writes the current answers back to that same file after every change. Together these guarantee switching sub-domains/pages (or a dev-server restart) never leaves a stage looking blank, since whatever was last typed/declared was already persisted to disk a moment earlier. `hydrate_from_saved` only fills in missing keys (`setdefault`), never overwriting a value already touched this run; `autosave` merges over the prior save (never wipes untouched sub-domains) and skips the disk write entirely when nothing changed. Autosave has no overwrite-confirmation prompt and keeps the last real assessor's name if the "Assessor name" field is currently empty — it exists purely so nothing is ever lost, and does not replace the explicit, attributed "💾 Save" flow below.
* **Elements (per-sub-domain theme split — now the standard model for all 12 sub-domains):** A sub-domain's 5 level-paragraphs are not always one indivisible narrative — in reality some parts of a sub-domain progress independently (e.g. "Traceability" can be at Level 3 while "Records & Certificates" is still at Level 1 for the same sub-domain), while other parts are single-shot achievements that only appear once a certain level is reached. `SubDomain` carries an `elements: tuple[Element, ...]` field (still optional in the schema — an empty tuple falls back to the legacy single-ladder rendering/scoring path — but every sub-domain currently populates it):
  ```
  Element(id, title, weight, level_text: dict[int, str], gates: tuple[Gate, ...])
  Gate(requires: element_id, min_level, applies_at_level)
  ```
  * `level_text` only has keys for the levels where that element/theme has distinct source content — themes are **not** forced to exist at all 5 levels (e.g. a theme with no Level 4 restatement simply caps at 3).
  * Elements must be derived by semantically re-reading the *existing* source text and grouping bullets by theme across levels — **never by inventing new sentences** to fill gaps. If a theme has no bullet at some level in the source, it is absent at that level, full stop.
  * A `Gate` expresses a genuine cross-element prerequisite only when the source text itself implies the dependency (e.g. an element's own Level 4 text says "...while maintaining traceability..." → gate on the `traceability` element). Do not invent gates speculatively.
  * All 12 sub-domains across `fa1.yaml`, `fa2.yaml` and `fa3.yaml` are now element-based (5-7 elements each). Each sub-domain's `levels:` block retains only `score`/`label`/`standards_ref`; all criteria content was regrouped into `elements:` by semantic theme, with every original bullet accounted for exactly once and no invented text. Gates were added only where the source text explicitly implied a prerequisite (currently one gate, in `Calibration and Traceability`); the remaining 11 sub-domains had no textually-justified cross-element dependency and so carry no gates.

### 2. Scoring & Math Logic (Declared Level + Next-Level Evidence, or Weighted Elements)
* **Level Scale:** 
  * `0`: Absent / Non-compliant (Baseline)
  * `1`: Basic / Ad hoc
  * `2`: Structured / Partially Compliant
  * `3`: Compliant (**Best Practice Target**)
  * `4`: Optimized / Continual Improvement
* **The assessor directly declares their current level.** Levels are holistic, narrative descriptions of practice — not independent checklist items that must all be true simultaneously. Requiring an assessor to tick a Level 1 bullet describing inferior/ad-hoc practice they have already surpassed, just to "unlock" credit for Level 2/3 (which is where they actually are), is not meaningful. Instead, the assessor reads each level's paragraph as a whole and **selects the one that currently matches reality** (a single judgement call, like picking a rubric row), stored in `st.session_state` as `f"{fa_id}::{sub_domain}::declared_level"`.
* **Criteria checklists are evidence of progress toward the *next* level only.** This applies to legacy (non-element) sub-domains. Live in `scoring.py` as a pure function, independent of Streamlit:
  1. Take `declared_level` (0-4) as given, not derived.
  2. If `declared_level < 4`, compute `ratio = checked / total` for the criteria of level `declared_level + 1` only.
  3. Levels at or below `declared_level` and levels beyond `declared_level + 1` do not affect the score.
* **Calculation:** `final_score = min(4.0, round(declared_level + partial_credit, 2))`, where `partial_credit` is the `ratio` from the next level (0.0 if `declared_level == 4`).
* **Element-based sub-domains score differently.** When `SubDomain.elements` is non-empty, there is no single ladder or checklist: each element gets its own direct-declared level (from its own `applicable_levels`, since not every element spans 0-4). `scoring.compute_sub_domain_element_score`:
  1. Reads each element's declared level (default: its lowest applicable level).
  2. Applies any `Gate`: if the element's declared level is `>= gate.applies_at_level` but the required element's declared level is `< gate.min_level`, the effective level is capped to `gate.applies_at_level - 1`.
  3. `final_score = weighted mean of each element's effective_level`, using `Element.weight` (default `1.0` for all — real priority weighting needs domain/SME input, not an invented default).

### 3. UI & Visualization (Progressive Disclosure)
* **Scaffolding:** Sidebar navigation is a single flat, ordered selector across all 12 sub-domains (via `chain_items`), not a two-level Focus-Area-then-sub-domain drill-down. The Focus Area is shown only as an "owner" caption/badge next to the selection, never as the primary grouping.
* **Chain Overview:** Render a full-width chart (e.g. horizontal bar, ordered by `sequence`, colored by `chain_stage`) showing achieved score for all 12 sub-domains at once, with a dashed reference line at the Level 3 target — this is what makes a weak link anywhere in the chain visible at a glance.
* **Layout:** Use `st.columns` to present the summary table alongside the live Plotly radar chart.
* **Element-based rendering (current path for all 12 sub-domains):** When `selected_domain.elements` is non-empty, `🌤️_Assessment.py` skips the single ladder entirely and instead:
  * Renders each element in its own expander, headed with a computed subsection number `f"{sub_domain.sequence}.{index}"` (e.g. `1.1`, `1.2` for Calibration's elements, `2.1` for Procurement's first — 1-based, computed at render time via `enumerate(sub_domain.elements, start=1)`, not stored on the `Element` dataclass) followed by the element title, with a `st.radio` limited to that element's `applicable_levels` (not always 0-4) — one independent judgement call per track, keyed as `f"{fa_id}::{sub_domain}::{element_id}::declared_level"`.
  * Below the radio, a free-text `st.text_area` ("Comment / justification") lets the assessor record feedback or justification for that subsection's declared level, keyed as `f"{fa_id}::{sub_domain}::{element_id}::comment"` — persisted/exported the same way as any other answer.
  * After collecting all declared levels, calls `compute_sub_domain_element_score` and surfaces a `st.warning` for any element whose effective level was capped by a `Gate`, naming the required element/level.
  * Shows one weighted `st.progress` bar and score caption for the whole sub-domain — there is no per-level stepper/ladder in this path, since elements don't share a single level axis.
* **Legacy single-ladder rendering (fallback path, currently unused by any shipped sub-domain but still supported for `elements == ()`):**
  * **Level Ladder:** Render a compact horizontal stepper (Level 0-4) at the top of the sub-domain view, highlighting the currently achieved level and the Level 3 target.
  * Levels at or below the declared level render collapsed and read-only (e.g. `✅ Level 2 — surpassed`, expandable to review the criteria as plain text, no checkboxes).
  * The next level (`declared_level + 1`) renders expanded by default with interactive checkboxes — this is the only level whose criteria affect the score.
  * Levels beyond that render collapsed/disabled ("locked") until the assessor declares the prior level.
  * One free-text `st.text_area` ("Comment / justification") below the checklist, keyed `f"{fa_id}::{sub_domain}::_subdomain::comment"`, covers the whole sub-domain (there are no sub-numbered subsections on this path).
* **Readability:** Inject custom CSS (`st.markdown(..., unsafe_allow_html=True)`) to increase font size and line-height across the app — body/markdown text, captions, checkbox/radio labels, expander headers, dataframe cells, and heading sizes (`h1`/`h2`/`h3`) — do not rely on Streamlit's default body text size.
* **Plotly Radar Chart:** 
  * Map `Sub-Domain` to `theta` and `Achieved Score` to `r`.
  * Fix `range_r` strictly between `[0, 4]`.
  * Always overlay a dashed benchmark line at `r = 3.0` (Level 3 Target).

### 4. Code Structure / Module Boundaries
* `data_loader.py` — YAML → unified `FocusArea` model, cached parsing only.
* `scoring.py` — pure hierarchical scoring functions (no Streamlit imports), unit-testable.
* `institutes.py` — the `INSTITUTES: dict[id, display_name]` constant shared by `🌤️_Assessment.py` and `pages/*.py`. Single source of truth for which NMHSs the tool supports.
* `theme.py` — `apply_custom_css()`, one shared Streamlit CSS injection (font size / line-height bump, sidebar header/file-uploader styling) called near the top of `🌤️_Assessment.py` and every page under `pages/`, so the two copies can't drift out of sync.
* `storage.py` — pure file-based persistence (no Streamlit imports), unit-testable like `scoring.py`. Reads/writes one YAML file per institute under `saved/` (e.g. `saved/UKMO.yaml`), never a database — this matches the project's existing YAML-as-source-of-truth convention and keeps saved assessments human-readable and diffable in git. One row/file per institute (not append-only history): saving overwrites the prior file, gated by an explicit confirm-before-overwrite prompt in the UI (see below). On disk, `answers` stays a flat `"fa::sub_domain::element::field"`-keyed mapping (one line per answer) but each key is shortened for readability via `_shorten_key`/`_lengthen_key`: the full sub-domain name is swapped for a short static slug (e.g. `calibration_traceability`) and `declared_level` is renamed to `level`; reading reverses this transparently, and pre-existing saves using the full names/`declared_level` still load correctly since only mapped names/fields are touched.
* `sidebar.py` — shared, Streamlit-touching sidebar widgets used by both `🌤️_Assessment.py` and `pages/1_📊_Overview.py` so the two copies can't drift (same rationale as `theme.py`): `render_institute_selector()` (the institute `st.selectbox`, keyed `"selected_institute"`), `hydrate_from_saved(institute)` and `autosave(institute, assessor_name, answers)` (see Hydrate on every rerun + silent autosave, above), and `render_export_import(institute, assessor_name, answers)` (the Export/Import file round trip). Save/Load (server-side, with assessor name + overwrite confirmation) stays defined directly in `🌤️_Assessment.py`, not shared, since it's Assessment-page-only.
* `🌤️_Assessment.py` — Streamlit UI only, and the app's entrypoint (`streamlit run "🌤️_Assessment.py"`; the emoji-prefixed filename gives the sidebar nav a proper icon + label instead of the default "app"): institute selector, save/load controls, navigation, level ladder / element rendering. Consumes `data_loader`, `scoring`, `institutes`, `storage`, and `sidebar`, contains no parsing, scoring, or persistence logic of its own.
* `pages/1_📊_Overview.py` — a second Streamlit page (native multipage app, auto-discovered from `pages/`, labeled "Overview" in the sidebar nav). Its dashboard section (charts/tables) stays read-only. Its sidebar shares the institute selector and Export/Import controls with the Assessment page via `sidebar.py` — switching institute or applying an import here does update `st.session_state` (unlike the dashboard section below it) — but Save/Load (server-side, with assessor name) remains Assessment-page-only. On top, it renders the live chain-overview bar chart, dashboard table, and radar chart for whichever institute is currently selected (shared across pages in the same session via `st.session_state["selected_institute"]`) — this is where those charts live now, not on the Assessment page itself, keeping the main page focused on data entry. Below that, it lists every saved institute (assessor, timestamp, avg score) and lets the user pick 2+ institutes to overlay on a comparison radar chart. To continue editing a saved assessment, use the "Load saved assessment" button on the main page instead.

### 5. Multi-Institute Support & Persistence
* **Institute selector:** A sidebar `st.selectbox` (options from `institutes.INSTITUTES`, factored into `sidebar.render_institute_selector()` and used by both `🌤️_Assessment.py` and `pages/1_📊_Overview.py`) picks which NMHS is currently being assessed; this choice namespaces every session-state key (see Session State Management above), so switching institutes mid-session never mixes their answers, and switching it on either page updates the other (shared `st.session_state["selected_institute"]`).
* **Save:** An "Assessor name" free-text field (no auth) plus a "💾 Save this assessment" button. On click, all `st.session_state` entries prefixed `f"{institute}::"` are collected verbatim (declared levels, checked criteria) and written via `storage.save_assessment` — scores are never persisted, they're recomputed on load/view via `scoring.score_all`. If a save already exists for that institute, the UI shows who saved it and when and requires an explicit "Yes, overwrite" click — saves are never silently clobbered.
* **Load:** A "📂 Load saved assessment" button (enabled only if a save exists for the selected institute) copies the saved `answers` dict back into `st.session_state` and reruns, restoring every declared level/checkbox exactly as saved.
* **Compare:** `pages/1_📊_Overview.py` is the shared view for showing teammates what each institute chose — the live current-session charts on top, then a saved-institutes overview table plus a multi-institute radar overlay below, so several people assessing different institutes (or the same institute at different times) can see and compare results without needing a database.
* **Export / Import (client-side, no server storage):** Sidebar controls (`sidebar.render_export_import`, present on both `🌤️_Assessment.py` and `pages/1_📊_Overview.py`) let an assessor download their current in-progress answers as a YAML file (`storage.export_yaml`, same shape as a server-side save) and later re-upload it (`storage.import_yaml`) to restore that session — on this machine, another deployment, or after clearing browser state. Import re-namespaces the file's `answers` to the *currently selected* institute regardless of which institute it was originally exported for, showing a warning on mismatch rather than blocking the import. Malformed or non-export uploads raise a `ValueError`, surfaced as a sidebar error instead of crashing the app. This is independent of, and does not touch, the `saved/` on-disk store.

---

## File Structure

```text
.
├── AGENTS.md
├── 🌤️_Assessment.py
├── data_loader.py
├── scoring.py
├── institutes.py
├── theme.py
├── storage.py
├── sidebar.py
├── pages/
│   └── 1_📊_Overview.py
├── saved/                 # one YAML file per institute, created on first save
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

## Agent Workflow: Commit Messages

When asked for a commit message provide a ready-to-paste commit command with Format: Short imperative title and concise bullet points.
