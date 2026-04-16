"""Profile Editor — Edit influencer voice, brand, and settings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="Profile", page_icon="👤", layout="wide")
inject_custom_css()

st.markdown("# Influencer Profile")
st.markdown("View and edit your voice, brand, and platform settings.")

profile = load_profile()

# Voice settings
st.markdown("### Voice")
col1, col2 = st.columns(2)
with col1:
    voice_desc = st.text_area(
        "Voice Description",
        value=profile.voice.description,
        height=120,
    )
    tone = st.text_input("Tone Keywords", value=", ".join(profile.voice.tone))
with col2:
    avoid = st.text_area(
        "Things to Avoid",
        value="\n".join(f"- {a}" for a in profile.voice.avoid),
        height=120,
    )
    examples = st.text_area(
        "Example Posts",
        value="\n".join(profile.voice.example_posts),
        height=100,
    )

st.markdown("---")

# Brand settings
st.markdown("### Brand")
col1, col2, col3 = st.columns(3)
with col1:
    brand_name = st.text_input("Brand Name", value=profile.brand.name)
    primary_color = st.color_picker("Primary Color", value=profile.brand.primary_color)
with col2:
    secondary_color = st.color_picker("Secondary Color", value=profile.brand.secondary_color)
    accent_color = st.color_picker("Accent Color", value=profile.brand.accent_color)
with col3:
    bg_color = st.color_picker("Background Color", value=profile.brand.background_color)
    text_color = st.color_picker("Text Color", value=profile.brand.text_color)

# Brand preview
st.markdown("#### Brand Preview")
st.markdown(
    f'<div style="background: {bg_color}; border-radius: 12px; padding: 2rem; '
    f'border: 1px solid {primary_color}40;">'
    f'<h2 style="color: {primary_color}; margin: 0;">{brand_name}</h2>'
    f'<p style="color: {text_color};">This is how your branded content will look.</p>'
    f'<span style="background: {secondary_color}20; color: {secondary_color}; '
    f'padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.85rem;">Tag</span> '
    f'<span style="background: {accent_color}20; color: {accent_color}; '
    f'padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.85rem;">Accent</span>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("---")

# Platform settings
st.markdown("### Platform Settings")
tab1, tab2, tab3 = st.tabs(["Twitter/X", "Instagram", "TikTok"])

with tab1:
    tw = profile.platforms.get("twitter")
    if tw:
        st.checkbox("Enabled", value=tw.enabled, key="tw_enabled")
        st.number_input("Max Hashtags", value=tw.max_hashtags, key="tw_hashtags")
        st.text_input("Default CTA", value=tw.default_cta, key="tw_cta")

with tab2:
    ig = profile.platforms.get("instagram")
    if ig:
        st.checkbox("Enabled", value=ig.enabled, key="ig_enabled")
        st.number_input("Carousel Slides", value=ig.carousel_slides, key="ig_slides")
        st.number_input("Max Hashtags", value=ig.max_hashtags, key="ig_hashtags")
        st.text_input("Default CTA", value=ig.default_cta, key="ig_cta")

with tab3:
    tt = profile.platforms.get("tiktok")
    if tt:
        st.checkbox("Enabled", value=tt.enabled, key="tt_enabled")
        st.number_input("Max Hashtags", value=tt.max_hashtags, key="tt_hashtags")
        st.text_input("Default CTA", value=tt.default_cta, key="tt_cta")

st.markdown("---")

# Topics
st.markdown("### Topics of Expertise")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Primary Topics**")
    primary_topics = st.text_area(
        "Primary",
        value="\n".join(profile.topics.get("primary", [])),
        label_visibility="collapsed",
    )
with col2:
    st.markdown("**Secondary Topics**")
    secondary_topics = st.text_area(
        "Secondary",
        value="\n".join(profile.topics.get("secondary", [])),
        label_visibility="collapsed",
    )

# Content settings
st.markdown("---")
st.markdown("### Content Quality Settings")
col1, col2, col3 = st.columns(3)
with col1:
    st.slider(
        "Voice Score Threshold",
        1, 10,
        value=profile.content_settings.voice_score_threshold,
        help="Content below this score gets auto-rewritten",
    )
with col2:
    st.slider(
        "Max Rewrite Attempts",
        1, 5,
        value=profile.content_settings.max_rewrite_attempts,
    )
with col3:
    st.slider(
        "Default Variants",
        1, 5,
        value=profile.content_settings.default_variants,
    )

# Save button
st.markdown("---")
if st.button("Save Profile", type="primary", use_container_width=True):
    st.info("Profile editing through the UI will save to `profiles/default.yaml`. This feature is coming soon — for now, edit the YAML file directly.")
