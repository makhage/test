"""OpenAI OAuth 2.0 PKCE flow for Codex access.

Opens a browser for sign-in, catches the callback on a local server,
exchanges the authorization code for tokens, and persists them for reuse.
Tokens are auto-refreshed when they expire.

Usage:
    from social_agent.auth.openai_oauth import get_openai_client

    client = get_openai_client()          # opens browser on first run
    response = client.responses.create(...)  # uses OAuth token
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from social_agent.config import DATA_DIR, get_settings

# ── OpenAI OAuth endpoints ─────────────────────────────────────────────────

AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
DEFAULT_SCOPES = "openai.organization.read openai.responses.write"

# Local callback server
REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8484
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"

# Token persistence
TOKEN_FILE = DATA_DIR / "openai_oauth_tokens.json"


# ── PKCE helpers ────────────────────────────────────────────────────────────


def _generate_code_verifier() -> str:
    """Generate a high-entropy code verifier (43-128 chars, RFC 7636)."""
    return secrets.token_urlsafe(64)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """Derive the S256 code challenge from the verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ── Token storage ───────────────────────────────────────────────────────────


def _save_tokens(tokens: dict[str, Any]) -> None:
    """Persist tokens to disk."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tokens["saved_at"] = datetime.utcnow().isoformat()
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def _load_tokens() -> dict[str, Any] | None:
    """Load tokens from disk, or None if missing."""
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _tokens_expired(tokens: dict[str, Any]) -> bool:
    """Check whether the access token is expired or about to expire."""
    saved_at = tokens.get("saved_at")
    expires_in = tokens.get("expires_in", 0)
    if not saved_at or not expires_in:
        return True
    saved = datetime.fromisoformat(saved_at)
    # Refresh if within 5 minutes of expiry
    return datetime.utcnow() > saved + timedelta(seconds=expires_in - 300)


# ── Local callback server ──────────────────────────────────────────────────


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the authorization code."""

    authorization_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.authorization_code = params["code"][0]
            self._respond("Sign-in successful — you can close this tab.")
        elif "error" in params:
            _OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self._respond(f"Sign-in failed: {_OAuthCallbackHandler.error}")
        else:
            self._respond("Waiting for OAuth callback...")

    def _respond(self, message: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = (
            "<!DOCTYPE html><html><body style='font-family:system-ui;text-align:center;"
            f"padding:3rem'><h2>{message}</h2></body></html>"
        )
        self.wfile.write(html.encode())

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP logs
        pass


def _wait_for_callback(timeout: int = 120) -> str:
    """Start a local server, wait for the OAuth callback, return the auth code."""
    server = http.server.HTTPServer(
        (REDIRECT_HOST, REDIRECT_PORT), _OAuthCallbackHandler
    )
    server.timeout = timeout

    _OAuthCallbackHandler.authorization_code = None
    _OAuthCallbackHandler.error = None

    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if _OAuthCallbackHandler.authorization_code or _OAuthCallbackHandler.error:
            break

    server.server_close()

    if _OAuthCallbackHandler.error:
        raise RuntimeError(f"OAuth error: {_OAuthCallbackHandler.error}")
    if not _OAuthCallbackHandler.authorization_code:
        raise TimeoutError("OAuth sign-in timed out — no callback received.")

    return _OAuthCallbackHandler.authorization_code


# ── OAuth flows ─────────────────────────────────────────────────────────────


def authorize(
    client_id: str,
    scopes: str = DEFAULT_SCOPES,
) -> dict[str, Any]:
    """Run the full OAuth 2.0 Authorization Code + PKCE flow.

    1. Opens the browser to OpenAI's sign-in page
    2. Waits for the redirect with the auth code
    3. Exchanges the code for access + refresh tokens
    4. Saves tokens to disk

    Returns the token response dict.
    """
    verifier = _generate_code_verifier()
    challenge = _generate_code_challenge(verifier)
    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    print(f"\nOpening browser for OpenAI sign-in...\n  {auth_url}\n")
    webbrowser.open(auth_url)

    code = _wait_for_callback()

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    resp = requests.post(TOKEN_URL, data=token_data, timeout=30)
    resp.raise_for_status()
    tokens = resp.json()

    _save_tokens(tokens)
    print("OpenAI OAuth tokens saved.\n")
    return tokens


def refresh_access_token(
    client_id: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Use the refresh token to get a new access token."""
    token_data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    resp = requests.post(TOKEN_URL, data=token_data, timeout=30)
    resp.raise_for_status()
    tokens = resp.json()
    _save_tokens(tokens)
    return tokens


def get_access_token() -> str:
    """Get a valid access token — refreshing or re-authorizing as needed.

    Reads client_id from settings.openai_oauth_client_id.
    """
    settings = get_settings()
    client_id = settings.openai_oauth_client_id

    if not client_id:
        raise ValueError(
            "Set OPENAI_OAUTH_CLIENT_ID in your .env to use OAuth. "
            "Register your app at https://platform.openai.com/settings/apps"
        )

    tokens = _load_tokens()

    # No tokens → full authorize
    if not tokens:
        tokens = authorize(client_id)
        return tokens["access_token"]

    # Tokens valid → use them
    if not _tokens_expired(tokens):
        return tokens["access_token"]

    # Tokens expired → try refresh
    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        try:
            tokens = refresh_access_token(client_id, refresh_token)
            return tokens["access_token"]
        except requests.HTTPError:
            # Refresh failed → full re-authorize
            pass

    tokens = authorize(client_id)
    return tokens["access_token"]


# ── Client factory ──────────────────────────────────────────────────────────


def get_openai_client():
    """Return an OpenAI client authenticated via OAuth.

    Falls back to API key if no OAuth client_id is configured.
    """
    from openai import OpenAI

    settings = get_settings()

    # Prefer OAuth if client_id is set
    if settings.openai_oauth_client_id:
        token = get_access_token()
        return OpenAI(api_key=token)

    # Fall back to static API key
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)

    raise ValueError(
        "No OpenAI credentials configured. Set either:\n"
        "  OPENAI_OAUTH_CLIENT_ID (for OAuth sign-in)\n"
        "  OPENAI_API_KEY (for static API key)"
    )


def logout() -> bool:
    """Remove stored OAuth tokens."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print("OpenAI OAuth tokens removed.")
        return True
    return False
