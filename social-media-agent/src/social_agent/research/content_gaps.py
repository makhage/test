"""Content Gap Analysis — what the audience wants vs. what the creator actually posts.

Compares the creator's posting history against audience questions from
Reddit and comments. Finds blind spots: topics the audience cares about
that the creator rarely or never covers.
"""

from __future__ import annotations

import json
from typing import Any

from social_agent.ai import chat_json
from social_agent.db.database import (
    RedditPostRecord,
    ScheduledPostRecord,
    get_session,
    init_db,
)


GAP_ANALYSIS_PROMPT = """You are a content strategist. Analyze the gap between what this creator posts about and what their audience actually wants.

WHAT THE CREATOR POSTS ABOUT (their recent content):
{creator_content}

WHAT THE AUDIENCE IS ASKING ABOUT (from Reddit and comments):
{audience_demand}

Find the GAPS — topics the audience cares about that the creator rarely/never covers.

Return JSON:
{{
  "covered_topics": ["topics the creator already covers well"],
  "audience_demands": ["topics the audience frequently asks about"],
  "gaps": [
    {{
      "topic": "specific topic the audience wants but creator doesn't cover",
      "demand_signal": "how we know the audience wants this",
      "demand_strength": "high|medium|low",
      "opportunity": "why this is a good content opportunity",
      "suggested_content": "specific content piece the creator should make"
    }},
    ...
  ],
  "oversaturated": ["topics the creator posts too much about relative to audience interest"],
  "summary": "1-2 sentence summary of the biggest content opportunity"
}}
"""


def analyze_content_gaps(limit: int = 50) -> dict[str, Any]:
    """Compare creator's content against audience demand signals."""
    init_db()
    session = get_session()
    try:
        # Creator's content
        posts = (
            session.query(ScheduledPostRecord)
            .order_by(ScheduledPostRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        creator_text = "\n".join(
            f"[{p.platform}/{p.content_type}] {p.content_json[:200]}"
            for p in posts
        ) if posts else "(No posts yet — analyze based on profile topics only)"

        # Audience demand: Reddit questions + high-engagement posts
        reddit_questions = (
            session.query(RedditPostRecord)
            .filter(RedditPostRecord.content_type.in_(["question", "recommendation"]))
            .order_by(RedditPostRecord.upvotes.desc())
            .limit(limit)
            .all()
        )
        reddit_hot = (
            session.query(RedditPostRecord)
            .order_by(RedditPostRecord.upvotes.desc())
            .limit(30)
            .all()
        )

        audience_text = ""
        if reddit_questions:
            audience_text += "AUDIENCE QUESTIONS:\n" + "\n".join(
                f"- (r/{r.subreddit}, {r.upvotes} upvotes) {r.title}"
                for r in reddit_questions
            )
        if reddit_hot:
            audience_text += "\n\nTOP REDDIT DISCUSSIONS:\n" + "\n".join(
                f"- (r/{r.subreddit}, {r.upvotes} upvotes) {r.title}"
                for r in reddit_hot
            )

        # Also include mined comments if available
        try:
            from social_agent.research.comment_miner import MinedCommentRecord
            comments = (
                session.query(MinedCommentRecord)
                .filter(MinedCommentRecord.category.in_(["request", "question"]))
                .order_by(MinedCommentRecord.priority.desc())
                .limit(20)
                .all()
            )
            if comments:
                audience_text += "\n\nDIRECT AUDIENCE REQUESTS (from comments):\n" + "\n".join(
                    f"- ({c.platform}, priority {c.priority}) {c.extracted_topic or c.comment_text[:100]}"
                    for c in comments
                )
        except Exception:
            pass

        if not audience_text:
            return {"error": "No audience demand data. Run Reddit scan and comment mining first."}

        result = chat_json(
            system="You are a content strategist.",
            user=GAP_ANALYSIS_PROMPT.format(
                creator_content=creator_text,
                audience_demand=audience_text,
            ),
            max_tokens=3000,
        )
        if result:
            # Write gaps to knowledge base
            try:
                from social_agent.knowledge import remember_many
                entries = []
                for gap in result.get("gaps", [])[:8]:
                    demand = gap.get("demand_strength", "medium")
                    relevance = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(demand, 0.6)
                    content = f"{gap.get('topic', '')}: {gap.get('opportunity', '')}"
                    entries.append(("content_gap", content, "gap_analysis", relevance))
                if entries:
                    remember_many(entries)
            except Exception:
                pass
            return result
        return {"error": "Failed to parse gap analysis"}
    finally:
        session.close()
