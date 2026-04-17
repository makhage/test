"""Approval Queue — Review and approve/reject pending posts with provenance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_status_badge, render_platform_badge
from social_agent.db.database import ScheduledPostRecord, get_session, init_db


def _render_content_preview(post: ScheduledPostRecord) -> str:
    """Render a readable preview of the post content."""
    try:
        data = json.loads(post.content_json)
        if post.content_type == "tweet":
            return data.get("text", "")
        if post.content_type == "thread":
            tweets = [data.get("text", "")] + data.get("thread_tweets", [])
            return "\n\n".join(f"{i + 1}. {t}" for i, t in enumerate(tweets))
        if post.content_type == "carousel":
            title = data.get("title", "")
            slides = data.get("slides", [])
            slide_previews = "\n".join(f"• **{s.get('heading', '')}** — {s.get('body', '')[:80]}" for s in slides[:4])
            return f"**{title}**\n\n{slide_previews}" + (f"\n... +{len(slides) - 4} more" if len(slides) > 4 else "")
        if post.content_type == "tiktok":
            return data.get("caption", "")
        return post.content_json[:300]
    except Exception:
        return post.content_json[:300]


def _publish_post(post: ScheduledPostRecord) -> dict:
    """Publish a post to its target platform."""
    try:
        data = json.loads(post.content_json)
    except Exception:
        return {"success": False, "error": "Invalid content JSON"}

    if post.platform == "twitter":
        from social_agent.publishers.twitter import TwitterPublisher
        from social_agent.models.content import Tweet
        try:
            publisher = TwitterPublisher()
            if post.content_type == "thread":
                tweet = Tweet(
                    text=data.get("text", ""),
                    is_thread=True,
                    thread_tweets=data.get("thread_tweets", []),
                    hashtags=data.get("hashtags", []),
                )
            else:
                tweet = Tweet(
                    text=data.get("text", ""),
                    hashtags=data.get("hashtags", []),
                )
            return publisher.publish(tweet)
        except Exception as e:
            return {"success": False, "error": f"Twitter publish failed: {e}"}

    return {
        "success": False,
        "error": f"Publishing for '{post.platform}' not yet implemented — use 'Approve only' and post manually."
    }


def _render_carousel_images(post: ScheduledPostRecord, profile) -> None:
    """Render the carousel as actual slide images."""
    try:
        data = json.loads(post.content_json)
        from social_agent.models.content import Carousel
        carousel = Carousel(**data)

        from social_agent.renderers.carousel_renderer import render_carousel
        images = render_carousel(carousel, profile.brand)
        if images:
            cols = st.columns(min(len(images), 4))
            for i, img_path in enumerate(images):
                with cols[i % len(cols)]:
                    st.image(str(img_path), caption=f"Slide {i + 1}", use_container_width=True)
    except Exception as e:
        st.caption(f"Could not render carousel images: {e}")


def _render_post_card(post: ScheduledPostRecord, profile, actions: bool = True) -> None:
    """Render one post with its source signal and actions."""
    preview = _render_content_preview(post)

    with st.container():
        # Provenance badge
        if post.source_signal:
            st.markdown(
                f'<div style="background:#6366F110;border-left:3px solid #6366F1;'
                f'padding:0.5rem 0.75rem;border-radius:4px;margin-bottom:0.5rem;">'
                f'<span style="color:#94A3B8;font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.05em;">Why this post</span><br>'
                f'<span style="color:#CBD5E1;font-size:0.85rem;">{post.source_signal}</span>'
                f'{"<br><span style=&quot;color:#6366F1;font-size:0.8rem;font-style:italic;&quot;>" + post.source_angle + "</span>" if post.source_angle else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

        col_content, col_actions = st.columns([3, 1])

        with col_content:
            st.markdown(
                f'<div style="display:flex;gap:0.5rem;margin-bottom:0.5rem;">'
                f'{render_platform_badge(post.platform)}'
                f'<span style="color:#64748B;font-size:0.8rem;">{post.content_type}</span>'
                f'<span style="color:#64748B;font-size:0.8rem;">· {post.created_at.strftime("%b %d")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(preview)

            # Render carousel as actual images
            if post.content_type == "carousel":
                with st.expander("Show rendered slides", expanded=False):
                    _render_carousel_images(post, profile)

        if actions:
            with col_actions:
                if st.button("Approve & Publish", key=f"approve_{post.id}", type="primary", use_container_width=True):
                    st.session_state[f"publishing_{post.id}"] = True
                if st.button("Approve only", key=f"approve_only_{post.id}", use_container_width=True):
                    post.status = "approved"
                    return "commit"
                if st.button("Reject", key=f"reject_{post.id}", use_container_width=True):
                    st.session_state[f"rejecting_{post.id}"] = True

        # Publishing flow
        if st.session_state.get(f"publishing_{post.id}"):
            from datetime import datetime
            with st.spinner("Publishing..."):
                result = _publish_post(post)
            if result.get("success"):
                post.status = "published"
                post.published_at = datetime.utcnow()
                post.published_post_id = str(result.get("post_id", ""))
                st.success(f"Published! {result.get('url', '')}")
                st.session_state[f"publishing_{post.id}"] = False
                return "commit"
            else:
                st.error(f"Publish failed: {result.get('error', 'unknown error')}")
                st.info("You can still 'Approve only' and post manually.")
                st.session_state[f"publishing_{post.id}"] = False

        # Rejection reason capture — teaches the agent
        if st.session_state.get(f"rejecting_{post.id}"):
            st.markdown(
                '<div style="background:#EF444410;border-left:3px solid #EF4444;'
                'padding:0.75rem;border-radius:4px;margin-top:0.5rem;">'
                '<p style="margin:0;color:#EF4444;font-weight:600;font-size:0.85rem;">'
                'Why are you rejecting this?</p>'
                '<p style="margin:0.25rem 0 0 0;color:#CBD5E1;font-size:0.8rem;">'
                'Your answer gets saved to the knowledge base so the agent stops generating similar misses.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            reason = st.text_area(
                "Reason",
                key=f"reason_{post.id}",
                placeholder="e.g. 'Too preachy', 'Wrong tone', 'I'd never say this'",
                label_visibility="collapsed",
            )
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                if st.button("Reject + teach agent", key=f"reject_confirm_{post.id}", type="primary"):
                    post.status = "rejected"
                    # Write rejection as negative knowledge
                    try:
                        from social_agent.knowledge import remember
                        topic_preview = preview[:100].replace("\n", " ")
                        feedback = (
                            f"Avoid content like this: '{topic_preview}'. "
                            f"Reason: {reason.strip() or 'user rejected without comment'}"
                        )
                        remember(
                            "performance",
                            feedback,
                            source=f"rejection_feedback (post #{post.id})",
                            relevance=1.0,
                        )
                    except Exception:
                        pass
                    st.session_state[f"rejecting_{post.id}"] = False
                    return "commit"
            with col_cancel:
                if st.button("Cancel", key=f"reject_cancel_{post.id}"):
                    st.session_state[f"rejecting_{post.id}"] = False
                    st.rerun()

        st.markdown("---")
    return None


def render() -> None:
    init_db()

    from social_agent.profiles.loader import load_profile
    profile = load_profile()

    st.markdown("# Approval Queue")
    st.caption("Every draft shows the signal that triggered it so you can tell if the agent's listening to your audience.")

    tab1, tab2, tab3, tab4 = st.tabs(["Pending", "Approved", "Published", "Rejected"])

    session = get_session()
    try:
        with tab1:
            pending = session.query(ScheduledPostRecord).filter_by(status="pending").order_by(
                ScheduledPostRecord.created_at.desc()
            ).all()
            if not pending:
                st.info("No pending posts. Open Create → generate content from suggested ideas.")
            else:
                for post in pending:
                    result = _render_post_card(post, profile, actions=True)
                    if result == "commit":
                        session.commit()
                        st.rerun()

        with tab2:
            approved = session.query(ScheduledPostRecord).filter_by(status="approved").order_by(
                ScheduledPostRecord.created_at.desc()
            ).all()
            if not approved:
                st.info("No approved posts yet.")
            else:
                for post in approved:
                    _render_post_card(post, profile, actions=False)

        with tab3:
            published = session.query(ScheduledPostRecord).filter_by(status="published").order_by(
                ScheduledPostRecord.published_at.desc()
            ).all()
            if not published:
                st.info("No published posts yet.")
            else:
                for post in published:
                    _render_post_card(post, profile, actions=False)

        with tab4:
            rejected = session.query(ScheduledPostRecord).filter_by(status="rejected").order_by(
                ScheduledPostRecord.created_at.desc()
            ).all()
            if not rejected:
                st.info("No rejected posts.")
            else:
                for post in rejected:
                    _render_post_card(post, profile, actions=False)
    finally:
        session.close()

    # ── Next Step ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Next Step")
    st.markdown("Check analytics to see what's performing — the agent learns from this automatically.")
    if st.button("View Analytics →", type="primary", use_container_width=True):
        st.switch_page("pages/5_Analytics.py")
