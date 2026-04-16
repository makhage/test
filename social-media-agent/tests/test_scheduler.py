"""Tests for the scheduling and approval workflow."""

import json
from datetime import datetime, timedelta

import pytest

from social_agent.models.content import Platform, PostStatus
from social_agent.scheduler.scheduler import PostScheduler


@pytest.fixture
def scheduler():
    s = PostScheduler()
    yield s
    s.stop()


class TestPostScheduler:
    def test_schedule_post_returns_pending(self, scheduler):
        post = scheduler.schedule_post(
            content_type="tweet",
            content_json='{"text": "hello"}',
            platform=Platform.TWITTER,
        )
        assert post.status == PostStatus.PENDING
        assert post.id == 1

    def test_schedule_multiple_posts_increments_id(self, scheduler):
        p1 = scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        p2 = scheduler.schedule_post("carousel", "{}", Platform.INSTAGRAM)
        assert p1.id == 1
        assert p2.id == 2

    def test_list_posts_returns_all(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        scheduler.schedule_post("carousel", "{}", Platform.INSTAGRAM)
        assert len(scheduler.list_posts()) == 2

    def test_list_posts_filters_by_status(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        scheduler.reject_post(1)

        pending = scheduler.list_posts(status=PostStatus.PENDING)
        assert len(pending) == 1

        rejected = scheduler.list_posts(status=PostStatus.REJECTED)
        assert len(rejected) == 1

    def test_approve_post_changes_status(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        result = scheduler.approve_post(1)
        assert result is not None
        assert result.status == PostStatus.APPROVED

    def test_approve_nonexistent_returns_none(self, scheduler):
        assert scheduler.approve_post(999) is None

    def test_approve_already_rejected_returns_none(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        scheduler.reject_post(1)
        assert scheduler.approve_post(1) is None

    def test_reject_post(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        result = scheduler.reject_post(1)
        assert result.status == PostStatus.REJECTED

    def test_reschedule_post(self, scheduler):
        scheduler.schedule_post("tweet", "{}", Platform.TWITTER)
        new_time = datetime.utcnow() + timedelta(hours=2)
        result = scheduler.reschedule_post(1, new_time)
        assert result is not None
        assert result.scheduled_time == new_time

    def test_publish_callback_called_on_approve(self, scheduler):
        published = []

        def fake_publisher(content):
            published.append(content)
            return {"success": True, "post_id": "123"}

        scheduler.register_publisher("twitter", fake_publisher)
        scheduler.schedule_post("tweet", '{"text": "hello"}', Platform.TWITTER)
        scheduler.approve_post(1)

        assert len(published) == 1
        assert published[0] == {"text": "hello"}

    def test_published_status_on_successful_publish(self, scheduler):
        def fake_publisher(content):
            return {"success": True, "post_id": "123"}

        scheduler.register_publisher("twitter", fake_publisher)
        scheduler.schedule_post("tweet", '{"text": "hello"}', Platform.TWITTER)
        scheduler.approve_post(1)

        post = scheduler.list_posts()[0]
        assert post.status == PostStatus.PUBLISHED
        assert post.published_at is not None

    def test_no_publisher_returns_error(self, scheduler):
        scheduler.schedule_post("tweet", '{"text": "hello"}', Platform.TWITTER)
        scheduler.approve_post(1)  # No publisher registered
        # Post should still be approved since _execute_publish returns error but doesn't change status back
        post = scheduler.list_posts()[0]
        assert post.status == PostStatus.APPROVED

    def test_future_scheduled_post_not_published_immediately(self, scheduler):
        published = []

        def fake_publisher(content):
            published.append(content)
            return {"success": True, "post_id": "123"}

        scheduler.register_publisher("twitter", fake_publisher)
        scheduler.start()

        future = datetime.utcnow() + timedelta(hours=24)
        scheduler.schedule_post("tweet", '{"text": "future"}', Platform.TWITTER, scheduled_time=future)
        scheduler.approve_post(1)

        # Should NOT have been published yet (scheduled for 24h from now)
        assert len(published) == 0
