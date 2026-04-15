"""Reply Inbox — Comment threads with suggested reply drafts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_status_badge
from social_agent.db.database import ReplyDraftRecord, get_session, init_db

st.set_page_config(page_title="Reply Inbox", page_icon="💬", layout="wide")
inject_custom_css()

st.markdown("# Reply Inbox")
st.markdown("Manage engagement with AI-drafted replies.")

init_db()

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
            for draft in drafts:
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Category color mapping
                    cat_colors = {
                        "question": "#3B82F6",
                        "compliment": "#10B981",
                        "criticism": "#F59E0B",
                        "spam": "#EF4444",
                        "general": "#94A3B8",
                    }
                    cat_color = cat_colors.get(draft.category, "#94A3B8")

                    st.markdown(
                        f'<div class="card">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                        f'<span style="color: {cat_color}; font-weight: 600; text-transform: uppercase; '
                        f'font-size: 0.75rem;">{draft.category}</span>'
                        f'<span style="color: #475569; font-size: 0.75rem;">Priority: {draft.priority}/10</span>'
                        f'</div>'
                        f'<p style="color: #94A3B8; margin-top: 0.5rem;">@{draft.original_comment_author}:</p>'
                        f'<p style="color: #F8FAFC; padding: 0.5rem; background: #0F172A; '
                        f'border-radius: 6px; margin: 0.5rem 0;">"{draft.original_comment_text}"</p>'
                        f'<p style="color: #10B981; font-weight: 500;">Suggested reply:</p>'
                        f'<p style="color: #F8FAFC; padding: 0.5rem; background: #10B98110; '
                        f'border-radius: 6px; border-left: 3px solid #10B981;">{draft.suggested_reply}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Approve", key=f"approve_reply_{draft.id}"):
                        draft.status = "approved"
                        session.commit()
                        st.rerun()
                    if st.button("Skip", key=f"skip_reply_{draft.id}"):
                        draft.status = "rejected"
                        session.commit()
                        st.rerun()
        else:
            st.info(
                "No pending replies. Fetch comments and generate drafts:\n\n"
                "```bash\nsocial-agent replies fetch\nsocial-agent replies draft\n```"
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
            for draft in approved:
                st.markdown(
                    f'<div class="card">'
                    f'{render_status_badge("approved")} @{draft.original_comment_author}: '
                    f'"{draft.original_comment_text[:100]}..."'
                    f'<br>Reply: "{draft.suggested_reply}"'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No approved replies.")
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
                st.markdown(
                    f'<div class="card">'
                    f'{render_status_badge(draft.status)} [{draft.category}] '
                    f'@{draft.original_comment_author}: "{draft.original_comment_text[:80]}..."'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No reply drafts yet.")
    finally:
        session.close()
