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
    """Send a chat request with JSON response mode and parse the result."""
    from google.genai import types

    client = _get_client()
    response = client.models.generate_content(
        model=model or TEXT_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system + "\n\nAlways respond with valid JSON only. No markdown fences, no commentary.",
            max_output_tokens=max_tokens,
            temperature=0.9,
            response_mime_type="application/json",
        ),
    )
    return parse_json(response.text or "")


def parse_json(raw: str) -> Any:
    """Extract JSON from a response. Handles markdown fences as fallback."""
    if not raw:
        return {}
    text = raw.strip()
    # Direct parse first (response_mime_type=application/json returns clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: strip markdown fences
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        pass
    # Fallback: find first { and last }
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        pass
    return {}
