"""Tweet and thread generation using AI."""

from __future__ import annotations

from social_agent.ai import chat, parse_json
from social_agent.models.content import InfluencerProfile, NicheIntelligence, Tweet


TWEET_SYSTEM_PROMPT = """You are a social media ghostwriter for the influencer described below.
Generate tweets in their authentic voice.

INFLUENCER VOICE:
{voice_description}

TONE: {tone}
AVOID: {avoid}

EXAMPLE POSTS BY THIS INFLUENCER:
{examples}

{trend_context}

RULES:
- Maximum 280 characters per tweet
- Be authentic to the influencer's voice — not generic AI
- Use hooks that stop the scroll
- If generating a thread, each tweet should stand alone but connect to the narrative
- Include hashtags only if they add value (max {max_hashtags})
- End with a CTA when appropriate: {cta}
"""


def _build_system_prompt(
    profile: InfluencerProfile,
    intelligence: NicheIntelligence | None = None,
) -> str:
    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"\nCURRENT VIRAL TRENDS IN YOUR NICHE:\n"
            f"- Trending topics: {', '.join(intelligence.trending_topics[:5])}\n"
            f"- Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:5])}\n"
            f"- Top formats: {', '.join(intelligence.top_formats[:3])}\n"
        )
        if intelligence.audience_questions:
            trend_context += f"- Questions your audience is asking (from Reddit): {', '.join(intelligence.audience_questions[:5])}\n"
        if intelligence.hot_takes:
            trend_context += f"- Hot takes getting engagement: {', '.join(intelligence.hot_takes[:3])}\n"
        if intelligence.authentic_phrases:
            trend_context += f"- Phrases real people use (sound human, not AI): {', '.join(intelligence.authentic_phrases[:5])}\n"
        trend_context += "Use these trends and real audience language to make your content timely, relevant, and human."

    twitter_settings = profile.platforms.get("twitter")
    max_hashtags = twitter_settings.max_hashtags if twitter_settings else 3
    cta = twitter_settings.default_cta if twitter_settings else ""

    return TWEET_SYSTEM_PROMPT.format(
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        avoid=", ".join(profile.voice.avoid),
        examples="\n".join(f'- "{p}"' for p in profile.voice.example_posts),
        trend_context=trend_context,
        max_hashtags=max_hashtags,
        cta=cta,
    )


def generate_tweet(
    topic: str,
    profile: InfluencerProfile,
    style: str = "engaging",
    intelligence: NicheIntelligence | None = None,
) -> Tweet:
    """Generate a single tweet using AI."""
    system = _build_system_prompt(profile, intelligence)
    user_prompt = (
        f"Write a tweet about: {topic}\n"
        f"Style: {style}\n\n"
        f"Return JSON with keys: text (string, max 280 chars), hashtags (list of strings)."
    )

    raw = chat(system=system, user=user_prompt, max_tokens=500)
    data = parse_json(raw)
    if not data or "text" not in data:
        data = {"text": raw.strip()[:280], "hashtags": []}

    return Tweet(
        text=data.get("text", "")[:280],
        hashtags=data.get("hashtags", []),
    )


def generate_thread(
    topic: str,
    profile: InfluencerProfile,
    num_tweets: int = 5,
    intelligence: NicheIntelligence | None = None,
) -> Tweet:
    """Generate a Twitter thread using AI."""
    system = _build_system_prompt(profile, intelligence)
    user_prompt = (
        f"Write a Twitter thread ({num_tweets} tweets) about: {topic}\n\n"
        f"Return JSON with keys:\n"
        f'- text: string (the first tweet / hook, max 280 chars)\n'
        f'- thread_tweets: list of strings (remaining tweets, each max 280 chars)\n'
        f'- hashtags: list of strings (for the last tweet)'
    )

    raw = chat(system=system, user=user_prompt, max_tokens=2000)
    try:
        data = parse_json(raw)
    except Exception:
        data = {"text": raw.strip()[:280], "thread_tweets": [], "hashtags": []}

    return Tweet(
        text=data.get("text", "")[:280],
        is_thread=True,
        thread_tweets=[t[:280] for t in data.get("thread_tweets", [])],
        hashtags=data.get("hashtags", []),
    )
