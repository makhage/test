"""Niche Profiler — Analyze the creator's own content to understand their niche.

Scrapes the creator's social media accounts (posts, bio, comments, video
transcripts) and uses Claude to build a comprehensive niche profile that
drives subreddit discovery and content strategy.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import anthropic
import requests
import tweepy

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
    created_at = Column(DateTime, default=datetime.utcnow)


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
    """Scrape the creator's Instagram: bio, recent captions, hashtags."""
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

        # Get recent media captions
        media_url = f"https://graph.facebook.com/v18.0/{account_id}/media"
        media_resp = requests.get(media_url, params={
            "fields": "caption,like_count,comments_count,media_type",
            "limit": 50,
            "access_token": settings.instagram_access_token,
        }, timeout=10)

        captions = []
        if media_resp.status_code == 200:
            for item in media_resp.json().get("data", []):
                if item.get("caption"):
                    captions.append(item["caption"])

        return {
            "platform": "instagram",
            "handle": profile_data.get("username", ""),
            "bio": profile_data.get("biography", ""),
            "followers": profile_data.get("followers_count", 0),
            "recent_posts": captions[:50],
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
    if not settings.openai_api_key:
        return ""

    try:
        import yt_dlp
        from openai import OpenAI

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
            client = OpenAI(api_key=settings.openai_api_key)
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
    youtube_channel_url: str | None = None,
    transcribe_videos: bool = True,
    max_video_transcripts: int = 3,
) -> dict[str, Any]:
    """Scrape the creator's content and use Claude to analyze their niche.

    Returns a full niche analysis including recommended subreddits.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"error": "ANTHROPIC_API_KEY required for niche analysis"}

    # --- Scrape all creator content ---
    creator_content: list[dict] = []

    # Twitter
    for handle in profile.competitors.twitter[:1]:  # Use first handle as the creator's own
        # The creator's own handle should ideally be in the profile
        pass

    # Try scraping creator's Twitter if we have bearer token
    if settings.twitter_bearer_token and profile.brand.name:
        twitter_data = scrape_creator_twitter(profile.brand.name)
        if twitter_data and "error" not in twitter_data:
            creator_content.append(twitter_data)

    # Instagram
    if settings.instagram_access_token and settings.instagram_business_account_id:
        ig_data = scrape_creator_instagram(settings.instagram_business_account_id)
        if ig_data and "error" not in ig_data:
            creator_content.append(ig_data)

    # YouTube
    video_transcripts: list[dict] = []
    if youtube_channel_url:
        yt_data = scrape_creator_youtube(youtube_channel_url)
        if yt_data and "error" not in yt_data:
            creator_content.append(yt_data)

            # Transcribe videos
            if transcribe_videos and yt_data.get("video_urls"):
                video_transcripts = transcribe_creator_videos(
                    yt_data["video_urls"],
                    max_videos=max_video_transcripts,
                )

    # Also include the existing profile data as context
    profile_context = {
        "platform": "profile_config",
        "bio": profile.voice.description,
        "recent_posts": profile.voice.example_posts,
        "topics_claimed": profile.topics.get("primary", []) + profile.topics.get("secondary", []),
    }
    creator_content.append(profile_context)

    # --- Format for Claude ---
    content_text = ""
    for source in creator_content:
        platform = source.get("platform", "unknown")
        bio = source.get("bio", "")
        posts = source.get("recent_posts", [])

        content_text += f"\n--- {platform.upper()} ---\n"
        if bio:
            content_text += f"Bio: {bio}\n"
        if source.get("pinned_tweet"):
            content_text += f"Pinned: {source['pinned_tweet']}\n"
        if source.get("topics_claimed"):
            content_text += f"Claimed topics: {', '.join(source['topics_claimed'])}\n"
        if posts:
            content_text += "Recent posts:\n"
            for p in posts[:30]:
                content_text += f"  - {p[:200]}\n"

    transcript_text = ""
    if video_transcripts:
        transcript_text = "\nVIDEO TRANSCRIPTS (what they actually say in their videos):\n"
        for vt in video_transcripts:
            transcript_text += f"\n[Video: {vt['url']}]\n{vt['transcript'][:2000]}\n"

    # --- Analyze with Claude ---
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": NICHE_ANALYSIS_PROMPT.format(
                creator_content=content_text,
                video_transcripts=transcript_text if transcript_text else "(No video transcripts available)",
            ),
        }],
    )

    raw = response.content[0].text
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        analysis = json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        analysis = {"error": "Failed to parse niche analysis", "raw": raw[:500]}

    # --- Save to database ---
    init_db()
    session = get_session()
    try:
        subreddits = [s["name"] for s in analysis.get("recommended_subreddits", [])]
        record = NicheProfileRecord(
            raw_content=json.dumps(creator_content, default=str)[:10000],
            niche_analysis=json.dumps(analysis),
            discovered_subreddits=json.dumps(subreddits),
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
