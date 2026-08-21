"""Overview: current live figures/tables for the selected institute on top,
saved-assessments list + compare below.

The live section reflects in-progress st.session_state answers (shared
across pages in the same session) so it always matches the Assessment page,
even before anything is saved. The saved section stays read-only -- to
continue editing a saved assessment, use the "Load saved assessment" button
on the main page (this page does not modify session_state).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import chain_items, load_model
from institutes import INSTITUTES
from scoring import score_all, stage_color_hex
from storage import list_assessments
from theme import apply_custom_css


def _long_name(institute_id: str) -> str:
    institute = INSTITUTES.get(institute_id)
    return institute.long if institute else institute_id

st.set_page_config(page_title="Overview", layout="wide")

apply_custom_css()

st.title("📊 Overview")

model = load_model()

# --- Current session (live, unsaved answers included) -------------------
selected_institute = st.session_state.get("selected_institute") or next(iter(INSTITUTES))
st.markdown(f"## 🔗 Current Session — {INSTITUTES[selected_institute].long}")
st.caption("Live figures for the institute currently selected on the Assessment page. Ordered end-to-end from instrument foundations through network design.")

scores_summary = score_all(model, selected_institute, st.session_state.get)
df_summary = pd.DataFrame(scores_summary).sort_values("Sequence")

# Same stage -> color mapping used for the sidebar nav's colored dots, so a
# stage looks the same color here as it does in the Assessment page's list.
stage_colors = dict(zip(df_summary["Stage (short)"], df_summary["Chain Stage"].map(stage_color_hex)))

fig_chain = px.bar(
    df_summary,
    x="Achieved Score",
    y="Sub-Domain",
    color="Stage (short)",
    color_discrete_map=stage_colors,
    orientation="h",
    range_x=[0, 4],
    category_orders={"Sub-Domain": df_summary["Sub-Domain"].tolist()[::-1]},
    text="Achieved Score",
    hover_data={"Chain Stage": True, "Stage (short)": False},
)
fig_chain.add_vline(x=3.0, line_dash="dash", line_color="red", annotation_text="Level 3 Target")
fig_chain.update_layout(height=450, legend_title_text="Chain Stage")
st.plotly_chart(fig_chain, width="stretch")

col1, col2 = st.columns([1, 1])

with col1:
    st.dataframe(
        df_summary[['Sequence', 'Sub-Domain', 'Achieved Score']],
        width="stretch",
        hide_index=True,
    )

with col2:
    fig = px.line_polar(
        df_summary,
        r='Achieved Score',
        theta='Sub-Domain',
        line_close=True,
        range_r=[0, 4],
        title="Maturity Profile vs. Best Practice Target (Level 3)"
    )
    fig.add_scatterpolar(
        r=[3.0] * len(df_summary),
        theta=df_summary['Sub-Domain'],
        name="Best Practice Target (Level 3)",
        line=dict(dash='dash', color='red')
    )
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Saved assessments (read-only) ---------------------------------------
st.markdown("## 📁 Saved Assessments")
st.caption("One saved record per institute. Switch to the main page to save, load, or edit an assessment.")

assessments = list_assessments()

if not assessments:
    st.info("No institute has saved an assessment yet.")
    st.stop()

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

