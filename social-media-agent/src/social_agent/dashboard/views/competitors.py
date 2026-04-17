"""Competitor Intel — Scan, analyze, and compare competitor accounts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.config import get_settings
from social_agent.db.database import CompetitorPostRecord, get_session, init_db
from social_agent.profiles.loader import load_profile


def render() -> None:
    init_db()

    st.markdown("# Competitor Intelligence")
    st.markdown("Monitor competitor accounts and learn from their strategies.")

    profile = load_profile()
    settings = get_settings()

    # Tracked competitors
    all_competitors = profile.competitors.twitter + profile.competitors.instagram

    if all_competitors:
        st.markdown("### Tracked Competitors")
        cols = st.columns(min(len(all_competitors), 5))
        for i, comp in enumerate(all_competitors):
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div class="card" style="text-align: center; padding: 0.75rem;">'
                    f'<p style="font-weight: 600; font-size: 1rem; color: #6366F1; margin: 0;">{comp}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Scan button
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col2:
        scan_clicked = st.button(
            "Scan Competitors",
            type="primary",
            use_container_width=True,
        )

    if scan_clicked:
        if not settings.twitter_bearer_token:
            st.error(
                "Competitor scanning needs a **Twitter bearer token**. "
                "Add `TWITTER_BEARER_TOKEN` in Settings to pull competitor posts."
            )
        elif not all_competitors:
            st.warning("No competitors configured. Edit `profiles/default.yaml` → `competitors` to add some.")
        else:
            with st.spinner("Scanning competitor accounts..."):
                try:
                    from social_agent.research.competitors import scrape_competitors
                    posts = scrape_competitors(profile)
                    st.success(f"Scraped {len(posts)} posts from competitor accounts!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    # Analyze button
    if st.button("Analyze Strategies"):
        if not settings.google_api_key:
            st.error("Add your Gemini API key in Settings to run analysis.")
        else:
            with st.spinner("Analyzing competitor strategies with Gemini..."):
                try:
                    from social_agent.research.competitors import analyze_competitors
                    report = analyze_competitors(profile)
                    if report:
                        st.success(f"Analyzed {len(report)} competitor accounts!")
                        for comp in report:
                            st.markdown(
                                f'<div class="card">'
                                f'<p style="font-weight: 600; color: #6366F1; font-size: 1.1rem;">@{comp.handle}</p>'
                                f'<p>Avg Likes: {comp.avg_likes:.0f} | Avg Shares: {comp.avg_shares:.0f} | '
                                f'Avg Comments: {comp.avg_comments:.0f}</p>'
                                f'{"<p style=&quot;color: #94A3B8;&quot;>Top topics: " + ", ".join(comp.top_topics[:5]) + "</p>" if comp.top_topics else ""}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    st.markdown("---")

    # Display data from DB
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
                    "posts": posts,
                    "top_post": max(posts, key=lambda p: p.likes),
                }

        if competitor_data:
            # Comparison chart
            st.markdown("### Engagement Comparison")
            handles = list(competitor_data.keys())
            avg_likes = [competitor_data[h]["avg_likes"] for h in handles]
            avg_shares = [competitor_data[h]["avg_shares"] for h in handles]
            avg_comments = [competitor_data[h]["avg_comments"] for h in handles]

            fig = go.Figure(data=[
                go.Bar(name="Avg Likes", x=handles, y=avg_likes, marker_color="#6366F1"),
                go.Bar(name="Avg Shares", x=handles, y=avg_shares, marker_color="#EC4899"),
                go.Bar(name="Avg Comments", x=handles, y=avg_comments, marker_color="#10B981"),
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
                with st.expander(f"@{handle} — {data['count']} posts scraped"):
                    st.markdown(
                        f'<div class="card">'
                        f'<p style="font-weight: 600; color: #10B981;">Best performing post:</p>'
                        f'<p style="line-height: 1.5;">{top.text[:400]}{"..." if len(top.text) > 400 else ""}</p>'
                        f'<p style="color: #94A3B8; font-size: 0.85rem;">'
                        f'{top.likes:,} likes | {top.shares:,} shares | {top.comments:,} comments</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    # Show recent posts
                    for p in data["posts"][:5]:
                        st.markdown(
                            f'<div class="card" style="padding: 0.75rem;">'
                            f'<p style="margin: 0;">{p.text[:200]}{"..." if len(p.text) > 200 else ""}</p>'
                            f'<p style="color: #475569; font-size: 0.8rem; margin: 0.25rem 0 0 0;">'
                            f'{p.likes} likes | {p.shares} shares</p></div>',
                            unsafe_allow_html=True,
                        )
        else:
            st.markdown(
                '<div class="card" style="text-align: center; padding: 3rem;">'
                '<p style="font-size: 1.2rem; color: #94A3B8;">No competitor data yet</p>'
                '<p style="color: #475569;">Click "Scan Competitors" to fetch their latest content.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
    finally:
        session.close()

    if not settings.twitter_bearer_token:
        st.info("Set `TWITTER_BEARER_TOKEN` in `.env` to enable competitor scanning.")

