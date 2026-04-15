"""Parse YAML influencer profiles into Pydantic models."""

from __future__ import annotations

from pathlib import Path

import yaml

from social_agent.config import PROFILES_DIR, PROJECT_ROOT
from social_agent.models.content import (
    BrandConfig,
    CompetitorConfig,
    ContentSettings,
    InfluencerProfile,
    InstagramSettings,
    PlatformSettings,
    TikTokSettings,
    TwitterSettings,
    VoiceConfig,
)


def load_profile(path: str | Path | None = None) -> InfluencerProfile:
    """Load an influencer profile from a YAML file.

    Args:
        path: Path to the YAML file. If relative, resolved from project root.
              Defaults to profiles/default.yaml.
    """
    if path is None:
        path = PROFILES_DIR / "default.yaml"
    else:
        path = Path(path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path

    with open(path) as f:
        raw = yaml.safe_load(f)

    voice = VoiceConfig(**raw.get("voice", {}))
    brand = BrandConfig(**raw.get("brand", {}))

    platforms: dict[str, PlatformSettings] = {}
    platform_map = {
        "twitter": TwitterSettings,
        "instagram": InstagramSettings,
        "tiktok": TikTokSettings,
    }
    for name, cls in platform_map.items():
        if name in raw.get("platforms", {}):
            platforms[name] = cls(**raw["platforms"][name])

    topics = raw.get("topics", {})
    competitors = CompetitorConfig(**raw.get("competitors", {}))
    content_settings = ContentSettings(**raw.get("content_settings", {}))

    return InfluencerProfile(
        voice=voice,
        brand=brand,
        platforms=platforms,
        topics=topics,
        competitors=competitors,
        content_settings=content_settings,
    )
