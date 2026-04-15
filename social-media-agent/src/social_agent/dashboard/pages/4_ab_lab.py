"""A/B Lab — Side-by-side variant comparison with engagement data."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.db.database import ContentVariantRecord, get_session, init_db

st.set_page_config(page_title="A/B Lab", page_icon="🧪", layout="wide")
inject_custom_css()

st.markdown("# A/B Lab")
st.markdown("Compare content variants side-by-side and track which performs best.")

init_db()

session = get_session()
try:
    variants = (
        session.query(ContentVariantRecord)
        .order_by(ContentVariantRecord.created_at.desc())
        .limit(20)
        .all()
    )

    if variants:
        # Group by parent content ID
        groups: dict[int | None, list] = {}
        for v in variants:
            key = v.parent_content_id or v.id
            if key not in groups:
                groups[key] = []
            groups[key].append(v)

        for group_id, group_variants in groups.items():
            st.markdown(f"### Content #{group_id}")
            cols = st.columns(len(group_variants))

            for i, (col, variant) in enumerate(zip(cols, group_variants)):
                with col:
                    try:
                        content = json.loads(variant.content_json)
                        text = content.get("text", variant.content_json)
                    except json.JSONDecodeError:
                        text = variant.content_json

                    engagement = variant.engagement_score
                    winner = "🏆 " if variant.is_winner else ""

                    st.markdown(
                        f'<div class="card">'
                        f'<p style="font-weight: 600; color: #6366F1;">'
                        f'{winner}Variant: {variant.variant_label}</p>'
                        f'<p style="color: #F8FAFC; padding: 0.5rem 0;">{text[:300]}</p>'
                        f'<p style="color: #94A3B8; font-size: 0.85rem;">'
                        f'Platform: {variant.platform} | Type: {variant.content_type}'
                        f'{"<br>Engagement: " + str(round(engagement, 1)) if engagement else ""}'
                        f'</p></div>',
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
    else:
        st.info(
            "No variants yet. Generate content with variants:\n\n"
            "```bash\nsocial-agent tweet \"AI trends\" --variants 3\n```"
        )
finally:
    session.close()
