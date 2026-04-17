"""Comment Mining — scrape the creator's own comment sections for content ideas.

When followers comment "Can you make a video about X?" or "How do I do Y?" —
those are guaranteed content topics because the audience is literally asking.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import requests
import tweepy

from social_agent.ai import chat_json
from social_agent.config import get_settings
from social_agent.db.database import get_session, init_db, Base
from social_agent.models.content import InfluencerProfile

from sqlalchemy import Column, DateTime, Integer, String, Text, Float
from social_agent.db.database import Base


class MinedCommentRecord(Base):
    __tablename__ = "mined_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)
    post_url = Column(String(500), default="")
    comment_author = Column(String(100), default="")
    comment_text = Column(Text, nullable=False)
    likes = Column(Integer, default=0)
    category = Column(String(50), default="")  # request, question, feedback, idea
    extracted_topic = Column(String(300), default="")
    priority = Column(Float, default=0.0)
    scraped_at = Column(DateTime, default=datetime.utcnow)


def mine_youtube_comments(video_url: str, max_comments: int = 100) -> list[dict]:
    """Extract comments from a YouTube video using yt-dlp."""
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "getcomments": True,
            "extractor_args": {"youtube": {"max_comments": [str(max_comments)]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        comments = info.get("comments", [])
        return [
            {
                "platform": "youtube",
                "post_url": video_url,
                "author": c.get("author", ""),
                "text": c.get("text", ""),
                "likes": c.get("like_count", 0),
            }
            for c in comments if c.get("text")
        ]
    except Exception:
        return []


def mine_twitter_replies(tweet_id: str) -> list[dict]:
    """Fetch replies to a specific tweet."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return []

    client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
    try:
        # Search for replies
        query = f"conversation_id:{tweet_id} is:reply"
        response = client.search_recent_tweets(
            query=query,
            max_results=100,
            tweet_fields=["public_metrics", "author_id"],
        )
        if not response.data:
            return []

        return [
            {
                "platform": "twitter",
                "post_url": f"https://x.com/i/status/{tweet_id}",
                "author": str(t.author_id),
                "text": t.text,
                "likes": (t.public_metrics or {}).get("like_count", 0),
            }
            for t in response.data
        ]
    except Exception:
        return []


class _SilentLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def mine_ytdlp_comments(video_url: str, platform: str, max_comments: int = 100) -> list[dict]:
    """Best-effort comment extraction via yt-dlp for TikTok / Instagram / others.

    yt-dlp supports comments on YouTube fully and TikTok / Instagram
    partially. We run it with ignoreerrors so platforms that refuse
    silently return no comments instead of exploding.
    """
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "getcomments": True,
            "ignoreerrors": True,
            "logger": _SilentLogger(),
            "extractor_args": {"youtube": {"max_comments": [str(max_comments)]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        if not info:
            return []
        comments = info.get("comments") or []
        return [
            {
                "platform": platform,
                "post_url": video_url,
                "author": c.get("author", "") or c.get("author_id", ""),
                "text": c.get("text", ""),
                "likes": c.get("like_count", 0) or 0,
            }
            for c in comments if c.get("text")
        ]
    except Exception:
        return []


def _detect_platform(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "twitter.com" in u or "x.com" in u:
        return "twitter"
    return "video"


def mine_video_comments(video: dict | str, max_comments: int = 100) -> list[dict]:
    """Mine comments from a single video, auto-dispatching by platform.

    Accepts either a URL string or a dict with platform+url keys.
    """
    if isinstance(video, str):
        url = video
        platform = _detect_platform(url)
    else:
        url = video.get("url", "")
        platform = video.get("platform") or _detect_platform(url)

    if not url:
        return []

    if platform == "youtube":
        return mine_youtube_comments(url, max_comments=max_comments)
    if platform == "twitter":
        # Extract tweet ID from URL
        import re as _re
        m = _re.search(r"/status/(\d+)", url)
        if m:
            return mine_twitter_replies(m.group(1))
        return []
    # TikTok / Instagram / unknown → best-effort via yt-dlp
    return mine_ytdlp_comments(url, platform, max_comments=max_comments)


def mine_from_videos(videos: list[dict], max_per_video: int = 100) -> dict[str, Any]:
    """Iterate a list of videos, mine comments from each, and persist.

    Returns a summary: {'total': int, 'by_platform': {...}, 'videos_scanned': int}.
    """
    init_db()
    all_comments: list[dict] = []
    by_platform: dict[str, int] = {}

    for v in videos:
        url = v.get("url") if isinstance(v, dict) else v
        if not url:
            continue
        mined = mine_video_comments(v, max_comments=max_per_video)
        for c in mined:
            all_comments.append(c)
            p = c.get("platform", "unknown")
            by_platform[p] = by_platform.get(p, 0) + 1

    session = get_session()
    try:
        for c in all_comments:
            session.add(MinedCommentRecord(
                platform=c["platform"],
                post_url=c.get("post_url", ""),
                comment_author=c.get("author", ""),
                comment_text=c["text"],
                likes=c.get("likes", 0),
            ))
        session.commit()
    finally:
        session.close()

    return {
        "total": len(all_comments),
        "by_platform": by_platform,
        "videos_scanned": len(videos),
    }


def mine_all_comments(
    profile: InfluencerProfile,
    video_urls: list[str] | None = None,
    tweet_ids: list[str] | None = None,
) -> list[dict]:
    """Mine comments from all provided sources."""
    init_db()
    all_comments: list[dict] = []

    for url in (video_urls or []):
        all_comments.extend(mine_youtube_comments(url))

    for tid in (tweet_ids or []):
        all_comments.extend(mine_twitter_replies(tid))

    # Save to DB
    session = get_session()
    try:
        for c in all_comments:
            record = MinedCommentRecord(
                platform=c["platform"],
                post_url=c.get("post_url", ""),
                comment_author=c.get("author", ""),
                comment_text=c["text"],
                likes=c.get("likes", 0),
            )
            session.add(record)
        session.commit()
    finally:
        session.close()

    return all_comments


CLASSIFY_PROMPT = """Analyze these audience comments from a content creator's posts. Classify each one and extract content ideas.

COMMENTS:
{comments}

For each comment, determine:
1. **Category**: "request" (asking for content about X), "question" (asking how to do X), "feedback" (praise/criticism of content), "idea" (suggests a topic indirectly), or "other"
2. **Extracted Topic**: If it's a request or question, what specific topic are they asking about?
3. **Priority**: 1-10, based on how many people would benefit from content about this (consider likes on the comment)

Return JSON:
{{
  "classified": [
    {{"index": 0, "category": "request", "extracted_topic": "Docker for beginners", "priority": 8.5}},
    ...
  ],
  "top_content_ideas": [
    {{"topic": "specific content topic", "source_count": N, "why": "why this would perform well"}},
    ...
  ]
}}
"""


def analyze_comments(limit: int = 100) -> dict[str, Any]:
    """Use AI to classify mined comments and extract content ideas."""
    init_db()
    session = get_session()
    try:
        records = (
            session.query(MinedCommentRecord)
            .filter(MinedCommentRecord.category == "")
            .order_by(MinedCommentRecord.likes.desc())
            .limit(limit)
            .all()
        )
        if not records:
            return {"classified": [], "top_content_ideas": []}

        comments_text = "\n".join(
            f"[{i}] (likes: {r.likes}) {r.comment_text[:200]}"
            for i, r in enumerate(records)
        )

        data = chat_json(
            system="You are an audience research analyst.",
            user=CLASSIFY_PROMPT.format(comments=comments_text),
            max_tokens=3000,
        )
        if not data:
            return {"error": "Failed to parse"}

        # Update DB records with classifications
        kb_entries = []
        for item in data.get("classified", []):
            idx = item.get("index", -1)
            if 0 <= idx < len(records):
                records[idx].category = item.get("category", "other")
                records[idx].extracted_topic = item.get("extracted_topic", "")
                priority = item.get("priority", 0.0)
                records[idx].priority = priority
                # Index meaningful comments into knowledge base
                category = item.get("category", "other")
                topic = item.get("extracted_topic", "")
                if category in ("request", "question") and topic:
                    kb_entries.append((
                        "audience_question",
                        f"{topic} (from your own comments, priority {priority:.1f})",
                        f"your {records[idx].platform} comments",
                        min(1.0, priority),
                    ))
        session.commit()

        if kb_entries:
            try:
                from social_agent.knowledge import remember_many
                remember_many(kb_entries)
            except Exception:
                pass

        return data
    finally:
        session.close()


def get_content_ideas_from_comments() -> list[dict]:
    """Get the top content ideas extracted from audience comments."""
    init_db()
    session = get_session()
    try:
        records = (
            session.query(MinedCommentRecord)
            .filter(MinedCommentRecord.category.in_(["request", "question"]))
            .filter(MinedCommentRecord.extracted_topic != "")
            .order_by(MinedCommentRecord.priority.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "topic": r.extracted_topic,
                "category": r.category,
                "original_comment": r.comment_text[:200],
                "likes": r.likes,
                "priority": r.priority,
                "platform": r.platform,
            }
            for r in records
        ]
    finally:
        session.close()
