"""Long-form → Short-form Repurposer.

Takes a YouTube video, podcast, or blog post URL, transcribes/extracts it,
and generates a full week of short-form content across all platforms.

One 20-minute video = 10-15 tweets, 2-3 carousels, 3-5 TikTok captions.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from social_agent.config import get_settings
from social_agent.models.content import InfluencerProfile, NicheIntelligence
from social_agent.research.niche_profiler import transcribe_video


LONGFORM_REPURPOSE_PROMPT = """You are an expert content repurposer. You take long-form content (video transcripts, blog posts, podcast episodes) and extract EVERY possible piece of short-form content from it.

INFLUENCER VOICE:
{voice_description}
Tone: {tone}

LONG-FORM SOURCE:
{source_content}

{trend_context}

Your job: Extract EVERY interesting idea, insight, story, tip, opinion, and quotable moment from this content. Then turn each one into platform-specific short-form content.

Generate ALL of the following:
1. **Tweets** (5-8): Each should be a standalone insight/take from the source. Mix of: hot takes, tips, story snippets, quotable lines. Each max 280 chars.
2. **Twitter Threads** (1-2): Deep dives into the meatiest topics from the source. 5-7 tweets each.
3. **Instagram Carousels** (2-3): Educational breakdowns of key concepts. 5-7 slides each with heading + body.
4. **TikTok Captions** (3-5): Hook-driven captions for talking-head videos where the creator discusses a point from the source. Include script notes (talking points, NOT word-for-word).

RULES:
- Each piece should stand ALONE — someone who never saw the original should still get value
- Don't just summarize — extract the most interesting/controversial/useful angles
- Use the influencer's actual voice, not generic AI
- Hooks should stop the scroll
- Vary the angles: don't make 5 tweets that say the same thing differently

Return JSON:
{{
  "source_summary": "<1-2 sentence summary of what the long-form content covers>",
  "key_insights": ["insight 1", "insight 2", ...],
  "tweets": [
    {{"text": "<max 280 chars>", "hashtags": [], "angle": "<what makes this tweet unique>"}},
    ...
  ],
  "threads": [
    {{
      "hook": "<first tweet, max 280 chars>",
      "tweets": ["<tweet 2>", "<tweet 3>", ...],
      "hashtags": [],
      "topic": "<thread topic>"
    }},
    ...
  ],
  "carousels": [
    {{
      "title": "<carousel title>",
      "slides": [{{"heading": "<max 8 words>", "body": "<2-3 sentences>"}}],
      "caption": "<IG caption>",
      "hashtags": []
    }},
    ...
  ],
  "tiktoks": [
    {{
      "caption": "<hook + body + CTA>",
      "hashtags": [],
      "script_notes": "<talking points for the video>",
      "angle": "<what point from the source this covers>"
    }},
    ...
  ]
}}
"""


def repurpose_longform(
    source_url: str | None = None,
    source_text: str | None = None,
    profile: InfluencerProfile | None = None,
    intelligence: NicheIntelligence | None = None,
) -> dict[str, Any]:
    """Turn a long-form piece of content into a week of short-form posts.

    Provide either a URL (video/podcast — will be transcribed) or raw text (blog post/transcript).
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Get the source content
    content = source_text or ""
    if source_url and not content:
        content = transcribe_video(source_url)
        if not content or content.startswith("("):
            # Try fetching as a web page
            try:
                import requests
                resp = requests.get(source_url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0"
                })
                # Strip HTML tags crudely
                import re
                text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                content = text[:8000]
            except Exception:
                pass

    if not content:
        return {"error": "Could not extract content from the source."}

    trend_context = ""
    if intelligence and intelligence.trending_topics:
        trend_context = (
            f"\nCurrent trends to tie into: {', '.join(intelligence.trending_topics[:5])}\n"
            f"Winning hooks: {', '.join(h.pattern for h in intelligence.winning_hooks[:3])}"
        )

    voice_desc = "Professional content creator"
    tone = "engaging, informative"
    if profile:
        voice_desc = profile.voice.description
        tone = ", ".join(profile.voice.tone)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": LONGFORM_REPURPOSE_PROMPT.format(
                voice_description=voice_desc,
                tone=tone,
                source_content=content[:6000],
                trend_context=trend_context,
            ),
        }],
    )

    raw = response.content[0].text
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse repurposed content", "raw": raw[:500]}
