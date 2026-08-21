"""Shared sidebar widgets used by both 🌤️_Assessment.py and pages/1_📊_Overview.py
so the two copies can't drift out of sync (same rationale as theme.py).

Covers: institute selection, hydrating session_state from saved/<institute>.yaml
on every rerun, silent autosave, and the Export/Import file round trip. The
explicit, attributed "💾 Save" button (with overwrite confirmation) stays
Assessment-page-only.
"""

from __future__ import annotations

import streamlit as st

from institutes import INSTITUTES
import storage


def _institute_option_label(key: str) -> str:
    mark = "✅ " if storage.get_assessment(key) is not None else "▫️ "
    return mark + INSTITUTES[key].short


def render_institute_selector() -> str:
    """Sidebar institute picker, keyed 'selected_institute' so both pages
    share the same selection within a session."""
    st.sidebar.header("Institute")
    selected_institute = st.sidebar.selectbox(
        "NMHS",
        options=list(INSTITUTES.keys()),
        format_func=_institute_option_label,
        key="selected_institute",
        label_visibility="collapsed",
    )
    st.caption(f"Institute: **{INSTITUTES[selected_institute].long}**")
    return selected_institute


def hydrate_from_saved(institute: str) -> None:
    """Merge saved/<institute>.yaml into session_state on every rerun (not
    just once), so switching sub-domains/pages -- or a dev-server restart --
    never leaves a stage looking blank. Uses setdefault so it never clobbers
    a value already set this run (e.g. the edit that triggered this rerun).
    Cheap: just a small YAML read + dict merge."""
    existing = storage.get_assessment(institute)
    if existing:
        for k, v in existing.answers.items():
            st.session_state.setdefault(k, v)


def autosave(institute: str, assessor_name: str, current_answers: dict) -> None:
    """Silently persist current_answers to saved/<institute>.yaml on every
    change, merged over the prior save so untouched sub-domains/elements
    survive. No overwrite-confirmation prompt here -- that stays on the
    explicit "💾 Save" button; this just guarantees nothing typed/declared is
    ever lost when navigating away from a stage. Skips the disk write when
    nothing actually changed, and preserves the last real assessor's name
    on the file rather than overwriting it with a blank/placeholder one."""
    existing = storage.get_assessment(institute)
    prior_answers = existing.answers if existing else {}
    merged = {**prior_answers, **current_answers}
    if merged == prior_answers:
        return
    attribution = assessor_name.strip() or (existing.assessor_name if existing else "Autosave")
    storage.save_assessment(institute, attribution, merged)


def render_export_import(institute: str, assessor_name: str, current_answers: dict) -> None:
    """Client-side YAML export/import round trip, independent of the
    server-side saved/ store."""
    export_col, import_col = st.sidebar.columns(2)
    export_col.download_button(
        "⬇️ Export",
        data=storage.export_yaml(institute, assessor_name, current_answers),
        file_name=f"{institute}_assessment.yaml",
        mime="application/x-yaml",
        width="stretch",
        disabled=not current_answers,
    )

    uploaded_file = import_col.file_uploader(
        "⬆️ Import", type=["yaml", "yml"], label_visibility="collapsed", key=f"import_uploader_{institute}"
    )
    if uploaded_file is not None:
        try:
            imported = storage.import_yaml(uploaded_file.getvalue().decode("utf-8"), institute)
        except ValueError:
            st.sidebar.error("Could not read that file — is it a valid exported assessment YAML?")
        else:
            if imported.institute != institute:
                source_label = (
                    INSTITUTES[imported.institute].short if imported.institute in INSTITUTES else imported.institute
                )
                st.sidebar.warning(f"File was exported for {source_label} — will be applied to {INSTITUTES[institute].short}.")
            if st.sidebar.button("Apply imported answers", width="stretch", key=f"apply_import_{institute}"):
                st.session_state.update(imported.answers)
                st.rerun()
