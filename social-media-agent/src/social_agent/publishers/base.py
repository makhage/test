"""Abstract publisher interface for all platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Publisher(ABC):
    """Base class for platform-specific publishers."""

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Check if API credentials are valid and have required permissions."""
        ...

    @abstractmethod
    def publish(self, content: Any) -> dict[str, Any]:
        """Publish content to the platform.

        Returns:
            Dict with at least: {"success": bool, "post_id": str, "url": str}
        """
        ...

    @abstractmethod
    def upload_media(self, file_path: str) -> str | None:
        """Upload a media file and return the media ID."""
        ...
