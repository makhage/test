"""Fetch trending/viral content from social media platforms."""

from __future__ import annotations

import json
from datetime import datetime

import requests
import tweepy

from social_agent.config import get_settings
from social_agent.db.database import ViralPostRecord, get_session, init_db
from social_agent.models.content import InfluencerProfile, Platform, ViralPost


def _scrape_twitter(
    keywords: list[str],
    min_likes: int = 500,
    max_results: int = 50,
) -> list[ViralPost]:
    """Search Twitter for high-engagement tweets in the niche."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return []

    client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
    posts: list[ViralPost] = []

    for keyword in keywords:
        try:
            query = f"{keyword} min_faves:{min_likes} -is:retweet lang:en"
            response = client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=["public_metrics", "author_id", "created_at"],
            )
            if response.data:
                for tweet in response.data:
                    metrics = tweet.public_metrics or {}
                    posts.append(ViralPost(
                        platform=Platform.TWITTER,
                        author=str(tweet.author_id),
                        text=tweet.text,
                        likes=metrics.get("like_count", 0),
                        shares=metrics.get("retweet_count", 0),
                        comments=metrics.get("reply_count", 0),
                        impressions=metrics.get("impression_count", 0),
                        url=f"https://x.com/i/status/{tweet.id}",
                        content_type="tweet",
                    ))
        except Exception:
            continue

    return posts


def _scrape_instagram_hashtags(
    hashtags: list[str],
) -> list[ViralPost]:
    """Fetch top posts by hashtag from Instagram Graph API."""
    settings = get_settings()
    if not settings.instagram_access_token:
        return []

    posts: list[ViralPost] = []
    for tag in hashtags:
        try:
            # Search for hashtag ID
            url = "https://graph.facebook.com/v18.0/ig_hashtag_search"
            resp = requests.get(url, params={
                "q": tag.lstrip("#"),
                "user_id": settings.instagram_business_account_id,
                "access_token": settings.instagram_access_token,
            }, timeout=10)
            if resp.status_code != 200:
                continue

            hashtag_id = resp.json().get("data", [{}])[0].get("id")
            if not hashtag_id:
                continue

            # Get top media for hashtag
            media_url = f"https://graph.facebook.com/v18.0/{hashtag_id}/top_media"
            media_resp = requests.get(media_url, params={
                "user_id": settings.instagram_business_account_id,
                "fields": "id,caption,like_count,comments_count,permalink",
                "access_token": settings.instagram_access_token,
            }, timeout=10)
            if media_resp.status_code != 200:
                continue

            for item in media_resp.json().get("data", []):
                posts.append(ViralPost(
                    platform=Platform.INSTAGRAM,
                    text=item.get("caption", ""),
                    likes=item.get("like_count", 0),
                    comments=item.get("comments_count", 0),
                    url=item.get("permalink", ""),
                    content_type="post",
                ))
        except Exception:
            continue

    return posts


def scan_niche(
    profile: InfluencerProfile,
    min_likes: int = 500,
) -> list[ViralPost]:
    """Scan all platforms for viral content in the influencer's niche."""
    init_db()
    all_topics = profile.topics.get("primary", []) + profile.topics.get("secondary", [])
    keywords = all_topics[:10]

    posts: list[ViralPost] = []

    # Twitter
    twitter_posts = _scrape_twitter(keywords, min_likes=min_likes)
    posts.extend(twitter_posts)

    # Instagram
    ig_posts = _scrape_instagram_hashtags(keywords)
    posts.extend(ig_posts)

    # Save to database
    session = get_session()
    try:
        for post in posts:
            record = ViralPostRecord(
                platform=post.platform.value,
                author=post.author,
                text=post.text,
                likes=post.likes,
                shares=post.shares,
                comments=post.comments,
                impressions=post.impressions,
                url=post.url,
                hashtags=json.dumps(post.hashtags),
                content_type=post.content_type,
            )
            session.add(record)
        session.commit()
    finally:
        session.close()

    return posts


def get_swipe_file(limit: int = 20) -> list[ViralPost]:
    """Retrieve top viral posts from the database."""
    init_db()
    session = get_session()
    try:
        records = (
            session.query(ViralPostRecord)
            .order_by(ViralPostRecord.likes.desc())
            .limit(limit)
            .all()
        )
        return [
            ViralPost(
                id=r.id,
                platform=Platform(r.platform),
                author=r.author,
                text=r.text,
                likes=r.likes,
                shares=r.shares,
                comments=r.comments,
                impressions=r.impressions,
                url=r.url,
                content_type=r.content_type,
            )
            for r in records
        ]
    finally:
        session.close()
