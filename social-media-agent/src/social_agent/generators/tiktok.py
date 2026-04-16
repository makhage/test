"""TikTok caption and script generation using AI."""

from __future__ import annotations

from social_agent.ai import chat, parse_json
from social_agent.models.content import InfluencerProfile, NicheIntelligence, TikTokCaption


TIKTOK_SYSTEM_PROMPT = """You are a TikTok content strategist creating captions and scripts for the influencer described below.

INFLUENCER VOICE:
{voice_description}

TONE: {tone}
AVOID: {avoid}

EXAMPLE POSTS BY THIS INFLUENCER:
{examples}

{trend_context}

TIKTOK RULES:
- Caption: hook in the first line — make people stop scrolling
- Use line breaks for readability
- Include a CTA: {cta}
- Max hashtags: {max_hashtags}
- Suggest a trending sound/audio if relevant
- If providing script notes: write as talking points, not a word-for-word script
- Keep it conversational and authentic to TikTok culture
"""


def _build_system_prompt(
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"\nCURRENT TIKTOK TRENDS IN YOUR NICHE:\n"
            f"- Trending topics: {', '.join(intelligence.trending_topics[:5])}\n"
            f"- Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:5])}\n"
        )
        if intelligence.audience_questions:
            trend_context += f"- Questions your audience is asking (from Reddit): {', '.join(intelligence.audience_questions[:3])}\n"
        if intelligence.authentic_phrases:
            trend_context += f"- Real audience language: {', '.join(intelligence.authentic_phrases[:5])}\n"
        trend_context += "Mirror these trends. Sound like a real person, not an AI."

    tiktok_settings = profile.platforms.get("tiktok")
    max_hashtags = tiktok_settings.max_hashtags if tiktok_settings else 5
    cta = tiktok_settings.default_cta if tiktok_settings else ""

    return TIKTOK_SYSTEM_PROMPT.format(
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        avoid=", ".join(profile.voice.avoid),
        examples="\n".join(f'- "{p}"' for p in profile.voice.example_posts),
        trend_context=trend_context,
        max_hashtags=max_hashtags,
        cta=cta,
    )


def generate_tiktok_caption(
    topic: str,
    profile: InfluencerProfile,
    style: str = "educational",
    intelligence: NicheIntelligence | None = None,
) -> TikTokCaption:
    """Generate a TikTok caption and optional script notes using AI."""
    system = _build_system_prompt(profile, intelligence)
    user_prompt = (
        f"Create a TikTok caption about: {topic}\n"
        f"Style: {style}\n\n"
        f"Return JSON with keys:\n"
        f"- caption: string (the post caption with hook + body + CTA)\n"
        f"- hashtags: list of strings\n"
        f"- sound_suggestion: string or null (trending audio suggestion)\n"
        f"- script_notes: string or null (talking points if this is a talking-head video)"
    )

    raw = chat(system=system, user=user_prompt, max_tokens=1500)
    try:
        data = parse_json(raw)
    except Exception:
        data = {"caption": raw.strip(), "hashtags": []}

    return TikTokCaption(
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", []),
        sound_suggestion=data.get("sound_suggestion"),
        script_notes=data.get("script_notes"),
    )
