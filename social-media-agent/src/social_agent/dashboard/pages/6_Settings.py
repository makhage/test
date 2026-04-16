"""Settings — Gemini API key, profile, platform credentials, knowledge base."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.dashboard.views import profile
from social_agent.config import get_settings, save_env_var
from social_agent.knowledge import stats as knowledge_stats

st.set_page_config(page_title="Settings", page_icon="", layout="wide")
inject_custom_css()

tab_connect, tab_profile, tab_knowledge = st.tabs([
    "Connections",
    "Profile & Voice",
    "Knowledge Base",
])

with tab_connect:
    st.markdown("## Connections")

    settings = get_settings()

    # ── Gemini ──────────────────────────────────────────────────────────────
    st.markdown("### Google Gemini")

    has_key = bool(settings.google_api_key)

    if has_key:
        masked = settings.google_api_key[:8] + "..." + settings.google_api_key[-4:]
        st.success(f"Connected — `{masked}`")
        st.caption("Gemini powers text generation, image generation, and audio transcription.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Replace Key", use_container_width=True):
                st.session_state["editing_key"] = True
                st.rerun()
        with col2:
            if st.button("Disconnect", use_container_width=True):
                save_env_var("GOOGLE_API_KEY", "")
                st.rerun()

        if st.session_state.get("editing_key"):
            new_key = st.text_input(
                "New API Key",
                type="password",
                placeholder="AIza...",
                key="new_google_key",
            )
            if st.button("Save", type="primary", use_container_width=True):
                if new_key.strip():
                    save_env_var("GOOGLE_API_KEY", new_key.strip())
                    st.session_state["editing_key"] = False
                    st.success("Updated!")
                    st.rerun()
    else:
        st.markdown(
            "Paste your Google Gemini API key to start generating content. "
            "Get one for free at **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)**."
        )
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="AIza...",
            label_visibility="collapsed",
        )
        if st.button("Connect", type="primary", use_container_width=True, disabled=not api_key):
            save_env_var("GOOGLE_API_KEY", api_key.strip())
            st.success("Connected!")
            st.rerun()

    st.markdown("---")

    # ── Platforms ───────────────────────────────────────────────────────────
    st.markdown("### Social Media Platforms")
    st.caption("Optional — only needed if you want to auto-publish.")

    platform_configs = [
        {
            "name": "Twitter / X",
            "connected": bool(settings.twitter_api_key and settings.twitter_access_token),
            "link": "https://developer.twitter.com/en/portal/dashboard",
            "keys": [
                ("TWITTER_API_KEY", settings.twitter_api_key, "API Key"),
                ("TWITTER_API_SECRET", settings.twitter_api_secret, "API Secret"),
                ("TWITTER_ACCESS_TOKEN", settings.twitter_access_token, "Access Token"),
                ("TWITTER_ACCESS_TOKEN_SECRET", settings.twitter_access_token_secret, "Access Token Secret"),
                ("TWITTER_BEARER_TOKEN", settings.twitter_bearer_token, "Bearer Token"),
            ],
        },
        {
            "name": "Instagram",
            "connected": bool(settings.instagram_access_token),
            "link": "https://developers.facebook.com/apps/",
            "keys": [
                ("INSTAGRAM_ACCESS_TOKEN", settings.instagram_access_token, "Access Token"),
                ("INSTAGRAM_BUSINESS_ACCOUNT_ID", settings.instagram_business_account_id, "Business Account ID"),
            ],
        },
        {
            "name": "TikTok",
            "connected": bool(settings.tiktok_access_token),
            "link": "https://developers.tiktok.com/",
            "keys": [
                ("TIKTOK_ACCESS_TOKEN", settings.tiktok_access_token, "Access Token"),
                ("TIKTOK_OPEN_ID", settings.tiktok_open_id, "Open ID"),
            ],
        },
        {
            "name": "Reddit",
            "connected": bool(settings.reddit_client_id),
            "link": "https://www.reddit.com/prefs/apps",
            "keys": [
                ("REDDIT_CLIENT_ID", settings.reddit_client_id, "Client ID"),
                ("REDDIT_CLIENT_SECRET", settings.reddit_client_secret, "Client Secret"),
            ],
        },
    ]

    for platform in platform_configs:
        status = "Connected" if platform["connected"] else "Not connected"
        with st.expander(f"{platform['name']} — {status}"):
            st.caption(f"Get credentials at {platform['link']}")
            for env_key, current_value, label in platform["keys"]:
                new_value = st.text_input(
                    label,
                    value=current_value,
                    type="password",
                    key=f"platform_{env_key}",
                )
                if new_value != current_value:
                    save_env_var(env_key, new_value)
            if st.button(f"Save {platform['name']}", key=f"save_{platform['name']}"):
                st.success(f"{platform['name']} credentials saved!")
                st.rerun()

with tab_profile:
    profile.render()

with tab_knowledge:
    st.markdown("## Knowledge Base")
    st.caption(
        "Everything the agent has learned about your niche, audience, and content. "
        "This gets automatically fed to Gemini on every call."
    )

    ks = knowledge_stats()
    st.metric("Total knowledge entries", ks["total"])

    if ks["total"] > 0:
        st.markdown("### Breakdown by category")
        cols = st.columns(3)
        labels = {
            "audience_question": "Audience Questions",
            "hot_take": "Hot Takes",
            "winning_hook": "Winning Hooks",
            "trend": "Trends",
            "niche_insight": "Niche Insights",
            "content_gap": "Content Gaps",
            "authentic_phrase": "Authentic Phrases",
            "performance": "Performance Data",
            "competitor_pattern": "Competitor Patterns",
        }
        for i, (cat, count) in enumerate(ks["by_category"].items()):
            if count > 0:
                with cols[i % 3]:
                    st.metric(labels.get(cat, cat), count)
    else:
        st.info(
            "Empty. Run the Niche Scanner and Reddit Intel to populate the knowledge base."
        )

    st.markdown("---")
    st.markdown("### Identity Files")
    st.caption(
        "These markdown files in `creator/` define who the agent is and who you are. "
        "Gemini reads them on every call. Edit them directly in your filesystem."
    )
    from social_agent.config import PROJECT_ROOT
    creator_dir = PROJECT_ROOT / "creator"
    st.code(f"{creator_dir}/agent.md\n{creator_dir}/skills.md\n{creator_dir}/soul.md")
