"""Content Studio — Generate and preview content across platforms."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st

from social_agent.dashboard.theme import inject_custom_css, render_platform_badge
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="Content Studio", page_icon="✏️", layout="wide")
inject_custom_css()

st.markdown("# Content Studio")
st.markdown("Generate tweets, carousels, and TikTok captions powered by AI.")

profile = load_profile()

# Content type selector
content_type = st.selectbox(
    "Content Type",
    ["Tweet", "Thread", "Carousel", "TikTok Caption", "All Platforms"],
)

# Topic input
topic = st.text_input("Topic", placeholder="e.g., 5 Python tips every developer should know")

# Options
col1, col2 = st.columns(2)
with col1:
    style = st.selectbox("Style", ["Engaging", "Educational", "Controversial", "Storytelling"])
with col2:
    num_variants = st.slider("A/B Variants", 1, 3, 1)

# Platform-specific options
if content_type == "Carousel":
    col1, col2 = st.columns(2)
    with col1:
        platform = st.selectbox("Platform", ["Instagram", "TikTok"])
    with col2:
        num_slides = st.slider("Number of Slides", 3, 10, 7)

if content_type == "Thread":
    num_tweets = st.slider("Tweets in Thread", 3, 15, 5)

# Generate button
if st.button("Generate Content", type="primary", use_container_width=True):
    if not topic:
        st.warning("Please enter a topic first.")
    else:
        st.info(
            f"Content generation requires API keys. "
            f"Set ANTHROPIC_API_KEY in your .env file, then use the CLI:\n\n"
            f"```bash\nsocial-agent {'tweet' if content_type == 'Tweet' else 'carousel' if content_type == 'Carousel' else 'tiktok'} \"{topic}\"\n```"
        )

st.markdown("---")

# Content preview area
st.markdown("### Preview")
st.markdown(
    '<div class="card">'
    "<p style='color: #94A3B8; text-align: center; padding: 2rem;'>"
    "Generated content will appear here"
    "</p></div>",
    unsafe_allow_html=True,
)
