"""Tests for database operations using in-memory SQLite."""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_agent.db.database import (
    AnalyticsRecord,
    Base,
    CompetitorPostRecord,
    ContentVariantRecord,
    NicheIntelligenceRecord,
    RedditPostRecord,
    ReplyDraftRecord,
    ScheduledPostRecord,
    ViralPostRecord,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database and session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestViralPostRecord:
    def test_create_and_query(self, db_session):
        record = ViralPostRecord(
            platform="twitter",
            text="This went viral!",
            likes=5000,
            shares=1200,
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(ViralPostRecord).first()
        assert result.text == "This went viral!"
        assert result.likes == 5000
        assert result.platform == "twitter"

    def test_ordering_by_likes(self, db_session):
        for likes in [100, 5000, 500]:
            db_session.add(ViralPostRecord(platform="twitter", text=f"Post {likes}", likes=likes))
        db_session.commit()

        results = db_session.query(ViralPostRecord).order_by(ViralPostRecord.likes.desc()).all()
        assert results[0].likes == 5000
        assert results[1].likes == 500
        assert results[2].likes == 100


class TestScheduledPostRecord:
    def test_create_with_default_status(self, db_session):
        record = ScheduledPostRecord(
            content_type="tweet",
            content_json='{"text": "hello"}',
            platform="twitter",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(ScheduledPostRecord).first()
        assert result.status == "draft"

    def test_filter_by_status(self, db_session):
        db_session.add(ScheduledPostRecord(content_type="tweet", content_json="{}", platform="twitter", status="pending"))
        db_session.add(ScheduledPostRecord(content_type="tweet", content_json="{}", platform="twitter", status="approved"))
        db_session.add(ScheduledPostRecord(content_type="tweet", content_json="{}", platform="twitter", status="pending"))
        db_session.commit()

        pending = db_session.query(ScheduledPostRecord).filter_by(status="pending").all()
        assert len(pending) == 2


class TestRedditPostRecord:
    def test_create_with_comments(self, db_session):
        comments = ["Great post!", "I disagree because..."]
        record = RedditPostRecord(
            subreddit="learnpython",
            title="How do I use decorators?",
            selftext="I've been trying to understand...",
            upvotes=342,
            num_comments=45,
            top_comments=json.dumps(comments),
            content_type="question",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(RedditPostRecord).first()
        assert result.subreddit == "learnpython"
        assert result.content_type == "question"
        assert json.loads(result.top_comments) == comments

    def test_filter_by_content_type(self, db_session):
        db_session.add(RedditPostRecord(subreddit="python", title="Q1", content_type="question", upvotes=100))
        db_session.add(RedditPostRecord(subreddit="python", title="T1", content_type="tutorial", upvotes=200))
        db_session.add(RedditPostRecord(subreddit="python", title="Q2", content_type="question", upvotes=300))
        db_session.commit()

        questions = db_session.query(RedditPostRecord).filter_by(content_type="question").all()
        assert len(questions) == 2


class TestNicheIntelligenceRecord:
    def test_json_fields(self, db_session):
        record = NicheIntelligenceRecord(
            trending_topics=json.dumps(["AI", "Python", "Rust"]),
            winning_hooks=json.dumps([{"pattern": "bold claim", "example": "X is dead"}]),
            top_formats=json.dumps(["carousel", "thread"]),
            audience_questions=json.dumps(["How to learn Python?", "Is AI replacing devs?"]),
            hot_takes=json.dumps(["Python is overrated"]),
            authentic_phrases=json.dumps(["ngl this is fire"]),
            source_post_count=42,
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(NicheIntelligenceRecord).first()
        topics = json.loads(result.trending_topics)
        assert "AI" in topics
        questions = json.loads(result.audience_questions)
        assert len(questions) == 2


class TestAnalyticsRecord:
    def test_create_and_query(self, db_session):
        record = AnalyticsRecord(
            post_id="tweet_123",
            platform="twitter",
            likes=500,
            shares=100,
            comments=50,
            impressions=10000,
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(AnalyticsRecord).first()
        assert result.likes == 500
        assert result.impressions == 10000


class TestContentVariantRecord:
    def test_create_variants(self, db_session):
        for label in ["hook_a", "hook_b", "hook_c"]:
            db_session.add(ContentVariantRecord(
                variant_label=label,
                content_type="tweet",
                content_json=json.dumps({"text": f"Test {label}"}),
                platform="twitter",
            ))
        db_session.commit()

        variants = db_session.query(ContentVariantRecord).all()
        assert len(variants) == 3

    def test_winner_selection(self, db_session):
        db_session.add(ContentVariantRecord(variant_label="a", content_json="{}", engagement_score=5.0))
        db_session.add(ContentVariantRecord(variant_label="b", content_json="{}", engagement_score=8.5, is_winner=True))
        db_session.commit()

        winner = db_session.query(ContentVariantRecord).filter_by(is_winner=True).first()
        assert winner.variant_label == "b"
        assert winner.engagement_score == 8.5


class TestReplyDraftRecord:
    def test_create_and_filter(self, db_session):
        db_session.add(ReplyDraftRecord(
            platform="twitter",
            original_comment_text="Great tutorial!",
            suggested_reply="Thanks! More coming soon.",
            category="compliment",
            priority=3,
            status="draft",
        ))
        db_session.add(ReplyDraftRecord(
            platform="twitter",
            original_comment_text="Can you cover Docker?",
            suggested_reply="Great idea! I'll add it to the list.",
            category="request",
            priority=8,
            status="draft",
        ))
        db_session.commit()

        drafts = db_session.query(ReplyDraftRecord).filter_by(status="draft").order_by(ReplyDraftRecord.priority.desc()).all()
        assert len(drafts) == 2
        assert drafts[0].priority == 8  # Higher priority first
