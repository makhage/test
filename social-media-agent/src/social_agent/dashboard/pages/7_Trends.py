"""Trend Radar — Live trending topics, viral hooks, and format insights."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.config import get_settings
from social_agent.db.database import ViralPostRecord, init_db, get_session
from social_agent.profiles.loader import load_profile
from social_agent.research.analyzer import get_latest_intelligence

st.set_page_config(page_title="Trend Radar", page_icon="📡", layout="wide")
inject_custom_css()
init_db()

st.markdown("# Trend Radar")
st.markdown("What's going viral in your niche right now.")

profile = load_profile()
settings = get_settings()

# Scan button
col_scan1, col_scan2 = st.columns([3, 1])
with col_scan2:
    scan_clicked = st.button(
        "Scan Now",
        type="primary",
        use_container_width=True,
        disabled=not bool(settings.twitter_bearer_token or settings.instagram_access_token),
    )

if scan_clicked:
    with st.spinner("Scanning niche for viral content..."):
        try:
            from social_agent.research.niche_monitor import run_niche_scan
            intel = run_niche_scan(profile, force_analysis=True)
            if intel:
                st.success(f"Scan complete! Found {intel.source_post_count} viral posts, extracted {len(intel.trending_topics)} trends.")
            else:
                st.warning("Scan completed but no trends extracted. Check your API keys.")
        except Exception as e:
            st.error(f"Scan failed: {e}")

# Analyze button (works from cached viral posts, no API needed)
if st.button("Re-analyze cached posts", disabled=not bool(settings.openai_api_key or settings.openai_oauth_client_id)):
    with st.spinner("Analyzing viral patterns with Claude..."):
        try:
            from social_agent.research.analyzer import analyze_viral_content
            intel = analyze_viral_content()
            if intel:
                st.success(f"Analysis complete! {len(intel.trending_topics)} trends, {len(intel.winning_hooks)} hooks identified.")
                st.rerun()
            else:
                st.warning("No viral posts in database to analyze. Scan first.")
        except Exception as e:
            st.error(f"Analysis failed: {e}")

st.markdown("---")

# Display current intelligence
intel = get_latest_intelligence()

if intel:
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(render_metric_card("Trending Topics", len(intel.trending_topics)), unsafe_allow_html=True)
    with col2:
        st.markdown(render_metric_card("Winning Hooks", len(intel.winning_hooks)), unsafe_allow_html=True)
    with col3:
        st.markdown(render_metric_card("Posts Analyzed", intel.source_post_count), unsafe_allow_html=True)

    st.markdown("---")

    # Trending topics
    st.markdown("### Trending Topics")
    topic_cols = st.columns(min(len(intel.trending_topics), 3) or 1)
    for i, topic in enumerate(intel.trending_topics):
        with topic_cols[i % len(topic_cols)]:
            st.markdown(
                f'<div class="card" style="text-align: center; padding: 0.75rem;">'
                f'<span style="color: #6366F1; font-weight: 700; font-size: 1.2rem;">#{i + 1}</span><br>'
                f'<span style="font-size: 0.95rem;">{topic}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Winning hooks
    st.markdown("### Winning Hooks")
    for hook in intel.winning_hooks:
        st.markdown(
            f'<div class="card">'
            f'<p style="font-weight: 600; color: #EC4899; font-size: 1rem;">{hook.pattern}</p>'
            f'<p style="color: #94A3B8; font-style: italic; margin: 0.3rem 0;">"{hook.example}"</p>'
            f'{"<p style=&quot;color: #475569; font-size: 0.8rem; margin: 0;&quot;>Seen " + str(hook.frequency) + " times</p>" if hook.frequency else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Audience Questions (from Reddit)
    if intel.audience_questions:
        st.markdown("---")
        st.markdown("### Audience Questions (from Reddit)")
        st.caption("Real questions your audience is asking — each one is a content topic idea.")
        for i, q in enumerate(intel.audience_questions, 1):
            st.markdown(
                f'<div class="card" style="padding: 0.6rem; border-left: 3px solid #3B82F6;">'
                f'<span style="color: #3B82F6; font-weight: 600;">Q{i}.</span> {q}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Hot Takes (from Reddit)
    if intel.hot_takes:
        st.markdown("---")
        st.markdown("### Hot Takes & Contrarian Opinions")
        st.caption("Opinions getting high engagement — agree or disagree for viral content.")
        for take in intel.hot_takes:
            st.markdown(
                f'<div class="card" style="padding: 0.6rem; border-left: 3px solid #F59E0B;">'
                f'<span style="color: #F59E0B;">🔥</span> {take}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Authentic Phrases (from Reddit)
    if intel.authentic_phrases:
        st.markdown("---")
        st.markdown("### Authentic Language")
        st.caption("How real people talk about these topics — use this language to sound human, not AI.")
        phrase_cols = st.columns(min(len(intel.authentic_phrases), 3) or 1)
        for i, phrase in enumerate(intel.authentic_phrases):
            with phrase_cols[i % len(phrase_cols)]:
                st.markdown(
                    f'<div class="card" style="padding: 0.5rem; text-align: center;">'
                    f'<p style="font-style: italic; color: #10B981; margin: 0;">"{phrase}"</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Top formats
    if intel.top_formats:
        st.markdown("---")
        st.markdown("### Top Performing Formats")
        for fmt in intel.top_formats:
            st.markdown(f"- **{fmt}**")

    # Engagement benchmarks
    benchmarks = intel.engagement_benchmarks
    if benchmarks:
        st.markdown("### Engagement Benchmarks")
        bench_cols = st.columns(min(len(benchmarks), 4) or 1)
        for i, (key, val) in enumerate(benchmarks.items()):
            with bench_cols[i % len(bench_cols)]:
                st.metric(key.replace("_", " ").title(), f"{val:,.0f}")

    st.caption(f"Last updated: {intel.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")

else:
    st.markdown(
        '<div class="card" style="text-align: center; padding: 3rem;">'
        '<p style="font-size: 1.2rem; color: #94A3B8;">No trend data yet</p>'
        '<p style="color: #475569;">Click "Scan Now" above to discover what\'s going viral in your niche.</p>'
        '</div>',
        unsafe_allow_html=True,
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
            plat_color = {"twitter": "#1DA1F2", "instagram": "#E4405F", "tiktok": "#00F2EA"}.get(post.platform, "#94A3B8")
            st.markdown(
                f'<div class="card">'
                f'<p style="color: {plat_color}; font-size: 0.8rem; font-weight: 600;">'
                f'{post.platform.upper()} — {post.likes:,} likes | {post.shares:,} shares | {post.comments:,} comments</p>'
                f'<p style="line-height: 1.5;">{post.text[:400]}{"..." if len(post.text) > 400 else ""}</p>'
                f'{"<a href=&quot;" + post.url + "&quot; target=&quot;_blank&quot; style=&quot;color: #6366F1; font-size: 0.8rem;&quot;>View original</a>" if post.url else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Swipe file is empty. Run a scan to find viral content.")
finally:
    session.close()
