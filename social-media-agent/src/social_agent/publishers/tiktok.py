"""TikTok publishing via Content Posting API."""

from __future__ import annotations

from typing import Any

import requests

from social_agent.config import get_settings
from social_agent.models.content import TikTokCaption
from social_agent.publishers.base import Publisher

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokPublisher(Publisher):
    def __init__(self) -> None:
        settings = get_settings()
        self._access_token = settings.tiktok_access_token
        self._open_id = settings.tiktok_open_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def validate_credentials(self) -> bool:
        try:
            url = f"{TIKTOK_API_BASE}/user/info/"
            resp = requests.get(
                url,
                headers=self._headers(),
                params={"fields": "open_id,display_name"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def upload_media(self, file_path: str) -> str | None:
        # TikTok uses a multi-step upload process
        return None

    def publish(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, TikTokCaption):
            return {"success": False, "error": "Expected TikTokCaption object"}

        try:
            caption = content.caption
            if content.hashtags:
                hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in content.hashtags)
                caption = f"{caption}\n\n{hashtag_text}"

            # TikTok Content Posting API - initialize video upload
            url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
            payload = {
                "post_info": {
                    "title": caption[:150],  # TikTok title limit
                    "privacy_level": "SELF_ONLY",  # Start as private for safety
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": "",  # Would be provided in production
                },
            }

            return {
                "success": False,
                "error": "TikTok publishing requires a video URL. "
                "Use publish_with_video_url() with a hosted video.",
                "caption_preview": caption,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_with_video_url(self, video_url: str, caption: str) -> dict[str, Any]:
        """Publish a video from a hosted URL."""
        try:
            url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
            payload = {
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "SELF_ONLY",
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_url,
                },
            }
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "post_id": data.get("data", {}).get("publish_id", ""),
                    "url": "",
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
