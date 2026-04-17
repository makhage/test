"""Load the agent's identity files for the current creator.

Each creator has their own agent.md, skills.md, soul.md under
`creators/<slug>/` (or `creator/` for the default creator).
These are prepended to every Gemini system prompt.
"""

from __future__ import annotations

from pathlib import Path

from social_agent.creators import creator_dir


def _read(name: str, slug: str | None = None) -> str:
    path = creator_dir(slug) / name
    if not path.exists():
        # Fallback to main creator/ directory for shared files (agent.md, skills.md)
        from social_agent.config import PROJECT_ROOT
        fallback = PROJECT_ROOT / "creator" / name
        if fallback.exists():
            return fallback.read_text()
        return ""
    return path.read_text()


def load_identity(slug: str | None = None) -> str:
    """Return the combined identity block to prepend to system prompts."""
    agent = _read("agent.md", slug)
    skills = _read("skills.md", slug)
    soul = _read("soul.md", slug)

    parts = []
    if agent:
        parts.append(f"# AGENT CORE\n\n{agent}")
    if skills:
        parts.append(f"# CAPABILITIES\n\n{skills}")
    if soul:
        parts.append(f"# CREATOR SOUL (Voice, Values, Identity)\n\n{soul}")
    return "\n\n---\n\n".join(parts)


def update_soul(content: str, slug: str | None = None) -> None:
    """Overwrite the creator's soul.md with new content."""
    d = creator_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / "soul.md").write_text(content)


def soul_from_niche_analysis(analysis: dict, linktree_data: dict | None = None) -> str:
    """Convert a niche analysis dict into a well-formatted soul.md."""
    name = ""
    if linktree_data:
        name = linktree_data.get("name", "")

    sections = [f"# Creator Soul\n"]

    if name:
        sections.append(f"## Identity\n\n**{name}**")
    sections.append(f"\n{analysis.get('niche_description', '')}\n")

    if audience := analysis.get("target_audience"):
        sections.append(f"## Audience\n\n{audience}\n")

    if style := analysis.get("content_style"):
        sections.append(f"## Voice & Style\n\n{style}\n")

    if themes := analysis.get("key_themes"):
        sections.append("## Core Themes\n")
        for t in themes:
            sections.append(f"- {t}")
        sections.append("")

    if topics := analysis.get("sub_topics"):
        sections.append("## Sub-topics You Cover\n")
        for t in topics:
            sections.append(f"- {t}")
        sections.append("")

    if pains := analysis.get("audience_pain_points"):
        sections.append("## What Your Audience Struggles With\n")
        for p in pains:
            sections.append(f"- {p}")
        sections.append("")

    return "\n".join(sections)
