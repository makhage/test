"""Main Streamlit dashboard — workflow-driven home page."""

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
    RedditPostRecord,
    init_db,
    get_session,
)
from social_agent.config import get_settings

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
    st.caption("**Workflow**")
    st.caption("1 Research → 2 Insights → 3 Create → 4 Publish → 5 Measure")

# ── Header ──────────────────────────────────────────────────────────────────

st.markdown("# Welcome back")

# ── Setup gate ──────────────────────────────────────────────────────────────

_settings = get_settings()
if not _settings.google_api_key:
    st.markdown(
        '<div class="card" style="border:1px solid #F59E0B40;background:#F59E0B10;padding:1.25rem;">'
        '<h4 style="margin:0 0 0.5rem 0;color:#F59E0B;">One-time setup needed</h4>'
        '<p style="color:#CBD5E1;margin:0;">Connect your Gemini API key to unlock everything.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Connect Gemini", type="primary", use_container_width=True):
        st.switch_page("pages/6_Settings.py")
    st.stop()

# ── Pipeline status — what's done, what's next ─────────────────────────────

session = get_session()
try:
    has_niche = session.query(NicheIntelligenceRecord).count() > 0
    has_reddit = session.query(RedditPostRecord).count() > 0
    drafts = session.query(ScheduledPostRecord).filter_by(status="draft").count()
    pending = session.query(ScheduledPostRecord).filter_by(status="pending").count()
    published = session.query(ScheduledPostRecord).filter_by(status="published").count()

    week_ago = datetime.utcnow() - timedelta(days=7)
    analytics = session.query(AnalyticsRecord).filter(
        AnalyticsRecord.recorded_at >= week_ago
    ).all()
    has_analytics = len(analytics) > 0
finally:
    session.close()

# Determine next step
next_step = None
if not has_niche:
    next_step = {
        "title": "Scan your niche",
        "caption": "Paste your Linktree and let the agent discover your topics, audience, and best subreddits.",
        "page": "pages/1_Research.py",
        "button": "Start Niche Scanner",
    }
elif not has_reddit:
    next_step = {
        "title": "Validate with real audience data",
        "caption": "Mine the subreddits you selected to see what questions, hot takes, and phrases your audience actually uses.",
        "page": "pages/1_Research.py",
        "button": "Run Reddit Intel",
    }
elif drafts == 0 and pending == 0:
    next_step = {
        "title": "Create your first post",
        "caption": "Generate tweets, carousels, or TikTok captions in your voice using everything we've learned.",
        "page": "pages/3_Create.py",
        "button": "Open Content Studio",
    }
elif pending > 0:
    next_step = {
        "title": f"Review {pending} pending post{'s' if pending != 1 else ''}",
        "caption": "Approve or reject content before it goes live.",
        "page": "pages/4_Publish.py",
        "button": "Open Review Queue",
    }
elif not has_analytics and published > 0:
    next_step = {
        "title": "Check your performance",
        "caption": "See what's landing and let the agent learn from it.",
        "page": "pages/5_Analytics.py",
        "button": "View Analytics",
    }
else:
    next_step = {
        "title": "Keep creating",
        "caption": "Generate more content, or check the Trends page for fresh ideas.",
        "page": "pages/3_Create.py",
        "button": "Create More Content",
    }

st.markdown(
    f'<div class="card" style="background:linear-gradient(135deg,#6366F120,#EC489920);'
    f'border:1px solid #6366F140;padding:1.5rem;">'
    f'<div style="color:#94A3B8;font-size:0.75rem;text-transform:uppercase;'
    f'letter-spacing:0.1em;margin-bottom:0.5rem;">Next Step</div>'
    f'<h3 style="margin:0 0 0.25rem 0;">{next_step["title"]}</h3>'
    f'<p style="color:#CBD5E1;margin:0;">{next_step["caption"]}</p>'
    f'</div>',
    unsafe_allow_html=True,
)

if st.button(next_step["button"], type="primary", use_container_width=True):
    st.switch_page(next_step["page"])

st.markdown("")

# ── Pipeline progress ───────────────────────────────────────────────────────

st.markdown("### Your Pipeline")

steps = [
    ("Research", has_niche, "1_1_Niche_Scanner.py"),
    ("Audience Data", has_reddit, "1_2_Reddit_Intel.py"),
    ("Drafts Created", (drafts + pending + published) > 0, "3_1_Create_Content.py"),
    ("Published", published > 0, "4_1_Review_Queue.py"),
    ("Analytics", has_analytics, "5_Analytics.py"),
]

cols = st.columns(len(steps))
for i, (label, done, page) in enumerate(steps):
    with cols[i]:
        icon = "✓" if done else "○"
        color = "#10B981" if done else "#64748B"
        st.markdown(
            f'<div style="text-align:center;padding:1rem;border:1px solid {color}40;'
            f'border-radius:8px;background:{color}10;">'
            f'<div style="color:{color};font-size:1.5rem;font-weight:700;">{icon}</div>'
            f'<div style="color:#CBD5E1;font-size:0.8rem;margin-top:0.25rem;">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Current stats ───────────────────────────────────────────────────────────

st.markdown("### At a Glance")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(render_metric_card("Drafts", drafts), unsafe_allow_html=True)
with col2:
    st.markdown(render_metric_card("Pending Review", pending), unsafe_allow_html=True)
with col3:
    st.markdown(render_metric_card("Published", published), unsafe_allow_html=True)
with col4:
    avg_engagement = "—"
    if analytics:
        total = sum(a.likes + a.shares + a.comments for a in analytics)
        avg_engagement = f"{total // len(analytics)}"
    st.markdown(render_metric_card("Avg Engagement", avg_engagement), unsafe_allow_html=True)
