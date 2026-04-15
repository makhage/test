"""Tests for Pydantic content models."""

import pytest
from pydantic import ValidationError

from social_agent.models.content import (
    Carousel,
    CarouselSlide,
    ContentBrief,
    NicheIntelligence,
    Platform,
    PostStatus,
    ScheduledPost,
    TikTokCaption,
    Tweet,
    ViralPost,
    VoiceScore,
)


def test_tweet_respects_max_length():
    tweet = Tweet(text="Hello world")
    assert len(tweet.text) <= 280


def test_tweet_rejects_over_280():
    with pytest.raises(ValidationError):
        Tweet(text="x" * 281)


def test_carousel_slide():
    slide = CarouselSlide(heading="Title", body="Some content here")
    assert slide.heading == "Title"
    assert slide.image_prompt is None


def test_carousel():
    slides = [
        CarouselSlide(heading="Intro", body="Welcome"),
        CarouselSlide(heading="Tip 1", body="First tip"),
        CarouselSlide(heading="CTA", body="Follow me"),
    ]
    carousel = Carousel(title="Test Carousel", slides=slides)
    assert len(carousel.slides) == 3
    assert carousel.platform == Platform.INSTAGRAM


def test_tiktok_caption():
    caption = TikTokCaption(
        caption="Check this out!",
        hashtags=["#coding", "#python"],
        sound_suggestion="trending audio",
    )
    assert len(caption.hashtags) == 2


def test_content_brief():
    brief = ContentBrief(
        topic="AI trends",
        platforms=[Platform.TWITTER, Platform.INSTAGRAM],
        num_variants=3,
    )
    assert len(brief.platforms) == 2
    assert brief.num_variants == 3


def test_scheduled_post_default_status():
    post = ScheduledPost(
        content_type="tweet",
        content_json='{"text": "hello"}',
        platform=Platform.TWITTER,
    )
    assert post.status == PostStatus.DRAFT


def test_viral_post():
    post = ViralPost(
        platform=Platform.TWITTER,
        text="This went viral",
        likes=50000,
        shares=10000,
    )
    assert post.likes == 50000


def test_niche_intelligence():
    intel = NicheIntelligence(
        trending_topics=["AI agents", "RAG patterns"],
        top_formats=["thread", "carousel"],
    )
    assert len(intel.trending_topics) == 2


def test_voice_score_bounds():
    score = VoiceScore(score=8, feedback="Great match", passed=True)
    assert score.score == 8

    with pytest.raises(ValidationError):
        VoiceScore(score=0, feedback="Too low")

    with pytest.raises(ValidationError):
        VoiceScore(score=11, feedback="Too high")
