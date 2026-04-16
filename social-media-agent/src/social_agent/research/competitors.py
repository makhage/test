"""Competitor account tracking and analysis."""

from __future__ import annotations

import json

import tweepy

from social_agent.ai import chat, parse_json
from social_agent.config import get_settings
from social_agent.db.database import CompetitorPostRecord, get_session, init_db
from social_agent.models.content import CompetitorProfile, InfluencerProfile, Platform


def _scrape_competitor_twitter(handle: str, max_results: int = 20) -> list[dict]:
    """Fetch recent tweets from a competitor account."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return []

    client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
    handle_clean = handle.lstrip("@")

    try:
        user = client.get_user(username=handle_clean)
        if not user.data:
            return []

        tweets = client.get_users_tweets(
            user.data.id,
            max_results=max_results,
            tweet_fields=["public_metrics", "created_at"],
        )
        if not tweets.data:
            return []

        results = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics or {}
            results.append({
                "handle": handle_clean,
                "text": tweet.text,
                "likes": metrics.get("like_count", 0),
                "shares": metrics.get("retweet_count", 0),
                "comments": metrics.get("reply_count", 0),
                "url": f"https://x.com/{handle_clean}/status/{tweet.id}",
            })
        return results
    except Exception:
        return []


def scrape_competitors(profile: InfluencerProfile) -> list[dict]:
    """Scrape content from all configured competitor accounts."""
    init_db()
    all_posts: list[dict] = []

    # Twitter competitors
    for handle in profile.competitors.twitter:
        posts = _scrape_competitor_twitter(handle)
        all_posts.extend(posts)

    # Save to database
    session = get_session()
    try:
        for post in all_posts:
            record = CompetitorPostRecord(
                handle=post["handle"],
                platform="twitter",
                text=post["text"],
                likes=post["likes"],
                shares=post["shares"],
                comments=post["comments"],
                url=post.get("url", ""),
            )
            session.add(record)
        session.commit()
    finally:
        session.close()

    return all_posts


def analyze_competitors(profile: InfluencerProfile) -> list[CompetitorProfile]:
    """Analyze competitor accounts and generate intelligence."""
    init_db()
    session = get_session()

    try:
        profiles: list[CompetitorProfile] = []

        for handle in profile.competitors.twitter:
            handle_clean = handle.lstrip("@")
            records = (
                session.query(CompetitorPostRecord)
                .filter(CompetitorPostRecord.handle == handle_clean)
                .order_by(CompetitorPostRecord.scraped_at.desc())
                .limit(50)
                .all()
            )

            if not records:
                profiles.append(CompetitorProfile(
                    handle=handle_clean,
                    platform=Platform.TWITTER,
                ))
                continue

            avg_likes = sum(r.likes for r in records) / len(records)
            avg_shares = sum(r.shares for r in records) / len(records)
            avg_comments = sum(r.comments for r in records) / len(records)

            # Use Gemini to extract topics from their content
            top_topics = _extract_topics(records)

            profiles.append(CompetitorProfile(
                handle=handle_clean,
                platform=Platform.TWITTER,
                avg_likes=avg_likes,
                avg_shares=avg_shares,
                avg_comments=avg_comments,
                top_topics=top_topics,
            ))

        return profiles
    finally:
        session.close()


def _extract_topics(records: list) -> list[str]:
    """Use AI to identify topics from competitor posts."""
    if not records:
        return []

    texts = "\n".join(r.text[:200] for r in records[:20])

    try:
        raw = chat(
            system="You are a content analyst.",
            user=(
                f"From these social media posts, extract the top 5 content topics/themes. "
                f"Return as a JSON array of strings.\n\nPosts:\n{texts}"
            ),
            max_tokens=500,
        )
        data = parse_json(raw)
        # parse_json returns a dict, but we expect a list here
        if isinstance(data, list):
            return data
        # If the model wrapped the array in an object, try to extract it
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
        return json.loads(raw.strip()) if raw.strip().startswith("[") else []
    except Exception:
        return []
