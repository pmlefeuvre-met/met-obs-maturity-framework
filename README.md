# Meteorological Maturity Assessment Tool

An interactive Streamlit + Plotly web app that turns structured maturity
matrices into a capability-audit tool for National Meteorological and
Hydrological Services (NMHSs). It evaluates operational maturity across 12
sub-domains — spanning instrument calibration, procurement, maintenance,
data processing, quality control, siting, metadata, and network design — on
a 0–4 CMMI-style scale, presented as one connected end-to-end Observation
Chain rather than three disconnected audits.

See [AGENTS.md](AGENTS.md) for the full system/data model and architecture
documentation.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
streamlit run "🌤️_Assessment.py"
```

## Features

- Declared-level + next-level-evidence scoring, or per-element weighted
  scoring, per sub-domain (see [AGENTS.md](AGENTS.md) for the scoring model).
- Multi-institute support with per-institute save/load (`saved/*.yaml`) and
  client-side export/import.
- Chain-overview bar chart, summary table, and radar chart, plus a
  multi-institute comparison view on the Overview page.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
