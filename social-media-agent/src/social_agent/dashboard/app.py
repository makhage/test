"""Main Streamlit dashboard — clean home page."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
from datetime import datetime, timedelta

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.db.database import (
    ScheduledPostRecord,
    NicheIntelligenceRecord,
    AnalyticsRecord,
    init_db,
    get_session,
)

st.set_page_config(
    page_title="Social Agent",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject_custom_css()

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<div class="sidebar-logo"><h1>Social Agent</h1></div>',
        unsafe_allow_html=True,
    )

# ── Header ──────────────────────────────────────────────────────────────────

st.markdown("# Social Agent")
st.caption("AI-powered content automation for creators")

# ── Setup Banner ────────────────────────────────────────────────────────────

from social_agent.config import get_settings
from social_agent.auth import _load_tokens, _tokens_expired

_settings = get_settings()
_has_anthropic = bool(_settings.anthropic_api_key)
_has_openai_oauth = bool(_settings.openai_oauth_client_id)
_has_openai_key = bool(_settings.openai_api_key)
_oauth_tokens = _load_tokens()
_oauth_signed_in = _has_openai_oauth and _oauth_tokens and not _tokens_expired(_oauth_tokens)
_has_openai = _oauth_signed_in or _has_openai_key

if not _has_anthropic or not _has_openai:
    st.markdown(
        '<div class="card" style="border:1px solid #F59E0B40;background:#F59E0B10;padding:1.25rem;">'
        '<h4 style="margin:0 0 0.75rem 0;color:#F59E0B;">Setup Required</h4>'
        '<p style="color:#CBD5E1;margin:0 0 0.75rem 0;">Connect your API keys to start generating content.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    setup_col1, setup_col2 = st.columns(2)

    with setup_col1:
        if _has_anthropic:
            st.success("Anthropic API Key  —  Connected")
        else:
            st.error("Anthropic API Key  —  Not set")
            st.caption("Add `ANTHROPIC_API_KEY` to your `.env` file")

    with setup_col2:
        if _oauth_signed_in:
            st.success("OpenAI  —  Signed in via OAuth")
        elif _has_openai_key:
            st.success("OpenAI API Key  —  Connected")
        elif _has_openai_oauth:
            st.warning("OpenAI OAuth  —  Not signed in yet")
            if st.button("Sign in to OpenAI", type="primary", use_container_width=True):
                st.switch_page("pages/13_Settings.py")
        else:
            st.error("OpenAI  —  Not configured")
            st.caption("Add `OPENAI_OAUTH_CLIENT_ID` or `OPENAI_API_KEY` to `.env`")

    if st.button("Go to Settings", use_container_width=True):
        st.switch_page("pages/13_Settings.py")

    st.markdown("")

# ── Metrics ─────────────────────────────────────────────────────────────────

session = get_session()
try:
    week_ago = datetime.utcnow() - timedelta(days=7)

    posts_this_week = session.query(ScheduledPostRecord).filter(
        ScheduledPostRecord.created_at >= week_ago
    ).count()

    pending_count = session.query(ScheduledPostRecord).filter_by(
        status="pending"
    ).count()

    analytics = session.query(AnalyticsRecord).filter(
        AnalyticsRecord.recorded_at >= week_ago
    ).all()
    if analytics:
        total = sum(a.likes + a.shares + a.comments for a in analytics)
        avg_engagement = f"{total / len(analytics):.0f}"
    else:
        avg_engagement = "—"

    published_count = session.query(ScheduledPostRecord).filter_by(
        status="published"
    ).count()
finally:
    session.close()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(render_metric_card("Created", posts_this_week), unsafe_allow_html=True)
with col2:
    st.markdown(render_metric_card("Pending Review", pending_count), unsafe_allow_html=True)
with col3:
    st.markdown(render_metric_card("Published", published_count), unsafe_allow_html=True)
with col4:
    st.markdown(render_metric_card("Avg Engagement", avg_engagement), unsafe_allow_html=True)

st.markdown("")

# ── Quick Actions ───────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        '<div class="card">'
        '<h4 style="margin:0 0 0.5rem 0;">Create Content</h4>'
        '<p style="color:#94A3B8;margin:0;font-size:0.9rem;">'
        'Generate tweets, carousels, and TikTok captions</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Open Studio", use_container_width=True, type="primary"):
        st.switch_page("pages/1_Create_Content.py")

with col2:
    st.markdown(
        '<div class="card">'
        '<h4 style="margin:0 0 0.5rem 0;">Review Queue</h4>'
        '<p style="color:#94A3B8;margin:0;font-size:0.9rem;">'
        f'{pending_count} post{"s" if pending_count != 1 else ""} waiting for approval</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Review Posts", use_container_width=True):
        st.switch_page("pages/2_Review_Queue.py")

with col3:
    st.markdown(
        '<div class="card">'
        '<h4 style="margin:0 0 0.5rem 0;">Scan Trends</h4>'
        '<p style="color:#94A3B8;margin:0;font-size:0.9rem;">'
        'Discover what\'s going viral in your niche</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("View Trends", use_container_width=True):
        st.switch_page("pages/7_Trends.py")

# ── Recent Activity ─────────────────────────────────────────────────────────

st.markdown("---")
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
            status_colors = {
                "draft": "#64748B", "pending": "#F59E0B",
                "approved": "#10B981", "published": "#6366F1",
                "rejected": "#EF4444",
            }
            color = status_colors.get(post.status, "#94A3B8")
            preview = post.content_json[:100].replace('"', '&quot;')
            st.markdown(
                f'<div class="card" style="padding:0.75rem 1rem;">'
                f'<span style="color:{color};font-weight:600;text-transform:uppercase;'
                f'font-size:0.7rem;letter-spacing:0.05em;">{post.status}</span> '
                f'<span style="color:#64748B;font-size:0.8rem;">'
                f'{post.platform} &middot; {post.content_type}</span>'
                f'<p style="margin:0.25rem 0 0;color:#CBD5E1;font-size:0.85rem;">'
                f'{preview}...</p></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No activity yet. Open the Content Studio to create your first post.")
finally:
    session.close()
