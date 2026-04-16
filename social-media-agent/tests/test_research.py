"""Tests for research modules — Reddit scraper classification, analyzer, content gaps."""

import pytest

from social_agent.research.reddit_scraper import _classify_post


class TestRedditPostClassification:
    """Test that posts are correctly classified by type."""

    def test_question_with_how_do_i(self):
        assert _classify_post("How do I use async in Python?", "", "") == "question"

    def test_question_with_question_mark(self):
        assert _classify_post("What's the best Python IDE?", "", "") == "recommendation"

    def test_question_with_help(self):
        assert _classify_post("Help! My Docker container keeps crashing", "", "") == "question"

    def test_question_with_eli5(self):
        assert _classify_post("ELI5: How does garbage collection work?", "", "") == "question"

    def test_tutorial(self):
        assert _classify_post("I built a Python web scraper — here's the tutorial", "", "") == "tutorial"

    def test_tutorial_with_guide(self):
        assert _classify_post("Complete guide to Python decorators", "", "") == "tutorial"

    def test_opinion_hot_take(self):
        assert _classify_post("Hot take: TypeScript is a waste of time", "", "") == "opinion"

    def test_opinion_unpopular(self):
        assert _classify_post("Unpopular opinion: Python is too slow for production", "", "") == "opinion"

    def test_opinion_rant(self):
        assert _classify_post("Rant: why does everyone use React?", "", "") == "opinion"

    def test_discovery_til(self):
        assert _classify_post("TIL Python has a walrus operator", "", "") == "discovery"

    def test_discovery_did_you_know(self):
        assert _classify_post("Did you know about Python's match statement?", "", "") == "discovery"

    def test_recommendation_best(self):
        assert _classify_post("Best Python libraries for data science?", "", "") == "recommendation"

    def test_recommendation_which(self):
        assert _classify_post("Which framework should I learn — Django or FastAPI?", "", "") == "recommendation"

    def test_discussion_flair(self):
        assert _classify_post("Some general thoughts on the Python ecosystem", "", "Discussion") == "discussion"

    def test_generic_post_defaults_to_discussion(self):
        assert _classify_post("Python 3.13 released", "", "") == "discussion"

    def test_i_made_classified_as_tutorial(self):
        assert _classify_post("I made a CLI tool for managing Docker containers", "", "") == "tutorial"


class TestNicheIntelligenceModel:
    """Test the NicheIntelligence model with Reddit-enriched fields."""

    def test_audience_questions_field(self):
        from social_agent.models.content import NicheIntelligence
        intel = NicheIntelligence(
            trending_topics=["AI"],
            audience_questions=["How to learn ML?", "Best GPU for training?"],
            hot_takes=["LLMs are overrated"],
            authentic_phrases=["skill issue", "this is the way"],
        )
        assert len(intel.audience_questions) == 2
        assert len(intel.hot_takes) == 1
        assert len(intel.authentic_phrases) == 2

    def test_empty_reddit_fields_default(self):
        from social_agent.models.content import NicheIntelligence
        intel = NicheIntelligence(trending_topics=["AI"])
        assert intel.audience_questions == []
        assert intel.hot_takes == []
        assert intel.authentic_phrases == []
