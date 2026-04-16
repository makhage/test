"""Carousel slide content generation using AI."""

from __future__ import annotations

from social_agent.ai import chat, parse_json
from social_agent.models.content import (
    Carousel,
    CarouselSlide,
    InfluencerProfile,
    NicheIntelligence,
    Platform,
)


CAROUSEL_SYSTEM_PROMPT = """You are a social media content strategist creating carousel slides for the influencer described below.

INFLUENCER VOICE:
{voice_description}

TONE: {tone}
AVOID: {avoid}

EXAMPLE POSTS BY THIS INFLUENCER:
{examples}

{trend_context}

CAROUSEL RULES:
- Slide 1: Title/hook slide — the most important slide. Must stop the scroll.
- Slides 2-{last_content}: Content slides with one key point each. Concise headings, short body text.
- Last slide: CTA slide — encourage saves, follows, shares.
- Headings: max 8 words, punchy and direct
- Body text: max 3 sentences per slide, conversational
- Each slide should provide standalone value
- Write in the influencer's authentic voice
- CTA: {cta}

BRAND COLORS (for image_prompt context):
Primary: {primary_color}, Secondary: {secondary_color}, Accent: {accent_color}
"""


def _build_system_prompt(
    profile: InfluencerProfile,
    num_slides: int,
    intelligence: NicheIntelligence | None = None,
) -> str:
    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"\nCURRENT VIRAL CAROUSEL PATTERNS IN YOUR NICHE:\n"
            f"- Trending topics: {', '.join(intelligence.trending_topics[:5])}\n"
            f"- Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:5])}\n"
            f"- Top formats: {', '.join(intelligence.top_formats[:3])}\n"
        )
        if intelligence.audience_questions:
            trend_context += f"- Questions your audience is asking (from Reddit): {', '.join(intelligence.audience_questions[:5])}\n"
        if intelligence.hot_takes:
            trend_context += f"- Contrarian opinions getting engagement: {', '.join(intelligence.hot_takes[:3])}\n"
        if intelligence.authentic_phrases:
            trend_context += f"- Real audience language to incorporate: {', '.join(intelligence.authentic_phrases[:5])}\n"
        trend_context += "Mirror these patterns. Use the audience's real language to make slides feel authentic."

    ig_settings = profile.platforms.get("instagram")
    cta = ig_settings.default_cta if ig_settings else ""

    return CAROUSEL_SYSTEM_PROMPT.format(
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        avoid=", ".join(profile.voice.avoid),
        examples="\n".join(f'- "{p}"' for p in profile.voice.example_posts),
        trend_context=trend_context,
        last_content=num_slides - 1,
        cta=cta,
        primary_color=profile.brand.primary_color,
        secondary_color=profile.brand.secondary_color,
        accent_color=profile.brand.accent_color,
    )


def generate_carousel(
    topic: str,
    profile: InfluencerProfile,
    num_slides: int = 7,
    platform: Platform = Platform.INSTAGRAM,
    intelligence: NicheIntelligence | None = None,
) -> Carousel:
    """Generate carousel slide content using AI."""
    system = _build_system_prompt(profile, num_slides, intelligence)
    user_prompt = (
        f"Create a {num_slides}-slide carousel about: {topic}\n"
        f"Platform: {platform.value}\n\n"
        f"Return JSON with keys:\n"
        f"- title: string (carousel title)\n"
        f"- caption: string (post caption, can be longer)\n"
        f"- hashtags: list of strings\n"
        f"- slides: list of objects, each with:\n"
        f"  - heading: string (max 8 words)\n"
        f"  - body: string (2-3 sentences)\n"
        f'  - image_prompt: string (brief description for AI background image, e.g., "abstract neural network flowing data")'
    )

    raw = chat(system=system, user=user_prompt, max_tokens=3000)
    try:
        data = parse_json(raw)
    except Exception:
        data = {
            "title": topic,
            "caption": "",
            "hashtags": [],
            "slides": [{"heading": topic, "body": "Content generation error — please retry."}],
        }

    slides = [
        CarouselSlide(
            heading=s.get("heading", ""),
            body=s.get("body", ""),
            image_prompt=s.get("image_prompt"),
        )
        for s in data.get("slides", [])
    ]

    return Carousel(
        title=data.get("title", topic),
        slides=slides,
        platform=platform,
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", []),
    )
