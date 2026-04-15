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

st.set_page_config(page_title="Niche Profile", page_icon="🧬", layout="wide")
inject_custom_css()
init_db()

st.markdown("# Niche Profile")
st.markdown("The agent reads your content — posts, bios, videos — to understand your niche and auto-discover the best subreddits.")

profile = load_profile()
settings = get_settings()

# --- Input: Creator's accounts ---
st.markdown("### Your Accounts")
st.caption("Provide your social media handles so the agent can analyze your actual content.")

col1, col2 = st.columns(2)
with col1:
    twitter_handle = st.text_input(
        "Twitter/X Handle",
        value=profile.brand.name or "",
        placeholder="@yourhandle",
    )
    instagram_id = st.text_input(
        "Instagram Business Account ID",
        value=settings.instagram_business_account_id or "",
        placeholder="Your IG business account ID",
    )
with col2:
    youtube_url = st.text_input(
        "YouTube Channel URL",
        placeholder="https://youtube.com/@yourchannel",
    )
    transcribe = st.checkbox("Transcribe videos with Whisper", value=True)

max_transcripts = 3
if transcribe:
    max_transcripts = st.slider("Videos to transcribe", 1, 10, 3)

st.markdown("---")

# --- Run Analysis ---
can_analyze = bool(settings.anthropic_api_key)

if st.button(
    "Analyze My Niche",
    type="primary",
    use_container_width=True,
    disabled=not can_analyze,
):
    with st.spinner("Scraping your content and analyzing your niche... (this may take a minute)"):
        try:
            from social_agent.research.niche_profiler import analyze_creator_niche

            analysis = analyze_creator_niche(
                profile=profile,
                youtube_channel_url=youtube_url if youtube_url else None,
                transcribe_videos=transcribe,
                max_video_transcripts=max_transcripts,
            )

            if "error" in analysis:
                st.error(f"Analysis failed: {analysis['error']}")
            else:
                st.success("Niche analysis complete!")
                st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {e}")

if not can_analyze:
    st.info("Set `ANTHROPIC_API_KEY` in `.env` to enable niche analysis.")

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
                st.markdown(
                    f'<div class="card" style="border-left: 4px solid {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                    f'<span style="font-weight: 700; color: #FF4500; font-size: 1.05rem;">'
                    f'{icon} r/{sub["name"]}</span>'
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
                if st.checkbox(
                    f"r/{sub['name']}",
                    value=sub.get("relevance") in ("high", "medium"),
                    key=f"sub_select_{sub['name']}",
                ):
                    selected.append(sub["name"])

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
