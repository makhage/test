"""Agent loop: Gemini with tool dispatch for social media content creation."""

from __future__ import annotations

import json
from typing import Any

from social_agent.ai import _get_client
from social_agent.generators.carousel import generate_carousel
from social_agent.generators.tiktok import generate_tiktok_caption
from social_agent.generators.tweet import generate_thread, generate_tweet
from social_agent.models.content import (
    Carousel,
    InfluencerProfile,
    NicheIntelligence,
    Platform,
    TikTokCaption,
    Tweet,
)
from social_agent.renderers.carousel_renderer import render_carousel


AGENT_SYSTEM_PROMPT = """You are a social media content automation agent for the influencer "{brand_name}".

VOICE: {voice_description}
TONE: {tone}

You help create, schedule, and manage social media content across Twitter/X, Instagram, and TikTok.

{trend_context}

You have the following tools available:
- generate_tweet: Create a tweet or thread
- generate_carousel: Create carousel slide content
- generate_tiktok: Create a TikTok caption/script
- render_carousel: Render carousel slides as branded images

Always use the influencer's authentic voice. Never produce generic AI content.
Ask clarifying questions if the request is ambiguous.
"""


def _build_agent_system(
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"CURRENT NICHE INTELLIGENCE:\n"
            f"Trending topics: {', '.join(intelligence.trending_topics[:5])}\n"
            f"Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:5])}\n"
            f"Top formats: {', '.join(intelligence.top_formats[:3])}\n"
            f"Use this intelligence to make content timely and engaging."
        )

    return AGENT_SYSTEM_PROMPT.format(
        brand_name=profile.brand.name,
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        trend_context=trend_context,
    )


def _tool_generate_tweet(
    topic: str,
    style: str = "engaging",
    is_thread: bool = False,
    num_tweets: int = 5,
    *,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    """Generate a tweet or thread."""
    if is_thread:
        result = generate_thread(
            topic=topic, profile=profile, num_tweets=num_tweets, intelligence=intelligence
        )
    else:
        result = generate_tweet(
            topic=topic, profile=profile, style=style, intelligence=intelligence
        )
    return result.model_dump_json(indent=2)


def _tool_generate_carousel(
    topic: str,
    num_slides: int = 7,
    platform: str = "instagram",
    *,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    """Generate a carousel."""
    result = generate_carousel(
        topic=topic,
        profile=profile,
        num_slides=num_slides,
        platform=Platform(platform),
        intelligence=intelligence,
    )
    return result.model_dump_json(indent=2)


def _tool_generate_tiktok(
    topic: str,
    style: str = "educational",
    *,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    """Generate a TikTok caption."""
    result = generate_tiktok_caption(
        topic=topic, profile=profile, style=style, intelligence=intelligence
    )
    return result.model_dump_json(indent=2)


def _tool_render_carousel(carousel_json: str, *, profile: InfluencerProfile, **_) -> str:
    """Render a carousel as images."""
    carousel = Carousel(**json.loads(carousel_json))
    paths = render_carousel(carousel, profile.brand)
    return json.dumps({"rendered_paths": [str(p) for p in paths]}, indent=2)


def run_agent(
    user_message: str,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
    max_iterations: int = 10,
) -> str:
    """Run the agent loop using Gemini's automatic function calling.

    Gemini's SDK supports passing Python functions directly as tools,
    so it handles the tool-dispatch loop for us.
    """
    from google.genai import types

    client = _get_client()
    system = _build_agent_system(profile, intelligence)

    # Wrap tool functions with the profile/intelligence context
    def tweet_tool(topic: str, style: str = "engaging", is_thread: bool = False, num_tweets: int = 5) -> str:
        """Generate a tweet or thread in the influencer's voice."""
        return _tool_generate_tweet(
            topic, style, is_thread, num_tweets,
            profile=profile, intelligence=intelligence,
        )

    def carousel_tool(topic: str, num_slides: int = 7, platform: str = "instagram") -> str:
        """Generate carousel slide content for Instagram or TikTok."""
        return _tool_generate_carousel(
            topic, num_slides, platform,
            profile=profile, intelligence=intelligence,
        )

    def tiktok_tool(topic: str, style: str = "educational") -> str:
        """Generate a TikTok caption and script notes."""
        return _tool_generate_tiktok(
            topic, style,
            profile=profile, intelligence=intelligence,
        )

    def render_tool(carousel_json: str) -> str:
        """Render a carousel JSON as branded PNG images."""
        return _tool_render_carousel(carousel_json, profile=profile)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[tweet_tool, carousel_tool, tiktok_tool, render_tool],
            ),
        )
        return response.text or "(No response)"
    except Exception as e:
        return f"Agent error: {e}"
