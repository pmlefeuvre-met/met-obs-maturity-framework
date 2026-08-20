"""Read-only view of saved institute assessments: list + compare.

To continue editing a saved assessment, use the "Load saved assessment"
button on the main page (this page does not modify session_state).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import chain_items, load_model
from institutes import INSTITUTES
from scoring import score_all
from storage import list_assessments


def _long_name(institute_id: str) -> str:
    institute = INSTITUTES.get(institute_id)
    return institute.long if institute else institute_id

st.set_page_config(page_title="Saved Assessments", layout="wide")

st.title("📁 Saved Assessments")
st.caption("One saved record per institute. Switch to the main page to save, load, or edit an assessment.")

assessments = list_assessments()

if not assessments:
    st.info("No institute has saved an assessment yet.")
    st.stop()

model = load_model()

summary_rows = []
for a in assessments:
    scores_df = pd.DataFrame(score_all(model, a.institute, a.answers.get))
    avg_score = round(scores_df["Achieved Score"].mean(), 2) if not scores_df.empty else 0.0
    on_target = int((scores_df["Achieved Score"] >= 3.0).sum()) if not scores_df.empty else 0
    summary_rows.append({
        "Institute": _long_name(a.institute),
        "Assessor": a.assessor_name,
        "Saved At (UTC)": a.saved_at,
        "Avg. Score": avg_score,
        "Sub-Domains at Target (≥3)": f"{on_target} / {len(scores_df)}" if not scores_df.empty else "0 / 0",
    })

st.markdown("## Overview")
st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

st.divider()

def _institute_label(institute_id: str) -> str:
    return _long_name(institute_id)


st.markdown("## Compare Institutes")
saved_ids = [a.institute for a in assessments]
selected_ids = st.multiselect(
    "Choose 2 or more saved institutes to overlay on a radar chart",
    options=saved_ids,
    default=saved_ids,
    format_func=_institute_label,
)

if len(selected_ids) >= 1:
    frames = []
    for a in assessments:
        if a.institute in selected_ids:
            df = pd.DataFrame(score_all(model, a.institute, a.answers.get))
            df["Institute"] = _long_name(a.institute)
            frames.append(df)
    combined = pd.concat(frames, ignore_index=True)

    fig = px.line_polar(
        combined,
        r="Achieved Score",
        theta="Sub-Domain",
        color="Institute",
        line_close=True,
        range_r=[0, 4],
        title="Maturity Profile Comparison vs. Best Practice Target (Level 3)",
    )

    # Reference dashed line at the Level 3 target, ordered same as the chain.
    ordered_names = [sd.name for _fa, sd in chain_items(model)]
    fig.add_scatterpolar(
        r=[3.0] * len(ordered_names),
        theta=ordered_names,
        name="Best Practice Target (Level 3)",
        line=dict(dash="dash", color="red"),
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.caption("Select at least one institute above to see its radar chart.")
