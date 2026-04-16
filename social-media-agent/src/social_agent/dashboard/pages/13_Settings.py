"""Settings & Authentication — fully in-GUI setup, no file editing needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings, save_env_var
from social_agent.auth import _load_tokens, _tokens_expired

st.set_page_config(page_title="Settings", page_icon="Settings", layout="wide")
inject_custom_css()


# ── Helper ──────────────────────────────────────────────────────────────────

def _start_oauth_flow(client_id: str):
    """Launch the OAuth flow — opens browser and waits for callback."""
    from social_agent.auth import authorize

    with st.spinner("Waiting for OpenAI sign-in... (check your browser)"):
        try:
            authorize(client_id)
            st.success("Signed in to OpenAI successfully!")
            st.rerun()
        except TimeoutError:
            st.error("Sign-in timed out. Please try again.")
        except Exception as e:
            st.error(f"Sign-in failed: {e}")


# ── Page ────────────────────────────────────────────────────────────────────

st.markdown("# Settings")

settings = get_settings()
tokens = _load_tokens()
has_oauth = bool(settings.openai_oauth_client_id)
oauth_signed_in = has_oauth and tokens and not _tokens_expired(tokens)
has_openai = oauth_signed_in or bool(settings.openai_api_key)

# ── OpenAI Sign-In (main section) ──────────────────────────────────────────

st.markdown("### OpenAI Account")

if oauth_signed_in:
    # Signed in — show status
    st.success("Signed in to OpenAI")

    saved_at = tokens.get("saved_at", "")
    expires_in = tokens.get("expires_in", 0)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status", "Active")
    with col2:
        display_time = saved_at[:19].replace("T", " ") if saved_at else ""
        st.metric("Signed in at", display_time)
    with col3:
        minutes_left = max(0, expires_in // 60)
        st.metric("Expires in", f"{minutes_left} min")

    if st.button("Sign Out", use_container_width=True):
        from social_agent.auth import logout
        logout()
        st.rerun()

elif has_oauth and tokens:
    # Token expired
    st.warning("Your session has expired.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh Session", type="primary", use_container_width=True):
            try:
                from social_agent.auth import refresh_access_token
                refresh_access_token(settings.openai_oauth_client_id, tokens.get("refresh_token", ""))
                st.success("Session refreshed!")
                st.rerun()
            except Exception:
                st.error("Refresh failed. Please sign in again.")
    with col2:
        if st.button("Sign In Again", use_container_width=True):
            _start_oauth_flow(settings.openai_oauth_client_id)

elif has_oauth:
    # Client ID set but not signed in yet
    st.info("Click below to sign in to your OpenAI account.")
    if st.button("Sign in to OpenAI", type="primary", use_container_width=True):
        _start_oauth_flow(settings.openai_oauth_client_id)

else:
    # First-time setup — guide the user through it
    st.markdown(
        "Connect your OpenAI account to start generating content. "
        "This is a one-time setup."
    )

    st.markdown("#### Step 1: Get your Client ID")
    st.markdown(
        "Go to **[platform.openai.com/settings/apps](https://platform.openai.com/settings/apps)**, "
        "register a new app, and set the redirect URI to:"
    )
    st.code("http://127.0.0.1:8484/callback", language=None)
    st.markdown("Then copy your **Client ID** and paste it below.")

    st.markdown("#### Step 2: Paste it here")
    client_id_input = st.text_input(
        "OpenAI Client ID",
        placeholder="Paste your Client ID here",
        label_visibility="collapsed",
    )

    if st.button("Save & Sign In", type="primary", use_container_width=True, disabled=not client_id_input):
        # Save to .env
        save_env_var("OPENAI_OAUTH_CLIENT_ID", client_id_input.strip())
        st.success("Client ID saved!")
        # Start OAuth flow
        _start_oauth_flow(client_id_input.strip())

st.markdown("---")

# ── Platform Connections ─────────────────────────────────────────────────────

st.markdown("### Platform Connections")

platform_configs = [
    {
        "name": "Twitter/X",
        "connected": bool(settings.twitter_api_key and settings.twitter_access_token),
        "keys": [
            ("TWITTER_API_KEY", settings.twitter_api_key),
            ("TWITTER_API_SECRET", settings.twitter_api_secret),
            ("TWITTER_ACCESS_TOKEN", settings.twitter_access_token),
            ("TWITTER_ACCESS_TOKEN_SECRET", settings.twitter_access_token_secret),
            ("TWITTER_BEARER_TOKEN", settings.twitter_bearer_token),
        ],
    },
    {
        "name": "Instagram",
        "connected": bool(settings.instagram_access_token),
        "keys": [
            ("INSTAGRAM_ACCESS_TOKEN", settings.instagram_access_token),
            ("INSTAGRAM_BUSINESS_ACCOUNT_ID", settings.instagram_business_account_id),
        ],
    },
    {
        "name": "TikTok",
        "connected": bool(settings.tiktok_access_token),
        "keys": [
            ("TIKTOK_ACCESS_TOKEN", settings.tiktok_access_token),
            ("TIKTOK_OPEN_ID", settings.tiktok_open_id),
        ],
    },
    {
        "name": "Reddit",
        "connected": bool(settings.reddit_client_id),
        "keys": [
            ("REDDIT_CLIENT_ID", settings.reddit_client_id),
            ("REDDIT_CLIENT_SECRET", settings.reddit_client_secret),
        ],
    },
]

for platform in platform_configs:
    with st.expander(
        f"{'Connected' if platform['connected'] else 'Not connected'} — {platform['name']}",
        expanded=False,
    ):
        changed = False
        for key, current_value in platform["keys"]:
            new_value = st.text_input(
                key,
                value=current_value,
                type="password" if "SECRET" in key or "TOKEN" in key else "default",
                key=f"platform_{key}",
            )
            if new_value != current_value and new_value:
                save_env_var(key, new_value)
                changed = True

        if changed:
            st.success(f"{platform['name']} credentials saved!")
            st.rerun()

st.markdown("---")

# ── Advanced ─────────────────────────────────────────────────────────────────

with st.expander("Advanced: Use API key instead of OAuth"):
    st.markdown("If you prefer using a static API key instead of OAuth sign-in:")
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=settings.openai_api_key,
        type="password",
        placeholder="sk-...",
        key="openai_api_key_input",
    )
    if st.button("Save API Key"):
        if api_key_input:
            save_env_var("OPENAI_API_KEY", api_key_input.strip())
            st.success("API key saved!")
            st.rerun()
