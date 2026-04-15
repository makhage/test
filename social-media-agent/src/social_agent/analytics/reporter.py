"""Generate performance reports and insights."""

from __future__ import annotations

from datetime import datetime, timedelta

from social_agent.analytics.tracker import get_analytics_history
from social_agent.db.database import AnalyticsRecord, get_session, init_db


def generate_report(days: int = 7) -> dict:
    """Generate a performance report for the last N days."""
    records = get_analytics_history(days=days)

    if not records:
        return {
            "period": f"Last {days} days",
            "total_posts": 0,
            "summary": "No analytics data available.",
        }

    total_likes = sum(r["likes"] for r in records)
    total_shares = sum(r["shares"] for r in records)
    total_comments = sum(r["comments"] for r in records)
    total_impressions = sum(r["impressions"] for r in records)
    total_reach = sum(r["reach"] for r in records)

    avg_likes = total_likes / len(records)
    avg_shares = total_shares / len(records)
    avg_comments = total_comments / len(records)

    # Platform breakdown
    platform_stats: dict[str, dict] = {}
    for r in records:
        plat = r["platform"]
        if plat not in platform_stats:
            platform_stats[plat] = {"count": 0, "likes": 0, "shares": 0, "comments": 0}
        platform_stats[plat]["count"] += 1
        platform_stats[plat]["likes"] += r["likes"]
        platform_stats[plat]["shares"] += r["shares"]
        platform_stats[plat]["comments"] += r["comments"]

    # Top posts
    top_posts = sorted(records, key=lambda r: r["likes"] + r["shares"] + r["comments"], reverse=True)[:5]

    return {
        "period": f"Last {days} days",
        "total_posts": len(records),
        "total_engagement": {
            "likes": total_likes,
            "shares": total_shares,
            "comments": total_comments,
            "impressions": total_impressions,
            "reach": total_reach,
        },
        "averages": {
            "avg_likes": round(avg_likes, 1),
            "avg_shares": round(avg_shares, 1),
            "avg_comments": round(avg_comments, 1),
        },
        "platform_breakdown": platform_stats,
        "top_posts": top_posts,
    }


def get_best_posting_times(days: int = 30) -> dict[str, list[str]]:
    """Analyze which posting times get the best engagement."""
    records = get_analytics_history(days=days)

    if not records:
        return {}

    # Group by hour and find best engagement
    hour_engagement: dict[str, dict[int, list[int]]] = {}
    for r in records:
        plat = r["platform"]
        if plat not in hour_engagement:
            hour_engagement[plat] = {}
        recorded_at = datetime.fromisoformat(r["recorded_at"])
        hour = recorded_at.hour
        engagement = r["likes"] + r["shares"] + r["comments"]
        if hour not in hour_engagement[plat]:
            hour_engagement[plat][hour] = []
        hour_engagement[plat][hour].append(engagement)

    best_times: dict[str, list[str]] = {}
    for plat, hours in hour_engagement.items():
        avg_by_hour = {h: sum(v) / len(v) for h, v in hours.items()}
        sorted_hours = sorted(avg_by_hour.items(), key=lambda x: x[1], reverse=True)
        best_times[plat] = [f"{h:02d}:00" for h, _ in sorted_hours[:3]]

    return best_times
