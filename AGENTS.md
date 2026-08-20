# AGENTS.md — Meteorological Maturity Assessment Tool (Streamlit)

## System Overview
This project is an interactive web-based capability assessment tool built with **Streamlit** and **Plotly**. It transforms static Excel maturity matrices into an interactive audit web app. National Meteorological and Hydrological Services (NMHSs) use this tool to evaluate their operational maturity across 12 sub-domains on a 0 to 4 CMMI-style scale.

---

## Core Operational Domains (Data Sources)

The app ingests three primary Excel files located in the root directory:
1. `FA1_Instrument_Lifecycle_Maintenance_Calibration_Maturity_Matrix_v3.xlsx`
   * *Sub-domains:* Calibration and Traceability, Procurement, Lifecycle Mgmt and Replacement, Sensor and Station Maintenance, Staff Competence and Training
2. `FA2_Data_Processing_Quality_Control_Analysis_Support_Maturity_Matrix_v3.xlsx`
   * *Sub-domains:* Data Processing, Quality Control, Expert Review & LTQM, Performance Monitoring
3. `FA3_Network_Station_Management_Metadata_Maturity_Matrix_v3.xlsx`
   * *Sub-domains:* Site Management, Metadata and Data Stewardship, Network Design and Lifecycle

---

## Technical Constraints & Guidelines

### 1. Data Ingestion & State Rules
* **Multi-Sheet Parsing:** Always inspect all sheets in each Excel workbook (`pd.ExcelFile.sheet_names`).
* **Bullet Parsing:** Extract bullet points from the `Criteria` cell by splitting on `\n` and stripping bullet characters (`•`).
* **Session State Management:** All user interactions (checked/unchecked criteria) **must** be stored in `st.session_state` using unique compound keys: `f"{fa_name}::{sub_domain}::L{level_score}::{bullet_index}"`. Do not rely on local variables for checkbox state across page re-runs.

### 2. Scoring & Math Logic
* **Level Scale:** 
  * `0`: Absent / Non-compliant (Baseline)
  * `1`: Basic / Ad hoc
  * `2`: Structured / Partially Compliant
  * `3`: Compliant (**Best Practice Target**)
  * `4`: Optimized / Continual Improvement
* **Calculation:** Calculate scores proportionally per level based on completed checkboxes. Cap maximum domain scores at `4.0`. Round output scores to two decimal places.

### 3. UI & Visualization
* **Scaffolding:** Use `st.sidebar` for navigation across Focus Areas and Sub-domains.
* **Layout:** Use `st.columns` to present the summary table alongside the live Plotly radar chart.
* **Plotly Radar Chart:** 
  * Map `Sub-Domain` to `theta` and `Achieved Score` to `r`.
  * Fix `range_r` strictly between `[0, 4]`.
  * Always overlay a dashed benchmark line at `r = 3.0` (Level 3 Target).

---

## File Structure

```text
.
├── AGENTS.md
├── app.py
├── requirements.txt
├── FA1_Instrument_Lifecycle_Maintenance_Calibration_Maturity_Matrix_v3.xlsx
├── FA2_Data_Processing_Quality_Control_Analysis_Support_Maturity_Matrix_v3.xlsx
└── FA3_Network_Station_Management_Metadata_Maturity_Matrix_v3.xlsx
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