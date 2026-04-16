"""A/B Lab — Generate variants, compare side-by-side, track winners."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings
from social_agent.db.database import ContentVariantRecord, get_session, init_db
from social_agent.models.content import Platform
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="A/B Lab", page_icon="🧪", layout="wide")
inject_custom_css()
init_db()

st.markdown("# A/B Lab")
st.markdown("Generate content variants, compare side-by-side, and track what performs best.")

profile = load_profile()
settings = get_settings()

# --- Generate Variants ---
st.markdown("### Generate Variants")

col1, col2, col3 = st.columns(3)
with col1:
    ab_topic = st.text_input("Topic", placeholder="e.g., Why Python beats Java", key="ab_topic")
with col2:
    ab_platform = st.selectbox("Platform", ["twitter", "instagram", "tiktok"], key="ab_plat")
with col3:
    ab_count = st.slider("Number of Variants", 2, 4, 3)

ab_original = st.text_area(
    "Original content (optional — leave blank to generate from scratch)",
    placeholder="Paste existing content here to generate variants of it...",
    height=80,
)

if st.button(
    "Generate Variants",
    type="primary",
    use_container_width=True,
    disabled=not bool(settings.google_api_key),
):
    if not ab_topic:
        st.warning("Enter a topic first.")
    else:
        with st.spinner(f"Generating {ab_count} variants..."):
            try:
                # Generate original if not provided
                original = ab_original
                if not original:
                    from social_agent.generators.tweet import generate_tweet
                    from social_agent.research.analyzer import get_latest_intelligence
                    intel = get_latest_intelligence()
                    result = generate_tweet(ab_topic, profile, "engaging", intel)
                    original = result.text

                from social_agent.ab_testing.variants import generate_variants
                variants = generate_variants(
                    topic=ab_topic,
                    original_content=original,
                    profile=profile,
                    platform=Platform(ab_platform),
                    num_variants=ab_count,
                )
                st.success(f"Generated {len(variants)} variants!")
                st.rerun()
            except Exception as e:
                st.error(f"Generation failed: {e}")

if not settings.google_api_key:
    st.info("Set `ANTHROPIC_API_KEY` in `.env` to enable variant generation.")

st.markdown("---")

# --- Display Existing Variants ---
st.markdown("### Variant Comparison")

session = get_session()
try:
    variants = (
        session.query(ContentVariantRecord)
        .order_by(ContentVariantRecord.created_at.desc())
        .limit(30)
        .all()
    )

    if variants:
        # Group by parent content ID or by creation batch (same created_at minute)
        groups: dict[str, list] = {}
        for v in variants:
            # Group by parent_content_id, or by creation timestamp (rounded to minute)
            if v.parent_content_id:
                key = f"content_{v.parent_content_id}"
            else:
                key = v.created_at.strftime("%Y%m%d_%H%M") if v.created_at else f"id_{v.id}"
            if key not in groups:
                groups[key] = []
            groups[key].append(v)

        for group_idx, (group_id, group_variants) in enumerate(groups.items()):
            st.markdown(f"#### Test #{group_idx + 1}")

            cols = st.columns(len(group_variants))
            for i, (col, variant) in enumerate(zip(cols, group_variants)):
                with col:
                    try:
                        content = json.loads(variant.content_json)
                        text = content.get("text", "")
                        approach = content.get("approach", "")
                    except (json.JSONDecodeError, TypeError):
                        text = variant.content_json or ""
                        approach = ""

                    engagement = variant.engagement_score
                    is_winner = variant.is_winner

                    # Card styling
                    border_style = "border: 2px solid #10B981;" if is_winner else ""
                    winner_badge = (
                        '<span style="background: #10B98120; color: #10B981; padding: 0.2rem 0.5rem; '
                        'border-radius: 4px; font-size: 0.75rem; font-weight: 600;">WINNER</span>'
                        if is_winner else ""
                    )

                    # Engagement bar
                    eng_html = ""
                    if engagement is not None:
                        bar_width = min(engagement * 10, 100)
                        bar_color = "#10B981" if engagement > 7 else "#F59E0B" if engagement > 4 else "#EF4444"
                        eng_html = (
                            f'<div style="margin-top: 0.5rem;">'
                            f'<p style="color: #94A3B8; font-size: 0.75rem; margin: 0;">Engagement: {engagement:.1f}</p>'
                            f'<div style="background: #0F172A; border-radius: 4px; height: 6px; margin-top: 0.25rem;">'
                            f'<div style="background: {bar_color}; border-radius: 4px; height: 6px; width: {bar_width}%;"></div>'
                            f'</div></div>'
                        )

                    st.markdown(
                        f'<div class="card" style="{border_style}">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                        f'<span style="font-weight: 600; color: #6366F1;">{variant.variant_label or f"Variant {i + 1}"}</span>'
                        f'{winner_badge}'
                        f'</div>'
                        f'{"<p style=&quot;color: #94A3B8; font-size: 0.8rem; font-style: italic;&quot;>" + approach + "</p>" if approach else ""}'
                        f'<p style="color: #F8FAFC; padding: 0.5rem 0; line-height: 1.5;">{text[:400]}</p>'
                        f'<p style="color: #475569; font-size: 0.75rem;">{variant.platform} / {variant.content_type}</p>'
                        f'{eng_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Score input
                    if engagement is None:
                        score = st.number_input(
                            "Engagement score",
                            min_value=0.0,
                            max_value=10.0,
                            step=0.5,
                            key=f"score_{variant.id}",
                        )
                        if st.button("Record", key=f"record_{variant.id}", use_container_width=True):
                            variant.engagement_score = score
                            session.commit()
                            st.rerun()

            st.markdown("---")
    else:
        st.markdown(
            '<div class="card" style="text-align: center; padding: 3rem;">'
            '<p style="font-size: 1.2rem; color: #94A3B8;">No variants yet</p>'
            '<p style="color: #475569;">Use the form above to generate your first A/B test.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
finally:
    session.close()
