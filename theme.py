"""Shared Streamlit UI styling. Injects one CSS block so the Assessment page
and every page under pages/ render text at the same sizes -- keeping this in
one place avoids the two copies drifting apart.
"""

import streamlit as st

_CSS = """
<style>
html, body, [class*="st-"] { font-size: 1.15rem !important; }
div[data-testid="stMarkdownContainer"] p, div[data-testid="stMarkdownContainer"] li { font-size: 1.15rem !important; line-height: 1.6 !important; }
div[data-testid="stCaptionContainer"] p { font-size: 1.05rem !important; line-height: 1.5 !important; }
div[data-testid="stCheckbox"] label p { font-size: 1.15rem !important; line-height: 1.6 !important; }
div[data-testid="stRadio"] label p { font-size: 1.15rem !important; line-height: 1.6 !important; }
div[data-testid="stExpander"] summary p { font-size: 1.2rem !important; }
div[data-testid="stDataFrame"] * { font-size: 1.05rem !important; }
h1 { font-size: 2.3rem !important; }
h2 { font-size: 1.8rem !important; }
h3 { font-size: 1.5rem !important; }
h1, h2, h3 { line-height: 1.35; }
[data-testid="stSidebar"] h2 { font-size: 1.05rem !important; margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.8; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { border: none !important; background: transparent !important; padding: 0 !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button { width: 100% !important; }
</style>
"""


def apply_custom_css() -> None:
    """Bump font size / line-height beyond Streamlit defaults for readability.
    Call once near the top of every page."""
    st.markdown(_CSS, unsafe_allow_html=True)
