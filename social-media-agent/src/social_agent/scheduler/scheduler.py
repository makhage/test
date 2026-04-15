"""APScheduler-based post scheduling with approval workflow."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from social_agent.models.content import Platform, PostStatus, ScheduledPost


class PostScheduler:
    """Manages scheduling and approval of social media posts."""

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
        )
        self._posts: dict[int, ScheduledPost] = {}
        self._next_id = 1
        self._publish_callbacks: dict[str, Callable] = {}
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    def register_publisher(self, platform: str, callback: Callable) -> None:
        self._publish_callbacks[platform] = callback

    def schedule_post(
        self,
        content_type: str,
        content_json: str,
        platform: Platform,
        scheduled_time: datetime | None = None,
    ) -> ScheduledPost:
        post = ScheduledPost(
            id=self._next_id,
            content_type=content_type,
            content_json=content_json,
            platform=platform,
            scheduled_time=scheduled_time,
            status=PostStatus.PENDING,
        )
        self._posts[self._next_id] = post
        self._next_id += 1
        return post

    def list_posts(self, status: PostStatus | None = None) -> list[ScheduledPost]:
        posts = list(self._posts.values())
        if status:
            posts = [p for p in posts if p.status == status]
        return sorted(posts, key=lambda p: p.created_at, reverse=True)

    def approve_post(self, post_id: int) -> ScheduledPost | None:
        post = self._posts.get(post_id)
        if not post or post.status != PostStatus.PENDING:
            return None

        post.status = PostStatus.APPROVED

        if post.scheduled_time and post.scheduled_time > datetime.utcnow():
            self._scheduler.add_job(
                self._execute_publish,
                "date",
                run_date=post.scheduled_time,
                args=[post_id],
                id=f"post_{post_id}",
            )
        else:
            self._execute_publish(post_id)

        return post

    def reject_post(self, post_id: int) -> ScheduledPost | None:
        post = self._posts.get(post_id)
        if not post or post.status != PostStatus.PENDING:
            return None
        post.status = PostStatus.REJECTED
        return post

    def reschedule_post(self, post_id: int, new_time: datetime) -> ScheduledPost | None:
        post = self._posts.get(post_id)
        if not post:
            return None
        post.scheduled_time = new_time
        job_id = f"post_{post_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(job_id, trigger="date", run_date=new_time)
        return post

    def _execute_publish(self, post_id: int) -> dict[str, Any]:
        post = self._posts.get(post_id)
        if not post:
            return {"success": False, "error": "Post not found"}

        callback = self._publish_callbacks.get(post.platform.value)
        if not callback:
            return {"success": False, "error": f"No publisher for {post.platform.value}"}

        content = json.loads(post.content_json)
        result = callback(content)
        if result.get("success"):
            post.status = PostStatus.PUBLISHED
            post.published_at = datetime.utcnow()
        return result
