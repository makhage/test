"""Reply Inbox — Fetch comments, generate drafts, approve replies through GUI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_status_badge
from social_agent.config import get_settings
from social_agent.db.database import ReplyDraftRecord, get_session, init_db
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="Reply Inbox", page_icon="💬", layout="wide")
inject_custom_css()
init_db()

st.markdown("# Reply Inbox")
st.markdown("Manage engagement with AI-drafted replies.")

profile = load_profile()
settings = get_settings()

# Action buttons
col1, col2, col3 = st.columns(3)

with col1:
    fetch_clicked = st.button(
        "Fetch New Comments",
        type="primary",
        use_container_width=True,
        disabled=not bool(settings.twitter_bearer_token),
    )

with col2:
    draft_clicked = st.button(
        "Draft Replies",
        use_container_width=True,
        disabled=not bool(settings.google_api_key),
    )

with col3:
    if st.button("Approve All Pending", use_container_width=True):
        session = get_session()
        try:
            pending = session.query(ReplyDraftRecord).filter_by(status="draft").all()
            for d in pending:
                d.status = "approved"
            session.commit()
            st.success(f"Approved {len(pending)} replies!")
            st.rerun()
        finally:
            session.close()

# Fetch comments
if fetch_clicked:
    with st.spinner("Fetching comments and mentions from Twitter..."):
        try:
            from social_agent.engagement.reply_manager import fetch_twitter_mentions
            mentions = fetch_twitter_mentions()
            if mentions:
                st.success(f"Found {len(mentions)} new mentions!")
                st.session_state["fetched_comments"] = mentions
            else:
                st.info("No new mentions found.")
        except Exception as e:
            st.error(f"Fetch failed: {e}")

# Draft replies from fetched comments
if draft_clicked:
    comments = st.session_state.get("fetched_comments", [])
    # Also check for undrafted comments in DB
    if not comments:
        st.info("Fetch comments first, then click Draft Replies.")
    else:
        with st.spinner("Generating reply drafts with Claude..."):
            try:
                from social_agent.engagement.reply_manager import draft_replies
                drafts = draft_replies(comments, profile)
                st.success(f"Generated {len(drafts)} reply drafts!")
                st.session_state["fetched_comments"] = []  # Clear after drafting
                st.rerun()
            except Exception as e:
                st.error(f"Draft generation failed: {e}")

st.markdown("---")

# Category color mapping
cat_colors = {
    "question": "#3B82F6",
    "compliment": "#10B981",
    "criticism": "#F59E0B",
    "spam": "#EF4444",
    "general": "#94A3B8",
}

# Filter tabs
tab1, tab2, tab3 = st.tabs(["Pending Drafts", "Approved", "All"])

with tab1:
    session = get_session()
    try:
        drafts = (
            session.query(ReplyDraftRecord)
            .filter_by(status="draft")
            .order_by(ReplyDraftRecord.priority.desc())
            .all()
        )

        if drafts:
            st.caption(f"{len(drafts)} pending replies")
            for draft in drafts:
                cat_color = cat_colors.get(draft.category, "#94A3B8")

                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(
                        f'<div class="card">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                        f'<span style="color: {cat_color}; font-weight: 600; text-transform: uppercase; '
                        f'font-size: 0.75rem;">{draft.category}</span>'
                        f'<span style="color: #475569; font-size: 0.75rem;">Priority: {draft.priority}/10</span>'
                        f'</div>'
                        f'<p style="color: #94A3B8; margin-top: 0.5rem; font-size: 0.85rem;">@{draft.original_comment_author}:</p>'
                        f'<p style="color: #F8FAFC; padding: 0.5rem; background: #0F172A; '
                        f'border-radius: 6px; margin: 0.5rem 0;">"{draft.original_comment_text}"</p>'
                        f'<p style="color: #10B981; font-weight: 500; font-size: 0.85rem; margin-bottom: 0.25rem;">Suggested reply:</p>'
                        f'<p style="color: #F8FAFC; padding: 0.5rem; background: #10B98110; '
                        f'border-radius: 6px; border-left: 3px solid #10B981;">{draft.suggested_reply}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown("<div style='padding-top: 2rem;'></div>", unsafe_allow_html=True)
                    if st.button("Approve", key=f"approve_reply_{draft.id}", use_container_width=True):
                        draft.status = "approved"
                        session.commit()
                        st.rerun()
                    if st.button("Skip", key=f"skip_reply_{draft.id}", use_container_width=True):
                        draft.status = "rejected"
                        session.commit()
                        st.rerun()
        else:
            st.markdown(
                '<div class="card" style="text-align: center; padding: 2rem;">'
                '<p style="color: #94A3B8;">No pending reply drafts</p>'
                '<p style="color: #475569; font-size: 0.85rem;">Fetch comments and generate drafts using the buttons above.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
    finally:
        session.close()

with tab2:
    session = get_session()
    try:
        approved = (
            session.query(ReplyDraftRecord)
            .filter_by(status="approved")
            .order_by(ReplyDraftRecord.created_at.desc())
            .all()
        )
        if approved:
            st.caption(f"{len(approved)} approved replies")
            for draft in approved:
                st.markdown(
                    f'<div class="card" style="padding: 0.75rem;">'
                    f'{render_status_badge("approved")} '
                    f'<span style="color: #94A3B8;">@{draft.original_comment_author}:</span> '
                    f'"{draft.original_comment_text[:80]}{"..." if len(draft.original_comment_text) > 80 else ""}"'
                    f'<br><span style="color: #10B981;">Reply:</span> "{draft.suggested_reply}"'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No approved replies yet.")
    finally:
        session.close()

with tab3:
    session = get_session()
    try:
        all_drafts = (
            session.query(ReplyDraftRecord)
            .order_by(ReplyDraftRecord.created_at.desc())
            .limit(50)
            .all()
        )
        if all_drafts:
            for draft in all_drafts:
                cat_color = cat_colors.get(draft.category, "#94A3B8")
                status_color = {"draft": "#F59E0B", "approved": "#10B981", "rejected": "#EF4444"}.get(draft.status, "#94A3B8")
                st.markdown(
                    f'<div class="card" style="padding: 0.6rem;">'
                    f'<span style="color: {status_color}; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;">{draft.status}</span> '
                    f'<span style="color: {cat_color}; font-size: 0.7rem;">[{draft.category}]</span> '
                    f'<span style="color: #94A3B8; font-size: 0.85rem;">@{draft.original_comment_author}:</span> '
                    f'"{draft.original_comment_text[:80]}{"..." if len(draft.original_comment_text) > 80 else ""}"'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No reply drafts yet.")
    finally:
        session.close()
