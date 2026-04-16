"""Shared AI client — all text generation goes through Google Gemini.

This module provides a single `chat()` function that every generator
and research module calls. Centralizing here means:
- One place to swap models
- One place for auth (via GOOGLE_API_KEY)
- Consistent JSON extraction from responses
"""

from __future__ import annotations

import json
from typing import Any

from social_agent.config import get_settings

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "imagen-3.0-generate-002"


def _get_client():
    """Get a configured Gemini client."""
    from google import genai

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError(
            "Google API key not configured. Add it in the Settings page of the dashboard, "
            "or set GOOGLE_API_KEY in your .env file."
        )
    return genai.Client(api_key=settings.google_api_key)


def chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
) -> str:
    """Send a chat request to Gemini and return the text response."""
    from google.genai import types

    client = _get_client()
    response = client.models.generate_content(
        model=model or TEXT_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.9,
        ),
    )
    return response.text or ""


def chat_json(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
) -> dict[str, Any]:
    """Send a chat request and parse the response as JSON."""
    raw = chat(system=system, user=user, max_tokens=max_tokens, model=model)
    return parse_json(raw)


def parse_json(raw: str) -> dict[str, Any]:
    """Extract JSON from a response that may contain markdown fences."""
    text = raw.strip()
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return {}
