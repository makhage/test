"""Settings & Authentication — Manage API keys and OpenAI OAuth sign-in."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings
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

st.markdown("# Settings & Authentication")
st.markdown("Manage your API connections and sign in to OpenAI for Codex access.")

st.markdown("---")

settings = get_settings()

# ── Connection Status ───────────────────────────────────────────────────────

st.markdown("### Connection Status")

col1, col2 = st.columns(2)

with col1:
    tokens = _load_tokens()
    has_oauth = bool(settings.openai_oauth_client_id)

    if has_oauth and tokens and not _tokens_expired(tokens):
        st.success("OpenAI OAuth\n\nSigned in")
    elif has_oauth and tokens:
        st.warning("OpenAI OAuth\n\nToken expired")
    elif settings.openai_api_key:
        masked = settings.openai_api_key[:8] + "..." + settings.openai_api_key[-4:]
        st.success(f"OpenAI API Key\n\n`{masked}`")
    else:
        st.error("OpenAI\n\nNot configured")

with col2:
    twitter_ok = bool(settings.twitter_api_key and settings.twitter_access_token)
    if twitter_ok:
        st.success("Twitter/X\n\nConnected")
    else:
        st.warning("Twitter/X\n\nNot connected")

st.markdown("---")

# ── OpenAI OAuth Sign-In ────────────────────────────────────────────────────

st.markdown("### OpenAI OAuth (Codex Access)")
st.markdown(
    "Sign in to OpenAI via OAuth to use Codex, DALL-E, and Whisper "
    "without managing API keys manually."
)

if not settings.openai_oauth_client_id:
    st.info(
        "**Setup required:** Add `OPENAI_OAUTH_CLIENT_ID` to your `.env` file.\n\n"
        "1. Go to [platform.openai.com/settings/apps](https://platform.openai.com/settings/apps)\n"
        "2. Register a new app\n"
        "3. Set redirect URI to `http://127.0.0.1:8484/callback`\n"
        "4. Copy the Client ID into your `.env`:\n"
        "```\nOPENAI_OAUTH_CLIENT_ID=your-client-id\n```"
    )
else:
    tokens = _load_tokens()

    if tokens and not _tokens_expired(tokens):
        st.success("You are signed in to OpenAI.")
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

        if st.button("Sign Out", type="secondary", use_container_width=True):
            from social_agent.auth import logout
            logout()
            st.rerun()

    elif tokens:
        st.warning("Your OAuth token has expired. Click below to refresh.")
        if st.button("Refresh Token", type="primary", use_container_width=True):
            try:
                from social_agent.auth import refresh_access_token
                refresh_access_token(
                    settings.openai_oauth_client_id,
                    tokens.get("refresh_token", ""),
                )
                st.success("Token refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Refresh failed: {e}. Try signing in again.")

        if st.button("Sign In Again", use_container_width=True):
            _start_oauth_flow(settings.openai_oauth_client_id)

    else:
        st.markdown("Click below to open the OpenAI sign-in page in your browser.")
        if st.button("Sign in to OpenAI", type="primary", use_container_width=True):
            _start_oauth_flow(settings.openai_oauth_client_id)

st.markdown("---")

# ── API Keys ────────────────────────────────────────────────────────────────

st.markdown("### API Keys")
st.markdown(
    "Alternatively, you can configure API keys directly. "
    "Add them to your `.env` file in the project root."
)

with st.expander("View .env template"):
    st.code(
        """# OpenAI (choose one: OAuth or API key)
OPENAI_OAUTH_CLIENT_ID=your-client-id    # For OAuth sign-in (recommended)
OPENAI_API_KEY=sk-...                     # Or use a static key

# Twitter/X
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_BEARER_TOKEN=

# Instagram
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=

# TikTok
TIKTOK_ACCESS_TOKEN=
TIKTOK_OPEN_ID=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=social-agent/0.1""",
        language="bash",
    )

st.markdown("---")

# ── Platform Connections ─────────────────────────────────────────────────────

st.markdown("### Platform Connections")

platforms = [
    ("Twitter/X", bool(settings.twitter_api_key), "TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET"),
    ("Instagram", bool(settings.instagram_access_token), "INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID"),
    ("TikTok", bool(settings.tiktok_access_token), "TIKTOK_ACCESS_TOKEN, TIKTOK_OPEN_ID"),
    ("Reddit", bool(settings.reddit_client_id), "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET"),
]

for name, connected, keys in platforms:
    col1, col2 = st.columns([1, 3])
    with col1:
        if connected:
            st.markdown(f"**{name}** &nbsp; :green[Connected]")
        else:
            st.markdown(f"**{name}** &nbsp; :red[Not connected]")
    with col2:
        if not connected:
            st.caption(f"Set: `{keys}`")
