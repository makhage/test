"""Tests for the knowledge base module."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_agent.db.database import Base, KnowledgeEntry


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    monkeypatch.setattr("social_agent.knowledge.init_db", lambda: None)
    monkeypatch.setattr("social_agent.knowledge.get_session", lambda: session)
    yield session
    session.close()


class TestRemember:
    def test_single_entry(self, db):
        from social_agent.knowledge import remember, recall
        remember("audience_question", "How do I learn Python?", source="r/learnpython")

        entries = recall()
        assert len(entries) == 1
        assert entries[0]["content"] == "How do I learn Python?"
        assert entries[0]["source"] == "r/learnpython"
        assert entries[0]["category"] == "audience_question"

    def test_batch_insert(self, db):
        from social_agent.knowledge import remember_many, recall
        remember_many([
            ("audience_question", "Q1", "src1", 0.9),
            ("winning_hook", "Hook A", "src2", 0.7),
            ("trend", "AI agents", "src3", 1.0),
        ])

        assert len(recall()) == 3

    def test_relevance_clamped(self, db):
        from social_agent.knowledge import remember, recall
        remember("trend", "test", relevance=5.0)  # Out of range
        entries = recall()
        assert entries[0]  # Just checking no crash

        e = db.query(KnowledgeEntry).first()
        assert 0.0 <= e.relevance <= 1.0


class TestRecall:
    def test_filter_by_category(self, db):
        from social_agent.knowledge import remember, recall
        remember("audience_question", "Q1")
        remember("winning_hook", "H1")
        remember("trend", "T1")

        qs = recall(categories=["audience_question"])
        assert len(qs) == 1
        assert qs[0]["category"] == "audience_question"

    def test_limit(self, db):
        from social_agent.knowledge import remember, recall
        for i in range(30):
            remember("trend", f"Topic {i}")
        assert len(recall(limit=5)) == 5

    def test_sorted_by_relevance(self, db):
        from social_agent.knowledge import remember, recall
        remember("trend", "Low", relevance=0.1)
        remember("trend", "High", relevance=0.9)
        remember("trend", "Mid", relevance=0.5)

        entries = recall()
        assert entries[0]["content"] == "High"
        assert entries[-1]["content"] == "Low"

    def test_empty_returns_empty_list(self, db):
        from social_agent.knowledge import recall
        assert recall() == []


class TestBuildContextBlock:
    def test_empty_returns_empty_string(self, db):
        from social_agent.knowledge import build_context_block
        assert build_context_block() == ""

    def test_groups_by_category(self, db):
        from social_agent.knowledge import remember, build_context_block
        remember("audience_question", "How to Python?")
        remember("winning_hook", "Bold claim pattern")
        remember("trend", "AI agents trending")

        block = build_context_block()
        assert "CREATOR KNOWLEDGE BASE" in block
        assert "How to Python?" in block
        assert "Bold claim pattern" in block
        assert "AI agents trending" in block
        # Check category headers
        assert "Questions" in block or "audience_question" in block

    def test_respects_max_chars(self, db):
        from social_agent.knowledge import remember, build_context_block
        for i in range(20):
            remember("trend", "X" * 500)

        block = build_context_block(max_chars=1000)
        assert len(block) <= 1100  # Some tolerance for truncation marker


class TestStats:
    def test_counts_by_category(self, db):
        from social_agent.knowledge import remember, stats
        remember("audience_question", "Q1")
        remember("audience_question", "Q2")
        remember("trend", "T1")

        s = stats()
        assert s["total"] == 3
        assert s["by_category"]["audience_question"] == 2
        assert s["by_category"]["trend"] == 1


class TestIdentityLoader:
    def test_load_identity_has_all_sections(self):
        from social_agent.identity import load_identity
        text = load_identity()
        assert "AGENT CORE" in text
        assert "CAPABILITIES" in text
        assert "CREATOR SOUL" in text

    def test_soul_from_niche_analysis(self):
        from social_agent.identity import soul_from_niche_analysis
        analysis = {
            "niche_description": "Python tutorials",
            "target_audience": "Junior devs",
            "content_style": "Educational, direct",
            "key_themes": ["Clean code", "Best practices"],
            "sub_topics": ["FastAPI", "Async"],
            "audience_pain_points": ["Debugging", "Type errors"],
        }
        soul = soul_from_niche_analysis(analysis, linktree_data={"name": "Alex"})
        assert "Alex" in soul
        assert "Python tutorials" in soul
        assert "Junior devs" in soul
        assert "Clean code" in soul
        assert "Debugging" in soul
