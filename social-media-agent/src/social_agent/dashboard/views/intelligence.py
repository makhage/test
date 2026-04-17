"""Intelligence Hub — All advanced features in one place."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_metric_card
from social_agent.config import get_settings
from social_agent.db.database import init_db
from social_agent.profiles.loader import load_profile


def render() -> None:
    init_db()

    st.markdown("# Intelligence Hub")
    st.markdown("Advanced content intelligence — repurpose, mine, learn, and discover.")

    profile = load_profile()
    settings = get_settings()
    has_api = bool(settings.google_api_key)

    tab_repurpose, tab_comments, tab_learn, tab_trends, tab_gaps, tab_recycle, tab_series, tab_personas = st.tabs([
        "Repurpose", "Comment Mining", "Learning Loop", "Trend Velocity",
        "Content Gaps", "Evergreen Recycler", "Series Planner", "Audience Personas",
    ])

    # ── Tab 1: Long-form → Short-form Repurposer ──────────────────────────────
    with tab_repurpose:
        st.markdown("### Long-form → Short-form Repurposer")
        st.caption("Paste a YouTube/TikTok/podcast URL or transcript → get a week of content.")

        source_url = st.text_input("Video/Podcast URL", placeholder="https://youtube.com/watch?v=...", key="repurpose_url")
        source_text = st.text_area("Or paste a transcript/blog post", height=150, key="repurpose_text",
                                    placeholder="Paste transcript or article text here...")

        if st.button("Repurpose into Short-form Content", type="primary", disabled=not has_api, key="repurpose_btn"):
            if not source_url and not source_text:
                st.warning("Provide a URL or paste text.")
            else:
                with st.spinner("Transcribing and generating content..."):
                    from social_agent.generators.longform_repurposer import repurpose_longform
                    from social_agent.research.analyzer import get_latest_intelligence
                    result = repurpose_longform(
                        source_url=source_url if source_url else None,
                        source_text=source_text if source_text else None,
                        profile=profile,
                        intelligence=get_latest_intelligence(),
                    )

                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"Generated: {len(result.get('tweets', []))} tweets, "
                               f"{len(result.get('threads', []))} threads, "
                               f"{len(result.get('carousels', []))} carousels, "
                               f"{len(result.get('tiktoks', []))} TikToks")

                    if result.get("source_summary"):
                        st.markdown(f"**Source:** {result['source_summary']}")

                    if result.get("key_insights"):
                        with st.expander("Key Insights Extracted"):
                            for i, insight in enumerate(result["key_insights"], 1):
                                st.markdown(f"{i}. {insight}")

                    # Tweets
                    if result.get("tweets"):
                        st.markdown("#### Tweets")
                        for tw in result["tweets"]:
                            st.markdown(f'<div class="card" style="padding: 0.6rem;">'
                                        f'<p style="margin: 0;">{tw.get("text", "")}</p>'
                                        f'<p style="color: #475569; font-size: 0.75rem; margin: 0.2rem 0 0 0;">'
                                        f'{tw.get("angle", "")}</p></div>', unsafe_allow_html=True)

                    # Threads
                    if result.get("threads"):
                        st.markdown("#### Threads")
                        for th in result["threads"]:
                            with st.expander(f"Thread: {th.get('topic', '')}"):
                                st.markdown(f"**Hook:** {th.get('hook', '')}")
                                for j, t in enumerate(th.get("tweets", []), 2):
                                    st.markdown(f"{j}. {t}")

                    # Carousels
                    if result.get("carousels"):
                        st.markdown("#### Carousels")
                        for car in result["carousels"]:
                            with st.expander(f"Carousel: {car.get('title', '')}"):
                                for slide in car.get("slides", []):
                                    st.markdown(f"- **{slide.get('heading', '')}**: {slide.get('body', '')}")
                                if car.get("caption"):
                                    st.markdown(f"*Caption: {car['caption']}*")

                    # TikToks
                    if result.get("tiktoks"):
                        st.markdown("#### TikTok Captions")
                        for tt in result["tiktoks"]:
                            st.markdown(f'<div class="card" style="padding: 0.6rem;">'
                                        f'<p>{tt.get("caption", "")}</p>'
                                        f'{"<p style=&quot;color: #94A3B8; font-size: 0.85rem;&quot;>Script: " + tt.get("script_notes", "") + "</p>" if tt.get("script_notes") else ""}'
                                        f'</div>', unsafe_allow_html=True)


    # ── Tab 2: Comment Mining ──────────────────────────────────────────────────
    with tab_comments:
        st.markdown("### Comment Mining")
        st.caption("Automatically pulls comments from the videos you selected in Niche Profile — across YouTube, TikTok, Instagram, and Twitter.")

        from social_agent.research.niche_profiler import get_stored_creator_videos
        stored_videos = get_stored_creator_videos()

        plat_color = {"youtube": "#FF0000", "tiktok": "#00F2EA", "instagram": "#E4405F", "twitter": "#1DA1F2"}

        if stored_videos:
            by_plat: dict[str, int] = {}
            for v in stored_videos:
                p = (v.get("platform") or "video").lower()
                by_plat[p] = by_plat.get(p, 0) + 1
            summary = " · ".join(
                f'<span style="color:{plat_color.get(k, "#94A3B8")};font-weight:600;">{v} {k}</span>'
                for k, v in by_plat.items()
            )
            st.markdown(
                f'<div class="card" style="padding:0.6rem;"><p style="margin:0;">'
                f'<span style="color:#10B981;">✓</span> {len(stored_videos)} videos saved from your last Niche scan: {summary}'
                f'</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No saved videos yet. Run **Research → Niche Profile** and pick which videos to analyze — they'll flow here automatically.")

        col_mine1, col_mine2 = st.columns(2)
        with col_mine1:
            if st.button("Mine comments from my videos", type="primary", disabled=not stored_videos, key="mine_auto_btn", use_container_width=True):
                with st.spinner(f"Mining comments across {len(stored_videos)} videos..."):
                    from social_agent.research.comment_miner import mine_from_videos
                    result = mine_from_videos(stored_videos, max_per_video=80)
                if result["total"]:
                    by_p = ", ".join(f"{v} from {k}" for k, v in result["by_platform"].items())
                    st.success(f"Mined {result['total']} comments ({by_p}).")
                else:
                    st.warning("No comments were accessible. Most TikTok/Instagram videos gate comments — try YouTube links for best results.")

        with col_mine2:
            if st.button("Analyze & extract content ideas", disabled=not has_api, key="analyze_comments_btn", use_container_width=True):
                with st.spinner("Classifying comments with Gemini..."):
                    from social_agent.research.comment_miner import analyze_comments
                    result = analyze_comments()
                    if "error" not in result:
                        st.success("Analysis complete!")
                        st.rerun()

        with st.expander("Advanced: add more sources manually"):
            col1, col2 = st.columns(2)
            with col1:
                yt_urls = st.text_area("YouTube Video URLs (one per line)", height=100, key="mine_yt",
                                        placeholder="https://youtube.com/watch?v=abc123")
            with col2:
                tweet_ids = st.text_area("Tweet IDs to mine replies (one per line)", height=100, key="mine_tw",
                                          placeholder="1234567890")
            if st.button("Mine from manual sources", key="mine_manual_btn"):
                with st.spinner("Mining comments..."):
                    from social_agent.research.comment_miner import mine_all_comments
                    yt_list = [u.strip() for u in yt_urls.split("\n") if u.strip()] if yt_urls else []
                    tw_list = [t.strip() for t in tweet_ids.split("\n") if t.strip()] if tweet_ids else []
                    comments = mine_all_comments(profile, video_urls=yt_list, tweet_ids=tw_list)
                    st.success(f"Mined {len(comments)} comments!")

        # Show extracted ideas
        from social_agent.research.comment_miner import get_content_ideas_from_comments
        ideas = get_content_ideas_from_comments()
        if ideas:
            st.markdown("#### Content Ideas from Your Audience")
            for idea in ideas:
                priority_color = "#10B981" if idea["priority"] > 7 else "#F59E0B" if idea["priority"] > 4 else "#94A3B8"
                st.markdown(
                    f'<div class="card" style="border-left: 3px solid {priority_color}; padding: 0.6rem;">'
                    f'<span style="color: {priority_color}; font-weight: 600;">{idea["priority"]:.0f}/10</span> '
                    f'<span style="font-weight: 600;">{idea["topic"]}</span>'
                    f'<p style="color: #94A3B8; font-size: 0.8rem; margin: 0.2rem 0 0 0;">'
                    f'[{idea["category"]}] "{idea["original_comment"][:100]}..."</p>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.info("No content ideas yet. Mine comments and run analysis above.")


    # ── Tab 3: Performance Learning Loop ──────────────────────────────────────
    with tab_learn:
        st.markdown("### Performance Learning Loop")
        st.caption("The agent analyzes what's working and adjusts future content strategy.")

        learn_days = st.selectbox("Analyze period", [7, 14, 30, 60, 90], index=2, key="learn_days")

        if st.button("Analyze Performance", type="primary", disabled=not has_api, key="learn_btn"):
            with st.spinner("Analyzing your content performance..."):
                from social_agent.analytics.learning_loop import analyze_performance
                result = analyze_performance(days=learn_days)

            if "error" in result:
                st.warning(result.get("recommendations", [result["error"]])[0] if result.get("recommendations") else result["error"])
            else:
                # Recommendations
                if result.get("recommendations"):
                    st.markdown("#### Recommendations")
                    for rec in result["recommendations"]:
                        st.markdown(f'<div class="card" style="padding: 0.6rem; border-left: 3px solid #6366F1;">'
                                    f'{rec}</div>', unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    if result.get("best_topics"):
                        st.markdown("#### Best Topics")
                        for t in result["best_topics"]:
                            st.markdown(f"- **{t.get('topic', '')}** (avg engagement: {t.get('avg_engagement', 0)})")
                with col2:
                    if result.get("top_content_types"):
                        st.markdown("#### Best Formats")
                        for t in result["top_content_types"]:
                            st.markdown(f"- **{t.get('type', '')}** ({t.get('trend', '')})")

                if result.get("content_mix_suggestion"):
                    st.markdown("#### Suggested Content Mix (Next Week)")
                    st.json(result["content_mix_suggestion"])


    # ── Tab 4: Trend Velocity ─────────────────────────────────────────────────
    with tab_trends:
        st.markdown("### Early Trend Detection")
        st.caption("Catch topics that are accelerating before they peak. Post first, not last.")

        if st.button("Detect Emerging Trends", type="primary", key="trend_btn"):
            with st.spinner("Analyzing topic velocity..."):
                from social_agent.research.trend_velocity import detect_emerging_topics
                all_topics = profile.topics.get("primary", []) + profile.topics.get("secondary", [])
                result = detect_emerging_topics(profile_topics=all_topics)

            emerging = result.get("emerging_topics", [])
            if emerging:
                st.success(f"Found {len(emerging)} emerging topics!")
                for topic in emerging:
                    urgency = topic.get("urgency", "medium")
                    urgency_color = {"high": "#EF4444", "medium": "#F59E0B", "low": "#94A3B8"}.get(urgency, "#94A3B8")
                    st.markdown(
                        f'<div class="card" style="border-left: 4px solid {urgency_color};">'
                        f'<div style="display: flex; justify-content: space-between;">'
                        f'<span style="font-weight: 700; font-size: 1.05rem;">{topic.get("topic", "")}</span>'
                        f'<span style="color: {urgency_color}; text-transform: uppercase; font-size: 0.75rem; font-weight: 600;">{urgency}</span>'
                        f'</div>'
                        f'{"<p style=&quot;color: #CBD5E1; margin: 0.3rem 0;&quot;>" + topic.get("what", "") + "</p>" if topic.get("what") else ""}'
                        f'{"<p style=&quot;color: #94A3B8; font-size: 0.85rem;&quot;>Content angle: " + topic.get("content_angle", "") + "</p>" if topic.get("content_angle") else ""}'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("No emerging trends detected. Make sure you've scanned Reddit recently.")


    # ── Tab 5: Content Gap Analysis ────────────────────────────────────────────
    with tab_gaps:
        st.markdown("### Content Gap Analysis")
        st.caption("Find what your audience wants but you're not covering.")

        if st.button("Analyze Content Gaps", type="primary", disabled=not has_api, key="gap_btn"):
            with st.spinner("Comparing your content vs audience demand..."):
                from social_agent.research.content_gaps import analyze_content_gaps
                result = analyze_content_gaps()

            if "error" in result:
                st.error(result["error"])
            else:
                if result.get("summary"):
                    st.markdown(f'<div class="card" style="border-left: 4px solid #6366F1; padding: 1rem;">'
                                f'<p style="font-size: 1.1rem; font-weight: 600; margin: 0;">{result["summary"]}</p>'
                                f'</div>', unsafe_allow_html=True)

                # Gaps
                gaps = result.get("gaps", [])
                if gaps:
                    st.markdown("#### Content Blind Spots")
                    for gap in gaps:
                        strength_color = {"high": "#EF4444", "medium": "#F59E0B", "low": "#94A3B8"}.get(
                            gap.get("demand_strength", ""), "#94A3B8")
                        st.markdown(
                            f'<div class="card" style="border-left: 3px solid {strength_color};">'
                            f'<p style="font-weight: 600; margin: 0;">{gap.get("topic", "")}</p>'
                            f'<p style="color: #94A3B8; font-size: 0.85rem; margin: 0.2rem 0;">'
                            f'Signal: {gap.get("demand_signal", "")}</p>'
                            f'<p style="color: #10B981; font-size: 0.85rem; margin: 0;">'
                            f'Suggested: {gap.get("suggested_content", "")}</p>'
                            f'</div>', unsafe_allow_html=True)

                # Oversaturated
                over = result.get("oversaturated", [])
                if over:
                    st.markdown("#### Possibly Oversaturated")
                    st.caption("You might be posting too much about these relative to audience interest.")
                    for topic in over:
                        st.markdown(f"- {topic}")


    # ── Tab 6: Evergreen Recycler ──────────────────────────────────────────────
    with tab_recycle:
        st.markdown("### Evergreen Content Recycler")
        st.caption("Find your top-performing old posts and refresh them with new hooks.")

        min_age = st.slider("Minimum age (days)", 30, 365, 90, key="recycle_age")

        if st.button("Find Recyclable Content", key="recycle_find_btn"):
            from social_agent.generators.evergreen_recycler import find_evergreen_candidates
            candidates = find_evergreen_candidates(min_age_days=min_age)
            if candidates:
                st.session_state["recycle_candidates"] = candidates
                st.success(f"Found {len(candidates)} recyclable posts!")
            else:
                st.info("No old posts with engagement data found. Needs published posts with tracked analytics.")

        candidates = st.session_state.get("recycle_candidates", [])
        for c in candidates:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(
                    f'<div class="card" style="padding: 0.6rem;">'
                    f'<span style="color: #6366F1;">{c["platform"]}/{c["content_type"]}</span> '
                    f'<span style="color: #94A3B8;">{c["age_days"]} days old | {c["engagement"]} engagement</span>'
                    f'<p style="margin: 0.2rem 0 0 0;">{c["content"][:150]}...</p>'
                    f'</div>', unsafe_allow_html=True)
            with col2:
                if st.button("Refresh", key=f"recycle_{c['id']}", disabled=not has_api):
                    with st.spinner("Generating refreshed versions..."):
                        from social_agent.generators.evergreen_recycler import recycle_content
                        result = recycle_content(c["content"], c["engagement"], c["age_days"], profile)
                    if "error" not in result:
                        for v in result.get("refreshed", []):
                            st.markdown(f'<div class="card"><p style="font-weight: 600; color: #10B981;">'
                                        f'{v.get("version", "")}</p><p>{v.get("content", "")}</p>'
                                        f'<p style="color: #475569; font-size: 0.8rem;">{v.get("what_changed", "")}</p>'
                                        f'</div>', unsafe_allow_html=True)


    # ── Tab 7: Series Planner ─────────────────────────────────────────────────
    with tab_series:
        st.markdown("### Content Series Planner")
        st.caption("Plan multi-part series that keep followers coming back.")

        series_topic = st.text_input("Series Topic", placeholder="e.g., Python from Zero to Hero", key="series_topic")
        col1, col2, col3 = st.columns(3)
        with col1:
            series_parts = st.slider("Number of Parts", 3, 10, 5, key="series_parts")
        with col2:
            series_format = st.selectbox("Format", ["carousel", "thread", "tiktok", "mixed"], key="series_format")
        with col3:
            series_platform = st.selectbox("Platform", ["instagram", "twitter", "tiktok"], key="series_platform")

        if st.button("Plan Series", type="primary", disabled=not has_api, key="series_btn"):
            if not series_topic:
                st.warning("Enter a topic first.")
            else:
                with st.spinner("Planning your content series..."):
                    from social_agent.generators.series_planner import plan_series
                    from social_agent.research.analyzer import get_latest_intelligence
                    result = plan_series(
                        topic=series_topic, num_parts=series_parts,
                        format=series_format, platform=series_platform,
                        profile=profile, intelligence=get_latest_intelligence(),
                    )

                if "error" in result:
                    st.error(result["error"])
                else:
                    st.markdown(f"### {result.get('series_title', '')}")
                    st.markdown(f"*{result.get('series_hook', '')}*")
                    if result.get("posting_schedule"):
                        st.markdown(f"**Schedule:** {result['posting_schedule']}")

                    for part in result.get("parts", []):
                        with st.expander(f"Part {part.get('part_number', '')} — {part.get('title', '')}"):
                            st.markdown(f"**Hook:** {part.get('hook', '')}")
                            for point in part.get("key_points", []):
                                st.markdown(f"- {point}")
                            if part.get("cliffhanger"):
                                st.markdown(f"**Cliffhanger:** {part['cliffhanger']}")
                            if part.get("content_brief"):
                                st.markdown(f"**Brief:** {part['content_brief']}")

                    if result.get("cross_platform_strategy"):
                        st.markdown(f"**Cross-platform:** {result['cross_platform_strategy']}")


    # ── Tab 8: Audience Personas ───────────────────────────────────────────────
    with tab_personas:
        st.markdown("### Audience Persona Modeling")
        st.caption("Build detailed personas of who actually follows you — from data, not guesses.")

        if st.button("Build Audience Personas", type="primary", disabled=not has_api, key="persona_btn"):
            with st.spinner("Analyzing your audience data..."):
                from social_agent.research.audience_personas import build_audience_personas
                result = build_audience_personas(profile)

            if "error" in result:
                st.error(result["error"])
            else:
                personas = result.get("personas", [])
                for persona in personas:
                    pct = persona.get("percentage_of_audience", 0)
                    st.markdown(
                        f'<div class="card">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                        f'<div>'
                        f'<p style="font-size: 1.2rem; font-weight: 700; color: #6366F1; margin: 0;">'
                        f'{persona.get("name", "")}</p>'
                        f'<p style="color: #EC4899; font-weight: 500; margin: 0;">{persona.get("title", "")}</p>'
                        f'</div>'
                        f'<span style="font-size: 1.5rem; font-weight: 700; color: #10B981;">{pct}%</span>'
                        f'</div>'
                        f'<p style="color: #CBD5E1; margin: 0.5rem 0;">{persona.get("backstory", "")}</p>'
                        f'</div>', unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    demo = persona.get("demographics", {})
                    with col1:
                        st.markdown(f"**Age:** {demo.get('age_range', 'N/A')}")
                        st.markdown(f"**Occupation:** {demo.get('occupation', 'N/A')}")
                        st.markdown("**Goals:**")
                        for g in persona.get("goals", []):
                            st.markdown(f"- {g}")
                    with col2:
                        st.markdown(f"**Experience:** {demo.get('experience_level', 'N/A')}")
                        prefs = persona.get("content_preferences", {})
                        st.markdown(f"**Favorite formats:** {', '.join(prefs.get('favorite_formats', []))}")
                        st.markdown("**Pain points:**")
                        for p in persona.get("pain_points", []):
                            st.markdown(f"- {p}")

                    st.markdown(f"**What hooks them:** {persona.get('what_makes_them_follow', '')}")
                    st.markdown("---")

                if result.get("content_implications"):
                    st.markdown("#### What This Means for Your Content")
                    for imp in result["content_implications"]:
                        st.markdown(f"- {imp}")

