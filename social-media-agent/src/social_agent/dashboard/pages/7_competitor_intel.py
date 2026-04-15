"""Competitor Intel — Side-by-side performance comparison."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.db.database import CompetitorPostRecord, get_session, init_db
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="Competitor Intel", page_icon="🔍", layout="wide")
inject_custom_css()

st.markdown("# Competitor Intelligence")
st.markdown("Monitor competitor accounts and learn from their strategies.")

init_db()
profile = load_profile()

# Show tracked competitors
all_competitors = profile.competitors.twitter + profile.competitors.instagram
if all_competitors:
    st.markdown("### Tracked Competitors")
    cols = st.columns(min(len(all_competitors), 4))
    for i, comp in enumerate(all_competitors):
        with cols[i % 4]:
            st.markdown(
                f'<div class="card" style="text-align: center;">'
                f'<p style="font-weight: 600; font-size: 1.1rem; color: #6366F1;">{comp}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown("---")

# Competitor data from DB
session = get_session()
try:
    competitor_handles = [c.lstrip("@") for c in profile.competitors.twitter]
    competitor_data: dict[str, dict] = {}

    for handle in competitor_handles:
        posts = (
            session.query(CompetitorPostRecord)
            .filter_by(handle=handle)
            .order_by(CompetitorPostRecord.scraped_at.desc())
            .limit(50)
            .all()
        )
        if posts:
            competitor_data[handle] = {
                "count": len(posts),
                "avg_likes": sum(p.likes for p in posts) / len(posts),
                "avg_shares": sum(p.shares for p in posts) / len(posts),
                "avg_comments": sum(p.comments for p in posts) / len(posts),
                "top_post": max(posts, key=lambda p: p.likes),
            }

    if competitor_data:
        # Comparison chart
        st.markdown("### Engagement Comparison")
        handles = list(competitor_data.keys())
        avg_likes = [competitor_data[h]["avg_likes"] for h in handles]
        avg_shares = [competitor_data[h]["avg_shares"] for h in handles]

        fig = go.Figure(data=[
            go.Bar(name="Avg Likes", x=handles, y=avg_likes, marker_color="#6366F1"),
            go.Bar(name="Avg Shares", x=handles, y=avg_shares, marker_color="#EC4899"),
        ])
        fig.update_layout(
            barmode="group",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Top posts per competitor
        st.markdown("### Top Posts by Competitor")
        for handle, data in competitor_data.items():
            top = data["top_post"]
            st.markdown(
                f'<div class="card">'
                f'<p style="font-weight: 600; color: #6366F1;">@{handle}</p>'
                f'<p>{top.text[:300]}{"..." if len(top.text) > 300 else ""}</p>'
                f'<p style="color: #94A3B8; font-size: 0.85rem;">'
                f'{top.likes:,} likes | {top.shares:,} shares | {top.comments:,} comments</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "No competitor data yet. Scan competitors:\n\n"
            "```bash\nsocial-agent research competitors\n```"
        )
finally:
    session.close()
