"""Shared AI client — all text generation goes through OpenAI (GPT-4o).

This module provides a single `chat()` function that every generator
and research module calls. Centralizing here means:
- One place to swap models
- One place for auth (OAuth or API key via get_openai_client)
- Consistent JSON extraction from responses
"""

from __future__ import annotations

import json
from typing import Any

from social_agent.auth import get_openai_client

MODEL = "gpt-4o"


def chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
) -> str:
    """Send a chat completion request and return the assistant's text.

    Args:
        system: System prompt.
        user: User prompt.
        max_tokens: Maximum tokens in the response.
        model: Override the default model.

    Returns:
        The assistant's response text.
    """
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model or MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def chat_json(
    *,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str | None = None,
) -> dict[str, Any]:
    """Send a chat request and parse the response as JSON.

    Handles markdown code fences (```json ... ```) automatically.
    Returns an empty dict on parse failure.
    """
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
