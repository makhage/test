"""Early Trend Detection — catch rising topics before they peak.

Tracks posting velocity on Reddit (posts per hour) to detect topics
that are gaining momentum. The goal: post FIRST, not last.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import anthropic

from social_agent.config import get_settings
from social_agent.db.database import RedditPostRecord, get_session, init_db


def calculate_trend_velocity(hours: int = 48) -> list[dict]:
    """Calculate which topics are accelerating in posting frequency.

    Compares the last `hours/2` period to the previous `hours/2` period.
    Topics that are speeding up = emerging trends.
    """
    init_db()
    session = get_session()
    try:
        now = datetime.utcnow()
        midpoint = now - timedelta(hours=hours // 2)
        start = now - timedelta(hours=hours)

        # Recent period
        recent = (
            session.query(RedditPostRecord)
            .filter(RedditPostRecord.scraped_at >= midpoint)
            .all()
        )

        # Earlier period
        earlier = (
            session.query(RedditPostRecord)
            .filter(
                RedditPostRecord.scraped_at >= start,
                RedditPostRecord.scraped_at < midpoint,
            )
            .all()
        )

        # Count keywords/topics in each period
        def extract_keywords(posts):
            from collections import Counter
            words = Counter()
            for p in posts:
                # Use title words as proxies for topics
                for word in p.title.lower().split():
                    if len(word) > 4 and word.isalpha():
                        words[word] += 1
            return words

        recent_keywords = extract_keywords(recent)
        earlier_keywords = extract_keywords(earlier)

        # Find accelerating topics
        velocities = []
        for word, recent_count in recent_keywords.items():
            earlier_count = earlier_keywords.get(word, 0)
            if recent_count >= 3:  # Minimum threshold
                if earlier_count == 0:
                    velocity = recent_count * 2  # New topic = high velocity
                else:
                    velocity = (recent_count - earlier_count) / max(earlier_count, 1)

                if velocity > 0:
                    velocities.append({
                        "keyword": word,
                        "recent_count": recent_count,
                        "earlier_count": earlier_count,
                        "velocity": round(velocity, 2),
                        "trend": "new" if earlier_count == 0 else "accelerating",
                    })

        return sorted(velocities, key=lambda x: x["velocity"], reverse=True)[:20]
    finally:
        session.close()


def detect_emerging_topics(
    profile_topics: list[str] | None = None,
) -> dict[str, Any]:
    """Detect emerging topics and match them against the creator's expertise.

    Returns topics the creator should post about NOW — before they peak.
    """
    settings = get_settings()

    velocities = calculate_trend_velocity()
    if not velocities:
        return {"emerging": [], "recommendations": []}

    # If we have Claude, get a smarter analysis
    if settings.anthropic_api_key:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        topics_context = ""
        if profile_topics:
            topics_context = f"\nCreator's expertise: {', '.join(profile_topics)}"

        prompt = (
            f"These keywords are accelerating on Reddit right now (velocity = how fast they're growing):\n\n"
            + "\n".join(f"- {v['keyword']} (velocity: {v['velocity']}, mentions: {v['recent_count']}, trend: {v['trend']})" for v in velocities[:15])
            + f"\n{topics_context}\n\n"
            f"Identify the 5 most promising EMERGING TOPICS (group related keywords). "
            f"For each, explain: what's happening, why it's trending, and suggest a content angle.\n\n"
            f"Return JSON:\n"
            f'{{"emerging_topics": [{{"topic": "...", "keywords": [...], "velocity": N, '
            f'"what": "what\'s happening", "why": "why now", "content_angle": "suggested post angle", '
            f'"urgency": "high|medium|low"}}]}}'
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw.strip())
        except (json.JSONDecodeError, IndexError):
            pass

    # Fallback: return raw velocities
    return {
        "emerging_topics": [
            {"topic": v["keyword"], "velocity": v["velocity"], "urgency": "high" if v["velocity"] > 2 else "medium"}
            for v in velocities[:10]
        ]
    }
