"""Publish — review queue and reply inbox."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import review_queue, reply_inbox

st.set_page_config(page_title="Publish", page_icon="", layout="wide")
inject_custom_css()

st.caption("Stage 4 of 5 · Publish")

tab_review, tab_replies = st.tabs([
    "Review Queue",
    "Reply Inbox",
])

with tab_review:
    review_queue.render()

with tab_replies:
    reply_inbox.render()
