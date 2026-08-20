import streamlit as st
import pandas as pd
import plotly.express as px

from data_loader import load_model, chain_items
from scoring import compute_sub_domain_score

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


st.set_page_config(page_title="Meteorological Maturity Assessment Tool", layout="wide")

# Readability: bump font size / line-height beyond Streamlit defaults.
st.markdown(
    """
    <style>
    div[data-testid="stCheckbox"] label p { font-size: 1.08rem !important; line-height: 1.6 !important; }
    div[data-testid="stExpander"] summary p { font-size: 1.1rem !important; }
    h1, h2, h3 { line-height: 1.35; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌤️ Meteorological Observation Maturity Assessment Tool")
st.caption("One connected Observation Chain, evaluated end-to-end on a 0-4 CMMI-style scale (FA1-FA3 are ownership labels, not separate audits).")

model = load_model()

if not model:
    st.error("YAML data files not found. Please place fa1.yaml, fa2.yaml, and fa3.yaml in the working directory.")
    st.stop()


def is_checked(fa_id: str, sub_domain_name: str, score: int, idx: int) -> bool:
    key = f"{fa_id}::{sub_domain_name}::L{score}::{idx}"
    return bool(st.session_state.get(key, False))


def declared_level_key(fa_id: str, sub_domain_name: str) -> str:
    return f"{fa_id}::{sub_domain_name}::declared_level"


def get_declared_level(fa_id: str, sub_domain_name: str) -> int:
    return int(st.session_state.get(declared_level_key(fa_id, sub_domain_name), 0))


items = chain_items(model)  # flat (FocusArea, SubDomain) list ordered by sequence, 1..12

# Compute scores across the whole chain once, used by both the chain overview
# chart and the sub-domain drill-down / final dashboard below.
scores_summary = []
for fa, sd in items:
    declared = get_declared_level(fa.id, sd.name)
    sd_result = compute_sub_domain_score(
        sd, declared, lambda score, idx, _fa=fa, _sd=sd: is_checked(_fa.id, _sd.name, score, idx)
    )
    scores_summary.append({
        "Sequence": sd.sequence,
        "Chain Stage": sd.chain_stage,
        "Stage (short)": short_stage(sd.chain_stage),
        "Focus Area": fa.id,
        "Sub-Domain": sd.name,
        "Achieved Score": sd_result.final_score,
        "Target Score": 3.0,  # Best Practice Target
        "Progress to Next %": f"{sd_result.completion_pct}%",
    })
df_summary = pd.DataFrame(scores_summary).sort_values("Sequence")

# Observation Chain Overview — the whole evaluation as one connected sequence,
# so a weak link anywhere in the chain is visible at a glance.
st.markdown("## 🔗 Observation Chain Overview")
st.caption("Ordered end-to-end from instrument foundations through network design. Bars are grouped by chain stage; FA labels are just the ownership split.")

fig_chain = px.bar(
    df_summary,
    x="Achieved Score",
    y="Sub-Domain",
    color="Stage (short)",
    orientation="h",
    range_x=[0, 4],
    category_orders={"Sub-Domain": df_summary["Sub-Domain"].tolist()[::-1]},
    text="Achieved Score",
    hover_data={"Chain Stage": True, "Stage (short)": False},
)
fig_chain.add_vline(x=3.0, line_dash="dash", line_color="red", annotation_text="Level 3 Target")
fig_chain.update_layout(height=450, legend_title_text="Chain Stage")
st.plotly_chart(fig_chain, width="stretch")
st.divider()

# Sidebar Navigation — one flat, ordered list across the whole chain.
st.sidebar.header("Navigation")
st.sidebar.caption("Observation Chain — one connected evaluation, ordered end-to-end.")
selected_fa, selected_domain = st.sidebar.selectbox(
    "Select a stage in the chain",
    options=items,
    format_func=lambda pair: f"{pair[1].sequence:02d}. {short_stage(pair[1].chain_stage)} — {pair[1].name}",
)
st.sidebar.caption(f"Owner: {selected_fa.id} — {selected_fa.title}")

# Main Form Area
st.subheader(f"{selected_domain.sequence:02d}. {selected_domain.chain_stage} ➔ {selected_domain.name}")
st.caption(f"{selected_fa.id}: {selected_fa.title} — {selected_fa.description}")

level_by_score = {lvl.score: lvl for lvl in selected_domain.levels}

st.markdown("**Which level currently best describes your practice for this sub-domain?**")
declared_level = st.radio(
    "Declared level",
    options=sorted(level_by_score),
    format_func=lambda s: f"L{s} — {level_by_score[s].label}",
    horizontal=True,
    key=declared_level_key(selected_fa.id, selected_domain.name),
    label_visibility="collapsed",
)
st.caption("Pick the paragraph that matches you *now* — do not re-litigate history. Ticking boxes below only tracks progress toward the next level.")

result = compute_sub_domain_score(
    selected_domain,
    declared_level,
    lambda score, idx: is_checked(selected_fa.id, selected_domain.name, score, idx),
)

# Level Ladder (compact stepper)
ladder_cols = st.columns(5)
for score in range(5):
    with ladder_cols[score]:
        if score <= result.achieved_level:
            st.markdown(f"**✅ Level {score}**")
        elif score == result.achieved_level + 1:
            st.markdown(f"**➡️ Level {score}**")
        else:
            st.markdown(f"🔒 Level {score}")
st.progress(min(result.final_score / 4.0, 1.0))
st.caption(f"Achieved score: **{result.final_score} / 4.0**  •  Best Practice Target: Level 3")
st.divider()

# Render Checklist by Maturity Level.
# Only the next level's criteria are interactive (evidence of progress toward
# it); surpassed and locked levels are shown read-only, since the assessor's
# declared level -- not bottom-up box-ticking -- is what determines the score.
next_score = declared_level + 1 if declared_level < 4 else None

for level in sorted(selected_domain.levels, key=lambda lvl: lvl.score):
    if level.score == 0:
        continue  # Level 0 represents "Absent / Non-compliant" baseline

    is_surpassed = level.score <= declared_level
    is_next = level.score == next_score

    if is_surpassed:
        header = f"✅ Level {level.score}: {level.label} — surpassed"
        expanded = False
    elif is_next:
        header = f"➡️ Level {level.score}: {level.label} — {round(result.partial_credit * 100)}% progress toward this level"
        expanded = True
    else:
        header = f"🔒 Level {level.score}: {level.label} — locked"
        expanded = False

    with st.expander(header, expanded=expanded):
        if is_surpassed:
            st.caption("Already surpassed — shown for reference only.")
            for criterion in level.criteria:
                st.markdown(f"- {criterion.text}")
        elif is_next:
            st.caption("Tick the criteria you currently satisfy to track progress toward this level.")
            for idx, criterion in enumerate(level.criteria):
                item_key = f"{selected_fa.id}::{selected_domain.name}::L{level.score}::{idx}"
                st.checkbox(criterion.text, key=item_key)
        else:
            st.caption("Declare the previous level first to unlock these criteria.")
            for criterion in level.criteria:
                st.markdown(f"- {criterion.text}")
        if level.standards_ref:
            st.caption("**Key Standards References:** " + "; ".join(level.standards_ref))

st.divider()

# Dashboard Summary View
st.markdown("## 📊 Live Assessment Dashboard")

col1, col2 = st.columns([1, 1])

with col1:
    st.dataframe(
        df_summary[['Sequence', 'Chain Stage', 'Sub-Domain', 'Achieved Score', 'Target Score', 'Progress to Next %']],
        width="stretch",
        hide_index=True,
    )

with col2:
    # Interactive Radar / Spider Chart
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

