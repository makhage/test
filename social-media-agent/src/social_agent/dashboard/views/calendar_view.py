"""Calendar View — Visual weekly/monthly content calendar with generation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
from datetime import datetime, timedelta

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_platform_badge
from social_agent.config import get_settings
from social_agent.db.database import ScheduledPostRecord, get_session, init_db
from social_agent.profiles.loader import load_profile


def render() -> None:
    init_db()

    st.markdown("# Content Calendar")
    st.caption("Visual overview of your scheduled content. Auto-fill pulls from your knowledge base.")

    profile = load_profile()
    settings = get_settings()

    # ── Auto-plan a week ─────────────────────────────────────────────────────
    if settings.google_api_key:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(
                "**Auto-plan** — fill next 7 days with content ideas from your audience research."
            )
        with col_b:
            if st.button("Auto-plan week", type="primary", use_container_width=True):
                with st.spinner("Planning content based on your knowledge base..."):
                    try:
                        from social_agent.calendar.planner import generate_calendar
                        schedule = generate_calendar(profile, days=7)

                        init_db()
                        sess = get_session()
                        try:
                            from social_agent.db.database import ScheduledPostRecord as SPR
                            for entry in schedule[:14]:
                                try:
                                    sched = datetime.fromisoformat(
                                        f"{entry.get('date', '')}T{entry.get('time', '10:00')}:00"
                                    )
                                except Exception:
                                    sched = datetime.utcnow() + timedelta(days=1)
                                sess.add(SPR(
                                    content_type=entry.get("content_type", "tweet"),
                                    content_json=json.dumps({
                                        "topic": entry.get("topic", ""),
                                        "hook_suggestion": entry.get("hook_suggestion", ""),
                                        "notes": entry.get("notes", ""),
                                    }),
                                    platform=entry.get("platform", "twitter"),
                                    scheduled_time=sched,
                                    status="draft",
                                    source_signal="Auto-planned from knowledge base",
                                    source_angle=entry.get("hook_suggestion", ""),
                                ))
                            sess.commit()
                            st.success(f"Added {len(schedule[:14])} draft posts to the calendar.")
                        finally:
                            sess.close()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Plan failed: {e}")
        st.markdown("---")

    # Load scheduled posts
    session = get_session()
    try:
        all_posts = session.query(ScheduledPostRecord).all()
        posts_by_date: dict[str, list] = {}
        for post in all_posts:
            if post.scheduled_time:
                date_key = post.scheduled_time.strftime("%Y-%m-%d")
            else:
                date_key = post.created_at.strftime("%Y-%m-%d")
            if date_key not in posts_by_date:
                posts_by_date[date_key] = []
            posts_by_date[date_key].append(post)
    finally:
        session.close()

    # View toggle
    view = st.radio("View", ["Week", "Month"], horizontal=True)

    # Week offset in session state
    if "week_offset" not in st.session_state:
        st.session_state.week_offset = 0

    # Date navigation
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Previous"):
            st.session_state.week_offset -= 1
            st.rerun()
    with col2:
        base = datetime.now() + timedelta(weeks=st.session_state.week_offset)
        st.markdown(
            f"<h3 style='text-align: center;'>{base.strftime('%B %Y')}</h3>",
            unsafe_allow_html=True,
        )
    with col3:
        if st.button("Next →"):
            st.session_state.week_offset += 1
            st.rerun()

    st.markdown("---")

    # Platform color map
    plat_colors = {"twitter": "#1DA1F2", "instagram": "#E4405F", "tiktok": "#00F2EA"}
    status_icons = {"draft": "📝", "pending": "⏳", "approved": "✅", "published": "🚀", "rejected": "❌"}

    # Weekly grid
    if view == "Week":
        today = datetime.now()
        start_of_week = (today + timedelta(weeks=st.session_state.week_offset)) - timedelta(
            days=(today + timedelta(weeks=st.session_state.week_offset)).weekday()
        )
        cols = st.columns(7)

        for i, col in enumerate(cols):
            day = start_of_week + timedelta(days=i)
            date_key = day.strftime("%Y-%m-%d")
            is_today = day.date() == today.date()
            border = "border: 2px solid #6366F1;" if is_today else "border: 1px solid #334155;"

            day_posts = posts_by_date.get(date_key, [])

            with col:
                posts_html = ""
                if day_posts:
                    for p in day_posts[:3]:
                        color = plat_colors.get(p.platform, "#94A3B8")
                        icon = status_icons.get(p.status, "")
                        preview = p.content_json[:40].replace('"', "'")
                        posts_html += (
                            f'<div style="background: {color}15; border-left: 3px solid {color}; '
                            f'border-radius: 4px; padding: 0.3rem 0.5rem; margin-bottom: 0.3rem; '
                            f'font-size: 0.7rem;">'
                            f'{icon} <span style="color: {color};">{p.platform}</span><br>'
                            f'<span style="color: #CBD5E1;">{preview}...</span></div>'
                        )
                    if len(day_posts) > 3:
                        posts_html += f'<p style="color: #475569; font-size: 0.7rem;">+{len(day_posts) - 3} more</p>'
                else:
                    posts_html = '<p style="color: #475569; font-size: 0.7rem; text-align: center; padding-top: 1rem;">—</p>'

                st.markdown(
                    f'<div style="background: #1E293B; border-radius: 8px; padding: 0.75rem; '
                    f'min-height: 180px; {border}">'
                    f'<p style="font-weight: 600; color: {"#6366F1" if is_today else "#94A3B8"}; '
                    f'font-size: 0.85rem; margin-bottom: 0.5rem;">'
                    f'{day.strftime("%a %d")}</p>'
                    f'{posts_html}</div>',
                    unsafe_allow_html=True,
                )
    else:
        # Month view
        today = datetime.now()
        offset_date = today + timedelta(weeks=st.session_state.week_offset)
        first_day = offset_date.replace(day=1)
        start_day = first_day - timedelta(days=first_day.weekday())

        header_cols = st.columns(7)
        for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            with header_cols[i]:
                st.markdown(
                    f"<p style='text-align: center; font-weight: 600; color: #94A3B8;'>{name}</p>",
                    unsafe_allow_html=True,
                )

        for week in range(6):
            cols = st.columns(7)
            for i, col in enumerate(cols):
                day = start_day + timedelta(days=week * 7 + i)
                date_key = day.strftime("%Y-%m-%d")
                is_current_month = day.month == first_day.month
                is_today = day.date() == today.date()
                text_color = "#F8FAFC" if is_current_month else "#475569"
                bg = "#1E293B"
                if is_today:
                    bg = "#6366F120"

                day_posts = posts_by_date.get(date_key, [])
                dot_html = ""
                for p in day_posts[:3]:
                    color = plat_colors.get(p.platform, "#94A3B8")
                    dot_html += f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{color};margin:0 1px;"></span>'

                with col:
                    st.markdown(
                        f'<div style="background: {bg}; border-radius: 4px; padding: 0.25rem; '
                        f'text-align: center; min-height: 50px;">'
                        f'<span style="color: {text_color}; font-size: 0.8rem;">{day.day}</span><br>'
                        f'{dot_html}</div>',
                        unsafe_allow_html=True,
                    )

    st.markdown("---")

    # --- Generate Calendar ---
    st.markdown("### Generate Content Calendar")

    col1, col2 = st.columns(2)
    with col1:
        plan_days = st.number_input("Days to plan", min_value=1, max_value=30, value=7)
    with col2:
        topics_input = st.text_input("Focus topics (comma-separated)", placeholder="AI, Python, Web Dev")

    if st.button(
        "Generate Calendar",
        type="primary",
        use_container_width=True,
        disabled=not bool(settings.google_api_key),
    ):
        topic_list = [t.strip() for t in topics_input.split(",")] if topics_input else None

        with st.spinner(f"Generating {plan_days}-day content calendar..."):
            try:
                from social_agent.calendar.planner import generate_calendar

                calendar = generate_calendar(profile, days=plan_days, topics=topic_list)

                if calendar:
                    st.success(f"Generated {len(calendar)} content entries!")

                    for entry in calendar:
                        plat = entry.get("platform", "")
                        color = plat_colors.get(plat, "#94A3B8")
                        st.markdown(
                            f'<div class="card" style="padding: 0.8rem;">'
                            f'<span style="color: #94A3B8; font-size: 0.8rem;">'
                            f'{entry.get("date", "")} {entry.get("time", "")}</span> '
                            f'<span style="color: {color}; font-weight: 600;">{plat}</span> '
                            f'<span style="color: #475569;">/ {entry.get("content_type", "")}</span>'
                            f'<p style="margin: 0.3rem 0 0 0; font-weight: 500;">{entry.get("topic", "")}</p>'
                            f'{"<p style=&quot;color: #94A3B8; font-size: 0.85rem; margin: 0;&quot;>Hook: " + entry.get("hook_suggestion", "") + "</p>" if entry.get("hook_suggestion") else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.warning("No calendar entries generated. Try different topics.")
            except Exception as e:
                st.error(f"Calendar generation failed: {e}")

    if not settings.google_api_key:
        st.info("Add your Gemini API key in Settings to enable calendar generation.")

