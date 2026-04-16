"""Approval Queue — Review and approve/reject pending posts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_status_badge, render_platform_badge
from social_agent.db.database import ScheduledPostRecord, get_session, init_db

st.set_page_config(page_title="Approval Queue", page_icon="✅", layout="wide")
inject_custom_css()

st.markdown("# Approval Queue")
st.markdown("Review pending posts before they go live.")

init_db()

# Filter tabs
tab1, tab2, tab3, tab4 = st.tabs(["Pending", "Approved", "Published", "Rejected"])

with tab1:
    session = get_session()
    try:
        pending = session.query(ScheduledPostRecord).filter_by(status="pending").all()
        if pending:
            for post in pending:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(
                            f'<div class="card">'
                            f'<p>{render_platform_badge(post.platform)} '
                            f'{render_status_badge("pending")}</p>'
                            f'<p><strong>{post.content_type}</strong></p>'
                            f'<p style="color: #94A3B8;">{post.content_json[:200]}...</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with col2:
                        if st.button("Approve", key=f"approve_{post.id}"):
                            post.status = "approved"
                            session.commit()
                            st.rerun()
                    with col3:
                        if st.button("Reject", key=f"reject_{post.id}"):
                            post.status = "rejected"
                            session.commit()
                            st.rerun()
        else:
            st.info("No pending posts. Generate content from the Content Studio!")
    finally:
        session.close()

with tab2:
    session = get_session()
    try:
        approved = session.query(ScheduledPostRecord).filter_by(status="approved").all()
        if approved:
            for post in approved:
                st.markdown(
                    f'<div class="card">'
                    f'{render_platform_badge(post.platform)} {render_status_badge("approved")} '
                    f'— {post.content_type}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No approved posts.")
    finally:
        session.close()

with tab3:
    st.info("No published posts yet.")

with tab4:
    st.info("No rejected posts.")
