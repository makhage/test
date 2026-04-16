"""SQLAlchemy models and database setup."""

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
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from social_agent.config import get_settings


class Base(DeclarativeBase):
    pass


class ViralPostRecord(Base):
    __tablename__ = "viral_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)
    author = Column(String(100), default="")
    text = Column(Text, nullable=False)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    url = Column(String(500), default="")
    hashtags = Column(Text, default="")  # JSON list
    content_type = Column(String(50), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


class ScheduledPostRecord(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_type = Column(String(50), nullable=False)
    content_json = Column(Text, nullable=False)
    platform = Column(String(20), nullable=False)
    scheduled_time = Column(DateTime, nullable=True)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


class AnalyticsRecord(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
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
    subreddit = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    selftext = Column(Text, default="")
    author = Column(String(100), default="")
    upvotes = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    url = Column(String(500), default="")
    permalink = Column(String(500), default="")
    top_comments = Column(Text, default="[]")  # JSON list of top comment texts
    flair = Column(String(100), default="")
    content_type = Column(String(50), default="")  # "discussion", "question", "tutorial", etc.
    scraped_at = Column(DateTime, default=datetime.utcnow)


class CompetitorPostRecord(Base):
    __tablename__ = "competitor_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    handle = Column(String(100), nullable=False)
    platform = Column(String(20), nullable=False)
    text = Column(Text, default="")
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    url = Column(String(500), default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeEntry(Base):
    """Indexed memory — every insight the agent learns gets a row here.

    Gemini can retrieve recent entries to stay grounded in the creator's
    specific context rather than relying on generic training.
    """
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False, index=True)
    # e.g. "niche_insight" | "audience_question" | "winning_hook" |
    #      "performance" | "trend" | "competitor_pattern" | "content_gap"
    content = Column(Text, nullable=False)  # The actual insight as readable text
    source = Column(String(200), default="")  # Where it came from (e.g. "r/learnpython")
    relevance = Column(Float, default=1.0)  # 0-1, for ranking in retrieval
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NicheIntelligenceRecord(Base):
    __tablename__ = "niche_intelligence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trending_topics = Column(Text, default="[]")  # JSON
    winning_hooks = Column(Text, default="[]")  # JSON
    top_formats = Column(Text, default="[]")  # JSON
    engagement_benchmarks = Column(Text, default="{}")  # JSON
    audience_questions = Column(Text, default="[]")  # JSON — from Reddit
    hot_takes = Column(Text, default="[]")  # JSON — from Reddit
    authentic_phrases = Column(Text, default="[]")  # JSON — from Reddit
    source_post_count = Column(Integer, default=0)
    generated_at = Column(DateTime, default=datetime.utcnow)


class ReplyDraftRecord(Base):
    __tablename__ = "reply_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)
    original_comment_author = Column(String(100), default="")
    original_comment_text = Column(Text, nullable=False)
    suggested_reply = Column(Text, default="")
    category = Column(String(20), default="general")
    priority = Column(Integer, default=0)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


_engine = None
_SessionLocal = None


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
    return _SessionLocal()


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
