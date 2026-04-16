"""Reddit scraper — mines subreddits for trending discussions, hot takes, and audience questions."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import praw

from social_agent.config import get_settings
from social_agent.db.database import RedditPostRecord, get_session, init_db
from social_agent.models.content import InfluencerProfile


def _get_reddit_client() -> Optional[praw.Reddit]:
    """Create an authenticated Reddit client."""
    settings = get_settings()
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        return None

    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )


def _classify_post(title: str, selftext: str, flair: str) -> str:
    """Classify a Reddit post type for content strategy."""
    title_lower = title.lower()
    flair_lower = flair.lower() if flair else ""

    # Check specific patterns first (before the generic ? fallback)
    if any(w in title_lower for w in ["tutorial", "guide", "walkthrough", "i built", "i made"]):
        return "tutorial"
    if any(w in title_lower for w in ["hot take", "unpopular opinion", "controversial", "rant", "am i wrong"]):
        return "opinion"
    if any(w in title_lower for w in ["til", "today i learned", "did you know", "interesting"]):
        return "discovery"
    if any(w in title_lower for w in ["what", "which", "best", "favorite", "recommend"]):
        return "recommendation"
    if any(w in title_lower for w in ["how do i", "how to", "help", "stuck", "can someone", "eli5"]):
        return "question"
    if any(w in flair_lower for w in ["discussion", "debate"]):
        return "discussion"
    # Generic ? as last resort — anything ending with a question mark not caught above
    if "?" in title_lower:
        return "question"
    return "discussion"


def scrape_subreddit(
    subreddit_name: str,
    sort: str = "hot",
    limit: int = 25,
    min_upvotes: int = 100,
    include_comments: bool = True,
    max_comment_depth: int = 3,
) -> list[dict]:
    """Scrape top/hot posts from a subreddit with their best comments.

    Args:
        subreddit_name: Name of the subreddit (without r/).
        sort: How to sort posts — "hot", "top", "rising", "new".
        limit: Max posts to fetch.
        min_upvotes: Minimum upvotes to include a post.
        include_comments: Whether to fetch top comments.
        max_comment_depth: How many top-level comments to grab.

    Returns:
        List of post dicts with title, text, comments, engagement metrics.
    """
    reddit = _get_reddit_client()
    if not reddit:
        return []

    try:
        sub = reddit.subreddit(subreddit_name)

        if sort == "top":
            posts_iter = sub.top(time_filter="week", limit=limit)
        elif sort == "rising":
            posts_iter = sub.rising(limit=limit)
        elif sort == "new":
            posts_iter = sub.new(limit=limit)
        else:
            posts_iter = sub.hot(limit=limit)

        results: list[dict] = []
        for post in posts_iter:
            if post.score < min_upvotes:
                continue
            if post.stickied:
                continue

            # Get top comments
            top_comments: list[str] = []
            if include_comments:
                post.comment_sort = "best"
                post.comments.replace_more(limit=0)
                for comment in post.comments[:max_comment_depth]:
                    if hasattr(comment, "body") and len(comment.body) > 20:
                        top_comments.append(comment.body[:500])

            results.append({
                "subreddit": subreddit_name,
                "title": post.title,
                "selftext": (post.selftext or "")[:2000],
                "author": str(post.author) if post.author else "[deleted]",
                "upvotes": post.score,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
                "url": post.url,
                "permalink": f"https://reddit.com{post.permalink}",
                "top_comments": top_comments,
                "flair": post.link_flair_text or "",
                "content_type": _classify_post(post.title, post.selftext or "", post.link_flair_text or ""),
            })

        return results
    except Exception:
        return []


def scrape_all_subreddits(
    profile: InfluencerProfile,
    sort: str = "hot",
    limit_per_sub: int = 25,
    override_subreddits: list[str] | None = None,
) -> list[dict]:
    """Scrape all configured subreddits for the influencer's niche.

    Uses auto-discovered subreddits if available, falls back to profile config.
    Can be overridden with an explicit list.
    """
    init_db()

    # Priority: explicit override > auto-discovered > profile config
    if override_subreddits:
        subreddits = override_subreddits
    else:
        # Check for auto-discovered subreddits
        from social_agent.research.niche_profiler import get_discovered_subreddits
        discovered = get_discovered_subreddits()
        subreddits = discovered if discovered else profile.reddit.subreddits

    all_posts: list[dict] = []
    reddit_config = profile.reddit

    for sub_name in subreddits:
        posts = scrape_subreddit(
            subreddit_name=sub_name,
            sort=sort,
            limit=limit_per_sub,
            min_upvotes=reddit_config.min_upvotes,
            include_comments=reddit_config.include_comments,
            max_comment_depth=reddit_config.max_comment_depth,
        )
        all_posts.extend(posts)

    # Save to database
    session = get_session()
    try:
        for post in all_posts:
            record = RedditPostRecord(
                subreddit=post["subreddit"],
                title=post["title"],
                selftext=post["selftext"],
                author=post["author"],
                upvotes=post["upvotes"],
                num_comments=post["num_comments"],
                upvote_ratio=post["upvote_ratio"],
                url=post["url"],
                permalink=post["permalink"],
                top_comments=json.dumps(post["top_comments"]),
                flair=post["flair"],
                content_type=post["content_type"],
            )
            session.add(record)
        session.commit()
    finally:
        session.close()

    return all_posts


def get_reddit_posts(
    subreddit: str | None = None,
    content_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve Reddit posts from the database."""
    init_db()
    session = get_session()
    try:
        query = session.query(RedditPostRecord)
        if subreddit:
            query = query.filter(RedditPostRecord.subreddit == subreddit)
        if content_type:
            query = query.filter(RedditPostRecord.content_type == content_type)

        records = query.order_by(RedditPostRecord.upvotes.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "subreddit": r.subreddit,
                "title": r.title,
                "selftext": r.selftext,
                "author": r.author,
                "upvotes": r.upvotes,
                "num_comments": r.num_comments,
                "upvote_ratio": r.upvote_ratio,
                "url": r.url,
                "permalink": r.permalink,
                "top_comments": json.loads(r.top_comments) if r.top_comments else [],
                "flair": r.flair,
                "content_type": r.content_type,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else "",
            }
            for r in records
        ]
    finally:
        session.close()


def get_audience_questions(limit: int = 20) -> list[dict]:
    """Get question-type posts — these are direct content topic ideas."""
    return get_reddit_posts(content_type="question", limit=limit)


def get_hot_takes(limit: int = 20) -> list[dict]:
    """Get opinion/controversial posts — inspiration for contrarian content."""
    return get_reddit_posts(content_type="opinion", limit=limit)


def get_subreddit_stats() -> dict[str, dict]:
    """Get aggregated stats per subreddit from the database."""
    init_db()
    session = get_session()
    try:
        from sqlalchemy import func
        stats = (
            session.query(
                RedditPostRecord.subreddit,
                func.count(RedditPostRecord.id).label("post_count"),
                func.avg(RedditPostRecord.upvotes).label("avg_upvotes"),
                func.max(RedditPostRecord.upvotes).label("max_upvotes"),
                func.avg(RedditPostRecord.num_comments).label("avg_comments"),
            )
            .group_by(RedditPostRecord.subreddit)
            .all()
        )
        return {
            row.subreddit: {
                "post_count": row.post_count,
                "avg_upvotes": round(float(row.avg_upvotes or 0), 1),
                "max_upvotes": row.max_upvotes or 0,
                "avg_comments": round(float(row.avg_comments or 0), 1),
            }
            for row in stats
        }
    finally:
        session.close()
