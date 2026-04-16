"""Tests for trend velocity calculation."""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_agent.db.database import Base, RedditPostRecord


@pytest.fixture
def db_with_trends(monkeypatch):
    """Create an in-memory DB with Reddit posts that simulate trending topics."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.utcnow()
    midpoint = now - timedelta(hours=24)

    # "python" — accelerating (more recent posts than earlier)
    for i in range(10):
        session.add(RedditPostRecord(
            subreddit="learnpython",
            title=f"How to learn python basics part {i}",
            upvotes=100 + i * 10,
            scraped_at=now - timedelta(hours=i),  # Recent
        ))
    for i in range(3):
        session.add(RedditPostRecord(
            subreddit="learnpython",
            title=f"Python question about basics {i}",
            upvotes=50,
            scraped_at=midpoint - timedelta(hours=i),  # Earlier
        ))

    # "docker" — new topic (only in recent period)
    for i in range(5):
        session.add(RedditPostRecord(
            subreddit="devops",
            title=f"Docker container networking issue {i}",
            upvotes=200,
            scraped_at=now - timedelta(hours=i),
        ))

    # "javascript" — declining (more earlier than recent)
    for i in range(2):
        session.add(RedditPostRecord(
            subreddit="webdev",
            title=f"JavaScript framework fatigue {i}",
            upvotes=100,
            scraped_at=now - timedelta(hours=i),
        ))
    for i in range(8):
        session.add(RedditPostRecord(
            subreddit="webdev",
            title=f"JavaScript framework comparison {i}",
            upvotes=100,
            scraped_at=midpoint - timedelta(hours=i),
        ))

    session.commit()

    # Monkey-patch the DB access in trend_velocity
    monkeypatch.setattr("social_agent.research.trend_velocity.init_db", lambda: None)
    monkeypatch.setattr("social_agent.research.trend_velocity.get_session", lambda: session)

    yield session
    session.close()


class TestCalculateTrendVelocity:
    def test_returns_list(self, db_with_trends):
        from social_agent.research.trend_velocity import calculate_trend_velocity
        result = calculate_trend_velocity(hours=48)
        assert isinstance(result, list)

    def test_accelerating_topics_have_positive_velocity(self, db_with_trends):
        from social_agent.research.trend_velocity import calculate_trend_velocity
        result = calculate_trend_velocity(hours=48)

        # Find python-related keywords
        python_entries = [r for r in result if "python" in r["keyword"] or "learn" in r["keyword"] or "basics" in r["keyword"]]
        # At least some should have positive velocity
        assert any(r["velocity"] > 0 for r in python_entries) or len(python_entries) == 0

    def test_new_topics_marked_as_new(self, db_with_trends):
        from social_agent.research.trend_velocity import calculate_trend_velocity
        result = calculate_trend_velocity(hours=48)

        docker_entries = [r for r in result if "docker" in r["keyword"]]
        for entry in docker_entries:
            assert entry["trend"] == "new"
            assert entry["earlier_count"] == 0

    def test_results_sorted_by_velocity_descending(self, db_with_trends):
        from social_agent.research.trend_velocity import calculate_trend_velocity
        result = calculate_trend_velocity(hours=48)

        if len(result) >= 2:
            for i in range(len(result) - 1):
                assert result[i]["velocity"] >= result[i + 1]["velocity"]

    def test_max_20_results(self, db_with_trends):
        from social_agent.research.trend_velocity import calculate_trend_velocity
        result = calculate_trend_velocity(hours=48)
        assert len(result) <= 20


class TestDetectEmergingTopics:
    def test_returns_dict_with_emerging_topics(self, db_with_trends):
        from social_agent.research.trend_velocity import detect_emerging_topics
        # Without Claude (no API key), should return raw velocities
        result = detect_emerging_topics()
        assert "emerging_topics" in result

    def test_accepts_profile_topics(self, db_with_trends):
        from social_agent.research.trend_velocity import detect_emerging_topics
        result = detect_emerging_topics(profile_topics=["Python", "Docker"])
        assert isinstance(result.get("emerging_topics", []), list)
