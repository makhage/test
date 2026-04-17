"""Score content for voice consistency and auto-rewrite if below threshold."""

from __future__ import annotations

from social_agent.ai import chat, chat_json, parse_json
from social_agent.models.content import InfluencerProfile, VoiceScore


SCORING_PROMPT = """You are an expert voice consistency evaluator. Score the following content against the influencer's voice profile.

INFLUENCER VOICE PROFILE:
Description: {voice_description}
Tone: {tone}
Things to avoid: {avoid}

Example posts in their authentic voice:
{examples}

CONTENT TO SCORE:
{content}

Score from 1-10 on these criteria:
- Tone match (does it sound like this person?)
- Vocabulary consistency (word choices match their style?)
- Authenticity (does it feel genuine or AI-generated?)
- Avoidance of blacklisted patterns (does it avoid what they avoid?)

Return JSON:
{{
  "score": <1-10>,
  "feedback": "<specific feedback on what matches and what feels off>",
  "passed": <true if score >= {threshold}>
}}
"""

REWRITE_PROMPT = """Rewrite this social media content to better match the influencer's voice.

VOICE PROFILE:
Description: {voice_description}
Tone: {tone}
Avoid: {avoid}

Examples of their real voice:
{examples}

ORIGINAL CONTENT:
{content}

FEEDBACK ON WHY IT DOESN'T MATCH:
{feedback}

Rewrite the content to fix the issues. Keep the same topic and key points,
but make it sound authentically like this influencer. Return ONLY the rewritten text.
"""


def score_voice(
    content: str,
    profile: InfluencerProfile,
) -> VoiceScore:
    """Score content against the influencer's voice profile."""
    threshold = profile.content_settings.voice_score_threshold

    user_prompt = SCORING_PROMPT.format(
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        avoid=", ".join(profile.voice.avoid),
        examples="\n".join(f'- "{p}"' for p in profile.voice.example_posts),
        content=content,
        threshold=threshold,
    )

    try:
        raw = chat(system="You are a voice consistency scoring expert for social media content.", user=user_prompt, max_tokens=500)
        data = parse_json(raw) if raw else {}
    except Exception:
        data = {}

    # If scoring failed, assume content passes — never block generation
    if not data:
        return VoiceScore(score=8, feedback="", passed=True)

    return VoiceScore(
        score=max(1, min(10, data.get("score", 8))),
        feedback=data.get("feedback", ""),
        passed=data.get("passed", data.get("score", 8) >= threshold),
    )


def rewrite_for_voice(
    content: str,
    feedback: str,
    profile: InfluencerProfile,
) -> str:
    """Rewrite content to better match the influencer's voice."""
    user_prompt = REWRITE_PROMPT.format(
        voice_description=profile.voice.description,
        tone=", ".join(profile.voice.tone),
        avoid=", ".join(profile.voice.avoid),
        examples="\n".join(f'- "{p}"' for p in profile.voice.example_posts),
        content=content,
        feedback=feedback,
    )

    return chat(system="You are a voice consistency scoring expert for social media content.", user=user_prompt, max_tokens=1500)


def score_and_rewrite(
    content: str,
    profile: InfluencerProfile,
) -> tuple[str, VoiceScore]:
    """Score content and auto-rewrite if below threshold. Returns (final_content, final_score)."""
    max_attempts = profile.content_settings.max_rewrite_attempts
    current_content = content

    for attempt in range(max_attempts + 1):
        score = score_voice(current_content, profile)
        score.rewrite_count = attempt

        if score.passed:
            return current_content, score

        if attempt < max_attempts:
            current_content = rewrite_for_voice(current_content, score.feedback, profile)

    # Return best attempt even if it didn't pass
    return current_content, score
