"""Reddit scraper — mines subreddits for trending discussions, hot takes, and audience questions.

Works WITHOUT API keys by using Reddit's public .json endpoints.
Falls back to PRAW if credentials are configured (higher rate limits).
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Optional

import requests

from social_agent.config import get_settings
from social_agent.db.database import RedditPostRecord, get_session, init_db
from social_agent.models.content import InfluencerProfile


_HEADERS = {
    "User-Agent": "SocialAgent/1.0 (content research bot; +https://github.com)",
}


def _get_reddit_client():
    """Create an authenticated Reddit client if credentials exist."""
    settings = get_settings()
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        return None
    try:
        import praw
        return praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
    except Exception:
        return None


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


def _scrape_subreddit_web(
    subreddit_name: str,
    sort: str = "hot",
    limit: int = 25,
    min_upvotes: int = 100,
    include_comments: bool = True,
    max_comment_depth: int = 3,
) -> list[dict]:
    """Scrape via Reddit's public .json endpoints — NO API keys needed."""
    sub = subreddit_name.strip().lstrip("r/").lstrip("/")
    sort_path = sort if sort in ("hot", "top", "rising", "new") else "hot"
    url = f"https://www.reddit.com/r/{sub}/{sort_path}.json"
    params: dict = {"limit": min(limit, 100), "raw_json": 1}
    if sort == "top":
        params["t"] = "week"

    results: list[dict] = []
    try:
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    children = data.get("data", {}).get("children", [])
    for child in children:
        post = child.get("data", {})
        if not post:
            continue
        if post.get("stickied"):
            continue
        score = post.get("ups", 0)
        if score < min_upvotes:
            continue

        permalink = post.get("permalink", "")

        # Fetch top comments from individual post
        top_comments: list[str] = []
        if include_comments and permalink:
            try:
                time.sleep(0.6)  # respect rate limit
                c_resp = requests.get(
                    f"https://www.reddit.com{permalink}.json",
                    headers=_HEADERS,
                    params={"limit": max_comment_depth, "sort": "best", "raw_json": 1},
                    timeout=10,
                )
                if c_resp.ok:
                    c_data = c_resp.json()
                    if isinstance(c_data, list) and len(c_data) > 1:
                        for cchild in c_data[1].get("data", {}).get("children", [])[:max_comment_depth]:
                            body = cchild.get("data", {}).get("body", "")
                            if len(body) > 20:
                                top_comments.append(body[:500])
            except Exception:
                pass

        title = post.get("title", "")
        selftext = (post.get("selftext") or "")[:2000]
        flair = post.get("link_flair_text") or ""

        results.append({
            "subreddit": sub,
            "title": title,
            "selftext": selftext,
            "author": post.get("author", "[deleted]"),
            "upvotes": score,
            "num_comments": post.get("num_comments", 0),
            "upvote_ratio": post.get("upvote_ratio", 0),
            "url": post.get("url", ""),
            "permalink": f"https://reddit.com{permalink}" if permalink else "",
            "top_comments": top_comments,
            "flair": flair,
            "content_type": _classify_post(title, selftext, flair),
        })

    return results


def _scrape_subreddit_praw(
    subreddit_name: str,
    sort: str = "hot",
    limit: int = 25,
    min_upvotes: int = 100,
    include_comments: bool = True,
    max_comment_depth: int = 3,
) -> list[dict]:
    """Scrape via PRAW (requires API credentials)."""
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


def scrape_subreddit(
    subreddit_name: str,
    sort: str = "hot",
    limit: int = 25,
    min_upvotes: int = 100,
    include_comments: bool = True,
    max_comment_depth: int = 3,
) -> list[dict]:
    """Scrape top/hot posts from a subreddit with their best comments.

    Uses PRAW if credentials are set (higher rate limits), otherwise
    falls back to Reddit's public .json endpoints — no API key needed.
    """
    settings = get_settings()
    has_creds = bool(settings.reddit_client_id and settings.reddit_client_secret)

    if has_creds:
        results = _scrape_subreddit_praw(
            subreddit_name, sort, limit, min_upvotes, include_comments, max_comment_depth,
        )
        if results:
            return results

    return _scrape_subreddit_web(
        subreddit_name, sort, limit, min_upvotes, include_comments, max_comment_depth,
    )


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

    # Index into the knowledge base — real audience signals
    try:
        from social_agent.knowledge import remember_many

        entries = []
        for post in all_posts[:50]:  # Cap to avoid flooding
            source = f"r/{post['subreddit']}"
            ctype = post["content_type"]
            title = post["title"]
            relevance = min(1.0, post.get("upvotes", 0) / 1000)

            if ctype == "question":
                entries.append(("audience_question", title, source, relevance))
            elif ctype == "opinion":
                entries.append(("hot_take", title, source, relevance))
            elif ctype == "recommendation":
                entries.append(("audience_question", title, source, relevance))
            # tutorials & discoveries are less directly useful as memory

        if entries:
            remember_many(entries)
    except Exception:
        pass

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
