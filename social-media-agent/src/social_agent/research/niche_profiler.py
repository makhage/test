"""Niche Profiler — Analyze the creator's own content to understand their niche.

Scrapes the creator's social media accounts (posts, bio, comments, video
transcripts) and uses Claude to build a comprehensive niche profile that
drives subreddit discovery and content strategy.

Supports a single Linktree URL as input — the agent extracts all platform
links automatically.
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
import tweepy

from social_agent.ai import chat_json
from social_agent.config import get_settings, DATA_DIR
from social_agent.db.database import get_session, init_db, Base
from social_agent.models.content import InfluencerProfile

from sqlalchemy import Column, DateTime, Integer, String, Text
from social_agent.db.database import Base


class NicheProfileRecord(Base):
    __tablename__ = "niche_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_content = Column(Text, default="")  # All scraped content, JSON
    niche_analysis = Column(Text, default="")  # Claude's analysis, JSON
    discovered_subreddits = Column(Text, default="[]")  # JSON list
    linktree_url = Column(String(500), default="")  # Source Linktree URL
    extracted_links = Column(Text, default="{}")  # JSON of extracted platform links
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Linktree Extraction — one URL to find all platform links
# ---------------------------------------------------------------------------

# Patterns to identify platform links
_PLATFORM_PATTERNS = {
    "twitter": [
        r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(@?\w+)",
    ],
    "tiktok": [
        r"(?:https?://)?(?:www\.)?tiktok\.com/@([\w.]+)",
    ],
    "instagram": [
        r"(?:https?://)?(?:www\.)?instagram\.com/([\w.]+)",
    ],
    "youtube": [
        r"(?:https?://)?(?:www\.)?youtube\.com/(@[\w]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/(?:c|channel|user)/([\w-]+)",
    ],
    "linkedin": [
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/([\w-]+)",
    ],
    "github": [
        r"(?:https?://)?(?:www\.)?github\.com/([\w-]+)",
    ],
    "twitch": [
        r"(?:https?://)?(?:www\.)?twitch\.tv/(\w+)",
    ],
    "website": [],  # catch-all for personal sites
}


def extract_linktree(linktree_url: str) -> dict[str, Any]:
    """Scrape a Linktree (or similar link-in-bio) page and extract all social links.

    Supports: Linktree, Beacons, Linkpop, Stan Store, bio.link, lnk.bio,
    and any link-in-bio page that renders links in HTML.

    Returns:
        {
            "name": "creator display name",
            "bio": "linktree bio text",
            "avatar_url": "profile pic URL",
            "links": [{"title": "...", "url": "..."}],
            "platforms": {
                "twitter": "https://twitter.com/handle",
                "tiktok": "https://tiktok.com/@handle",
                "instagram": "https://instagram.com/handle",
                "youtube": "https://youtube.com/@channel",
                ...
            },
            "other_links": ["https://mycourse.com", ...]
        }
    """
    result: dict[str, Any] = {
        "name": "",
        "bio": "",
        "avatar_url": "",
        "links": [],
        "platforms": {},
        "other_links": [],
    }

    try:
        # Fetch the page
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        resp = requests.get(linktree_url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        # --- Try Linktree JSON data first (embedded in page) ---
        # Linktree embeds account data as JSON in a script tag
        json_match = re.search(r'__NEXT_DATA__.*?>(.*?)</script>', html, re.DOTALL)
        if json_match:
            try:
                page_data = json.loads(json_match.group(1))
                props = page_data.get("props", {}).get("pageProps", {})
                account = props.get("account", props.get("userProfile", {}))

                if account:
                    result["name"] = account.get("pageTitle", account.get("username", ""))
                    result["bio"] = account.get("description", "")
                    result["avatar_url"] = account.get("profilePictureUrl", "")

                links_data = props.get("links", props.get("socialLinks", []))
                for link in links_data:
                    if isinstance(link, dict):
                        url = link.get("url", "")
                        title = link.get("title", link.get("name", ""))
                        if url:
                            result["links"].append({"title": title, "url": url})
            except (json.JSONDecodeError, KeyError):
                pass

        # --- Fallback: extract all URLs from the HTML ---
        if not result["links"]:
            # Find all href links
            href_pattern = r'href=["\']([^"\']+)["\']'
            all_urls = re.findall(href_pattern, html)

            # Also find URLs in data attributes (some link-in-bio tools use these)
            data_url_pattern = r'data-(?:href|url|link)=["\']([^"\']+)["\']'
            all_urls.extend(re.findall(data_url_pattern, html))

            # Find link text near URLs using anchor tags
            anchor_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
            anchors = re.findall(anchor_pattern, html, re.DOTALL)
            for url, text in anchors:
                clean_text = re.sub(r'<[^>]+>', '', text).strip()
                if url.startswith("http") and not any(skip in url for skip in [
                    "linktree.com", "beacons.ai", "linktr.ee",
                    "cdn.", "static.", "fonts.", "analytics",
                ]):
                    result["links"].append({"title": clean_text[:100], "url": url})

            # Deduplicate
            if not result["links"]:
                for url in all_urls:
                    if url.startswith("http") and not any(skip in url for skip in [
                        "linktree.com", "beacons.ai", "linktr.ee",
                        "cdn.", "static.", "fonts.", "analytics",
                        ".css", ".js", ".png", ".jpg", ".svg",
                    ]):
                        result["links"].append({"title": "", "url": url})

        # Extract bio/name from meta tags if not found
        if not result["name"]:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
            if title_match:
                result["name"] = re.sub(r'\s*[|–-]\s*Linktree.*', '', title_match.group(1)).strip()

        if not result["bio"]:
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html)
            if desc_match:
                result["bio"] = desc_match.group(1)

        # --- Classify links into platforms ---
        for link in result["links"]:
            url = link["url"]
            classified = False

            for platform, patterns in _PLATFORM_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        result["platforms"][platform] = url
                        classified = True
                        break
                if classified:
                    break

            if not classified and url.startswith("http"):
                result["other_links"].append(url)

        # Deduplicate other_links
        result["other_links"] = list(set(result["other_links"]))

    except Exception as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Scrapers — pull the creator's own content from each platform
# ---------------------------------------------------------------------------


def scrape_creator_twitter(handle: str) -> dict[str, Any]:
    """Scrape the creator's own Twitter account: bio, pinned tweet, recent tweets."""
    settings = get_settings()
    if not settings.twitter_bearer_token:
        return {}

    client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
    handle_clean = handle.lstrip("@")

    try:
        user = client.get_user(
            username=handle_clean,
            user_fields=["description", "public_metrics", "pinned_tweet_id"],
        )
        if not user.data:
            return {}

        bio = user.data.description or ""
        followers = (user.data.public_metrics or {}).get("followers_count", 0)

        # Get recent tweets
        tweets = client.get_users_tweets(
            user.data.id,
            max_results=100,
            tweet_fields=["public_metrics", "created_at"],
            exclude=["retweets"],
        )
        tweet_texts = []
        if tweets.data:
            for t in tweets.data:
                tweet_texts.append(t.text)

        # Get pinned tweet
        pinned = ""
        if user.data.pinned_tweet_id:
            pinned_tweet = client.get_tweet(user.data.pinned_tweet_id)
            if pinned_tweet.data:
                pinned = pinned_tweet.data.text

        return {
            "platform": "twitter",
            "handle": handle_clean,
            "bio": bio,
            "followers": followers,
            "pinned_tweet": pinned,
            "recent_posts": tweet_texts[:50],
        }
    except Exception as e:
        return {"platform": "twitter", "error": str(e)}


def scrape_creator_instagram(account_id: str) -> dict[str, Any]:
    """Scrape the creator's Instagram: bio, recent captions, hashtags, and video URLs."""
    settings = get_settings()
    if not settings.instagram_access_token:
        return {}

    try:
        # Get profile info
        url = f"https://graph.facebook.com/v18.0/{account_id}"
        resp = requests.get(url, params={
            "fields": "biography,followers_count,media_count,username",
            "access_token": settings.instagram_access_token,
        }, timeout=10)

        if resp.status_code != 200:
            return {}

        profile_data = resp.json()

        # Get recent media captions + video URLs
        media_url = f"https://graph.facebook.com/v18.0/{account_id}/media"
        media_resp = requests.get(media_url, params={
            "fields": "caption,like_count,comments_count,media_type,media_url,permalink",
            "limit": 50,
            "access_token": settings.instagram_access_token,
        }, timeout=10)

        captions = []
        video_urls = []
        if media_resp.status_code == 200:
            for item in media_resp.json().get("data", []):
                if item.get("caption"):
                    captions.append(item["caption"])
                # Collect video/reel URLs for transcription
                if item.get("media_type") in ("VIDEO", "REELS"):
                    permalink = item.get("permalink", "")
                    if permalink:
                        video_urls.append(permalink)

        return {
            "platform": "instagram",
            "handle": profile_data.get("username", ""),
            "bio": profile_data.get("biography", ""),
            "followers": profile_data.get("followers_count", 0),
            "recent_posts": captions[:50],
            "video_urls": video_urls[:10],
        }
    except Exception as e:
        return {"platform": "instagram", "error": str(e)}


def scrape_creator_tiktok(tiktok_url: str) -> dict[str, Any]:
    """Scrape a TikTok creator's profile: bio, video captions, and video URLs for transcription.

    Uses yt-dlp which supports TikTok profile/video extraction.
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": 20,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tiktok_url, download=False)

        if not info:
            return {}

        # TikTok profile extraction
        uploader = info.get("uploader", info.get("title", ""))
        description = info.get("description", "")
        entries = info.get("entries", [])

        video_titles = []
        video_urls = []
        for entry in (entries or [])[:20]:
            if not entry:
                continue
            title = entry.get("title", entry.get("description", ""))
            if title:
                video_titles.append(title[:300])
            url = entry.get("url", entry.get("webpage_url", ""))
            if url:
                video_urls.append(url)

        return {
            "platform": "tiktok",
            "handle": uploader,
            "bio": description[:1000],
            "recent_posts": video_titles,
            "video_urls": video_urls[:10],
        }
    except Exception as e:
        return {"platform": "tiktok", "error": str(e)}


def scrape_creator_instagram_public(instagram_url: str) -> dict[str, Any]:
    """Scrape an Instagram profile using yt-dlp (no Graph API needed).

    Works with public profiles — extracts reel/video URLs and captions.
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": 20,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(instagram_url, download=False)

        if not info:
            return {}

        uploader = info.get("uploader", info.get("title", ""))
        entries = info.get("entries", [])

        captions = []
        video_urls = []
        for entry in (entries or [])[:20]:
            if not entry:
                continue
            desc = entry.get("description", entry.get("title", ""))
            if desc:
                captions.append(desc[:500])
            url = entry.get("url", entry.get("webpage_url", ""))
            if url:
                video_urls.append(url)

        return {
            "platform": "instagram",
            "handle": uploader,
            "bio": info.get("description", "")[:1000],
            "recent_posts": captions,
            "video_urls": video_urls[:10],
        }
    except Exception as e:
        return {"platform": "instagram", "error": str(e)}


def scrape_creator_youtube(channel_url: str) -> dict[str, Any]:
    """Scrape the creator's YouTube: channel description, video titles, transcripts."""
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": 20,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

        if not info:
            return {}

        channel_desc = info.get("description", "")
        entries = info.get("entries", [])

        video_titles = []
        video_urls = []
        for entry in entries[:20]:
            if entry and entry.get("title"):
                video_titles.append(entry["title"])
                video_urls.append(entry.get("url", ""))

        return {
            "platform": "youtube",
            "channel_name": info.get("title", info.get("uploader", "")),
            "bio": channel_desc[:1000],
            "recent_posts": video_titles,
            "video_urls": video_urls[:10],  # For transcription
        }
    except Exception as e:
        return {"platform": "youtube", "error": str(e)}


# ---------------------------------------------------------------------------
# Video Transcription — download audio + transcribe with Whisper
# ---------------------------------------------------------------------------


def transcribe_video(video_url: str) -> str:
    """Download a video's audio and transcribe it with OpenAI Whisper."""
    settings = get_settings()
    if not settings.openai_api_key and not settings.openai_oauth_client_id:
        return ""

    try:
        import yt_dlp

        from social_agent.auth import get_openai_client

        # Download audio only
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "audio.mp3"
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
                "outtmpl": str(Path(tmpdir) / "audio.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Find the downloaded file
            audio_files = list(Path(tmpdir).glob("audio.*"))
            if not audio_files:
                return ""

            audio_file = audio_files[0]

            # Check file size — Whisper API limit is 25MB
            if audio_file.stat().st_size > 25 * 1024 * 1024:
                return "(Video too long to transcribe — over 25MB audio)"

            # Transcribe with Whisper
            client = get_openai_client()
            with open(audio_file, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text",
                )

            return transcript[:5000]  # Cap at 5000 chars
    except Exception as e:
        return f"(Transcription failed: {e})"


def transcribe_creator_videos(video_urls: list[str], max_videos: int = 5) -> list[dict]:
    """Transcribe multiple videos and return transcripts."""
    results = []
    for url in video_urls[:max_videos]:
        transcript = transcribe_video(url)
        if transcript and not transcript.startswith("("):
            results.append({"url": url, "transcript": transcript})
    return results


# ---------------------------------------------------------------------------
# Niche Analysis — Claude analyzes all scraped content
# ---------------------------------------------------------------------------


NICHE_ANALYSIS_PROMPT = """You are an expert social media strategist. Analyze this creator's content to deeply understand their niche, audience, and content style.

CREATOR'S CONTENT FROM THEIR ACCOUNTS:
{creator_content}

{video_transcripts}

Based on ALL of this content (posts, bio, video transcripts, topics they cover), provide a comprehensive niche analysis:

1. **Primary Niche**: What is their main content area? Be specific (not just "tech" — more like "Python programming for beginners" or "AI/ML engineering for practitioners")
2. **Sub-Topics**: What specific sub-topics do they frequently cover?
3. **Target Audience**: Who is their audience? (skill level, interests, pain points)
4. **Content Style**: How do they communicate? (educational, entertaining, opinionated, tutorial-focused, etc.)
5. **Key Themes**: What recurring themes or messages come through their content?
6. **Audience Pain Points**: Based on their content and what they address, what does their audience struggle with?
7. **Recommended Subreddits**: Based on this niche analysis, recommend 10-15 subreddits where their target audience hangs out. For each subreddit, explain WHY it's relevant. Include a mix of:
   - Large general subreddits for the niche
   - Medium-sized focused subreddits
   - Small niche-specific subreddits where deep discussions happen
   - Subreddits where the audience asks questions (content topic goldmine)

Return JSON:
{{
  "primary_niche": "specific niche description",
  "sub_topics": ["topic1", "topic2", ...],
  "target_audience": "description of who watches/follows them",
  "content_style": "description of their style",
  "key_themes": ["theme1", "theme2", ...],
  "audience_pain_points": ["pain point 1", "pain point 2", ...],
  "recommended_subreddits": [
    {{"name": "subreddit_name", "reason": "why this is relevant", "relevance": "high|medium|low", "type": "general|focused|niche|questions"}},
    ...
  ]
}}
"""


def analyze_creator_niche(
    profile: InfluencerProfile,
    linktree_url: str | None = None,
    youtube_channel_url: str | None = None,
    tiktok_url: str | None = None,
    instagram_url: str | None = None,
    twitter_handle: str | None = None,
    transcribe_videos: bool = True,
    max_video_transcripts: int = 5,
) -> dict[str, Any]:
    """Scrape the creator's content across all platforms and use Claude to analyze their niche.

    The simplest way: pass a `linktree_url` and all platform links are
    extracted automatically. Or pass individual URLs directly.

    Supports: Twitter, Instagram (Graph API or public URL), TikTok, YouTube.
    Transcribes videos from ALL platforms (YouTube, TikTok, Instagram Reels).

    Returns a full niche analysis including recommended subreddits.
    """
    settings = get_settings()

    # --- Extract links from Linktree if provided ---
    linktree_data: dict[str, Any] = {}
    if linktree_url:
        linktree_data = extract_linktree(linktree_url)
        platforms = linktree_data.get("platforms", {})

        # Auto-fill any URLs not explicitly provided
        if not twitter_handle and "twitter" in platforms:
            # Extract handle from URL
            tw_url = platforms["twitter"]
            tw_match = re.search(r'(?:twitter\.com|x\.com)/(@?\w+)', tw_url)
            if tw_match:
                twitter_handle = tw_match.group(1)

        if not tiktok_url and "tiktok" in platforms:
            tiktok_url = platforms["tiktok"]

        if not instagram_url and "instagram" in platforms:
            instagram_url = platforms["instagram"]

        if not youtube_channel_url and "youtube" in platforms:
            youtube_channel_url = platforms["youtube"]

    # --- Scrape all creator content ---
    creator_content: list[dict] = []
    all_video_urls: list[tuple[str, str]] = []  # (platform, url)

    # Linktree bio/name as context
    if linktree_data:
        lt_context: dict[str, Any] = {"platform": "linktree"}
        if linktree_data.get("name"):
            lt_context["handle"] = linktree_data["name"]
        if linktree_data.get("bio"):
            lt_context["bio"] = linktree_data["bio"]
        # Include other links (courses, websites, etc.) as context
        other = linktree_data.get("other_links", [])
        all_links = linktree_data.get("links", [])
        if all_links:
            lt_context["recent_posts"] = [
                f'{l.get("title", "")} — {l.get("url", "")}'.strip(" —")
                for l in all_links if l.get("url")
            ]
        if lt_context.get("bio") or lt_context.get("recent_posts"):
            creator_content.append(lt_context)

    # Twitter
    resolved_handle = twitter_handle or profile.brand.name
    if settings.twitter_bearer_token and resolved_handle:
        twitter_data = scrape_creator_twitter(resolved_handle)
        if twitter_data and "error" not in twitter_data:
            creator_content.append(twitter_data)

    # Instagram — try Graph API first, fall back to public scraping
    if settings.instagram_access_token and settings.instagram_business_account_id:
        ig_data = scrape_creator_instagram(settings.instagram_business_account_id)
        if ig_data and "error" not in ig_data:
            creator_content.append(ig_data)
            for url in ig_data.get("video_urls", []):
                all_video_urls.append(("instagram", url))
    elif instagram_url:
        ig_data = scrape_creator_instagram_public(instagram_url)
        if ig_data and "error" not in ig_data:
            creator_content.append(ig_data)
            for url in ig_data.get("video_urls", []):
                all_video_urls.append(("instagram", url))

    # TikTok
    if tiktok_url:
        tiktok_data = scrape_creator_tiktok(tiktok_url)
        if tiktok_data and "error" not in tiktok_data:
            creator_content.append(tiktok_data)
            for url in tiktok_data.get("video_urls", []):
                all_video_urls.append(("tiktok", url))

    # YouTube
    if youtube_channel_url:
        yt_data = scrape_creator_youtube(youtube_channel_url)
        if yt_data and "error" not in yt_data:
            creator_content.append(yt_data)
            for url in yt_data.get("video_urls", []):
                all_video_urls.append(("youtube", url))

    # Also include the existing profile data as context
    profile_context = {
        "platform": "profile_config",
        "bio": profile.voice.description,
        "recent_posts": profile.voice.example_posts,
        "topics_claimed": profile.topics.get("primary", []) + profile.topics.get("secondary", []),
    }
    creator_content.append(profile_context)

    # --- Transcribe videos from ALL platforms ---
    video_transcripts: list[dict] = []
    if transcribe_videos and all_video_urls and (settings.openai_api_key or settings.openai_oauth_client_id):
        # Spread transcriptions across platforms for a balanced view
        platform_groups: dict[str, list[str]] = {}
        for platform, url in all_video_urls:
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(url)

        # Allocate transcription slots across platforms
        remaining = max_video_transcripts
        urls_to_transcribe: list[tuple[str, str]] = []
        # Round-robin across platforms
        while remaining > 0:
            added_any = False
            for platform, urls in platform_groups.items():
                if urls and remaining > 0:
                    url = urls.pop(0)
                    urls_to_transcribe.append((platform, url))
                    remaining -= 1
                    added_any = True
            if not added_any:
                break

        for platform, url in urls_to_transcribe:
            transcript = transcribe_video(url)
            if transcript and not transcript.startswith("("):
                video_transcripts.append({
                    "platform": platform,
                    "url": url,
                    "transcript": transcript,
                })

    # --- Format for Claude ---
    content_text = ""
    for source in creator_content:
        platform = source.get("platform", "unknown")
        bio = source.get("bio", "")
        posts = source.get("recent_posts", [])

        content_text += f"\n--- {platform.upper()} ---\n"
        if source.get("handle"):
            content_text += f"Handle: @{source['handle']}\n"
        if bio:
            content_text += f"Bio: {bio}\n"
        if source.get("pinned_tweet"):
            content_text += f"Pinned: {source['pinned_tweet']}\n"
        if source.get("followers"):
            content_text += f"Followers: {source['followers']:,}\n"
        if source.get("topics_claimed"):
            content_text += f"Claimed topics: {', '.join(source['topics_claimed'])}\n"
        if posts:
            content_text += "Recent posts/captions:\n"
            for p in posts[:30]:
                content_text += f"  - {p[:200]}\n"

    transcript_text = ""
    if video_transcripts:
        transcript_text = "\nVIDEO TRANSCRIPTS (what they actually say in their videos — this is the best signal for their real niche):\n"
        for vt in video_transcripts:
            transcript_text += f"\n[{vt['platform'].upper()} Video: {vt['url']}]\n{vt['transcript'][:2000]}\n"

    # --- Analyze with AI ---
    analysis = chat_json(
        system="You are an expert social media strategist.",
        user=NICHE_ANALYSIS_PROMPT.format(
            creator_content=content_text,
            video_transcripts=transcript_text if transcript_text else "(No video transcripts available)",
        ),
        max_tokens=4000,
    )
    if not analysis:
        analysis = {"error": "Failed to parse niche analysis"}

    # --- Save to database ---
    init_db()
    session = get_session()
    try:
        subreddits = [s["name"] for s in analysis.get("recommended_subreddits", [])]
        record = NicheProfileRecord(
            raw_content=json.dumps(creator_content, default=str)[:10000],
            niche_analysis=json.dumps(analysis),
            discovered_subreddits=json.dumps(subreddits),
            linktree_url=linktree_url or "",
            extracted_links=json.dumps(linktree_data.get("platforms", {})) if linktree_data else "{}",
        )
        session.add(record)
        session.commit()
    finally:
        session.close()

    return analysis


def get_latest_niche_profile() -> dict[str, Any] | None:
    """Retrieve the most recent niche analysis from the database."""
    init_db()
    session = get_session()
    try:
        record = (
            session.query(NicheProfileRecord)
            .order_by(NicheProfileRecord.created_at.desc())
            .first()
        )
        if not record:
            return None

        analysis = json.loads(record.niche_analysis) if record.niche_analysis else {}
        analysis["_discovered_subreddits"] = json.loads(record.discovered_subreddits) if record.discovered_subreddits else []
        analysis["_created_at"] = record.created_at.isoformat() if record.created_at else ""
        return analysis
    finally:
        session.close()


def get_discovered_subreddits() -> list[str]:
    """Get the auto-discovered subreddit list."""
    profile = get_latest_niche_profile()
    if not profile:
        return []
    return profile.get("_discovered_subreddits", [])
