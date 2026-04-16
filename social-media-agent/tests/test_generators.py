"""Tests for content generators with mocked AI responses."""

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


class TestTweetGenerator:
    @patch("social_agent.ai.get_openai_client")
    def test_generate_tweet(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            '```json\n{"text": "Python tip: use enumerate() instead of range(len())", "hashtags": ["python"]}\n```'
        )
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("Python tips", profile)

        assert result.text == "Python tip: use enumerate() instead of range(len())"
        assert "python" in result.hashtags
        assert len(result.text) <= 280

    @patch("social_agent.ai.get_openai_client")
    def test_generate_tweet_with_intelligence(self, mock_client_fn, profile, intelligence):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            '{"text": "Hot take: Python is NOT overrated.", "hashtags": ["python", "hottake"]}'
        )
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("Python opinions", profile, intelligence=intelligence)

        assert result.text
        assert len(result.text) <= 280

    @patch("social_agent.ai.get_openai_client")
    def test_generate_tweet_truncates_over_280(self, mock_client_fn, profile):
        mock_client = MagicMock()
        long_text = "x" * 300
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            json.dumps({"text": long_text, "hashtags": []})
        )
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("test", profile)
        assert len(result.text) <= 280

    @patch("social_agent.ai.get_openai_client")
    def test_generate_thread(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "text": "Thread: 5 Python mistakes",
            "thread_tweets": ["1. Using mutable default args", "2. Not using generators", "3. Ignoring type hints"],
            "hashtags": ["python"],
        }))
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tweet import generate_thread
        result = generate_thread("Python mistakes", profile, num_tweets=5)

        assert result.is_thread is True
        assert len(result.thread_tweets) == 3
        assert result.text.startswith("Thread:")

    @patch("social_agent.ai.get_openai_client")
    def test_handles_malformed_json(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "This is just plain text, not JSON"
        )
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet("test", profile)
        assert result.text != ""


class TestCarouselGenerator:
    @patch("social_agent.ai.get_openai_client")
    def test_generate_carousel(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "title": "5 Python Tips",
            "caption": "Save this for later!",
            "hashtags": ["python"],
            "slides": [
                {"heading": "Tip 1", "body": "Use f-strings", "image_prompt": "code"},
                {"heading": "Tip 2", "body": "Use pathlib", "image_prompt": "files"},
            ],
        }))
        mock_client_fn.return_value = mock_client

        from social_agent.generators.carousel import generate_carousel
        result = generate_carousel("Python tips", profile, num_slides=5, platform=Platform.INSTAGRAM)

        assert result.title == "5 Python Tips"
        assert len(result.slides) == 2
        assert result.platform == Platform.INSTAGRAM
        assert result.slides[0].heading == "Tip 1"


class TestTikTokGenerator:
    @patch("social_agent.ai.get_openai_client")
    def test_generate_tiktok_caption(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "caption": "POV: you just discovered Python decorators",
            "hashtags": ["python", "coding"],
            "sound_suggestion": "original audio",
            "script_notes": "Start with confused face, then explain decorators simply.",
        }))
        mock_client_fn.return_value = mock_client

        from social_agent.generators.tiktok import generate_tiktok_caption
        result = generate_tiktok_caption("Python decorators", profile)

        assert "decorators" in result.caption
        assert result.sound_suggestion == "original audio"
        assert result.script_notes is not None


class TestLongformRepurposer:
    @patch("social_agent.ai.get_openai_client")
    def test_repurpose_from_text(self, mock_client_fn, profile):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "source_summary": "A deep dive into Python decorators",
            "key_insights": ["Decorators are just functions wrapping functions"],
            "tweets": [{"text": "Decorators decoded", "hashtags": [], "angle": "hook"}],
            "threads": [],
            "carousels": [{"title": "Decorators 101", "slides": [{"heading": "What", "body": "They wrap functions"}], "caption": "", "hashtags": []}],
            "tiktoks": [{"caption": "POV: decorators", "hashtags": [], "script_notes": "Explain it", "angle": "tutorial"}],
        }))
        mock_client_fn.return_value = mock_client

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


# ── Helpers ────────────────────────────────────────────────────────────────


def _mock_openai_response(text: str):
    """Create a mock OpenAI chat completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = text
    return mock_response
