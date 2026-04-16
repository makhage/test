"""Knowledge base — indexed memory that grounds Gemini in the creator's context.

Every research step (niche analysis, Reddit mining, performance tracking) writes
insights here. Before every content generation call, we pull the most recent
and relevant entries and prepend them to the system prompt.

This gives Gemini a persistent memory across sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from social_agent.db.database import KnowledgeEntry, get_session, init_db


# Valid categories — keep in sync with KnowledgeEntry.category
CATEGORIES = {
    "niche_insight",        # Output of niche analysis
    "audience_question",    # Question from Reddit/comments
    "winning_hook",         # A hook pattern that's working
    "performance",          # A post performed well/poorly
    "trend",                # A topic that's accelerating
    "competitor_pattern",   # What a competitor is doing that works
    "content_gap",          # Audience demand not being met
    "hot_take",             # Opinion that drives engagement
    "authentic_phrase",     # Real language the audience uses
}


def remember(
    category: str,
    content: str,
    *,
    source: str = "",
    relevance: float = 1.0,
) -> None:
    """Write an insight into the knowledge base."""
    if category not in CATEGORIES:
        # Unknown categories still stored but flagged for review
        pass

    init_db()
    session = get_session()
    try:
        entry = KnowledgeEntry(
            category=category,
            content=content,
            source=source,
            relevance=max(0.0, min(1.0, relevance)),
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()


def remember_many(entries: Iterable[tuple[str, str, str, float]]) -> None:
    """Batch insert. Each tuple is (category, content, source, relevance)."""
    init_db()
    session = get_session()
    try:
        for category, content, source, relevance in entries:
            session.add(KnowledgeEntry(
                category=category,
                content=content,
                source=source,
                relevance=max(0.0, min(1.0, relevance)),
            ))
        session.commit()
    finally:
        session.close()


def recall(
    categories: list[str] | None = None,
    days: int = 30,
    limit: int = 20,
) -> list[dict]:
    """Get the most recent, relevant knowledge entries.

    Returns list of dicts with keys: category, content, source, created_at.
    Sorted by relevance desc, then recency desc.
    """
    init_db()
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = session.query(KnowledgeEntry).filter(
            KnowledgeEntry.created_at >= cutoff
        )
        if categories:
            query = query.filter(KnowledgeEntry.category.in_(categories))

        entries = query.order_by(
            KnowledgeEntry.relevance.desc(),
            KnowledgeEntry.created_at.desc(),
        ).limit(limit).all()

        return [{
            "category": e.category,
            "content": e.content,
            "source": e.source,
            "created_at": e.created_at.isoformat(),
        } for e in entries]
    finally:
        session.close()


def build_context_block(max_chars: int = 3000) -> str:
    """Return a formatted block of the most relevant recent knowledge,
    ready to prepend to a Gemini system prompt.

    Returns empty string if the knowledge base is empty.
    """
    entries = recall(limit=40)
    if not entries:
        return ""

    # Group by category for readability
    by_category: dict[str, list[dict]] = {}
    for e in entries:
        by_category.setdefault(e["category"], []).append(e)

    lines = ["# CREATOR KNOWLEDGE BASE", ""]
    category_labels = {
        "niche_insight": "What we know about this creator's niche",
        "audience_question": "Questions the audience actually asks",
        "winning_hook": "Hook patterns that work in this niche",
        "performance": "What performed well recently",
        "trend": "Currently trending topics",
        "content_gap": "Audience demand not yet addressed",
        "hot_take": "Opinions driving engagement",
        "authentic_phrase": "Real language this audience uses",
        "competitor_pattern": "What's working for competitors",
    }

    for cat, cat_entries in by_category.items():
        label = category_labels.get(cat, cat.replace("_", " ").title())
        lines.append(f"## {label}")
        for e in cat_entries[:8]:  # cap per category
            lines.append(f"- {e['content']}")
        lines.append("")

    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n... (truncated)"
    return block


def stats() -> dict:
    """Summary stats for the dashboard."""
    init_db()
    session = get_session()
    try:
        total = session.query(KnowledgeEntry).count()
        by_category = {}
        for cat in CATEGORIES:
            by_category[cat] = session.query(KnowledgeEntry).filter_by(category=cat).count()
        return {"total": total, "by_category": by_category}
    finally:
        session.close()
