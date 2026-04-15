"""Agent loop: Claude with tool dispatch for social media content creation."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from social_agent.config import get_settings
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
- schedule_post: Schedule content for posting
- list_scheduled: View pending posts

Always use the influencer's authentic voice. Never produce generic AI content.
Ask clarifying questions if the request is ambiguous.
"""

TOOLS = [
    {
        "name": "generate_tweet",
        "description": "Generate a tweet in the influencer's voice about a given topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What the tweet should be about"},
                "style": {
                    "type": "string",
                    "description": "Tone/style: engaging, educational, controversial, storytelling",
                    "default": "engaging",
                },
                "is_thread": {
                    "type": "boolean",
                    "description": "Whether to generate a multi-tweet thread",
                    "default": False,
                },
                "num_tweets": {
                    "type": "integer",
                    "description": "Number of tweets in the thread (if is_thread is true)",
                    "default": 5,
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "generate_carousel",
        "description": "Generate carousel slide content for Instagram or TikTok.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Carousel topic"},
                "num_slides": {
                    "type": "integer",
                    "description": "Number of slides (default 7)",
                    "default": 7,
                },
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "tiktok"],
                    "default": "instagram",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "render_carousel",
        "description": "Render carousel data as branded PNG images.",
        "input_schema": {
            "type": "object",
            "properties": {
                "carousel_json": {
                    "type": "string",
                    "description": "JSON-serialized Carousel object from generate_carousel",
                },
            },
            "required": ["carousel_json"],
        },
    },
    {
        "name": "generate_tiktok",
        "description": "Generate a TikTok caption and script notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "TikTok video topic"},
                "style": {
                    "type": "string",
                    "description": "Style: educational, storytelling, trend-reaction, tutorial",
                    "default": "educational",
                },
            },
            "required": ["topic"],
        },
    },
]


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


def _handle_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    """Execute a tool and return the result as a string."""
    if tool_name == "generate_tweet":
        if tool_input.get("is_thread"):
            result = generate_thread(
                topic=tool_input["topic"],
                profile=profile,
                num_tweets=tool_input.get("num_tweets", 5),
                intelligence=intelligence,
            )
        else:
            result = generate_tweet(
                topic=tool_input["topic"],
                profile=profile,
                style=tool_input.get("style", "engaging"),
                intelligence=intelligence,
            )
        return result.model_dump_json(indent=2)

    elif tool_name == "generate_carousel":
        platform = Platform(tool_input.get("platform", "instagram"))
        result = generate_carousel(
            topic=tool_input["topic"],
            profile=profile,
            num_slides=tool_input.get("num_slides", 7),
            platform=platform,
            intelligence=intelligence,
        )
        return result.model_dump_json(indent=2)

    elif tool_name == "render_carousel":
        carousel_data = json.loads(tool_input["carousel_json"])
        carousel = Carousel(**carousel_data)
        paths = render_carousel(carousel, profile.brand)
        return json.dumps({"rendered_paths": [str(p) for p in paths]}, indent=2)

    elif tool_name == "generate_tiktok":
        result = generate_tiktok_caption(
            topic=tool_input["topic"],
            profile=profile,
            style=tool_input.get("style", "educational"),
            intelligence=intelligence,
        )
        return result.model_dump_json(indent=2)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run_agent(
    user_message: str,
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
    max_iterations: int = 10,
) -> str:
    """Run the agent loop: send user message, handle tool calls, return final response."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system = _build_agent_system(profile, intelligence)

    messages: list[dict] = [{"role": "user", "content": user_message}]

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Check if we have tool use blocks
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No tool calls — extract final text response
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_blocks)

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_block in tool_use_blocks:
            result = _handle_tool_call(
                tool_name=tool_block.name,
                tool_input=tool_block.input,
                profile=profile,
                intelligence=intelligence,
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    return "Agent reached maximum iterations. Please try a more specific request."
