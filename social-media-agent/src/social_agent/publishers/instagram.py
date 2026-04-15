"""Instagram publishing via Graph API."""

from __future__ import annotations

from typing import Any

import requests

from social_agent.config import get_settings
from social_agent.models.content import Carousel
from social_agent.publishers.base import Publisher

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class InstagramPublisher(Publisher):
    def __init__(self) -> None:
        settings = get_settings()
        self._access_token = settings.instagram_access_token
        self._account_id = settings.instagram_business_account_id

    def validate_credentials(self) -> bool:
        try:
            url = f"{GRAPH_API_BASE}/{self._account_id}"
            resp = requests.get(
                url,
                params={"access_token": self._access_token, "fields": "id,username"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def upload_media(self, file_path: str) -> str | None:
        # Instagram Graph API requires media to be hosted at a public URL
        # In production, you'd upload to a CDN first
        return None

    def _create_container(self, image_url: str, caption: str = "") -> str | None:
        """Create a media container for a single image."""
        url = f"{GRAPH_API_BASE}/{self._account_id}/media"
        resp = requests.post(
            url,
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": self._access_token,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("id")
        return None

    def _create_carousel_container(
        self, children_ids: list[str], caption: str
    ) -> str | None:
        """Create a carousel container from child media IDs."""
        url = f"{GRAPH_API_BASE}/{self._account_id}/media"
        resp = requests.post(
            url,
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
                "access_token": self._access_token,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("id")
        return None

    def _publish_container(self, container_id: str) -> dict[str, Any]:
        """Publish a prepared media container."""
        url = f"{GRAPH_API_BASE}/{self._account_id}/media_publish"
        resp = requests.post(
            url,
            data={
                "creation_id": container_id,
                "access_token": self._access_token,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            post_id = resp.json().get("id", "")
            return {
                "success": True,
                "post_id": post_id,
                "url": f"https://www.instagram.com/p/{post_id}/",
            }
        return {"success": False, "error": resp.text}

    def publish(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, Carousel):
            return {"success": False, "error": "Expected Carousel object"}

        try:
            caption = content.caption
            if content.hashtags:
                hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in content.hashtags)
                caption = f"{caption}\n\n{hashtag_text}"

            # Note: In production, carousel images would need to be uploaded
            # to a publicly accessible URL first (e.g., S3/CDN)
            return {
                "success": False,
                "error": "Instagram publishing requires images hosted at public URLs. "
                "Upload carousel images to a CDN first, then use publish_from_urls().",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_from_urls(
        self, image_urls: list[str], caption: str, hashtags: list[str] | None = None
    ) -> dict[str, Any]:
        """Publish a carousel from publicly hosted image URLs."""
        try:
            if hashtags:
                hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
                caption = f"{caption}\n\n{hashtag_text}"

            # Create child containers
            children_ids: list[str] = []
            for url in image_urls:
                cid = self._create_container(url)
                if cid:
                    children_ids.append(cid)

            if not children_ids:
                return {"success": False, "error": "Failed to create media containers"}

            # Create carousel container
            carousel_id = self._create_carousel_container(children_ids, caption)
            if not carousel_id:
                return {"success": False, "error": "Failed to create carousel container"}

            return self._publish_container(carousel_id)
        except Exception as e:
            return {"success": False, "error": str(e)}
