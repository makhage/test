"""Claude-powered viral pattern extraction and analysis."""

from __future__ import annotations

import json
from datetime import datetime

import anthropic

from social_agent.config import get_settings
from social_agent.db.database import (
    NicheIntelligenceRecord,
    ViralPostRecord,
    get_session,
    init_db,
)
from social_agent.models.content import HookPattern, NicheIntelligence


ANALYSIS_PROMPT = """You are a viral content analyst. Analyze the following high-performing social media posts and extract patterns.

VIRAL POSTS:
{posts}

Analyze these posts and extract:
1. **Trending Topics**: What specific topics are these posts about? List the top 5-10 topics.
2. **Winning Hooks**: What opening lines/hooks are these posts using? Identify the pattern (e.g., "contrarian take", "numbered list", "question hook", "bold claim"). Give the pattern name and an example.
3. **Top Formats**: What content formats are performing best? (thread, single tweet, carousel, listicle, story, tutorial, etc.)
4. **Engagement Benchmarks**: What are the average likes, shares, comments?

Return JSON:
{{
  "trending_topics": ["topic1", "topic2", ...],
  "winning_hooks": [
    {{"pattern": "pattern name", "example": "example opening line", "frequency": N}},
    ...
  ],
  "top_formats": ["format1", "format2", ...],
  "engagement_benchmarks": {{"avg_likes": N, "avg_shares": N, "avg_comments": N}}
}}
"""


def analyze_viral_content(limit: int = 50) -> NicheIntelligence | None:
    """Analyze recent viral posts from the database and extract patterns."""
    init_db()
    session = get_session()

    try:
        records = (
            session.query(ViralPostRecord)
            .order_by(ViralPostRecord.likes.desc())
            .limit(limit)
            .all()
        )

        if not records:
            return None

        # Format posts for Claude
        posts_text = "\n\n".join(
            f"[{r.platform}] Likes: {r.likes} | Shares: {r.shares} | Comments: {r.comments}\n{r.text}"
            for r in records
        )

        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": ANALYSIS_PROMPT.format(posts=posts_text),
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
            return None

        hooks = [
            HookPattern(
                pattern=h.get("pattern", ""),
                example=h.get("example", ""),
                frequency=h.get("frequency", 0),
            )
            for h in data.get("winning_hooks", [])
        ]

        intelligence = NicheIntelligence(
            trending_topics=data.get("trending_topics", []),
            winning_hooks=hooks,
            top_formats=data.get("top_formats", []),
            engagement_benchmarks=data.get("engagement_benchmarks", {}),
            source_post_count=len(records),
        )

        # Save to database
        record = NicheIntelligenceRecord(
            trending_topics=json.dumps(intelligence.trending_topics),
            winning_hooks=json.dumps([h.model_dump() for h in intelligence.winning_hooks]),
            top_formats=json.dumps(intelligence.top_formats),
            engagement_benchmarks=json.dumps(intelligence.engagement_benchmarks),
            source_post_count=intelligence.source_post_count,
        )
        session.add(record)
        session.commit()

        return intelligence
    finally:
        session.close()


def get_latest_intelligence() -> NicheIntelligence | None:
    """Retrieve the most recent niche intelligence from the database."""
    init_db()
    session = get_session()

    try:
        record = (
            session.query(NicheIntelligenceRecord)
            .order_by(NicheIntelligenceRecord.generated_at.desc())
            .first()
        )
        if not record:
            return None

        hooks_data = json.loads(record.winning_hooks)
        hooks = [
            HookPattern(
                pattern=h.get("pattern", ""),
                example=h.get("example", ""),
                frequency=h.get("frequency", 0),
                avg_engagement=h.get("avg_engagement", 0.0),
            )
            for h in hooks_data
        ]

        return NicheIntelligence(
            trending_topics=json.loads(record.trending_topics),
            winning_hooks=hooks,
            top_formats=json.loads(record.top_formats),
            engagement_benchmarks=json.loads(record.engagement_benchmarks),
            source_post_count=record.source_post_count,
            generated_at=record.generated_at,
        )
    finally:
        session.close()
