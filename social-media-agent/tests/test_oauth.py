"""Tests for OpenAI OAuth 2.0 PKCE flow."""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from social_agent.auth import (
    _generate_code_challenge,
    _generate_code_verifier,
    _load_tokens,
    _save_tokens,
    _tokens_expired,
    get_openai_client,
    logout,
)


class TestPKCE:
    def test_verifier_length(self):
        verifier = _generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_verifier_is_url_safe(self):
        verifier = _generate_code_verifier()
        # URL-safe base64 characters only
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in allowed for c in verifier)

    def test_verifier_uniqueness(self):
        v1 = _generate_code_verifier()
        v2 = _generate_code_verifier()
        assert v1 != v2

    def test_challenge_is_deterministic(self):
        verifier = "test_verifier_12345"
        c1 = _generate_code_challenge(verifier)
        c2 = _generate_code_challenge(verifier)
        assert c1 == c2

    def test_challenge_differs_for_different_verifiers(self):
        c1 = _generate_code_challenge("verifier_a")
        c2 = _generate_code_challenge("verifier_b")
        assert c1 != c2

    def test_challenge_is_base64url_no_padding(self):
        challenge = _generate_code_challenge("test_verifier")
        assert "=" not in challenge
        assert "+" not in challenge
        assert "/" not in challenge


class TestTokenStorage:
    def test_save_and_load(self, tmp_path, monkeypatch):
        token_file = tmp_path / "tokens.json"
        monkeypatch.setattr("social_agent.auth.TOKEN_FILE", token_file)

        tokens = {"access_token": "at_123", "refresh_token": "rt_456", "expires_in": 3600}
        _save_tokens(tokens)

        loaded = _load_tokens()
        assert loaded["access_token"] == "at_123"
        assert loaded["refresh_token"] == "rt_456"
        assert "saved_at" in loaded

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("social_agent.auth.TOKEN_FILE", tmp_path / "nonexistent.json")
        assert _load_tokens() is None

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        token_file = tmp_path / "bad.json"
        token_file.write_text("not json{{{")
        monkeypatch.setattr("social_agent.auth.TOKEN_FILE", token_file)
        assert _load_tokens() is None

    def test_tokens_not_expired(self):
        tokens = {
            "expires_in": 3600,
            "saved_at": datetime.utcnow().isoformat(),
        }
        assert _tokens_expired(tokens) is False

    def test_tokens_expired(self):
        tokens = {
            "expires_in": 3600,
            "saved_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        }
        assert _tokens_expired(tokens) is True

    def test_tokens_expired_within_5min_buffer(self):
        tokens = {
            "expires_in": 3600,
            "saved_at": (datetime.utcnow() - timedelta(seconds=3400)).isoformat(),
        }
        assert _tokens_expired(tokens) is True

    def test_tokens_expired_missing_fields(self):
        assert _tokens_expired({}) is True
        assert _tokens_expired({"expires_in": 3600}) is True


class TestLogout:
    def test_logout_removes_file(self, tmp_path, monkeypatch):
        token_file = tmp_path / "tokens.json"
        token_file.write_text('{"access_token": "test"}')
        monkeypatch.setattr("social_agent.auth.TOKEN_FILE", token_file)

        assert logout() is True
        assert not token_file.exists()

    def test_logout_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("social_agent.auth.TOKEN_FILE", tmp_path / "nope.json")
        assert logout() is False


class TestGetOpenAIClient:
    @patch("openai.OpenAI")
    @patch("social_agent.auth.get_settings")
    def test_falls_back_to_api_key(self, mock_settings, mock_openai):
        mock_settings.return_value.openai_oauth_client_id = ""
        mock_settings.return_value.openai_api_key = "sk-test-key"

        client = get_openai_client()
        mock_openai.assert_called_once_with(api_key="sk-test-key")

    @patch("social_agent.auth.get_settings")
    def test_raises_with_no_credentials(self, mock_settings):
        mock_settings.return_value.openai_oauth_client_id = ""
        mock_settings.return_value.openai_api_key = ""

        with pytest.raises(ValueError, match="No OpenAI credentials"):
            get_openai_client()

    @patch("openai.OpenAI")
    @patch("social_agent.auth.get_access_token", return_value="oauth_token_123")
    @patch("social_agent.auth.get_settings")
    def test_uses_oauth_when_client_id_set(self, mock_settings, mock_get_token, mock_openai):
        mock_settings.return_value.openai_oauth_client_id = "my-client-id"
        mock_settings.return_value.openai_api_key = "sk-also-set"

        client = get_openai_client()
        # OAuth takes priority over API key
        mock_openai.assert_called_once_with(api_key="oauth_token_123")
