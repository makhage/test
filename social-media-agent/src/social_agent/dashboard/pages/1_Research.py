"""Research hub — niche, audience, trends, competitors in one place."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import (
    niche_scanner,
    reddit_intel,
    trends,
    competitors,
)

st.set_page_config(page_title="Research", page_icon="", layout="wide")
inject_custom_css()

st.caption("Stage 1 of 5 · Research")

tab_niche, tab_reddit, tab_trends, tab_comp = st.tabs([
    "Niche Scanner",
    "Reddit Intel",
    "Trends",
    "Competitors",
])

with tab_niche:
    niche_scanner.render()

with tab_reddit:
    reddit_intel.render()

with tab_trends:
    trends.render()

with tab_comp:
    competitors.render()
