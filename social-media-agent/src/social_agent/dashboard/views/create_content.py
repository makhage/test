"""Content Studio — auto-suggests ideas from research, one-click generate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings
from social_agent.db.database import ScheduledPostRecord, init_db, get_session
from social_agent.models.content import Platform
from social_agent.profiles.loader import load_profile


FORMAT_LABELS = {
    "tweet": "Tweet",
    "thread": "Thread",
    "carousel": "Carousel",
    "tiktok": "TikTok",
}


def _save_draft(content_type: str, content_dict: dict, platform: str) -> int:
    """Save generated content to the review queue."""
    init_db()
    session = get_session()
    try:
        record = ScheduledPostRecord(
            content_type=content_type,
            content_json=json.dumps(content_dict),
            platform=platform,
            status="pending",
        )
        session.add(record)
        session.commit()
        return record.id
    finally:
        session.close()


def _generate_and_show(format_type: str, topic: str, style: str, profile, intel) -> None:
    """Generate content of the right format and display it."""
    from social_agent.research.analyzer import get_latest_intelligence
    intel = intel or get_latest_intelligence()

    if format_type == "tweet":
        from social_agent.generators.tweet import generate_tweet
        result = generate_tweet(topic, profile, style, intel)
        st.markdown(
            f'<div class="card"><p style="font-size:1.05rem;line-height:1.5;">{result.text}</p>'
            f'{"<p style=&quot;color:#6366F1;&quot;>#" + " #".join(result.hashtags) + "</p>" if result.hashtags else ""}'
            f'<p style="color:#64748B;font-size:0.75rem;">{len(result.text)}/280</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Save to Review Queue", key=f"save_tweet_{topic[:20]}"):
            _save_draft("tweet", result.model_dump(), "twitter")
            st.success("Saved to Review Queue")

    elif format_type == "thread":
        from social_agent.generators.tweet import generate_thread
        result = generate_thread(topic, profile, 5, intel)
        st.markdown(f'<div class="card"><p style="font-weight:600;color:#6366F1;">Hook</p>'
                    f'<p style="font-size:1.05rem;">{result.text}</p></div>', unsafe_allow_html=True)
        for j, t in enumerate(result.thread_tweets, 1):
            st.markdown(
                f'<div class="card" style="margin-left:1.5rem;border-left:3px solid #6366F140;">'
                f'<p style="color:#94A3B8;font-size:0.8rem;">Tweet {j + 1}</p><p>{t}</p></div>',
                unsafe_allow_html=True,
            )
        if st.button("Save to Review Queue", key=f"save_thread_{topic[:20]}"):
            _save_draft("thread", result.model_dump(), "twitter")
            st.success("Saved to Review Queue")

    elif format_type == "carousel":
        from social_agent.generators.carousel import generate_carousel
        result = generate_carousel(topic, profile, 7, Platform.INSTAGRAM, intel)
        st.markdown(f'<p style="font-weight:600;">{result.title}</p>')
        for i, slide in enumerate(result.slides, 1):
            st.markdown(
                f'<div class="card"><p style="color:#6366F1;font-size:0.8rem;">Slide {i}</p>'
                f'<p style="font-weight:700;">{slide.heading}</p>'
                f'<p>{slide.body}</p></div>',
                unsafe_allow_html=True,
            )
        if result.caption:
            st.caption(result.caption)
        if st.button("Save to Review Queue", key=f"save_car_{topic[:20]}"):
            _save_draft("carousel", result.model_dump(), "instagram")
            st.success("Saved to Review Queue")

    elif format_type == "tiktok":
        from social_agent.generators.tiktok import generate_tiktok_caption
        result = generate_tiktok_caption(topic, profile, style)
        st.markdown(f'<div class="card"><p>{result.caption}</p>'
                    f'{"<p style=&quot;color:#6366F1;&quot;>#" + " #".join(result.hashtags) + "</p>" if result.hashtags else ""}'
                    f'</div>', unsafe_allow_html=True)
        if result.sound_suggestion:
            st.caption(f"Suggested sound: {result.sound_suggestion}")
        if result.script_notes:
            st.markdown(f"**Script notes:** {result.script_notes}")
        if st.button("Save to Review Queue", key=f"save_tt_{topic[:20]}"):
            _save_draft("tiktok", result.model_dump(), "tiktok")
            st.success("Saved to Review Queue")


def render() -> None:
    init_db()

    st.markdown("# Content Studio")

    profile = load_profile()
    settings = get_settings()

    if not settings.google_api_key:
        st.warning("Add your Gemini API key in Settings to enable content generation.")
        return

    # ── Auto-suggestions ────────────────────────────────────────────────────
    st.markdown(
        "### Suggested for you"
    )
    st.caption(
        "Ideas the agent generated from your knowledge base — audience questions, trends, "
        "content gaps, and hot takes. Click Generate on any idea."
    )

    # Cache suggestions in session so they don't regenerate on every rerun
    if st.button("↻ Refresh suggestions", use_container_width=False):
        st.session_state.pop("content_ideas", None)

    if "content_ideas" not in st.session_state:
        with st.spinner("Thinking about what you should post..."):
            from social_agent.generators.idea_engine import suggest_content_ideas
            st.session_state["content_ideas"] = suggest_content_ideas(count=6)

    ideas = st.session_state.get("content_ideas", [])

    if not ideas:
        st.info(
            "**No research data yet.** Run the Niche Scanner and Reddit Intel first so the "
            "agent can suggest ideas based on your audience. Until then you can still create "
            "content manually below."
        )
    else:
        for i, idea in enumerate(ideas):
            format_type = idea.get("format", "tweet").lower()
            with st.container():
                col_info, col_gen = st.columns([3, 1])
                with col_info:
                    st.markdown(
                        f'<div class="card" style="margin:0;">'
                        f'<div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">'
                        f'<span style="background:#6366F120;color:#6366F1;padding:0.15rem 0.6rem;'
                        f'border-radius:999px;font-size:0.7rem;text-transform:uppercase;font-weight:600;">'
                        f'{FORMAT_LABELS.get(format_type, format_type)}</span>'
                        f'<span style="color:#64748B;font-size:0.75rem;">via {idea.get("source", "")[:80]}</span>'
                        f'</div>'
                        f'<p style="font-weight:600;margin:0 0 0.25rem 0;">{idea.get("topic", "")}</p>'
                        f'<p style="color:#94A3B8;margin:0;font-size:0.85rem;">{idea.get("angle", "")}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_gen:
                    gen_key = f"gen_idea_{i}"
                    if st.button("Generate", key=gen_key, use_container_width=True, type="primary"):
                        st.session_state[f"generating_{i}"] = True

            # If clicked, generate below this card
            if st.session_state.get(f"generating_{i}"):
                with st.spinner("Generating..."):
                    _generate_and_show(
                        format_type=format_type,
                        topic=idea.get("topic", ""),
                        style=idea.get("style", "engaging"),
                        profile=profile,
                        intel=None,
                    )

    st.markdown("---")

    # ── Manual mode (collapsed) ─────────────────────────────────────────────
    with st.expander("Create from your own topic"):
        content_type = st.selectbox(
            "Format",
            ["Tweet", "Thread", "Carousel", "TikTok"],
            key="manual_format",
        )
        topic = st.text_input(
            "Topic",
            placeholder="e.g. 5 Python tips every developer should know",
            key="manual_topic",
        )
        style = st.selectbox(
            "Style",
            ["engaging", "educational", "controversial", "storytelling"],
            key="manual_style",
        )

        if st.button("Generate from topic", type="primary", disabled=not topic):
            with st.spinner("Generating..."):
                format_map = {
                    "Tweet": "tweet",
                    "Thread": "thread",
                    "Carousel": "carousel",
                    "TikTok": "tiktok",
                }
                _generate_and_show(
                    format_type=format_map[content_type],
                    topic=topic,
                    style=style,
                    profile=profile,
                    intel=None,
                )

    # ── Next step ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Next Step")
    st.markdown("Once you've saved drafts, approve them before publishing.")
    if st.button("Go to Review Queue →", type="primary", use_container_width=True):
        st.switch_page("pages/4_Publish.py")
