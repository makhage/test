"""Main Streamlit dashboard app with landing page and sidebar navigation."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.db.database import init_db

# Page config
st.set_page_config(
    page_title="Social Media Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
init_db()

# Inject custom CSS
inject_custom_css()

# Sidebar branding
with st.sidebar:
    st.markdown(
        '<div class="sidebar-logo"><h1>Social Agent</h1></div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

# Landing page / Home
st.markdown("# Welcome to Social Agent")
st.markdown("Your AI-powered social media content automation dashboard.")

st.markdown("---")

# Key metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(render_metric_card("Posts This Week", "0"), unsafe_allow_html=True)

with col2:
    st.markdown(render_metric_card("Pending Approval", "0"), unsafe_allow_html=True)

with col3:
    st.markdown(render_metric_card("Avg Engagement", "—"), unsafe_allow_html=True)

with col4:
    st.markdown(render_metric_card("Trending Topics", "0"), unsafe_allow_html=True)

st.markdown("---")

# Quick actions
st.markdown("### Quick Actions")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("Generate Tweet", use_container_width=True):
        st.switch_page("pages/1_content_studio.py")

with col2:
    if st.button("Create Carousel", use_container_width=True):
        st.switch_page("pages/1_content_studio.py")

with col3:
    if st.button("Scan Trends", use_container_width=True):
        st.switch_page("pages/6_trend_radar.py")

with col4:
    if st.button("View Analytics", use_container_width=True):
        st.switch_page("pages/5_analytics.py")

st.markdown("---")

# Recent activity
st.markdown("### Recent Activity")
st.info("No recent activity. Generate your first piece of content to get started!")

# Tips
with st.expander("Getting Started"):
    st.markdown("""
    1. **Set up your profile** — Edit `profiles/default.yaml` with your voice, brand, and topics
    2. **Scan your niche** — Run `social-agent research scan` to find viral content in your space
    3. **Generate content** — Use the Content Studio or CLI to create tweets, carousels, and TikTok captions
    4. **Review & approve** — All content goes through an approval queue before posting
    5. **Track performance** — Monitor engagement and let the agent learn from what works
    """)
