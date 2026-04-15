"""Fetch engagement metrics from platform APIs."""

from __future__ import annotations

from datetime import datetime

import requests
import tweepy

from social_agent.config import get_settings
from social_agent.db.database import AnalyticsRecord, get_session, init_db
from social_agent.models.content import Platform


def track_tweet(tweet_id: str) -> dict:
    """Fetch engagement metrics for a specific tweet."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return {}

    client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
    try:
        tweet = client.get_tweet(
            tweet_id,
            tweet_fields=["public_metrics"],
        )
        if tweet.data:
            metrics = tweet.data.public_metrics or {}
            record = {
                "post_id": tweet_id,
                "platform": Platform.TWITTER.value,
                "likes": metrics.get("like_count", 0),
                "shares": metrics.get("retweet_count", 0),
                "comments": metrics.get("reply_count", 0),
                "impressions": metrics.get("impression_count", 0),
            }
            _save_analytics(record)
            return record
    except Exception:
        pass
    return {}


def track_instagram_post(post_id: str) -> dict:
    """Fetch engagement metrics for an Instagram post."""
    settings = get_settings()
    if not settings.instagram_access_token:
        return {}

    try:
        url = f"https://graph.facebook.com/v18.0/{post_id}"
        resp = requests.get(url, params={
            "fields": "like_count,comments_count,impressions,reach",
            "access_token": settings.instagram_access_token,
        }, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            record = {
                "post_id": post_id,
                "platform": Platform.INSTAGRAM.value,
                "likes": data.get("like_count", 0),
                "comments": data.get("comments_count", 0),
                "impressions": data.get("impressions", 0),
                "reach": data.get("reach", 0),
            }
            _save_analytics(record)
            return record
    except Exception:
        pass
    return {}


def _save_analytics(record: dict) -> None:
    """Persist analytics data to database."""
    init_db()
    session = get_session()
    try:
        db_record = AnalyticsRecord(
            post_id=record.get("post_id", ""),
            platform=record.get("platform", ""),
            likes=record.get("likes", 0),
            shares=record.get("shares", 0),
            comments=record.get("comments", 0),
            impressions=record.get("impressions", 0),
            reach=record.get("reach", 0),
        )
        session.add(db_record)
        session.commit()
    finally:
        session.close()


def get_analytics_history(
    platform: str | None = None,
    days: int = 7,
) -> list[dict]:
    """Retrieve analytics records from the database."""
    init_db()
    session = get_session()
    try:
        query = session.query(AnalyticsRecord)
        if platform:
            query = query.filter(AnalyticsRecord.platform == platform)

        cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=days)
        query = query.filter(AnalyticsRecord.recorded_at >= cutoff)

        records = query.order_by(AnalyticsRecord.recorded_at.desc()).all()
        return [
            {
                "post_id": r.post_id,
                "platform": r.platform,
                "likes": r.likes,
                "shares": r.shares,
                "comments": r.comments,
                "impressions": r.impressions,
                "reach": r.reach,
                "recorded_at": r.recorded_at.isoformat(),
            }
            for r in records
        ]
    finally:
        session.close()
