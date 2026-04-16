"""A/B content variant generation and tracking."""

from __future__ import annotations

import json

from social_agent.ai import chat, parse_json
from social_agent.db.database import ContentVariantRecord, get_session, init_db
from social_agent.models.content import ContentVariant, InfluencerProfile, Platform


VARIANT_PROMPT = """Generate {num_variants} distinct variations of this social media content.
Each variant should take a different angle, hook, or style while covering the same topic.

INFLUENCER VOICE: {voice_description}
TONE: {tone}
PLATFORM: {platform}
TOPIC: {topic}

ORIGINAL CONTENT:
{original}

Create {num_variants} variants with different approaches:
- Variant A: Different hook/opening
- Variant B: Different angle or framing
- Variant C: Different style (if 3 variants)

Return JSON array:
[
  {{
    "variant_label": "hook_a",
    "content": "<full content text>",
    "approach": "<brief description of what makes this variant different>"
  }},
  ...
]
"""


def generate_variants(
    topic: str,
    original_content: str,
    profile: InfluencerProfile,
    platform: Platform = Platform.TWITTER,
    num_variants: int = 2,
    content_type: str = "tweet",
) -> list[ContentVariant]:
    """Generate A/B variants of content with different hooks/angles."""
    raw = chat(
        system="You are a social media content strategist specializing in A/B testing.",
        user=VARIANT_PROMPT.format(
            num_variants=num_variants,
            voice_description=profile.voice.description,
            tone=", ".join(profile.voice.tone),
            platform=platform.value,
            topic=topic,
            original=original_content,
        ),
        max_tokens=3000,
    )

    parsed = parse_json(raw)
    data = parsed if isinstance(parsed, list) else parsed.get("variants", []) if parsed else []

    variants: list[ContentVariant] = []
    for item in data:
        variant = ContentVariant(
            variant_label=item.get("variant_label", ""),
            content_type=content_type,
            content_json=json.dumps({"text": item.get("content", ""), "approach": item.get("approach", "")}),
            platform=platform,
        )
        variants.append(variant)

    # Save to database
    _save_variants(variants)

    return variants


def _save_variants(variants: list[ContentVariant]) -> None:
    """Persist variants to database."""
    init_db()
    session = get_session()
    try:
        for v in variants:
            record = ContentVariantRecord(
                parent_content_id=v.parent_content_id,
                variant_label=v.variant_label,
                content_type=v.content_type,
                content_json=v.content_json,
                platform=v.platform.value,
            )
            session.add(record)
        session.commit()
    finally:
        session.close()


def record_variant_performance(variant_id: int, engagement_score: float) -> None:
    """Update a variant's engagement score after posting."""
    init_db()
    session = get_session()
    try:
        record = session.query(ContentVariantRecord).filter_by(id=variant_id).first()
        if record:
            record.engagement_score = engagement_score
        session.commit()
    finally:
        session.close()


def pick_winner(parent_content_id: int) -> ContentVariant | None:
    """Pick the best-performing variant for a given content piece."""
    init_db()
    session = get_session()
    try:
        records = (
            session.query(ContentVariantRecord)
            .filter_by(parent_content_id=parent_content_id)
            .filter(ContentVariantRecord.engagement_score.isnot(None))
            .order_by(ContentVariantRecord.engagement_score.desc())
            .all()
        )
        if not records:
            return None

        winner = records[0]
        winner.is_winner = True
        session.commit()

        return ContentVariant(
            id=winner.id,
            parent_content_id=winner.parent_content_id,
            variant_label=winner.variant_label,
            content_type=winner.content_type,
            content_json=winner.content_json,
            platform=Platform(winner.platform),
            engagement_score=winner.engagement_score,
            is_winner=True,
        )
    finally:
        session.close()
