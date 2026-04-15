"""Trend Radar — Live trending topics, viral hooks, and format insights."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.db.database import ViralPostRecord, init_db, get_session
from social_agent.research.analyzer import get_latest_intelligence

st.set_page_config(page_title="Trend Radar", page_icon="📡", layout="wide")
inject_custom_css()

st.markdown("# Trend Radar")
st.markdown("What's going viral in your niche right now.")

init_db()

# Get latest intelligence
intel = get_latest_intelligence()

if intel:
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            render_metric_card("Trending Topics", len(intel.trending_topics)),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            render_metric_card("Winning Hooks", len(intel.winning_hooks)),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            render_metric_card("Posts Analyzed", intel.source_post_count),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Trending topics
    st.markdown("### Trending Topics")
    for i, topic in enumerate(intel.trending_topics, 1):
        st.markdown(
            f'<div class="card" style="display: inline-block; margin-right: 0.5rem; padding: 0.5rem 1rem;">'
            f'<span style="color: #6366F1; font-weight: 600;">#{i}</span> {topic}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Winning hooks
    st.markdown("### Winning Hooks")
    for hook in intel.winning_hooks:
        st.markdown(
            f'<div class="card">'
            f'<p style="font-weight: 600; color: #EC4899;">{hook.pattern}</p>'
            f'<p style="color: #94A3B8; font-style: italic;">"{hook.example}"</p>'
            f'{"<p style=\\"color: #475569;\\">Seen " + str(hook.frequency) + " times</p>" if hook.frequency else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Top formats
    if intel.top_formats:
        st.markdown("### Top Performing Formats")
        for fmt in intel.top_formats:
            st.markdown(f"- **{fmt}**")

    # Engagement benchmarks
    benchmarks = intel.engagement_benchmarks
    if benchmarks:
        st.markdown("### Engagement Benchmarks")
        cols = st.columns(3)
        for i, (key, val) in enumerate(benchmarks.items()):
            with cols[i % 3]:
                st.metric(key.replace("_", " ").title(), f"{val:,.0f}")

    st.markdown(f"*Last updated: {intel.generated_at.strftime('%Y-%m-%d %H:%M')}*")

else:
    st.info(
        "No trend data yet. Scan your niche to populate the Trend Radar:\n\n"
        "```bash\nsocial-agent research scan\n```"
    )

# Swipe file section
st.markdown("---")
st.markdown("### Swipe File")
st.markdown("High-performing content saved for inspiration.")

session = get_session()
try:
    viral_posts = (
        session.query(ViralPostRecord)
        .order_by(ViralPostRecord.likes.desc())
        .limit(10)
        .all()
    )
    if viral_posts:
        for post in viral_posts:
            st.markdown(
                f'<div class="card">'
                f'<p style="color: #94A3B8; font-size: 0.8rem;">'
                f'[{post.platform.upper()}] {post.likes:,} likes | {post.shares:,} shares</p>'
                f'<p>{post.text[:300]}{"..." if len(post.text) > 300 else ""}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Swipe file is empty. Run a niche scan to find viral content.")
finally:
    session.close()
