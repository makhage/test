"""Evergreen Content Recycling — refresh top-performing old posts.

Finds the creator's best content from 3+ months ago, rewrites it with
fresh hooks/angles, and suggests reposting. Most followers won't remember.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import anthropic

from social_agent.config import get_settings
from social_agent.db.database import AnalyticsRecord, ScheduledPostRecord, get_session, init_db
from social_agent.models.content import InfluencerProfile


RECYCLE_PROMPT = """You are a content recycling expert. Take this high-performing old post and create refreshed versions with new hooks and angles.

ORIGINAL POST (performed well {age} ago):
{original_content}

ENGAGEMENT: {engagement}

INFLUENCER VOICE: {voice_description}

Create 3 refreshed versions of this content:
1. **New hook**: Same core message, completely different opening line
2. **New angle**: Same topic, different perspective or framing
3. **Updated version**: Incorporate any new developments or trends

Return JSON:
{{
  "original_summary": "<what the original was about>",
  "why_recycle": "<why this content is worth reposting>",
  "refreshed": [
    {{
      "version": "new_hook",
      "content": "<full refreshed post text>",
      "what_changed": "<how this differs from original>"
    }},
    {{
      "version": "new_angle",
      "content": "<full refreshed post text>",
      "what_changed": "<how this differs from original>"
    }},
    {{
      "version": "updated",
      "content": "<full refreshed post text>",
      "what_changed": "<what was updated/added>"
    }}
  ]
}}
"""


def find_evergreen_candidates(min_age_days: int = 90, limit: int = 10) -> list[dict]:
    """Find top-performing posts that are old enough to recycle."""
    init_db()
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=min_age_days)

        posts = (
            session.query(ScheduledPostRecord)
            .filter(
                ScheduledPostRecord.status == "published",
                ScheduledPostRecord.created_at < cutoff,
            )
            .all()
        )

        # Join with analytics
        candidates = []
        for post in posts:
            analytics = (
                session.query(AnalyticsRecord)
                .filter_by(post_id=str(post.id))
                .first()
            )
            engagement = 0
            if analytics:
                engagement = analytics.likes + analytics.shares + analytics.comments

            age_days = (datetime.utcnow() - post.created_at).days if post.created_at else 0

            candidates.append({
                "id": post.id,
                "content_type": post.content_type,
                "platform": post.platform,
                "content": post.content_json[:500],
                "engagement": engagement,
                "age_days": age_days,
                "created_at": post.created_at.isoformat() if post.created_at else "",
            })

        return sorted(candidates, key=lambda x: x["engagement"], reverse=True)[:limit]
    finally:
        session.close()


def recycle_content(
    original_content: str,
    engagement: int,
    age_days: int,
    profile: InfluencerProfile,
) -> dict[str, Any]:
    """Generate refreshed versions of an evergreen post."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    age_str = f"{age_days // 30} months" if age_days > 60 else f"{age_days} days"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": RECYCLE_PROMPT.format(
                original_content=original_content,
                engagement=f"{engagement} total interactions",
                age=age_str,
                voice_description=profile.voice.description,
            ),
        }],
    )

    raw = response.content[0].text
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse recycled content"}
