"""Batch content calendar generation informed by research intelligence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from social_agent.ai import chat, parse_json
from social_agent.models.content import InfluencerProfile, NicheIntelligence
from social_agent.research.analyzer import get_latest_intelligence


CALENDAR_PROMPT = """You are a content calendar strategist for a social media influencer.

INFLUENCER VOICE: {voice_description}
TOPICS OF EXPERTISE: {topics}

{trend_context}

Create a {days}-day content calendar starting from {start_date}.
{topic_instruction}

Guidelines:
- Mix content types: tweets, carousels, TikTok videos
- Spread across platforms based on optimal posting times
- Vary topics to avoid repetition
- Prioritize trending topics when relevant to the influencer's expertise
- Include at least 1-2 carousel posts per week (high engagement)
- Include thread posts for complex topics

Posting schedule:
- Twitter: {twitter_times}
- Instagram: {instagram_times}
- TikTok: {tiktok_times}

Return JSON array:
[
  {{
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "platform": "twitter|instagram|tiktok",
    "content_type": "tweet|thread|carousel|tiktok",
    "topic": "specific topic for this post",
    "hook_suggestion": "suggested opening hook",
    "notes": "any additional notes"
  }},
  ...
]
"""


def generate_calendar(
    profile: InfluencerProfile,
    days: int = 7,
    topics: list[str] | None = None,
    start_date: datetime | None = None,
) -> list[dict]:
    """Generate a content calendar for the specified number of days."""
    if start_date is None:
        start_date = datetime.utcnow()

    # Get current intelligence
    intel = get_latest_intelligence()
    trend_context = ""
    if intel and intel.trending_topics:
        trend_context = (
            f"CURRENT VIRAL TRENDS:\n"
            f"Trending: {', '.join(intel.trending_topics[:5])}\n"
            f"Winning hooks: {', '.join(h.pattern for h in intel.winning_hooks[:3])}\n"
            f"Prioritize these trending topics when they align with expertise."
        )

    all_topics = profile.topics.get("primary", []) + profile.topics.get("secondary", [])
    topic_instruction = ""
    if topics:
        topic_instruction = f"Focus on these specific topics: {', '.join(topics)}"

    posting_times = profile.content_settings.posting_times

    raw = chat(
        system="You are a content calendar strategist for social media influencers.",
        user=CALENDAR_PROMPT.format(
            voice_description=profile.voice.description,
            topics=", ".join(all_topics),
            trend_context=trend_context,
            days=days,
            start_date=start_date.strftime("%Y-%m-%d"),
            topic_instruction=topic_instruction,
            twitter_times=", ".join(posting_times.get("twitter", ["09:00", "12:30", "17:00"])),
            instagram_times=", ".join(posting_times.get("instagram", ["08:00", "12:00", "18:00"])),
            tiktok_times=", ".join(posting_times.get("tiktok", ["07:00", "12:00", "19:00"])),
        ),
        max_tokens=4000,
    )

    parsed = parse_json(raw)
    return parsed if isinstance(parsed, list) else []
