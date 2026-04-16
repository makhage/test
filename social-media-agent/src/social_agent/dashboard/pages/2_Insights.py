"""Insights — synthesized intelligence from all research."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import intelligence

st.set_page_config(page_title="Insights", page_icon="", layout="wide")
inject_custom_css()

st.caption("Stage 2 of 5 · Insights")

intelligence.render()
