"""Tests for intelligence hub features — learning loop, gap analysis, series planner, etc."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_agent.db.database import (
    AnalyticsRecord,
    Base,
    RedditPostRecord,
    ScheduledPostRecord,
)
from social_agent.models.content import (
    InfluencerProfile,
    VoiceConfig,
    BrandConfig,
    ContentSettings,
)


@pytest.fixture
def profile():
    return InfluencerProfile(
        voice=VoiceConfig(
            description="A tech dev advocate",
            tone=["conversational"],
            avoid=["jargon"],
            example_posts=["Test post"],
        ),
        brand=BrandConfig(name="TestBrand"),
        content_settings=ContentSettings(voice_score_threshold=7),
    )


@pytest.fixture
def db_with_history(monkeypatch):
    """DB with posting history + analytics for learning loop tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.utcnow()

    # Scheduled posts
    for i, (ctype, platform, engagement) in enumerate([
        ("tweet", "twitter", 100),
        ("carousel", "instagram", 500),
        ("tweet", "twitter", 150),
        ("carousel", "instagram", 800),
        ("tiktok", "tiktok", 300),
    ]):
        post = ScheduledPostRecord(
            id=i + 1,
            content_type=ctype,
            content_json=json.dumps({"text": f"Test {ctype} {i}"}),
            platform=platform,
            status="published",
            created_at=now - timedelta(days=i),
        )
        session.add(post)

        analytics = AnalyticsRecord(
            post_id=str(i + 1),
            platform=platform,
            likes=engagement,
            shares=engagement // 5,
            comments=engagement // 10,
            impressions=engagement * 10,
            recorded_at=now - timedelta(days=i),
        )
        session.add(analytics)

    # Reddit posts for gap analysis
    for title, ctype in [
        ("How to use Docker with Python?", "question"),
        ("Best practices for FastAPI?", "question"),
        ("I hate JavaScript build tools", "opinion"),
        ("Python vs Rust performance comparison", "discussion"),
    ]:
        session.add(RedditPostRecord(
            subreddit="learnpython",
            title=title,
            upvotes=500,
            content_type=ctype,
        ))

    session.commit()

    monkeypatch.setattr("social_agent.analytics.learning_loop.init_db", lambda: None)
    monkeypatch.setattr("social_agent.analytics.learning_loop.get_session", lambda: session)
    monkeypatch.setattr("social_agent.research.content_gaps.init_db", lambda: None)
    monkeypatch.setattr("social_agent.research.content_gaps.get_session", lambda: session)

    yield session
    session.close()


class TestPerformanceLearningLoop:
    def test_gather_performance_data(self, db_with_history):
        from social_agent.analytics.learning_loop import gather_performance_data
        data = gather_performance_data(days=30)
        assert len(data) == 5
        # Should be sorted by engagement descending
        assert data[0]["total_engagement"] >= data[1]["total_engagement"]

    def test_gather_performance_data_has_required_fields(self, db_with_history):
        from social_agent.analytics.learning_loop import gather_performance_data
        data = gather_performance_data(days=30)
        for d in data:
            assert "content_type" in d
            assert "platform" in d
            assert "likes" in d
            assert "total_engagement" in d

    @patch("social_agent.ai._get_client")
    def test_analyze_performance_no_data(self, mock_client, monkeypatch):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        monkeypatch.setattr("social_agent.analytics.learning_loop.init_db", lambda: None)
        monkeypatch.setattr("social_agent.analytics.learning_loop.get_session", lambda: session)

        from social_agent.analytics.learning_loop import analyze_performance
        result = analyze_performance(days=30)
        assert "recommendations" in result
        session.close()

    def test_get_generation_hints_no_data(self, monkeypatch):
        # Mock empty DB
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        monkeypatch.setattr("social_agent.analytics.learning_loop.init_db", lambda: None)
        monkeypatch.setattr("social_agent.analytics.learning_loop.get_session", lambda: session)

        from social_agent.analytics.learning_loop import get_generation_hints
        hints = get_generation_hints(days=30)
        # Should return empty dict or dict with empty lists, no crash
        assert isinstance(hints, dict)
        session.close()


class TestContentGapAnalysis:
    @patch("social_agent.ai._get_client")
    def test_no_audience_data_returns_error(self, mock_client, monkeypatch):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        monkeypatch.setattr("social_agent.research.content_gaps.init_db", lambda: None)
        monkeypatch.setattr("social_agent.research.content_gaps.get_session", lambda: session)

        from social_agent.research.content_gaps import analyze_content_gaps
        result = analyze_content_gaps()
        assert "error" in result
        session.close()


class TestSeriesPlanner:
    @patch("social_agent.ai._get_client")
    def test_plan_series(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "series_title": "Python Zero to Hero",
            "series_hook": "5 parts to mastery",
            "parts": [
                {"part_number": 1, "title": "Variables", "hook": "Let's start", "key_points": ["Types"], "cliffhanger": "Next: loops", "content_brief": "Explain variables"},
                {"part_number": 2, "title": "Loops", "hook": "Back again", "key_points": ["For", "While"], "cliffhanger": "Next: functions", "content_brief": "Explain loops"},
            ],
            "posting_schedule": "every 2 days",
            "cross_platform_strategy": "Tease on Twitter, full on IG",
        })
        mock_client.models.generate_content.return_value = mock_response
        mock_client_fn.return_value = mock_client

        from social_agent.generators.series_planner import plan_series
        result = plan_series("Python basics", num_parts=5, profile=profile)

        assert result["series_title"] == "Python Zero to Hero"
        assert len(result["parts"]) == 2
        assert result["parts"][0]["part_number"] == 1


class TestEvergeenRecycler:
    def test_find_candidates_empty_db(self, monkeypatch):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        monkeypatch.setattr("social_agent.generators.evergreen_recycler.init_db", lambda: None)
        monkeypatch.setattr("social_agent.generators.evergreen_recycler.get_session", lambda: session)

        from social_agent.generators.evergreen_recycler import find_evergreen_candidates
        result = find_evergreen_candidates()
        assert result == []
        session.close()


class TestAudiencePersonas:
    @patch("social_agent.ai._get_client")
    def test_no_data_handles_gracefully(self, mock_client_fn, profile, monkeypatch):
        # Mock the AI to raise an error (simulating no auth)
        mock_client_fn.side_effect = ValueError("No Google API key")

        from social_agent.research.audience_personas import build_audience_personas
        result = build_audience_personas(profile)
        assert "error" in result
