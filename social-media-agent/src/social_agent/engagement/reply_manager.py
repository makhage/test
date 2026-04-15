"""Generate reply drafts for comments and mentions."""

from __future__ import annotations

import json

import anthropic
import tweepy

from social_agent.config import get_settings
from social_agent.db.database import ReplyDraftRecord, get_session, init_db
from social_agent.models.content import (
    CommentCategory,
    InfluencerProfile,
    Platform,
    PostStatus,
    ReplyDraft,
)


REPLY_PROMPT = """You are a social media engagement manager for the influencer described below.
Draft a reply to this comment in their authentic voice.

INFLUENCER VOICE:
{voice_description}
Tone: {tone}

ORIGINAL COMMENT:
Author: @{author}
Text: {comment_text}

Guidelines:
- Reply authentically in the influencer's voice
- Be helpful for questions, gracious for compliments, measured for criticism
- Keep it concise — 1-2 sentences max
- Add personality but stay professional
- Never be dismissive or argumentative

Return JSON:
{{
  "reply": "<suggested reply text>",
  "category": "question|compliment|criticism|spam|general",
  "priority": <1-10, higher = more important to reply to>
}}
"""


def fetch_twitter_mentions(max_results: int = 20) -> list[dict]:
    """Fetch recent mentions from Twitter."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return []

    client = tweepy.Client(
        bearer_token=settings.twitter_bearer_token,
        consumer_key=settings.twitter_api_key,
        consumer_secret=settings.twitter_api_secret,
        access_token=settings.twitter_access_token,
        access_token_secret=settings.twitter_access_token_secret,
    )

    try:
        me = client.get_me()
        if not me.data:
            return []

        mentions = client.get_users_mentions(
            me.data.id,
            max_results=max_results,
            tweet_fields=["author_id", "public_metrics", "created_at"],
        )

        if not mentions.data:
            return []

        results = []
        for mention in mentions.data:
            results.append({
                "platform": "twitter",
                "author": str(mention.author_id),
                "text": mention.text,
                "tweet_id": str(mention.id),
            })
        return results
    except Exception:
        return []


def draft_replies(
    comments: list[dict],
    profile: InfluencerProfile,
) -> list[ReplyDraft]:
    """Generate reply drafts for a list of comments."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    drafts: list[ReplyDraft] = []

    for comment in comments:
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": REPLY_PROMPT.format(
                        voice_description=profile.voice.description,
                        tone=", ".join(profile.voice.tone),
                        author=comment.get("author", "unknown"),
                        comment_text=comment.get("text", ""),
                    ),
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
                data = {"reply": raw.strip(), "category": "general", "priority": 5}

            platform = Platform(comment.get("platform", "twitter"))
            category_str = data.get("category", "general")
            try:
                category = CommentCategory(category_str)
            except ValueError:
                category = CommentCategory.GENERAL

            draft = ReplyDraft(
                platform=platform,
                original_comment_author=comment.get("author", ""),
                original_comment_text=comment.get("text", ""),
                suggested_reply=data.get("reply", ""),
                category=category,
                priority=data.get("priority", 5),
            )
            drafts.append(draft)
        except Exception:
            continue

    # Save to database
    _save_drafts(drafts)
    return drafts


def _save_drafts(drafts: list[ReplyDraft]) -> None:
    """Persist reply drafts to database."""
    init_db()
    session = get_session()
    try:
        for d in drafts:
            record = ReplyDraftRecord(
                platform=d.platform.value,
                original_comment_author=d.original_comment_author,
                original_comment_text=d.original_comment_text,
                suggested_reply=d.suggested_reply,
                category=d.category.value,
                priority=d.priority,
                status=d.status.value,
            )
            session.add(record)
        session.commit()
    finally:
        session.close()


def get_pending_drafts() -> list[ReplyDraft]:
    """Get all pending reply drafts."""
    init_db()
    session = get_session()
    try:
        records = (
            session.query(ReplyDraftRecord)
            .filter_by(status="draft")
            .order_by(ReplyDraftRecord.priority.desc())
            .all()
        )
        return [
            ReplyDraft(
                id=r.id,
                platform=Platform(r.platform),
                original_comment_author=r.original_comment_author,
                original_comment_text=r.original_comment_text,
                suggested_reply=r.suggested_reply,
                category=CommentCategory(r.category),
                priority=r.priority,
                status=PostStatus(r.status),
            )
            for r in records
        ]
    finally:
        session.close()


def approve_draft(draft_id: int) -> bool:
    """Approve a reply draft."""
    init_db()
    session = get_session()
    try:
        record = session.query(ReplyDraftRecord).filter_by(id=draft_id).first()
        if record:
            record.status = "approved"
            session.commit()
            return True
        return False
    finally:
        session.close()
