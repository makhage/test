"""Tests for content generators with mocked Claude API responses."""

import json
from unittest.mock import MagicMock, patch

import pytest

from social_agent.models.content import (
    InfluencerProfile,
    NicheIntelligence,
    HookPattern,
    Platform,
    VoiceConfig,
    BrandConfig,
    ContentSettings,
)


@pytest.fixture
def profile():
    return InfluencerProfile(
        voice=VoiceConfig(
            description="A tech-savvy dev advocate",
            tone=["conversational", "witty"],
            avoid=["corporate jargon"],
            example_posts=["Stop using print() to debug Python."],
        ),
        brand=BrandConfig(name="TestBrand"),
        content_settings=ContentSettings(voice_score_threshold=7),
    )


@pytest.fixture
def intelligence():
    return NicheIntelligence(
        trending_topics=["AI agents", "Python 3.13"],
        winning_hooks=[HookPattern(pattern="bold claim", example="X is dead", frequency=5)],
        top_formats=["carousel", "thread"],
        audience_questions=["How do I learn Python?"],
        hot_takes=["Python is overrated"],
        authentic_phrases=["ngl this is underrated"],
    )


def _mock_claude_response(text: str):
    """Create a mock Anthropic client that returns the given text."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = text
    mock_block.type = "text"
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestTweetGenerator:
    @patch("social_agent.generators.tweet.get_settings")
    @patch("social_agent.generators.tweet.anthropic.Anthropic")
    def test_generate_tweet(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(
            '```json\n{"text": "Python tip: use enumerate() instead of range(len())", "hashtags": ["python"]}\n```'
        )

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("Python tips", profile)

        assert result.text == "Python tip: use enumerate() instead of range(len())"
        assert "python" in result.hashtags
        assert len(result.text) <= 280

    @patch("social_agent.generators.tweet.get_settings")
    @patch("social_agent.generators.tweet.anthropic.Anthropic")
    def test_generate_tweet_with_intelligence(self, mock_anthropic_cls, mock_settings, profile, intelligence):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(
            '{"text": "Hot take: Python is NOT overrated.", "hashtags": ["python", "hottake"]}'
        )

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("Python opinions", profile, intelligence=intelligence)

        assert result.text
        assert len(result.text) <= 280

    @patch("social_agent.generators.tweet.get_settings")
    @patch("social_agent.generators.tweet.anthropic.Anthropic")
    def test_generate_tweet_truncates_over_280(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        long_text = "x" * 300
        mock_anthropic_cls.return_value = _mock_claude_response(
            json.dumps({"text": long_text, "hashtags": []})
        )

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("test", profile)
        assert len(result.text) <= 280

    @patch("social_agent.generators.tweet.get_settings")
    @patch("social_agent.generators.tweet.anthropic.Anthropic")
    def test_generate_thread(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(json.dumps({
            "text": "Thread: 5 Python mistakes 🧵",
            "thread_tweets": ["1. Using mutable default args", "2. Not using generators", "3. Ignoring type hints"],
            "hashtags": ["python"],
        }))

        from social_agent.generators.tweet import generate_thread
        result = generate_thread("Python mistakes", profile, num_tweets=5)

        assert result.is_thread is True
        assert len(result.thread_tweets) == 3
        assert result.text.startswith("Thread:")

    @patch("social_agent.generators.tweet.get_settings")
    @patch("social_agent.generators.tweet.anthropic.Anthropic")
    def test_handles_malformed_json(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response("This is just plain text, not JSON")

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("test", profile)
        # Should fallback gracefully
        assert result.text != ""


class TestCarouselGenerator:
    @patch("social_agent.generators.carousel.get_settings")
    @patch("social_agent.generators.carousel.anthropic.Anthropic")
    def test_generate_carousel(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(json.dumps({
            "title": "5 Python Tips",
            "caption": "Save this for later!",
            "hashtags": ["python"],
            "slides": [
                {"heading": "Tip 1", "body": "Use f-strings", "image_prompt": "code"},
                {"heading": "Tip 2", "body": "Use pathlib", "image_prompt": "files"},
            ],
        }))

        from social_agent.generators.carousel import generate_carousel
        result = generate_carousel("Python tips", profile, num_slides=5, platform=Platform.INSTAGRAM)

        assert result.title == "5 Python Tips"
        assert len(result.slides) == 2
        assert result.platform == Platform.INSTAGRAM
        assert result.slides[0].heading == "Tip 1"


class TestTikTokGenerator:
    @patch("social_agent.generators.tiktok.get_settings")
    @patch("social_agent.generators.tiktok.anthropic.Anthropic")
    def test_generate_tiktok_caption(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(json.dumps({
            "caption": "POV: you just discovered Python decorators 🤯",
            "hashtags": ["python", "coding"],
            "sound_suggestion": "original audio",
            "script_notes": "Start with confused face, then explain decorators simply.",
        }))

        from social_agent.generators.tiktok import generate_tiktok_caption
        result = generate_tiktok_caption("Python decorators", profile)

        assert "decorators" in result.caption
        assert result.sound_suggestion == "original audio"
        assert result.script_notes is not None


class TestLongformRepurposer:
    @patch("social_agent.generators.longform_repurposer.get_settings")
    @patch("social_agent.generators.longform_repurposer.anthropic.Anthropic")
    def test_repurpose_from_text(self, mock_anthropic_cls, mock_settings, profile):
        mock_settings.return_value.anthropic_api_key = "test-key"
        mock_anthropic_cls.return_value = _mock_claude_response(json.dumps({
            "source_summary": "A deep dive into Python decorators",
            "key_insights": ["Decorators are just functions wrapping functions"],
            "tweets": [{"text": "Decorators decoded 🧵", "hashtags": [], "angle": "hook"}],
            "threads": [],
            "carousels": [{"title": "Decorators 101", "slides": [{"heading": "What", "body": "They wrap functions"}], "caption": "", "hashtags": []}],
            "tiktoks": [{"caption": "POV: decorators", "hashtags": [], "script_notes": "Explain it", "angle": "tutorial"}],
        }))

        from social_agent.generators.longform_repurposer import repurpose_longform
        result = repurpose_longform(
            source_text="Today we're going to talk about Python decorators...",
            profile=profile,
        )

        assert "error" not in result
        assert len(result["tweets"]) >= 1
        assert len(result["carousels"]) >= 1
        assert len(result["tiktoks"]) >= 1
        assert result["source_summary"]
