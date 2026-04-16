"""AI-powered viral pattern extraction and analysis."""

from __future__ import annotations

import json
from datetime import datetime

from social_agent.ai import chat_json, parse_json
from social_agent.db.database import (
    NicheIntelligenceRecord,
    RedditPostRecord,
    ViralPostRecord,
    get_session,
    init_db,
)
from social_agent.models.content import HookPattern, NicheIntelligence


ANALYSIS_PROMPT = """You are a viral content analyst. Analyze the following high-performing content from social media AND Reddit, then extract patterns that make content resonate with real audiences.

VIRAL SOCIAL MEDIA POSTS:
{posts}

TOP REDDIT DISCUSSIONS (these show what real people care about — their questions, opinions, and language):
{reddit_posts}

Analyze ALL of this content and extract:
1. **Trending Topics**: What specific topics are getting the most engagement? Include topics from both social media AND Reddit. List the top 5-10 topics.
2. **Winning Hooks**: What opening lines/hooks grab attention? Look at both social media hooks AND Reddit post titles (Reddit titles that get 1000+ upvotes are proven hooks). Identify the pattern (e.g., "contrarian take", "question hook", "bold claim", "TIL/discovery", "myth-busting", "unpopular opinion"). Give the pattern name and an example.
3. **Audience Pain Points**: What questions are people asking on Reddit? What are they struggling with? These are guaranteed content topics.
4. **Hot Takes & Opinions**: What controversial or contrarian views are getting engagement on Reddit? These make great social media content.
5. **Top Formats**: What content formats are performing best? (thread, single tweet, carousel, listicle, tutorial, opinion piece, etc.)
6. **Authentic Language**: What phrases, slang, or ways of explaining things do real people use on Reddit? (This helps content sound human, not AI-generated.)
7. **Engagement Benchmarks**: What are the average engagement metrics?

Return JSON:
{{
  "trending_topics": ["topic1", "topic2", ...],
  "winning_hooks": [
    {{"pattern": "pattern name", "example": "example opening line", "frequency": N}},
    ...
  ],
  "audience_questions": ["question people are asking 1", "question 2", ...],
  "hot_takes": ["contrarian opinion 1", "hot take 2", ...],
  "authentic_phrases": ["phrase real people use 1", "phrase 2", ...],
  "top_formats": ["format1", "format2", ...],
  "engagement_benchmarks": {{"avg_likes": N, "avg_shares": N, "avg_comments": N, "avg_reddit_upvotes": N}}
}}
"""


def analyze_viral_content(limit: int = 50) -> NicheIntelligence | None:
    """Analyze recent viral posts + Reddit discussions and extract patterns."""
    init_db()
    session = get_session()

    try:
        records = (
            session.query(ViralPostRecord)
            .order_by(ViralPostRecord.likes.desc())
            .limit(limit)
            .all()
        )

        # Also fetch Reddit posts
        reddit_records = (
            session.query(RedditPostRecord)
            .order_by(RedditPostRecord.upvotes.desc())
            .limit(limit)
            .all()
        )

        if not records and not reddit_records:
            return None

        # Format social media posts for Gemini
        posts_text = "\n\n".join(
            f"[{r.platform}] Likes: {r.likes} | Shares: {r.shares} | Comments: {r.comments}\n{r.text}"
            for r in records
        ) if records else "(No social media posts scraped yet)"

        # Format Reddit posts for Gemini — include titles, selftext, AND top comments
        reddit_parts: list[str] = []
        for r in reddit_records:
            comments = json.loads(r.top_comments) if r.top_comments else []
            comments_text = "\n  ".join(f"- {c[:200]}" for c in comments[:3])
            reddit_parts.append(
                f"[r/{r.subreddit}] [{r.content_type}] Upvotes: {r.upvotes} | Comments: {r.num_comments}\n"
                f"Title: {r.title}\n"
                f"{r.selftext[:300] if r.selftext else ''}"
                f"{chr(10) + '  Top comments:' + chr(10) + '  ' + comments_text if comments_text else ''}"
            )
        reddit_text = "\n\n".join(reddit_parts) if reddit_parts else "(No Reddit posts scraped yet)"

        data = chat_json(
            system="You are a viral content analyst.",
            user=ANALYSIS_PROMPT.format(posts=posts_text, reddit_posts=reddit_text),
            max_tokens=3000,
        )
        if not data:
            return None

        hooks = [
            HookPattern(
                pattern=h.get("pattern", ""),
                example=h.get("example", ""),
                frequency=h.get("frequency", 0),
            )
            for h in data.get("winning_hooks", [])
        ]

        total_sources = len(records) + len(reddit_records)
        intelligence = NicheIntelligence(
            trending_topics=data.get("trending_topics", []),
            winning_hooks=hooks,
            top_formats=data.get("top_formats", []),
            engagement_benchmarks=data.get("engagement_benchmarks", {}),
            audience_questions=data.get("audience_questions", []),
            hot_takes=data.get("hot_takes", []),
            authentic_phrases=data.get("authentic_phrases", []),
            source_post_count=total_sources,
        )

        # Save to database
        record = NicheIntelligenceRecord(
            trending_topics=json.dumps(intelligence.trending_topics),
            winning_hooks=json.dumps([h.model_dump() for h in intelligence.winning_hooks]),
            top_formats=json.dumps(intelligence.top_formats),
            engagement_benchmarks=json.dumps(intelligence.engagement_benchmarks),
            audience_questions=json.dumps(intelligence.audience_questions),
            hot_takes=json.dumps(intelligence.hot_takes),
            authentic_phrases=json.dumps(intelligence.authentic_phrases),
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
            audience_questions=json.loads(record.audience_questions) if record.audience_questions else [],
            hot_takes=json.loads(record.hot_takes) if record.hot_takes else [],
            authentic_phrases=json.loads(record.authentic_phrases) if record.authentic_phrases else [],
            source_post_count=record.source_post_count,
            generated_at=record.generated_at,
        )
    finally:
        session.close()
