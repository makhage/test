"""Content creation — studio, A/B testing, calendar."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import create_content, ab_testing, calendar_view

st.set_page_config(page_title="Create", page_icon="", layout="wide")
inject_custom_css()

st.caption("Stage 3 of 5 · Create")

tab_studio, tab_ab, tab_cal = st.tabs([
    "Content Studio",
    "A/B Testing",
    "Calendar",
])

with tab_studio:
    create_content.render()

with tab_ab:
    ab_testing.render()

with tab_cal:
    calendar_view.render()
