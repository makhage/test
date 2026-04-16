"""Settings & Authentication — simple API key setup in the GUI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings, save_env_var

st.set_page_config(page_title="Settings", page_icon="Settings", layout="wide")
inject_custom_css()

st.markdown("# Settings")

settings = get_settings()

# ── OpenAI API Key ──────────────────────────────────────────────────────────

st.markdown("### OpenAI")

has_key = bool(settings.openai_api_key)

if has_key:
    masked = settings.openai_api_key[:8] + "..." + settings.openai_api_key[-4:]
    st.success(f"Connected — {masked}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Replace Key", use_container_width=True):
            st.session_state["editing_openai_key"] = True
            st.rerun()
    with col2:
        if st.button("Disconnect", use_container_width=True):
            save_env_var("OPENAI_API_KEY", "")
            st.rerun()

    if st.session_state.get("editing_openai_key"):
        new_key = st.text_input(
            "New API Key",
            type="password",
            placeholder="sk-...",
            key="new_openai_key",
        )
        if st.button("Save", type="primary", use_container_width=True):
            if new_key.strip():
                save_env_var("OPENAI_API_KEY", new_key.strip())
                st.session_state["editing_openai_key"] = False
                st.success("Updated!")
                st.rerun()
else:
    st.markdown(
        "Paste your OpenAI API key to start generating content. "
        "Get one at **[platform.openai.com/api-keys](https://platform.openai.com/api-keys)** "
        "(click \"Create new secret key\")."
    )

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        label_visibility="collapsed",
    )

    if st.button("Connect", type="primary", use_container_width=True, disabled=not api_key):
        if api_key.strip().startswith("sk-"):
            save_env_var("OPENAI_API_KEY", api_key.strip())
            st.success("Connected!")
            st.rerun()
        else:
            st.error("Invalid key format. OpenAI keys start with `sk-`.")

st.markdown("---")

# ── Platform Connections ─────────────────────────────────────────────────────

st.markdown("### Social Media Platforms")
st.caption("Optional — only needed if you want to auto-publish to these platforms.")

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
