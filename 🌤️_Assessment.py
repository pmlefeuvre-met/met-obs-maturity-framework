import streamlit as st

from data_loader import load_model, chain_items
from scoring import compute_sub_domain_score, compute_sub_domain_element_score, short_stage, short_topic, stage_color_dot
from institutes import INSTITUTES
from theme import apply_custom_css
import storage
import sidebar as sidebar_ui


st.set_page_config(page_title="Meteorological Maturity Assessment Tool", layout="wide")

apply_custom_css()

st.title("🌤️ Meteorological Observation Maturity Assessment Tool")
st.caption("A Capability Maturity Model Integration evaluates local land surface observing practices against WMO and international standards across the full observational lifecycle to ensure data is traceable, sustainable, and fit for purpose.")

model = load_model()

if not model:
    st.error("YAML data files not found. Please place fa1.yaml, fa2.yaml, and fa3.yaml in the working directory.")
    st.stop()

items = chain_items(model)  # flat (FocusArea, SubDomain) list ordered by sequence, 1..12

# Sidebar Navigation — one flat, ordered list across the whole chain. Options
# use short fixed labels (not the full chain-stage name, which made entries
# too long to read) with a colored dot prefix so the 8 chain stages are still
# visually distinguishable at a glance.
st.sidebar.header("Navigation")
selected_fa, selected_domain = st.sidebar.selectbox(
    "Select a topic",
    options=items,
    format_func=lambda pair: f"{stage_color_dot(pair[1].chain_stage)} {short_topic(pair[1].sequence)}",
)
#st.sidebar.caption(f"Owner: {selected_fa.id — {selected_fa.title}}") 

# Met Institute selector — every session_state key below is namespaced by
# this so switching institutes keeps each one's answers separate. Shared with
# the Overview page via sidebar.py so the two copies can't drift.
selected_institute = sidebar_ui.render_institute_selector()

# Hydrate once per rerun: if this institute has a saved file, merge any
# missing answers into session_state before rendering the current stage, so
# switching stages/pages never shows a blank form for already-declared work.
sidebar_ui.hydrate_from_saved(selected_institute)

# Save / Load — persists to saved/<institute>.yaml (see storage.py). Saving
# never silently clobbers another assessor's work: an existing save requires
# an explicit overwrite confirmation.
existing_save = storage.get_assessment(selected_institute)
if existing_save:
    when = existing_save.saved_at[:16].replace("T", " ")
    st.sidebar.caption(f"🟢 Saved by {existing_save.assessor_name} · {when} UTC")
else:
    st.sidebar.caption("⚪ Not saved yet")

assessor_name = st.sidebar.text_input(
    "Assessor name", key="assessor_name", placeholder="Assessor name", label_visibility="collapsed"
)

# Per-assessor history — keyed by (institute, assessor name), no timestamp.
# Lets an assessor recover their own last save even if someone else has
# since overwritten the shared file above.
assessor_history = storage.get_assessor_history(selected_institute, assessor_name) if assessor_name.strip() else None
if assessor_history is not None:
    when_mine = assessor_history.saved_at[:16].replace("T", " ")
    st.sidebar.caption(f"🕘 Your last save here: {when_mine} UTC")
    if st.sidebar.button("↩️ Load my last save", width="stretch"):
        st.session_state.update(assessor_history.answers)
        st.rerun()

load_col, save_col = st.sidebar.columns(2)
load_clicked = load_col.button("📂 Load", disabled=existing_save is None, width="stretch")
save_clicked = save_col.button("💾 Save", width="stretch")

if load_clicked and existing_save:
    st.session_state.update(existing_save.answers)
    st.rerun()

if save_clicked:
    if not assessor_name.strip():
        st.sidebar.error("Enter an assessor name before saving.")
    elif existing_save is not None:
        st.session_state["_pending_overwrite"] = True
    else:
        st.session_state["_do_save"] = True

if st.session_state.get("_pending_overwrite") and existing_save is not None:
    st.sidebar.warning(f"Overwrite {existing_save.assessor_name}'s save?")
    confirm_col1, confirm_col2 = st.sidebar.columns(2)
    if confirm_col1.button("Yes", key="confirm_overwrite_yes", width="stretch"):
        st.session_state["_pending_overwrite"] = False
        st.session_state["_do_save"] = True
    if confirm_col2.button("No", key="confirm_overwrite_cancel", width="stretch"):
        st.session_state["_pending_overwrite"] = False

# Export / Import — a client-side YAML round trip independent of saved/ on
# disk: lets an assessor take their session home, or resume it on another
# machine/deployment, without needing server-side storage at all. Shared
# with the Overview page via sidebar.py.
current_answers = {k: v for k, v in st.session_state.items() if str(k).startswith(f"{selected_institute}::")}
sidebar_ui.render_export_import(selected_institute, assessor_name, current_answers)

st.sidebar.divider()


def is_checked(institute: str, fa_id: str, sub_domain_name: str, score: int, idx: int) -> bool:
    key = f"{institute}::{fa_id}::{sub_domain_name}::L{score}::{idx}"
    return bool(st.session_state.get(key, False))


def declared_level_key(institute: str, fa_id: str, sub_domain_name: str) -> str:
    return f"{institute}::{fa_id}::{sub_domain_name}::declared_level"


def element_level_key(institute: str, fa_id: str, sub_domain_name: str, element_id: str) -> str:
    return f"{institute}::{fa_id}::{sub_domain_name}::{element_id}::declared_level"


def comment_key(institute: str, fa_id: str, sub_domain_name: str, element_id: str) -> str:
    return f"{institute}::{fa_id}::{sub_domain_name}::{element_id}::comment"


# Deferred save — placed here for layout convenience; saving itself only
# needs the raw answers (scores are recomputed on load, and shown on the
# Overview page rather than here).
if st.session_state.pop("_do_save", False):
    session_answers = {k: v for k, v in st.session_state.items() if str(k).startswith(f"{selected_institute}::")}
    # Merge over the previous save so a partial session (e.g. an assessor who
    # didn't Load first and only touched a few sub-domains) can't silently
    # wipe out other sub-domains' answers already on disk.
    prior_answers = existing_save.answers if existing_save is not None else {}
    answers = {**prior_answers, **session_answers}
    storage.save_assessment(selected_institute, assessor_name, answers)
    st.sidebar.success(f"Saved for {INSTITUTES[selected_institute].short}.")

# Main Form Area
st.subheader(f"{selected_domain.sequence:02d}. {selected_domain.chain_stage} ➔ {selected_domain.name}")
st.caption(f"{selected_fa.id}: {selected_fa.title} — {selected_fa.description}")

if selected_domain.elements:
    # Element-based sub-domain: independent tracks, each declared separately.
    # Non-conflicting tracks can sit at different levels at once; a Gate caps
    # a track's effective level when the source content ties it to another.
    st.caption(
        "This sub-domain has independent tracks — declare each one where it "
        "currently stands. A track can be capped if it depends on another (shown below)."
    )

    declared_levels: dict[str, int] = {}
    for idx, element in enumerate(selected_domain.elements, start=1):
        options = list(element.applicable_levels)
        subsection_number = f"{selected_domain.sequence}.{idx}"
        with st.expander(f"🔹 {subsection_number} {element.title}", expanded=True):
            declared = st.radio(
                element.title,
                options=options,
                format_func=lambda s, _el=element: f"L{s} — {_el.level_text[s]}",
                key=element_level_key(selected_institute, selected_fa.id, selected_domain.name, element.id),
                label_visibility="collapsed",
            )
            declared_levels[element.id] = declared
            st.text_area(
                "Comment / justification",
                key=comment_key(selected_institute, selected_fa.id, selected_domain.name, element.id),
                placeholder=f"Feedback or justification for {subsection_number} {element.title}…",
            )

    result = compute_sub_domain_element_score(selected_domain, declared_levels)

    for element in selected_domain.elements:
        outcome = result.outcomes[element.id]
        if outcome.gated:
            gate = next(g for g in element.gates if g.applies_at_level - 1 == outcome.effective_level)
            st.warning(
                f"**{element.title}** capped at Level {outcome.effective_level} "
                f"(declared L{outcome.declared_level}): needs **{gate.requires}** at Level {gate.min_level}+ first."
            )

    st.progress(min(result.final_score / 4.0, 1.0))
    st.caption(f"Weighted sub-domain score: **{result.final_score} / 4.0**  •  Best Practice Target: Level 3")
    st.divider()

else:
    level_by_score = {lvl.score: lvl for lvl in selected_domain.levels}

    st.markdown("**Which level currently best describes your practice for this sub-domain?**")
    declared_level = st.radio(
        "Declared level",
        options=sorted(level_by_score),
        format_func=lambda s: f"L{s} — {level_by_score[s].label}",
        horizontal=True,
        key=declared_level_key(selected_institute, selected_fa.id, selected_domain.name),
        label_visibility="collapsed",
    )
    st.caption("Pick the paragraph that matches you *now* — do not re-litigate history. Ticking boxes below only tracks progress toward the next level.")

    result = compute_sub_domain_score(
        selected_domain,
        declared_level,
        lambda score, idx: is_checked(selected_institute, selected_fa.id, selected_domain.name, score, idx),
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
                    item_key = f"{selected_institute}::{selected_fa.id}::{selected_domain.name}::L{level.score}::{idx}"
                    st.checkbox(criterion.text, key=item_key)
            else:
                st.caption("Declare the previous level first to unlock these criteria.")
                for criterion in level.criteria:
                    st.markdown(f"- {criterion.text}")
            if level.standards_ref:
                st.caption("**Key Standards References:** " + "; ".join(level.standards_ref))

    st.text_area(
        "Comment / justification",
        key=comment_key(selected_institute, selected_fa.id, selected_domain.name, "_subdomain"),
        placeholder="Feedback or justification for this sub-domain…",
    )

    st.divider()

# Autosave — silently persists every declared level/checkbox/comment typed on
# this stage to saved/<institute>.yaml, merged over prior answers. This is
# what makes switching stages safe: hydrate_from_saved() re-fills session_state
# from this same file on the next rerun, so nothing typed is ever stranded.
autosave_answers = {k: v for k, v in st.session_state.items() if str(k).startswith(f"{selected_institute}::")}
sidebar_ui.autosave(selected_institute, assessor_name, autosave_answers)

st.caption("See the **Overview** page in the sidebar for the live chain chart, dashboard table, and radar chart.")

