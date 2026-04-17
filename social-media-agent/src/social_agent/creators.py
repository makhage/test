"""Multi-creator support.

The current creator is stored in:
1. Streamlit session state (during a dashboard session)
2. An env var / file (for CLI usage and as fallback)

All DB queries and file paths route through `current_slug()` so each
creator gets their own isolated knowledge base, soul.md, and data.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from social_agent.config import PROJECT_ROOT
from social_agent.db.database import CreatorRecord, DEFAULT_CREATOR_SLUG, get_session, init_db

CREATORS_DIR = PROJECT_ROOT / "creators"
_ACTIVE_SLUG_FILE = PROJECT_ROOT / "data" / "active_creator.txt"


# ── Slug helpers ────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Turn a display name into a filesystem/DB-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "creator"


# ── Active creator tracking ─────────────────────────────────────────────────

def current_slug() -> str:
    """Return the currently active creator's slug.

    Looks at Streamlit session state first (if available), then the
    persisted file, then falls back to 'default'.
    """
    # Try streamlit session state
    try:
        import streamlit as st  # noqa
        if hasattr(st, "session_state") and "active_creator_slug" in st.session_state:
            return st.session_state["active_creator_slug"]
    except Exception:
        pass

    # Fall back to persisted file
    try:
        if _ACTIVE_SLUG_FILE.exists():
            slug = _ACTIVE_SLUG_FILE.read_text().strip()
            if slug:
                return slug
    except Exception:
        pass

    return DEFAULT_CREATOR_SLUG


def set_active_slug(slug: str) -> None:
    """Set the active creator slug in both session state and file."""
    try:
        import streamlit as st
        st.session_state["active_creator_slug"] = slug
    except Exception:
        pass

    _ACTIVE_SLUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ACTIVE_SLUG_FILE.write_text(slug)


# ── Creator CRUD ────────────────────────────────────────────────────────────

def list_creators() -> list[dict]:
    """List all creators with their metadata."""
    init_db()
    session = get_session()
    try:
        records = session.query(CreatorRecord).order_by(CreatorRecord.created_at).all()
        return [{
            "slug": r.slug,
            "name": r.name or r.slug,
            "linktree_url": r.linktree_url,
            "avatar_url": r.avatar_url,
        } for r in records]
    finally:
        session.close()


def get_creator(slug: str) -> Optional[dict]:
    """Get a specific creator by slug."""
    init_db()
    session = get_session()
    try:
        r = session.query(CreatorRecord).filter_by(slug=slug).first()
        if not r:
            return None
        return {
            "slug": r.slug,
            "name": r.name or r.slug,
            "linktree_url": r.linktree_url,
            "avatar_url": r.avatar_url,
        }
    finally:
        session.close()


def create_creator(name: str, linktree_url: str = "", slug: str | None = None) -> str:
    """Create a new creator. Returns the slug."""
    slug = slug or slugify(name)

    init_db()
    session = get_session()
    try:
        existing = session.query(CreatorRecord).filter_by(slug=slug).first()
        if existing:
            # Update instead of error
            existing.name = name or existing.name
            if linktree_url:
                existing.linktree_url = linktree_url
            session.commit()
            return slug

        session.add(CreatorRecord(slug=slug, name=name, linktree_url=linktree_url))
        session.commit()
    finally:
        session.close()

    # Seed creator's identity files
    creator_dir = CREATORS_DIR / slug
    creator_dir.mkdir(parents=True, exist_ok=True)

    # Copy templates from main creator/ dir if they exist
    main_creator_dir = PROJECT_ROOT / "creator"
    for fname in ["agent.md", "skills.md", "soul.md"]:
        src = main_creator_dir / fname
        dst = creator_dir / fname
        if src.exists() and not dst.exists():
            dst.write_text(src.read_text())

    return slug


def delete_creator(slug: str) -> bool:
    """Remove a creator and all their data. Returns True if deleted."""
    if slug == DEFAULT_CREATOR_SLUG:
        return False  # Can't delete the default

    init_db()
    session = get_session()
    try:
        r = session.query(CreatorRecord).filter_by(slug=slug).first()
        if not r:
            return False

        # Cascade delete from all creator-scoped tables
        from social_agent.db.database import (
            ViralPostRecord, ScheduledPostRecord, AnalyticsRecord,
            ContentVariantRecord, RedditPostRecord, CompetitorPostRecord,
            KnowledgeEntry, NicheIntelligenceRecord, ReplyDraftRecord,
        )
        for model in [
            ViralPostRecord, ScheduledPostRecord, AnalyticsRecord,
            ContentVariantRecord, RedditPostRecord, CompetitorPostRecord,
            KnowledgeEntry, NicheIntelligenceRecord, ReplyDraftRecord,
        ]:
            session.query(model).filter_by(creator_slug=slug).delete()

        session.delete(r)
        session.commit()
    finally:
        session.close()

    # Remove creator's files
    import shutil
    creator_dir = CREATORS_DIR / slug
    if creator_dir.exists():
        shutil.rmtree(creator_dir, ignore_errors=True)

    return True


# ── Per-creator file paths ──────────────────────────────────────────────────

def creator_dir(slug: str | None = None) -> Path:
    """Get the directory holding this creator's identity files."""
    slug = slug or current_slug()
    if slug == DEFAULT_CREATOR_SLUG:
        # Default uses the original creator/ dir for backwards compatibility
        return PROJECT_ROOT / "creator"
    d = CREATORS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d
