"""Shared AI client — all text generation goes through Google Gemini.

Every call automatically gets the agent's identity (agent.md + skills.md + soul.md)
plus the most recent knowledge base entries prepended to the system prompt.
This gives Gemini persistent context about who the creator is and what we've
learned about their audience.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, TypeVar

from social_agent.config import get_settings

TEXT_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "imagen-3.0-generate-002"

# Transient API failures (capacity, rate limits) get retried with backoff.
_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
_MAX_RETRIES = 4
_BASE_DELAY = 1.5

T = TypeVar("T")


def _is_transient(exc: Exception) -> bool:
    """Detect transient API errors worth retrying."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _RETRY_STATUS_CODES:
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("unavailable", "deadline", "overloaded", "rate limit", "429", "503", "500", "502", "504")
    )


def _call_with_retry(fn: Callable[[], T]) -> T:
    """Call a Gemini function with exponential backoff on transient errors."""
    last: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if not _is_transient(exc) or attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_BASE_DELAY * (2 ** attempt))
    assert last is not None
    raise last


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


def _augmented_system(system: str, skip_context: bool = False) -> str:
    """Prepend identity + knowledge base to the user's system prompt."""
    if skip_context:
        return system

    try:
        from social_agent.identity import load_identity
        from social_agent.knowledge import build_context_block
        identity = load_identity()
        knowledge = build_context_block()
    except Exception:
        identity = ""
        knowledge = ""

    parts = []
    if identity:
        parts.append(identity)
    if knowledge:
        parts.append(knowledge)
    parts.append(f"# TASK\n\n{system}")
    return "\n\n---\n\n".join(parts)


def chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
    skip_context: bool = False,
) -> str:
    """Send a chat request to Gemini and return the text response.

    Args:
        skip_context: If True, don't prepend identity + knowledge. Use for
            the niche scanner itself (to avoid chicken-and-egg before soul.md exists).
    """
    from google.genai import types

    client = _get_client()
    response = _call_with_retry(lambda: client.models.generate_content(
        model=model or TEXT_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=_augmented_system(system, skip_context),
            max_output_tokens=max_tokens,
            temperature=0.9,
        ),
    ))
    return response.text or ""


def chat_json(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
    skip_context: bool = False,
) -> dict[str, Any]:
    """Send a chat request and parse as JSON. Tries JSON mode, falls back to text."""
    from google.genai import types

    client = _get_client()
    augmented_system = _augmented_system(system, skip_context)

    # Try with JSON response mode first
    try:
        response = _call_with_retry(lambda: client.models.generate_content(
            model=model or TEXT_MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=augmented_system + "\n\nRespond with valid JSON only.",
                max_output_tokens=max_tokens,
                temperature=0.9,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                response_mime_type="application/json",
            ),
        ))
        result = parse_json(response.text or "")
        if result:
            return result
    except Exception:
        pass

    # Fallback: plain text mode with JSON instruction
    response = _call_with_retry(lambda: client.models.generate_content(
        model=model or TEXT_MODEL,
        contents=user + "\n\nRespond with valid JSON only. No markdown fences.",
        config=types.GenerateContentConfig(
            system_instruction=augmented_system,
            max_output_tokens=max_tokens,
            temperature=0.9,
        ),
    ))
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
