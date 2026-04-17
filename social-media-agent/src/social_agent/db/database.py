"""SQLAlchemy models and database setup.

Every table that holds creator-specific data has a `creator_slug` column
so the same database can serve multiple creators in isolation.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from social_agent.config import get_settings


DEFAULT_CREATOR_SLUG = "default"


class Base(DeclarativeBase):
    pass


class CreatorRecord(Base):
    """One row per creator the user manages."""
    __tablename__ = "creators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), default="")
    linktree_url = Column(String(500), default="")
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ViralPostRecord(Base):
    __tablename__ = "viral_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    platform = Column(String(20), nullable=False)
    author = Column(String(100), default="")
    text = Column(Text, nullable=False)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    url = Column(String(500), default="")
    hashtags = Column(Text, default="")
    content_type = Column(String(50), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


class ScheduledPostRecord(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    content_type = Column(String(50), nullable=False)
    content_json = Column(Text, nullable=False)
    platform = Column(String(20), nullable=False)
    scheduled_time = Column(DateTime, nullable=True)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    published_post_id = Column(String(100), default="")  # Platform-assigned ID
    source_signal = Column(Text, default="")
    source_angle = Column(Text, default="")


class AnalyticsRecord(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    post_id = Column(String(100), nullable=False)
    platform = Column(String(20), nullable=False)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class ContentVariantRecord(Base):
    __tablename__ = "content_variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    parent_content_id = Column(Integer, nullable=True)
    variant_label = Column(String(50), default="")
    content_type = Column(String(50), default="")
    content_json = Column(Text, default="")
    platform = Column(String(20), default="twitter")
    engagement_score = Column(Float, nullable=True)
    is_winner = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RedditPostRecord(Base):
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    subreddit = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    selftext = Column(Text, default="")
    author = Column(String(100), default="")
    upvotes = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    url = Column(String(500), default="")
    permalink = Column(String(500), default="")
    top_comments = Column(Text, default="[]")
    flair = Column(String(100), default="")
    content_type = Column(String(50), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


class CompetitorPostRecord(Base):
    __tablename__ = "competitor_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    handle = Column(String(100), nullable=False)
    platform = Column(String(20), nullable=False)
    text = Column(Text, default="")
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    url = Column(String(500), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    category = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(200), default="")
    relevance = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NicheIntelligenceRecord(Base):
    __tablename__ = "niche_intelligence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    trending_topics = Column(Text, default="[]")
    winning_hooks = Column(Text, default="[]")
    top_formats = Column(Text, default="[]")
    engagement_benchmarks = Column(Text, default="{}")
    audience_questions = Column(Text, default="[]")
    hot_takes = Column(Text, default="[]")
    authentic_phrases = Column(Text, default="[]")
    source_post_count = Column(Integer, default=0)
    generated_at = Column(DateTime, default=datetime.utcnow)


class ReplyDraftRecord(Base):
    __tablename__ = "reply_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_slug = Column(String(100), default=DEFAULT_CREATOR_SLUG, index=True)
    platform = Column(String(20), nullable=False)
    original_comment_author = Column(String(100), default="")
    original_comment_text = Column(Text, nullable=False)
    suggested_reply = Column(Text, default="")
    category = Column(String(20), default="general")
    priority = Column(Integer, default=0)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Engine setup ────────────────────────────────────────────────────────────

_engine = None
_SessionLocal = None

# Models that get auto-scoped to the current creator on insert
_CREATOR_SCOPED_MODELS = (
    "ViralPostRecord",
    "ScheduledPostRecord",
    "AnalyticsRecord",
    "ContentVariantRecord",
    "RedditPostRecord",
    "CompetitorPostRecord",
    "KnowledgeEntry",
    "NicheIntelligenceRecord",
    "ReplyDraftRecord",
)


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
        _install_creator_scoping()
    return _SessionLocal()


def _install_creator_scoping() -> None:
    """Attach an event listener that auto-fills creator_slug on insert."""
    from sqlalchemy import event

    @event.listens_for(Session, "before_flush")
    def _set_creator_slug(session, flush_context, instances):
        try:
            from social_agent.creators import current_slug
            slug = current_slug()
        except Exception:
            slug = DEFAULT_CREATOR_SLUG

        for obj in session.new:
            if obj.__class__.__name__ in _CREATOR_SCOPED_MODELS:
                if hasattr(obj, "creator_slug") and not getattr(obj, "creator_slug", None):
                    obj.creator_slug = slug


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Auto-migration: add creator_slug column to older DBs that don't have it
    with engine.begin() as conn:
        tables_to_migrate = [
            "viral_posts", "scheduled_posts", "analytics", "content_variants",
            "reddit_posts", "competitor_posts", "knowledge_entries",
            "niche_intelligence", "reply_drafts",
        ]
        for table in tables_to_migrate:
            try:
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                columns = [row[1] for row in result]
                if "creator_slug" not in columns:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN creator_slug VARCHAR(100) "
                        f"DEFAULT '{DEFAULT_CREATOR_SLUG}'"
                    ))
            except Exception:
                pass  # Table doesn't exist yet or DB is not SQLite

        # Add published_post_id to scheduled_posts if missing
        try:
            result = conn.execute(text("PRAGMA table_info(scheduled_posts)"))
            columns = [row[1] for row in result]
            if "published_post_id" not in columns:
                conn.execute(text(
                    "ALTER TABLE scheduled_posts ADD COLUMN published_post_id VARCHAR(100) DEFAULT ''"
                ))
        except Exception:
            pass

    # Ensure default creator exists
    session = get_session()
    try:
        default = session.query(CreatorRecord).filter_by(slug=DEFAULT_CREATOR_SLUG).first()
        if not default:
            session.add(CreatorRecord(slug=DEFAULT_CREATOR_SLUG, name="Default Creator"))
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
