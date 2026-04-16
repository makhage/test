"""Analytics — Engagement charts, performance reports, audience insights."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.analytics.reporter import generate_report
from social_agent.analytics.tracker import get_analytics_history
from social_agent.db.database import init_db

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")
inject_custom_css()

st.markdown("# Analytics")
st.markdown("Track performance and understand what's working.")

init_db()

# Time period selector
period = st.selectbox("Time Period", ["7 days", "14 days", "30 days", "90 days"])
days = int(period.split()[0])

# Generate report
report = generate_report(days=days)

# Top-level metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        render_metric_card("Total Posts", report.get("total_posts", 0)),
        unsafe_allow_html=True,
    )
with col2:
    engagement = report.get("total_engagement", {})
    st.markdown(
        render_metric_card("Total Likes", engagement.get("likes", 0)),
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        render_metric_card("Total Shares", engagement.get("shares", 0)),
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        render_metric_card("Total Comments", engagement.get("comments", 0)),
        unsafe_allow_html=True,
    )

st.markdown("---")

# Charts
records = get_analytics_history(days=days)

if records:
    # Engagement over time
    st.markdown("### Engagement Over Time")
    dates = [r["recorded_at"] for r in records]
    likes = [r["likes"] for r in records]
    shares = [r["shares"] for r in records]
    comments = [r["comments"] for r in records]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=likes, name="Likes", line=dict(color="#6366F1")))
    fig.add_trace(go.Scatter(x=dates, y=shares, name="Shares", line=dict(color="#EC4899")))
    fig.add_trace(go.Scatter(x=dates, y=comments, name="Comments", line=dict(color="#10B981")))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Platform breakdown
    platform_stats = report.get("platform_breakdown", {})
    if platform_stats:
        st.markdown("### Platform Breakdown")
        platforms = list(platform_stats.keys())
        plat_likes = [platform_stats[p]["likes"] for p in platforms]

        fig2 = go.Figure(data=[
            go.Bar(
                x=platforms,
                y=plat_likes,
                marker_color=["#1DA1F2", "#E4405F", "#00F2EA"][:len(platforms)],
            )
        ])
        fig2.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8"),
            yaxis_title="Total Likes",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Top posts
    top_posts = report.get("top_posts", [])
    if top_posts:
        st.markdown("### Top Performing Posts")
        for i, post in enumerate(top_posts, 1):
            total = post["likes"] + post["shares"] + post["comments"]
            st.markdown(
                f'<div class="card">'
                f'<p style="font-weight: 600;">#{i} — {post["platform"].upper()}</p>'
                f'<p>Likes: {post["likes"]} | Shares: {post["shares"]} | Comments: {post["comments"]} | Total: {total}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info(
        "No analytics data yet. Post content and track engagement to see charts here.\n\n"
        "```bash\nsocial-agent analytics report --last 7d\n```"
    )
