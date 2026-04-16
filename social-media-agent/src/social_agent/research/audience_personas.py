"""Audience Persona Modeling — build detailed personas from data.

Uses Reddit discussions, comment analysis, engagement patterns, and
niche intelligence to build detailed personas of the creator's audience.
"""

from __future__ import annotations

import json
from typing import Any

from social_agent.ai import chat_json
from social_agent.db.database import (
    AnalyticsRecord,
    RedditPostRecord,
    get_session,
    init_db,
)
from social_agent.models.content import InfluencerProfile


PERSONA_PROMPT = """You are an audience research expert. Build detailed audience personas from this data.

CREATOR'S NICHE: {niche_description}
TOPICS THEY COVER: {topics}

DATA FROM THEIR AUDIENCE'S COMMUNITIES (Reddit):
{reddit_data}

AUDIENCE ENGAGEMENT PATTERNS:
{engagement_data}

AUDIENCE COMMENTS & REQUESTS:
{comment_data}

Build 3-4 distinct audience personas. Each persona should feel like a real person — give them a name, backstory, and specific behaviors.

Return JSON:
{{
  "personas": [
    {{
      "name": "<first name>",
      "title": "<short description, e.g., 'The Career Switcher'>",
      "demographics": {{
        "age_range": "25-35",
        "occupation": "junior developer",
        "experience_level": "1-3 years",
        "location_type": "urban, US/EU"
      }},
      "backstory": "<2-3 sentence backstory>",
      "goals": ["goal 1", "goal 2"],
      "pain_points": ["pain 1", "pain 2"],
      "content_preferences": {{
        "favorite_formats": ["carousel", "tutorial thread"],
        "favorite_topics": ["Python basics", "career advice"],
        "browsing_time": "evenings and weekends",
        "platforms": ["instagram", "reddit", "youtube"]
      }},
      "what_makes_them_follow": "<what content hooks them>",
      "what_makes_them_unfollow": "<what turns them off>",
      "percentage_of_audience": 35
    }},
    ...
  ],
  "overall_insights": [
    "insight about the audience as a whole",
    ...
  ],
  "content_implications": [
    "what this means for content strategy",
    ...
  ]
}}
"""


def build_audience_personas(
    profile: InfluencerProfile,
) -> dict[str, Any]:
    """Build detailed audience personas from all available data."""
    init_db()
    session = get_session()
    try:
        # Reddit data — what the audience discusses
        reddit_posts = (
            session.query(RedditPostRecord)
            .order_by(RedditPostRecord.upvotes.desc())
            .limit(40)
            .all()
        )
        reddit_text = "\n".join(
            f"[r/{r.subreddit}] [{r.content_type}] ({r.upvotes} upvotes) {r.title}"
            for r in reddit_posts
        ) if reddit_posts else "(No Reddit data — scan subreddits first)"

        # Engagement data
        analytics = (
            session.query(AnalyticsRecord)
            .order_by(AnalyticsRecord.recorded_at.desc())
            .limit(30)
            .all()
        )
        engagement_text = "\n".join(
            f"[{a.platform}] Likes: {a.likes} Shares: {a.shares} Comments: {a.comments} "
            f"Impressions: {a.impressions}"
            for a in analytics
        ) if analytics else "(No engagement data yet)"

        # Mined comments
        comment_text = ""
        try:
            from social_agent.research.comment_miner import MinedCommentRecord
            comments = (
                session.query(MinedCommentRecord)
                .order_by(MinedCommentRecord.priority.desc())
                .limit(30)
                .all()
            )
            if comments:
                comment_text = "\n".join(
                    f"[{c.category}] (priority {c.priority}) {c.comment_text[:150]}"
                    for c in comments
                )
        except Exception:
            pass

        all_topics = profile.topics.get("primary", []) + profile.topics.get("secondary", [])

        try:
            result = chat_json(
                system="You are an audience research expert.",
                user=PERSONA_PROMPT.format(
                    niche_description=profile.voice.description,
                    topics=", ".join(all_topics),
                    reddit_data=reddit_text,
                    engagement_data=engagement_text,
                    comment_data=comment_text or "(No comment data)",
                ),
                max_tokens=4000,
            )
            return result if result else {"error": "Failed to parse personas"}
        except Exception as e:
            return {"error": str(e)}
    finally:
        session.close()
