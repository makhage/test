"""Twitter/X publishing via Tweepy."""

from __future__ import annotations

from typing import Any

import tweepy

from social_agent.config import get_settings
from social_agent.models.content import Tweet
from social_agent.publishers.base import Publisher


class TwitterPublisher(Publisher):
    def __init__(self) -> None:
        settings = get_settings()
        # v1.1 API for media uploads
        auth = tweepy.OAuth1UserHandler(
            settings.twitter_api_key,
            settings.twitter_api_secret,
            settings.twitter_access_token,
            settings.twitter_access_token_secret,
        )
        self._api_v1 = tweepy.API(auth)

        # v2 API for creating tweets
        self._client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            consumer_key=settings.twitter_api_key,
            consumer_secret=settings.twitter_api_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret,
        )

    def validate_credentials(self) -> bool:
        try:
            self._client.get_me()
            return True
        except Exception:
            return False

    def upload_media(self, file_path: str) -> str | None:
        try:
            media = self._api_v1.media_upload(filename=file_path)
            return str(media.media_id)
        except Exception:
            return None

    def publish(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, Tweet):
            return {"success": False, "error": "Expected Tweet object"}

        try:
            media_ids = []
            for path in content.media_paths:
                mid = self.upload_media(path)
                if mid:
                    media_ids.append(mid)

            if content.is_thread:
                return self._publish_thread(content, media_ids)

            text = content.text
            if content.hashtags:
                hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in content.hashtags)
                if len(text) + len(hashtag_text) + 1 <= 280:
                    text = f"{text}\n{hashtag_text}"

            kwargs: dict[str, Any] = {"text": text}
            if media_ids:
                kwargs["media_ids"] = media_ids

            response = self._client.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            return {
                "success": True,
                "post_id": tweet_id,
                "url": f"https://x.com/i/status/{tweet_id}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _publish_thread(self, content: Tweet, media_ids: list[str]) -> dict[str, Any]:
        all_tweets = [content.text] + content.thread_tweets
        tweet_ids: list[str] = []
        reply_to: str | None = None

        for i, text in enumerate(all_tweets):
            # Add hashtags to last tweet
            if i == len(all_tweets) - 1 and content.hashtags:
                hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in content.hashtags)
                if len(text) + len(hashtag_text) + 1 <= 280:
                    text = f"{text}\n{hashtag_text}"

            kwargs: dict[str, Any] = {"text": text}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to
            if i == 0 and media_ids:
                kwargs["media_ids"] = media_ids

            response = self._client.create_tweet(**kwargs)
            tid = response.data["id"]
            tweet_ids.append(tid)
            reply_to = tid

        return {
            "success": True,
            "post_id": tweet_ids[0],
            "url": f"https://x.com/i/status/{tweet_ids[0]}",
            "thread_ids": tweet_ids,
        }
