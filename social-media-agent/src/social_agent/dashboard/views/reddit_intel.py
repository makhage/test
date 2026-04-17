"""Reddit Intelligence — Mine subreddits for content ideas, audience questions, and real language."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st
import plotly.graph_objects as go

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.config import get_settings
from social_agent.db.database import RedditPostRecord, get_session, init_db
from social_agent.profiles.loader import load_profile


def render() -> None:
    init_db()

    st.markdown("# Reddit Intelligence")
    st.markdown("Mine subreddits for trending topics, audience questions, hot takes, and authentic language.")

    profile = load_profile()
    settings = get_settings()

    # --- Subreddit source: auto-discovered vs manual ---
    from social_agent.research.niche_profiler import get_discovered_subreddits
    discovered_subs = get_discovered_subreddits()
    active_subs = st.session_state.get("active_subreddits", discovered_subs if discovered_subs else profile.reddit.subreddits)
    source_label = "Auto-Discovered" if discovered_subs else "Manual Config"

    st.markdown("### Active Subreddits")
    if discovered_subs:
        st.caption(f"🧬 **{source_label}** — These were auto-discovered by analyzing your content. Go to Niche Profile to re-analyze.")
    else:
        st.caption(f"📝 **{source_label}** — From `profiles/default.yaml`. Run Niche Profile analysis to auto-discover subreddits.")

    if active_subs:
        cols = st.columns(min(len(active_subs), 5))
        for i, sub in enumerate(active_subs):
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div class="card" style="text-align: center; padding: 0.6rem;">'
                    f'<p style="font-weight: 600; color: #FF4500; margin: 0;">r/{sub}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("No subreddits configured. Go to Niche Profile to auto-discover them, or add manually in `profiles/default.yaml`.")

    # --- Scan controls ---
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sort_by = st.selectbox("Sort posts by", ["hot", "top", "rising", "new"])
    with col2:
        limit_per_sub = st.number_input("Posts per subreddit", min_value=5, max_value=100, value=25)
    with col3:
        st.markdown("<div style='padding-top: 1.7rem;'></div>", unsafe_allow_html=True)
        scan_clicked = st.button(
            "Scan Subreddits",
            type="primary",
            use_container_width=True,
        )

    if scan_clicked:
        if not active_subs:
            st.warning("No subreddits to scan. Run Niche Profile first to auto-discover them.")
        else:
            with st.spinner(f"Scanning {len(active_subs)} subreddits..."):
                try:
                    from social_agent.research.reddit_scraper import scrape_all_subreddits
                    posts = scrape_all_subreddits(
                        profile,
                        sort=sort_by,
                        limit_per_sub=limit_per_sub,
                        override_subreddits=active_subs,
                    )
                    st.success(f"Scraped {len(posts)} posts from {len(active_subs)} subreddits!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    st.markdown("---")

    # --- Display data ---
    session = get_session()
    try:
        total_posts = session.query(RedditPostRecord).count()

        if total_posts > 0:
            # Stats overview
            from social_agent.research.reddit_scraper import get_subreddit_stats
            stats = get_subreddit_stats()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(render_metric_card("Total Posts", total_posts), unsafe_allow_html=True)
            with col2:
                st.markdown(
                    render_metric_card("Subreddits", len(stats)),
                    unsafe_allow_html=True,
                )
            with col3:
                max_upvotes = max((s["max_upvotes"] for s in stats.values()), default=0)
                st.markdown(
                    render_metric_card("Top Post Score", f"{max_upvotes:,}"),
                    unsafe_allow_html=True,
                )

            # Subreddit comparison chart
            if stats:
                st.markdown("### Subreddit Engagement")
                sub_names = list(stats.keys())
                avg_upvotes = [stats[s]["avg_upvotes"] for s in sub_names]
                avg_comments = [stats[s]["avg_comments"] for s in sub_names]

                fig = go.Figure(data=[
                    go.Bar(name="Avg Upvotes", x=[f"r/{s}" for s in sub_names], y=avg_upvotes, marker_color="#FF4500"),
                    go.Bar(name="Avg Comments", x=[f"r/{s}" for s in sub_names], y=avg_comments, marker_color="#6366F1"),
                ])
                fig.update_layout(
                    barmode="group",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94A3B8"),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # --- Content by type ---
            tab_questions, tab_hot_takes, tab_tutorials, tab_trending, tab_all = st.tabs([
                "Audience Questions", "Hot Takes", "Tutorials", "Trending", "All Posts"
            ])

            with tab_questions:
                st.markdown("### What Your Audience Is Asking")
                st.caption("These are direct content topic ideas — answer these as tweets, carousels, or TikToks.")
                questions = (
                    session.query(RedditPostRecord)
                    .filter(RedditPostRecord.content_type == "question")
                    .order_by(RedditPostRecord.upvotes.desc())
                    .limit(20)
                    .all()
                )
                if questions:
                    for q in questions:
                        comments = json.loads(q.top_comments) if q.top_comments else []
                        st.markdown(
                            f'<div class="card">'
                            f'<div style="display: flex; justify-content: space-between;">'
                            f'<span style="color: #FF4500; font-size: 0.8rem;">r/{q.subreddit}</span>'
                            f'<span style="color: #94A3B8; font-size: 0.8rem;">{q.upvotes:,} upvotes | {q.num_comments} comments</span>'
                            f'</div>'
                            f'<p style="font-weight: 600; font-size: 1.05rem; margin: 0.4rem 0;">{q.title}</p>'
                            f'{"<p style=&quot;color: #CBD5E1; font-size: 0.9rem;&quot;>" + q.selftext[:200] + "...</p>" if q.selftext and len(q.selftext) > 20 else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if comments:
                            with st.expander(f"Top answers ({len(comments)})"):
                                for c in comments[:3]:
                                    st.markdown(
                                        f'<div style="background: #0F172A; border-left: 3px solid #6366F1; '
                                        f'padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.5rem;">'
                                        f'<p style="color: #CBD5E1; font-size: 0.85rem; margin: 0;">{c[:300]}'
                                        f'{"..." if len(c) > 300 else ""}</p></div>',
                                        unsafe_allow_html=True,
                                    )
                else:
                    st.info("No questions found. Try scanning with more subreddits.")

            with tab_hot_takes:
                st.markdown("### Hot Takes & Contrarian Opinions")
                st.caption("These make great social media content — agree or disagree with them.")
                opinions = (
                    session.query(RedditPostRecord)
                    .filter(RedditPostRecord.content_type == "opinion")
                    .order_by(RedditPostRecord.upvotes.desc())
                    .limit(20)
                    .all()
                )
                if opinions:
                    for o in opinions:
                        st.markdown(
                            f'<div class="card">'
                            f'<span style="color: #FF4500; font-size: 0.8rem;">r/{o.subreddit}</span> '
                            f'<span style="color: #94A3B8; font-size: 0.8rem;">{o.upvotes:,} upvotes</span>'
                            f'<p style="font-weight: 600; margin: 0.3rem 0;">{o.title}</p>'
                            f'{"<p style=&quot;color: #CBD5E1; font-size: 0.9rem;&quot;>" + o.selftext[:300] + "...</p>" if o.selftext and len(o.selftext) > 20 else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("No hot takes found. Subreddits like r/ExperiencedDevs are great for these.")

            with tab_tutorials:
                st.markdown("### Tutorials & Discoveries")
                st.caption("Content that teaches — high-performing tutorial posts to learn from.")
                tutorials = (
                    session.query(RedditPostRecord)
                    .filter(RedditPostRecord.content_type.in_(["tutorial", "discovery"]))
                    .order_by(RedditPostRecord.upvotes.desc())
                    .limit(20)
                    .all()
                )
                if tutorials:
                    for t in tutorials:
                        st.markdown(
                            f'<div class="card">'
                            f'<span style="color: #FF4500; font-size: 0.8rem;">r/{t.subreddit}</span> '
                            f'<span style="color: #10B981; font-size: 0.8rem;">{t.content_type}</span> '
                            f'<span style="color: #94A3B8; font-size: 0.8rem;">{t.upvotes:,} upvotes</span>'
                            f'<p style="font-weight: 600; margin: 0.3rem 0;">{t.title}</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("No tutorials found yet.")

            with tab_trending:
                st.markdown("### Trending Now")
                st.caption("Most upvoted posts across all tracked subreddits.")
                trending = (
                    session.query(RedditPostRecord)
                    .order_by(RedditPostRecord.upvotes.desc())
                    .limit(15)
                    .all()
                )
                for t in trending:
                    pct = f"{t.upvote_ratio * 100:.0f}%" if t.upvote_ratio else ""
                    st.markdown(
                        f'<div class="card" style="padding: 0.8rem;">'
                        f'<span style="color: #FF4500; font-size: 0.8rem; font-weight: 600;">r/{t.subreddit}</span> '
                        f'<span style="color: #94A3B8; font-size: 0.8rem;">'
                        f'{t.upvotes:,} upvotes ({pct}) | {t.num_comments} comments</span>'
                        f'<p style="font-weight: 500; margin: 0.3rem 0 0 0;">{t.title}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            with tab_all:
                st.markdown("### All Scraped Posts")
                # Filter by subreddit
                filter_sub = st.selectbox(
                    "Filter by subreddit",
                    ["All"] + profile.reddit.subreddits,
                    key="filter_sub",
                )
                query = session.query(RedditPostRecord)
                if filter_sub != "All":
                    query = query.filter(RedditPostRecord.subreddit == filter_sub)
                all_posts = query.order_by(RedditPostRecord.upvotes.desc()).limit(50).all()

                for p in all_posts:
                    type_color = {
                        "question": "#3B82F6", "opinion": "#F59E0B", "tutorial": "#10B981",
                        "discovery": "#8B5CF6", "discussion": "#94A3B8", "recommendation": "#EC4899",
                    }.get(p.content_type, "#94A3B8")
                    st.markdown(
                        f'<div class="card" style="padding: 0.6rem;">'
                        f'<span style="color: #FF4500; font-size: 0.75rem;">r/{p.subreddit}</span> '
                        f'<span style="color: {type_color}; font-size: 0.7rem; text-transform: uppercase; font-weight: 600;">{p.content_type}</span> '
                        f'<span style="color: #475569; font-size: 0.75rem;">{p.upvotes:,} pts</span>'
                        f'<p style="margin: 0.2rem 0 0 0;">{p.title}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                '<div class="card" style="text-align: center; padding: 3rem;">'
                '<p style="font-size: 1.2rem; color: #94A3B8;">No Reddit data yet</p>'
                '<p style="color: #475569;">Click "Scan Subreddits" to discover what your audience is talking about.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
    finally:
        session.close()

    # ── Next Step ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Next Step")
    st.markdown(
        "Great — now you have real audience data. Synthesize it into content strategy in the Intelligence hub, "
        "or jump straight to creating content that answers their actual questions."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("See Intelligence Hub →", use_container_width=True):
            st.switch_page("pages/2_Insights.py")
    with col2:
        if st.button("Create Content →", type="primary", use_container_width=True):
            st.switch_page("pages/3_Create.py")

