"""Performance Learning Loop — the agent learns what works and adjusts.

Analyzes historical engagement data to identify which content types,
topics, hooks, and posting times perform best, then feeds these insights
back into future content generation.
"""

from __future__ import annotations

import json
from typing import Any

from social_agent.ai import chat_json
from social_agent.db.database import (
    AnalyticsRecord,
    ContentVariantRecord,
    ScheduledPostRecord,
    get_session,
    init_db,
)


LEARNING_PROMPT = """You are a content performance analyst. Analyze this creator's posting history and engagement data to find patterns.

POSTING HISTORY WITH ENGAGEMENT:
{post_data}

Analyze the data and find:
1. **Top performing content types**: Which types (tweet, thread, carousel, tiktok) get the most engagement?
2. **Best topics**: Which topics/themes drive the highest engagement?
3. **Best hooks**: What opening styles/hooks consistently perform well?
4. **Best posting times**: When does content perform best?
5. **Platform comparison**: Which platform gives the best ROI?
6. **Declining patterns**: What used to work but is now declining?
7. **Recommendations**: Specific, actionable recommendations for next week's content.

Return JSON:
{{
  "top_content_types": [{{"type": "carousel", "avg_engagement": 1500, "trend": "growing"}}],
  "best_topics": [{{"topic": "Python tips", "avg_engagement": 2000}}],
  "best_hooks": [{{"pattern": "contrarian take", "avg_engagement": 1800}}],
  "best_posting_times": {{"twitter": ["09:00", "17:00"], "instagram": ["12:00"]}},
  "platform_ranking": ["instagram", "twitter", "tiktok"],
  "recommendations": [
    "Shift 60% of content to carousels — they get 3x the engagement of tweets",
    "Post more about Python — it consistently outperforms AI topics",
    ...
  ],
  "content_mix_suggestion": {{
    "twitter": {{"tweets": 3, "threads": 2}},
    "instagram": {{"carousels": 3}},
    "tiktok": {{"videos": 2}}
  }}
}}
"""


def gather_performance_data(days: int = 30) -> list[dict]:
    """Collect posting history with engagement metrics."""
    init_db()
    session = get_session()
    try:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        posts = (
            session.query(ScheduledPostRecord)
            .filter(ScheduledPostRecord.created_at >= cutoff)
            .all()
        )

        analytics = (
            session.query(AnalyticsRecord)
            .filter(AnalyticsRecord.recorded_at >= cutoff)
            .all()
        )
        analytics_by_post = {a.post_id: a for a in analytics}

        results = []
        for post in posts:
            a = analytics_by_post.get(str(post.id))
            results.append({
                "content_type": post.content_type,
                "platform": post.platform,
                "status": post.status,
                "content_preview": post.content_json[:200],
                "created_at": post.created_at.isoformat() if post.created_at else "",
                "likes": a.likes if a else 0,
                "shares": a.shares if a else 0,
                "comments": a.comments if a else 0,
                "impressions": a.impressions if a else 0,
                "total_engagement": (a.likes + a.shares + a.comments) if a else 0,
            })

        return sorted(results, key=lambda x: x["total_engagement"], reverse=True)
    finally:
        session.close()


def analyze_performance(days: int = 30) -> dict[str, Any]:
    """Run the learning loop: analyze performance and generate recommendations."""
    data = gather_performance_data(days)
    if not data:
        return {
            "recommendations": ["Not enough data yet. Post content and track engagement first."],
            "top_content_types": [],
            "best_topics": [],
        }

    post_text = "\n".join(
        f"[{d['platform']}/{d['content_type']}] Engagement: {d['total_engagement']} "
        f"(likes:{d['likes']} shares:{d['shares']} comments:{d['comments']}) "
        f"Posted: {d['created_at'][:10]} | {d['content_preview'][:100]}"
        for d in data
    )

    try:
        result = chat_json(
            system="You are a social media analytics expert.",
            user=LEARNING_PROMPT.format(post_data=post_text),
            max_tokens=3000,
        )
        return result or {"error": "Failed to parse response"}
    except Exception as e:
        return {"error": str(e)}


def get_generation_hints(days: int = 30) -> dict[str, Any]:
    """Get hints to inject into content generation prompts based on learned performance.

    Returns a dict that can be merged into the system prompt context.
    """
    analysis = analyze_performance(days)
    if "error" in analysis:
        return {}

    hints = {
        "preferred_content_types": [t["type"] for t in analysis.get("top_content_types", [])[:3]],
        "best_topics": [t["topic"] for t in analysis.get("best_topics", [])[:5]],
        "best_hooks": [h["pattern"] for h in analysis.get("best_hooks", [])[:3]],
        "content_mix": analysis.get("content_mix_suggestion", {}),
        "recommendations": analysis.get("recommendations", [])[:3],
    }
    return hints
