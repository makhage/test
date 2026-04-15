"""Calendar View — Visual weekly/monthly content calendar."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from datetime import datetime, timedelta

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_platform_badge

st.set_page_config(page_title="Content Calendar", page_icon="📅", layout="wide")
inject_custom_css()

st.markdown("# Content Calendar")
st.markdown("Visual overview of your content schedule.")

# View toggle
view = st.radio("View", ["Week", "Month"], horizontal=True)

# Date navigation
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if st.button("← Previous"):
        pass
with col2:
    st.markdown(f"<h3 style='text-align: center;'>{datetime.now().strftime('%B %Y')}</h3>", unsafe_allow_html=True)
with col3:
    if st.button("Next →"):
        pass

st.markdown("---")

# Weekly grid
if view == "Week":
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    cols = st.columns(7)

    for i, col in enumerate(cols):
        day = start_of_week + timedelta(days=i)
        with col:
            is_today = day.date() == today.date()
            border = "border: 2px solid #6366F1;" if is_today else "border: 1px solid #334155;"
            st.markdown(
                f'<div style="background: #1E293B; border-radius: 8px; padding: 0.75rem; '
                f'min-height: 150px; {border}">'
                f'<p style="font-weight: 600; color: {"#6366F1" if is_today else "#94A3B8"}; '
                f'font-size: 0.85rem; margin-bottom: 0.5rem;">'
                f'{day.strftime("%a %d")}</p>'
                f'<p style="color: #475569; font-size: 0.75rem; text-align: center; '
                f'padding-top: 2rem;">No posts</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    # Month view - 5 rows x 7 columns grid
    today = datetime.now()
    first_day = today.replace(day=1)
    start_day = first_day - timedelta(days=first_day.weekday())

    # Header row
    header_cols = st.columns(7)
    for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        with header_cols[i]:
            st.markdown(f"<p style='text-align: center; font-weight: 600; color: #94A3B8;'>{name}</p>", unsafe_allow_html=True)

    # Calendar grid
    for week in range(5):
        cols = st.columns(7)
        for i, col in enumerate(cols):
            day = start_day + timedelta(days=week * 7 + i)
            with col:
                is_current_month = day.month == today.month
                is_today = day.date() == today.date()
                text_color = "#F8FAFC" if is_current_month else "#475569"
                bg = "#1E293B"
                if is_today:
                    bg = "#6366F120"
                st.markdown(
                    f'<div style="background: {bg}; border-radius: 4px; padding: 0.25rem; '
                    f'text-align: center; min-height: 40px;">'
                    f'<span style="color: {text_color}; font-size: 0.8rem;">{day.day}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

st.markdown("---")

# Generate calendar button
st.markdown("### Generate Calendar")
col1, col2 = st.columns(2)
with col1:
    days = st.number_input("Days to plan", min_value=1, max_value=30, value=7)
with col2:
    topics_input = st.text_input("Focus topics (comma-separated)", placeholder="AI, Python, Web Dev")

if st.button("Generate Content Calendar", type="primary", use_container_width=True):
    st.info(
        "Calendar generation requires API keys. Use the CLI:\n\n"
        f"```bash\nsocial-agent calendar generate --days {days}"
        f"{f' --topics \"{topics_input}\"' if topics_input else ''}\n```"
    )
