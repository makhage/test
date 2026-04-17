"""Niche Profile — Analyze the creator's content to auto-discover their niche and subreddits."""

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

    st.markdown("# Niche Profile")
    st.markdown("The agent reads your content — posts, bios, videos — to understand your niche and auto-discover the best subreddits.")

    profile = load_profile()
    settings = get_settings()

    # --- Primary input: Linktree URL ---
    st.markdown("### Paste Your Linktree")
    st.caption("One link is all the agent needs — it extracts your Twitter, TikTok, Instagram, YouTube, and everything else automatically.")

    linktree_url = st.text_input(
        "Linktree / Link-in-bio URL",
        placeholder="https://linktr.ee/yourname",
        help="Also works with Beacons, Stan Store, bio.link, lnk.bio, or any link-in-bio page.",
    )

    # Preview extracted links
    twitter_handle = ""
    tiktok_url = ""
    instagram_url = ""
    youtube_url = ""

    if linktree_url:
        with st.spinner("Extracting links..."):
            from social_agent.research.niche_profiler import extract_linktree
            lt_data = extract_linktree(linktree_url)

        if lt_data.get("error"):
            st.error(f"Could not read Linktree: {lt_data['error']}")
        else:
            platforms_found = lt_data.get("platforms", {})
            all_links = lt_data.get("links", [])

            # Show creator info
            if lt_data.get("name"):
                st.markdown(
                    f'<div class="card" style="padding: 1rem;">'
                    f'<p style="font-size: 1.2rem; font-weight: 700; color: #6366F1; margin: 0;">{lt_data["name"]}</p>'
                    f'{"<p style=&quot;color: #CBD5E1; margin: 0.3rem 0 0 0;&quot;>" + lt_data.get("bio", "") + "</p>" if lt_data.get("bio") else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Show extracted platforms
            if platforms_found:
                st.markdown("**Platforms found:**")
                plat_icons = {
                    "twitter": "𝕏", "tiktok": "♪", "instagram": "📷",
                    "youtube": "▶", "linkedin": "💼", "github": "🐙", "twitch": "🎮",
                }
                plat_cols = st.columns(min(len(platforms_found), 4))
                for i, (plat, url) in enumerate(platforms_found.items()):
                    with plat_cols[i % len(plat_cols)]:
                        icon = plat_icons.get(plat, "🔗")
                        st.markdown(
                            f'<div class="card" style="padding: 0.5rem; text-align: center;">'
                            f'<p style="font-size: 1.2rem; margin: 0;">{icon}</p>'
                            f'<p style="font-weight: 600; color: #10B981; margin: 0; font-size: 0.85rem;">{plat.title()}</p>'
                            f'<p style="color: #475569; font-size: 0.7rem; margin: 0; word-break: break-all;">{url[:50]}</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                # Pre-fill from extracted
                twitter_handle = ""
                if "twitter" in platforms_found:
                    import re as _re
                    tw_match = _re.search(r'(?:twitter\.com|x\.com)/(@?\w+)', platforms_found["twitter"])
                    if tw_match:
                        twitter_handle = tw_match.group(1)
                tiktok_url = platforms_found.get("tiktok", "")
                instagram_url = platforms_found.get("instagram", "")
                youtube_url = platforms_found.get("youtube", "")

            # Show other links
            other = lt_data.get("other_links", [])
            if other:
                with st.expander(f"Other links found ({len(other)})"):
                    for link in other:
                        st.markdown(f"- {link}")

    # --- Manual override / fallback ---
    with st.expander("Or enter links manually"):
        col1, col2 = st.columns(2)
        with col1:
            twitter_handle = st.text_input(
                "Twitter/X Handle",
                value=twitter_handle,
                placeholder="@yourhandle",
                key="manual_twitter",
            )
            tiktok_url = st.text_input(
                "TikTok Profile URL",
                value=tiktok_url,
                placeholder="https://tiktok.com/@yourhandle",
                key="manual_tiktok",
            )
        with col2:
            instagram_url = st.text_input(
                "Instagram Profile URL",
                value=instagram_url,
                placeholder="https://instagram.com/yourhandle",
                key="manual_instagram",
            )
            youtube_url = st.text_input(
                "YouTube Channel URL",
                value=youtube_url,
                placeholder="https://youtube.com/@yourchannel",
                key="manual_youtube",
            )

    platforms_to_scrape = []
    if twitter_handle:
        platforms_to_scrape.append("Twitter")
    if tiktok_url:
        platforms_to_scrape.append("TikTok")
    if instagram_url:
        platforms_to_scrape.append("Instagram")
    if youtube_url:
        platforms_to_scrape.append("YouTube")

    if platforms_to_scrape:
        st.markdown(
            f'<div class="card" style="padding: 0.6rem;">'
            f'<p style="margin: 0; color: #94A3B8;">Will scrape: '
            f'{" + ".join(f"<strong style=&quot;color: #10B981;&quot;>{p}</strong>" for p in platforms_to_scrape)}'
            f'</p></div>',
            unsafe_allow_html=True,
        )

    # --- Video picker ---
    st.markdown("---")
    st.markdown("### Pick videos to analyze")
    st.caption("The agent fetches your most recent videos across platforms. Check the ones you want transcribed and mined for comments.")

    video_platforms_available = bool(tiktok_url or instagram_url or youtube_url)

    col_fetch, col_info = st.columns([1, 3])
    with col_fetch:
        fetch_clicked = st.button(
            "Load my videos",
            use_container_width=True,
            disabled=not video_platforms_available,
            help="Pulls the most recent 8 videos per platform with thumbnails.",
        )
    with col_info:
        if not video_platforms_available:
            st.caption("Paste a Linktree, TikTok, Instagram, or YouTube URL above to list videos.")

    if fetch_clicked:
        with st.spinner("Fetching video previews..."):
            from social_agent.research.niche_profiler import list_creator_videos
            videos = list_creator_videos(
                tiktok_url=tiktok_url or None,
                instagram_url=instagram_url or None,
                youtube_url=youtube_url or None,
                per_platform=8,
            )
        st.session_state["available_videos"] = videos
        if not videos:
            st.warning("Couldn't load any video previews. The platform may be blocking scraping — you can still analyze without transcripts.")

    available_videos = st.session_state.get("available_videos", [])
    selected_videos: list[dict] = []

    if available_videos:
        # Select-all controls
        sa_col1, sa_col2, sa_col3 = st.columns([1, 1, 3])
        with sa_col1:
            if st.button("Select all", use_container_width=True):
                for i, _ in enumerate(available_videos):
                    st.session_state[f"vid_pick_{i}"] = True
                st.rerun()
        with sa_col2:
            if st.button("Clear", use_container_width=True):
                for i, _ in enumerate(available_videos):
                    st.session_state[f"vid_pick_{i}"] = False
                st.rerun()
        with sa_col3:
            st.caption(f"Found **{len(available_videos)}** videos across your platforms.")

        plat_colors = {"tiktok": "#00F2EA", "instagram": "#E4405F", "youtube": "#FF0000"}
        grid_cols = st.columns(4)
        for i, v in enumerate(available_videos):
            with grid_cols[i % 4]:
                thumb = v.get("thumbnail") or ""
                plat = v.get("platform", "video")
                color = plat_colors.get(plat, "#6366F1")
                if thumb:
                    try:
                        st.image(thumb, use_container_width=True)
                    except Exception:
                        st.markdown(
                            '<div style="height:120px;background:#1E293B;border-radius:8px;'
                            'display:flex;align-items:center;justify-content:center;color:#64748B;">'
                            'no preview</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div style="height:120px;background:#1E293B;border-radius:8px;'
                        'display:flex;align-items:center;justify-content:center;color:#64748B;">'
                        'no preview</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f'<p style="margin:0.25rem 0 0 0;font-size:0.7rem;'
                    f'color:{color};text-transform:uppercase;font-weight:600;">{plat}</p>'
                    f'<p style="margin:0;font-size:0.8rem;color:#CBD5E1;min-height:2.4em;line-height:1.2em;">'
                    f'{(v.get("title") or "")[:80]}</p>',
                    unsafe_allow_html=True,
                )
                checked = st.checkbox(
                    "Include",
                    value=st.session_state.get(f"vid_pick_{i}", i < 8),
                    key=f"vid_pick_{i}",
                )
                if checked:
                    selected_videos.append(v)

        if selected_videos:
            st.markdown(
                f'<div class="card" style="padding:0.5rem 0.75rem;">'
                f'<span style="color:#10B981;font-weight:600;">{len(selected_videos)}</span> '
                f'<span style="color:#94A3B8;">videos selected — these will be transcribed and mined for comments.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- Options ---
    st.markdown("---")
    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        transcribe = st.checkbox("Transcribe selected videos", value=True)
    with opt_col2:
        mine_comments = st.checkbox("Mine comments from selected videos", value=True)

    # --- Run Analysis ---
    can_analyze = bool(settings.google_api_key)

    if st.button(
        "Analyze My Niche",
        type="primary",
        use_container_width=True,
        disabled=not can_analyze,
    ):
        steps = []
        if linktree_url:
            steps.append("reading Linktree")
        if platforms_to_scrape:
            steps.append(f"scraping {', '.join(platforms_to_scrape)}")
        if transcribe and selected_videos:
            steps.append(f"transcribing {len(selected_videos)} videos")
        steps.append("analyzing with Gemini")

        with st.spinner(f"{'  →  '.join(steps)}..."):
            try:
                from social_agent.research.niche_profiler import analyze_creator_niche

                analysis = analyze_creator_niche(
                    profile=profile,
                    linktree_url=linktree_url if linktree_url else None,
                    youtube_channel_url=youtube_url if youtube_url else None,
                    tiktok_url=tiktok_url if tiktok_url else None,
                    instagram_url=instagram_url if instagram_url else None,
                    twitter_handle=twitter_handle if twitter_handle else None,
                    transcribe_videos=transcribe,
                    max_video_transcripts=max(len(selected_videos), 1) if selected_videos else 5,
                    selected_videos=selected_videos if selected_videos else None,
                )

                if "error" in analysis:
                    st.error(f"Analysis failed: {analysis['error']}")
                else:
                    # Auto-mine comments from the same selected videos
                    if mine_comments and selected_videos:
                        try:
                            from social_agent.research.comment_miner import mine_from_videos
                            with st.spinner(f"Mining comments from {len(selected_videos)} videos..."):
                                mine_summary = mine_from_videos(selected_videos, max_per_video=80)
                            if mine_summary["total"]:
                                by_p = ", ".join(f"{v} from {k}" for k, v in mine_summary["by_platform"].items())
                                st.success(f"Niche analysis complete. Mined {mine_summary['total']} comments ({by_p}). See Insights → Comment Mining.")
                            else:
                                st.success("Niche analysis complete! (No comments were accessible on the selected videos — most TikTok/IG videos are gated.)")
                        except Exception as e:
                            st.warning(f"Niche analysis complete, but comment mining failed: {e}")
                    else:
                        st.success("Niche analysis complete! Updated creator/soul.md and added insights to the knowledge base.")
                    st.rerun()
            except Exception as e:
                st.error(f"Analysis failed: {e}")

    if not can_analyze:
        st.info("Add your Gemini API key in Settings to enable niche analysis.")

    # --- Display Results ---
    st.markdown("---")

    from social_agent.research.niche_profiler import get_latest_niche_profile
    niche = get_latest_niche_profile()

    if niche and "error" not in niche:
        # Top-level niche summary
        st.markdown("### Your Niche")
        st.markdown(
            f'<div class="card" style="border-left: 4px solid #6366F1;">'
            f'<p style="font-size: 1.3rem; font-weight: 700; color: #6366F1; margin: 0;">'
            f'{niche.get("primary_niche", "Unknown")}</p>'
            f'<p style="color: #CBD5E1; margin-top: 0.3rem;">{niche.get("target_audience", "")}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                render_metric_card("Sub-Topics", len(niche.get("sub_topics", []))),
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                render_metric_card("Pain Points", len(niche.get("audience_pain_points", []))),
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                render_metric_card("Subreddits Found", len(niche.get("recommended_subreddits", []))),
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Two-column layout
        left, right = st.columns([1, 1])

        with left:
            # Sub-topics
            st.markdown("### Sub-Topics You Cover")
            for topic in niche.get("sub_topics", []):
                st.markdown(
                    f'<div class="card" style="padding: 0.5rem 0.75rem; display: inline-block; margin: 0.2rem;">'
                    f'{topic}</div>',
                    unsafe_allow_html=True,
                )

            # Content style
            st.markdown("### Your Content Style")
            st.markdown(
                f'<div class="card">'
                f'<p style="color: #CBD5E1;">{niche.get("content_style", "N/A")}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Key themes
            if niche.get("key_themes"):
                st.markdown("### Key Themes")
                for theme in niche["key_themes"]:
                    st.markdown(f"- {theme}")

        with right:
            # Audience pain points
            st.markdown("### What Your Audience Struggles With")
            st.caption(
                "These are **inferred** from your content — if you talk about X, your audience probably wants to learn X. "
                "Validate with real audience data in **Reddit Intel** (next step below)."
            )
            st.caption("Each of these is a content idea.")
            for i, pain in enumerate(niche.get("audience_pain_points", []), 1):
                st.markdown(
                    f'<div class="card" style="padding: 0.5rem 0.75rem; border-left: 3px solid #EF4444;">'
                    f'<span style="color: #EF4444; font-weight: 600;">{i}.</span> {pain}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # --- Discovered Subreddits (the main event) ---
        st.markdown("---")
        st.markdown("### Auto-Discovered Subreddits")
        st.caption("The agent picked these based on your content. These are where your audience hangs out.")

        subreddits = niche.get("recommended_subreddits", [])

        if subreddits:
            # Group by relevance
            high = [s for s in subreddits if s.get("relevance") == "high"]
            medium = [s for s in subreddits if s.get("relevance") == "medium"]
            low = [s for s in subreddits if s.get("relevance") == "low"]

            type_icons = {
                "general": "🌐",
                "focused": "🎯",
                "niche": "🔬",
                "questions": "❓",
            }

            relevance_colors = {
                "high": "#10B981",
                "medium": "#F59E0B",
                "low": "#94A3B8",
            }

            for group_name, group in [("High Relevance", high), ("Medium Relevance", medium), ("Lower Relevance", low)]:
                if not group:
                    continue
                color = relevance_colors.get(group[0].get("relevance", ""), "#94A3B8")
                st.markdown(f"#### {group_name}")
                for sub in group:
                    icon = type_icons.get(sub.get("type", ""), "📌")
                    name = sub["name"].lstrip("r/").lstrip("/")
                    st.markdown(
                        f'<div class="card" style="border-left: 4px solid {color};">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                        f'<span style="font-weight: 700; color: #FF4500; font-size: 1.05rem;">'
                        f'{icon} r/{name}</span>'
                        f'<span style="color: {color}; font-size: 0.75rem; text-transform: uppercase; '
                        f'font-weight: 600;">{sub.get("type", "")}</span>'
                        f'</div>'
                        f'<p style="color: #CBD5E1; margin: 0.3rem 0 0 0; font-size: 0.9rem;">{sub.get("reason", "")}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # --- Apply to profile ---
            st.markdown("---")
            st.markdown("### Apply to Reddit Scanner")
            st.caption("Select which subreddits to use for ongoing content research.")

            selected = []
            sub_cols = st.columns(3)
            for i, sub in enumerate(subreddits):
                with sub_cols[i % 3]:
                    clean_name = sub["name"].lstrip("r/").lstrip("/")
                    if st.checkbox(
                        f"r/{clean_name}",
                        value=sub.get("relevance") in ("high", "medium"),
                        key=f"sub_select_{clean_name}",
                    ):
                        selected.append(clean_name)

            if st.button("Apply Selected Subreddits", use_container_width=True):
                st.info(
                    f"Selected {len(selected)} subreddits: {', '.join(f'r/{s}' for s in selected)}\n\n"
                    f"Update `profiles/default.yaml` → `reddit.subreddits` with:\n"
                    f"```yaml\nreddit:\n  subreddits:\n" +
                    "\n".join(f"    - {s}" for s in selected) +
                    "\n```"
                )
                # Also store in session state for the Reddit scanner to use
                st.session_state["active_subreddits"] = selected
                st.success(f"Active subreddits updated! The Reddit scanner will now use these {len(selected)} subreddits.")

        if niche.get("_created_at"):
            st.caption(f"Analysis performed: {niche['_created_at']}")

        # Next step
        st.markdown("---")
        st.markdown("### Next Step")
        st.markdown(
            "Your niche analysis is a **hypothesis**. Now validate it with real audience data — "
            "run Reddit Intel on the subreddits above to see what your audience actually says."
        )
        if st.button("Continue to Reddit Intel →", type="primary", use_container_width=True):
            st.switch_page("pages/1_Research.py")

    else:
        st.markdown(
            '<div class="card" style="text-align: center; padding: 3rem;">'
            '<p style="font-size: 3rem; margin: 0;">🧬</p>'
            '<p style="font-size: 1.2rem; color: #94A3B8; margin: 0.5rem 0;">No niche analysis yet</p>'
            '<p style="color: #475569;">Enter your social media handles above and click "Analyze My Niche".<br>'
            'The agent will read your posts, bio, and videos to understand your content niche<br>'
            'and automatically discover the best subreddits for research.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

