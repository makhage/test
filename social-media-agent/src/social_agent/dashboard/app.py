"""Main Streamlit dashboard app with landing page and sidebar navigation."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.db.database import (
    ScheduledPostRecord,
    ViralPostRecord,
    NicheIntelligenceRecord,
    AnalyticsRecord,
    init_db,
    get_session,
)

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

# Fetch real metrics
session = get_session()
try:
    from datetime import datetime, timedelta

    week_ago = datetime.utcnow() - timedelta(days=7)
    posts_this_week = session.query(ScheduledPostRecord).filter(
        ScheduledPostRecord.created_at >= week_ago
    ).count()
    pending_count = session.query(ScheduledPostRecord).filter_by(status="pending").count()

    analytics = session.query(AnalyticsRecord).filter(
        AnalyticsRecord.recorded_at >= week_ago
    ).all()
    avg_engagement = "—"
    if analytics:
        total = sum(a.likes + a.shares + a.comments for a in analytics)
        avg_engagement = f"{total / len(analytics):.0f}"

    intel = session.query(NicheIntelligenceRecord).order_by(
        NicheIntelligenceRecord.generated_at.desc()
    ).first()
    import json
    trending_count = len(json.loads(intel.trending_topics)) if intel else 0
finally:
    session.close()

# Key metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(render_metric_card("Posts This Week", posts_this_week), unsafe_allow_html=True)
with col2:
    st.markdown(render_metric_card("Pending Approval", pending_count), unsafe_allow_html=True)
with col3:
    st.markdown(render_metric_card("Avg Engagement", avg_engagement), unsafe_allow_html=True)
with col4:
    st.markdown(render_metric_card("Trending Topics", trending_count), unsafe_allow_html=True)

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
session = get_session()
try:
    recent = (
        session.query(ScheduledPostRecord)
        .order_by(ScheduledPostRecord.created_at.desc())
        .limit(5)
        .all()
    )
    if recent:
        for post in recent:
            status_color = {
                "draft": "#64748B", "pending": "#F59E0B",
                "approved": "#10B981", "published": "#6366F1", "rejected": "#EF4444",
            }.get(post.status, "#94A3B8")
            content_preview = post.content_json[:120].replace('"', '&quot;')
            st.markdown(
                f'<div class="card" style="padding: 1rem;">'
                f'<span style="color: {status_color}; font-weight: 600; text-transform: uppercase; '
                f'font-size: 0.7rem; letter-spacing: 0.05em;">{post.status}</span> '
                f'<span style="color: #94A3B8; font-size: 0.8rem;">{post.platform} / {post.content_type}</span>'
                f'<p style="margin: 0.25rem 0 0 0; color: #CBD5E1; font-size: 0.9rem;">{content_preview}...</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No activity yet. Head to the Content Studio to generate your first post!")
finally:
    session.close()

# Getting started
with st.expander("Getting Started"):
    st.markdown("""
    1. **Configure API keys** — Add your `ANTHROPIC_API_KEY` (required) and platform API keys to `.env`
    2. **Edit your profile** — Go to the Profile page to set your voice, brand colors, and topics
    3. **Scan your niche** — Use the Trend Radar to discover what's going viral
    4. **Generate content** — The Content Studio creates tweets, carousels, and TikTok captions
    5. **Review & approve** — All content goes through the Approval Queue before posting
    6. **Track performance** — The Analytics page shows what's working
    """)
