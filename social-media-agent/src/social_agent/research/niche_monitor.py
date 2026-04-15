"""Continuous niche monitoring and trend detection."""

from __future__ import annotations

from datetime import datetime, timedelta

from social_agent.models.content import InfluencerProfile, NicheIntelligence
from social_agent.research.analyzer import analyze_viral_content, get_latest_intelligence
from social_agent.research.scraper import scan_niche


def run_niche_scan(
    profile: InfluencerProfile,
    min_likes: int = 500,
    force_analysis: bool = False,
) -> NicheIntelligence | None:
    """Run a full niche scan: scrape + analyze.

    Skips analysis if recent intelligence exists (within last 24 hours)
    unless force_analysis is True.
    """
    # Scrape fresh content
    scan_niche(profile, min_likes=min_likes)

    # Check if analysis is needed
    if not force_analysis:
        latest = get_latest_intelligence()
        if latest and latest.generated_at > datetime.utcnow() - timedelta(hours=24):
            return latest

    # Analyze
    return analyze_viral_content()


def detect_emerging_topics(
    profile: InfluencerProfile,
) -> list[str]:
    """Detect topics that are trending up but haven't peaked yet.

    Compares current intelligence against the influencer's topic list
    to find overlap — topics the influencer can speak to that are trending.
    """
    intel = get_latest_intelligence()
    if not intel:
        return []

    influencer_topics = set()
    for topic_list in profile.topics.values():
        for topic in topic_list:
            influencer_topics.add(topic.lower())

    # Find trending topics that match influencer expertise
    emerging = []
    for trend in intel.trending_topics:
        trend_lower = trend.lower()
        for expertise in influencer_topics:
            if expertise in trend_lower or trend_lower in expertise:
                emerging.append(trend)
                break

    return emerging
