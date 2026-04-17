"""Content idea generator — synthesizes everything we know into ready-to-create ideas.

Instead of asking the user "what do you want to write about?", this module
reads the knowledge base + research data and proposes specific content ideas
tied to real audience signals.
"""

from __future__ import annotations

from typing import Any

from social_agent.ai import chat_json
from social_agent.knowledge import recall
from social_agent.research.analyzer import get_latest_intelligence
from social_agent.research.niche_profiler import get_latest_niche_profile


def suggest_content_ideas(count: int = 6) -> list[dict[str, Any]]:
    """Generate concrete content ideas based on the agent's knowledge.

    Returns list of dicts:
        {
            "topic": "specific content topic",
            "format": "tweet" | "thread" | "carousel" | "tiktok",
            "angle": "why this will work",
            "source": "what signal triggered this (e.g. 'r/learnpython asks about this 12 times')",
            "style": "engaging" | "educational" | "controversial" | "storytelling",
        }

    Falls back to generic suggestions if knowledge base is empty.
    """
    # Pull the raw signals we'll synthesize
    audience_questions = recall(categories=["audience_question"], limit=15)
    hot_takes = recall(categories=["hot_take"], limit=10)
    trends = recall(categories=["trend"], limit=8)
    gaps = recall(categories=["content_gap"], limit=10)
    niche = recall(categories=["niche_insight"], limit=5)

    # If we have nothing, return empty — UI will show "run research first"
    if not (audience_questions or hot_takes or trends or gaps or niche):
        return []

    # Build a summary of signals for Gemini to work from
    signal_sections = []
    if niche:
        signal_sections.append("CREATOR NICHE:\n" + "\n".join(f"- {e['content']}" for e in niche[:3]))
    if audience_questions:
        signal_sections.append(
            "QUESTIONS THE AUDIENCE IS ACTUALLY ASKING (from Reddit):\n"
            + "\n".join(f"- {e['content']} (in {e['source']})" for e in audience_questions[:10])
        )
    if gaps:
        signal_sections.append(
            "CONTENT GAPS — unmet audience demand:\n"
            + "\n".join(f"- {e['content']}" for e in gaps[:5])
        )
    if hot_takes:
        signal_sections.append(
            "HOT TAKES getting engagement:\n"
            + "\n".join(f"- {e['content']}" for e in hot_takes[:5])
        )
    if trends:
        signal_sections.append(
            "TRENDING IN THIS NICHE:\n"
            + "\n".join(f"- {e['content']}" for e in trends[:5])
        )

    signals = "\n\n".join(signal_sections)

    prompt = f"""Using the signals below, propose {count} specific, concrete content ideas this creator should make.

Each idea must:
- Be tied to a real signal (a question someone asked, a gap you identified, a trend)
- Specify the right format for the content (tweet, thread, carousel, or tiktok)
- Include a clear angle — why this version of the idea will work
- Reference the source signal so the creator sees where it came from

Mix formats: some quick tweets, some deeper threads/carousels, one or two spicy takes.
Don't pick generic topics. Pick specifics that resonate with the exact signals given.

SIGNALS:
{signals}

Return JSON:
{{
  "ideas": [
    {{
      "topic": "specific, concrete topic",
      "format": "tweet | thread | carousel | tiktok",
      "angle": "1-sentence why this works",
      "source": "which signal triggered this (from the list above)",
      "style": "engaging | educational | controversial | storytelling"
    }}
  ]
}}
"""

    try:
        result = chat_json(
            system="You turn audience signals into specific content ideas. You never output generic topics.",
            user=prompt,
            max_tokens=3000,
        )
        ideas = result.get("ideas", []) if result else []
        return ideas[:count]
    except Exception:
        return []
