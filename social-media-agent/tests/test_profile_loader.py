"""Tests for profile loading."""

from pathlib import Path

from social_agent.models.content import InfluencerProfile
from social_agent.profiles.loader import load_profile


FIXTURES_DIR = Path(__file__).parent


def test_load_default_profile():
    profile = load_profile()
    assert isinstance(profile, InfluencerProfile)
    assert profile.voice.description
    assert len(profile.voice.tone) > 0
    assert profile.brand.name == "TechWithAlex"
    assert profile.brand.primary_color == "#6366F1"


def test_profile_has_platforms():
    profile = load_profile()
    assert "twitter" in profile.platforms
    assert "instagram" in profile.platforms
    assert profile.platforms["twitter"].enabled is True


def test_profile_has_topics():
    profile = load_profile()
    assert "primary" in profile.topics
    assert len(profile.topics["primary"]) > 0


def test_profile_has_competitors():
    profile = load_profile()
    assert len(profile.competitors.twitter) > 0


def test_profile_content_settings():
    profile = load_profile()
    assert profile.content_settings.voice_score_threshold == 7
    assert profile.content_settings.max_rewrite_attempts == 3


def test_profile_has_reddit_config():
    profile = load_profile()
    assert len(profile.reddit.subreddits) > 0
    assert "learnpython" in profile.reddit.subreddits
    assert profile.reddit.min_upvotes == 100
    assert profile.reddit.include_comments is True
