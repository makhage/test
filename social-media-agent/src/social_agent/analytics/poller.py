"""Analytics poller — pulls engagement metrics from platforms and writes them
to the AnalyticsRecord table + knowledge base.

Call poll_all() from the dashboard, a CLI, or a cron to keep analytics current.
"""

from __future__ import annotations

from datetime import datetime

from social_agent.db.database import (
    AnalyticsRecord,
    ScheduledPostRecord,
    get_session,
    init_db,
)


def poll_twitter() -> dict:
    """Fetch engagement for all published Twitter posts of the current creator."""
    from social_agent.config import get_settings
    from social_agent.creators import current_slug

    settings = get_settings()
    if not all([
        settings.twitter_api_key,
        settings.twitter_access_token,
        settings.twitter_bearer_token,
    ]):
        return {"success": False, "error": "Twitter credentials not configured", "updated": 0}

    try:
        import tweepy
        client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            consumer_key=settings.twitter_api_key,
            consumer_secret=settings.twitter_api_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret,
        )
    except Exception as e:
        return {"success": False, "error": f"Twitter client init failed: {e}", "updated": 0}

    init_db()
    slug = current_slug()
    session = get_session()
    updated = 0

    try:
        # Get all published Twitter posts for this creator with a real post_id
        posts = session.query(ScheduledPostRecord).filter(
            ScheduledPostRecord.creator_slug == slug,
            ScheduledPostRecord.platform == "twitter",
            ScheduledPostRecord.status == "published",
            ScheduledPostRecord.published_post_id != "",
        ).all()

        if not posts:
            return {"success": True, "updated": 0, "message": "No published Twitter posts yet"}

        post_ids = [p.published_post_id for p in posts]
        # Tweepy v2 supports batch fetching — max 100 per call
        for chunk_start in range(0, len(post_ids), 100):
            chunk = post_ids[chunk_start:chunk_start + 100]
            try:
                response = client.get_tweets(
                    ids=chunk,
                    tweet_fields=["public_metrics"],
                )
                if not response.data:
                    continue
                for tweet in response.data:
                    metrics = tweet.public_metrics or {}
                    session.add(AnalyticsRecord(
                        creator_slug=slug,
                        post_id=str(tweet.id),
                        platform="twitter",
                        likes=metrics.get("like_count", 0),
                        shares=metrics.get("retweet_count", 0),
                        comments=metrics.get("reply_count", 0),
                        impressions=metrics.get("impression_count", 0),
                        recorded_at=datetime.utcnow(),
                    ))
                    updated += 1
            except Exception:
                continue

        session.commit()
    finally:
        session.close()

    # Write top performers to knowledge base
    try:
        _update_performance_knowledge()
    except Exception:
        pass

    return {"success": True, "updated": updated}


def _update_performance_knowledge() -> None:
    """Summarize top-performing recent posts into the knowledge base."""
    from social_agent.creators import current_slug
    from social_agent.knowledge import remember_many
    import json

    slug = current_slug()
    session = get_session()
    try:
        # Join published posts with their latest analytics
        posts = session.query(ScheduledPostRecord).filter(
            ScheduledPostRecord.creator_slug == slug,
            ScheduledPostRecord.status == "published",
            ScheduledPostRecord.published_post_id != "",
        ).all()

        top = []
        for post in posts:
            # Get latest analytics for this post
            latest = session.query(AnalyticsRecord).filter_by(
                creator_slug=slug,
                post_id=post.published_post_id,
            ).order_by(AnalyticsRecord.recorded_at.desc()).first()
            if latest:
                engagement = latest.likes + latest.shares + latest.comments
                top.append((engagement, post, latest))

        if not top:
            return

        top.sort(key=lambda x: x[0], reverse=True)
        entries = []
        for engagement, post, analytics in top[:5]:
            try:
                data = json.loads(post.content_json)
                preview = data.get("text", "")[:120] or data.get("title", "")[:120]
            except Exception:
                preview = post.content_json[:120]

            if engagement > 10:  # Only note actual performers
                entries.append((
                    "performance",
                    f"High-performing post ({engagement} engagement): {preview}",
                    f"twitter #{post.published_post_id}",
                    min(1.0, engagement / 500),
                ))

        if entries:
            remember_many(entries)
    finally:
        session.close()


def poll_all() -> dict:
    """Poll every platform that has credentials. Returns per-platform results."""
    results = {}
    results["twitter"] = poll_twitter()
    return results
