"""Content Series Planning — multi-part series that build on each other.

Plans connected content series (Part 1, Part 2, etc.) that drive followers
to come back. Works especially well for carousels and threads.
"""

from __future__ import annotations

from typing import Any

from social_agent.ai import chat, parse_json
from social_agent.models.content import InfluencerProfile, NicheIntelligence


SERIES_PROMPT = """You are a content series strategist. Design a multi-part content series that builds audience anticipation and drives repeat engagement.

INFLUENCER VOICE: {voice_description}
TONE: {tone}
SERIES TOPIC: {topic}
NUMBER OF PARTS: {num_parts}
FORMAT: {format}
PLATFORM: {platform}

{trend_context}

Design a {num_parts}-part content series about "{topic}". Each part should:
- Stand alone (provide value even if someone only sees one part)
- Build on the previous part (reward followers who see them all)
- End with a hook that makes people want the next part
- Be formatted for {platform} as a {format}

Return JSON:
{{
  "series_title": "<overall series name>",
  "series_hook": "<one-line pitch for the whole series>",
  "parts": [
    {{
      "part_number": 1,
      "title": "<part title>",
      "hook": "<opening hook for this part>",
      "key_points": ["point 1", "point 2", ...],
      "cliffhanger": "<what makes people want Part 2>",
      "content_brief": "<full content brief for this part>"
    }},
    ...
  ],
  "posting_schedule": "<recommended cadence, e.g., 'every 2 days' or 'Mon/Wed/Fri'>",
  "cross_platform_strategy": "<how to promote the series across platforms>"
}}
"""


def plan_series(
    topic: str,
    num_parts: int = 5,
    format: str = "carousel",
    platform: str = "instagram",
    profile: InfluencerProfile | None = None,
    intelligence: NicheIntelligence | None = None,
) -> dict[str, Any]:
    """Plan a multi-part content series."""
    voice_desc = profile.voice.description if profile else "Professional content creator"
    tone = ", ".join(profile.voice.tone) if profile else "engaging"

    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = f"Current trends: {', '.join(intelligence.trending_topics[:5])}"

    user_prompt = SERIES_PROMPT.format(
        voice_description=voice_desc,
        tone=tone,
        topic=topic,
        num_parts=num_parts,
        format=format,
        platform=platform,
        trend_context=trend_context,
    )

    raw = chat(system="You are a content series strategist for social media creators.", user=user_prompt, max_tokens=4000)
    try:
        return parse_json(raw)
    except Exception:
        return {"error": "Failed to parse series plan"}
