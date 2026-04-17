"""Chat with the agent — natural language content planning."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import chat

st.set_page_config(page_title="Chat", page_icon="", layout="wide")
inject_custom_css()

chat.render()
