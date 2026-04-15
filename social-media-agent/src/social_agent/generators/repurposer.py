"""Cross-platform content repurposing — one topic → all platforms."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from social_agent.config import get_settings
from social_agent.models.content import (
    Carousel,
    CarouselSlide,
    InfluencerProfile,
    NicheIntelligence,
    Platform,
    TikTokCaption,
    Tweet,
)


REPURPOSE_PROMPT = """You are a multi-platform content strategist. Create adapted content for each platform from a single topic.

INFLUENCER VOICE:
{voice_description}
Tone: {tone}

TOPIC: {topic}

Create content adapted for each platform. Each version should be tailored to the platform's
audience behavior, format constraints, and engagement patterns — NOT just copy-pasted.

Return JSON:
{{
  "twitter": {{
    "text": "<tweet text, max 280 chars, hook-driven>",
    "hashtags": ["tag1", "tag2"],
    "is_thread": false
  }},
  "instagram": {{
    "title": "<carousel title>",
    "slides": [
      {{"heading": "<max 8 words>", "body": "<2-3 sentences>", "image_prompt": "<background description>"}},
      ...
    ],
    "caption": "<instagram caption with hook + value + CTA>",
    "hashtags": ["tag1", "tag2", ...]
  }},
  "tiktok": {{
    "caption": "<tiktok caption with hook>",
    "hashtags": ["tag1", "tag2"],
    "sound_suggestion": "<trending audio or null>",
    "script_notes": "<talking points for video>"
  }}
}}
"""


def repurpose_content(
    topic: str,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> dict[str, Any]:
    """Generate content for all platforms from a single topic."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"\nCurrent trends: {', '.join(intelligence.trending_topics[:5])}\n"
            f"Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:3])}"
        )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": REPURPOSE_PROMPT.format(
                voice_description=profile.voice.description,
                tone=", ".join(profile.voice.tone),
                topic=f"{topic}{trend_context}",
            ),
        }],
    )

    raw = response.content[0].text
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse repurposed content"}

    results: dict[str, Any] = {}

    # Twitter
    tw = data.get("twitter", {})
    if tw:
        results["twitter"] = Tweet(
            text=tw.get("text", "")[:280],
            hashtags=tw.get("hashtags", []),
            is_thread=tw.get("is_thread", False),
            thread_tweets=tw.get("thread_tweets", []),
        )

    # Instagram
    ig = data.get("instagram", {})
    if ig:
        slides = [
            CarouselSlide(
                heading=s.get("heading", ""),
                body=s.get("body", ""),
                image_prompt=s.get("image_prompt"),
            )
            for s in ig.get("slides", [])
        ]
        results["instagram"] = Carousel(
            title=ig.get("title", topic),
            slides=slides,
            platform=Platform.INSTAGRAM,
            caption=ig.get("caption", ""),
            hashtags=ig.get("hashtags", []),
        )

    # TikTok
    tt = data.get("tiktok", {})
    if tt:
        results["tiktok"] = TikTokCaption(
            caption=tt.get("caption", ""),
            hashtags=tt.get("hashtags", []),
            sound_suggestion=tt.get("sound_suggestion"),
            script_notes=tt.get("script_notes"),
        )

    return results
