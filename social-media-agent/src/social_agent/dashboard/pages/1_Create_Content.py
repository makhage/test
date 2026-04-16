"""Content Studio — Generate and preview content directly in the GUI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings, ensure_output_dirs
from social_agent.db.database import ScheduledPostRecord, init_db, get_session
from social_agent.models.content import Platform
from social_agent.profiles.loader import load_profile

st.set_page_config(page_title="Content Studio", page_icon="✏️", layout="wide")
inject_custom_css()
init_db()

st.markdown("# Content Studio")
st.markdown("Generate tweets, carousels, and TikTok captions powered by AI.")

profile = load_profile()
settings = get_settings()

# Check API key
has_api_key = bool(settings.openai_api_key or settings.openai_oauth_client_id)
if not has_api_key:
    st.warning("Set `ANTHROPIC_API_KEY` in your `.env` file to enable content generation.")

# Content type selector
content_type = st.selectbox(
    "Content Type",
    ["Tweet", "Thread", "Carousel", "TikTok Caption", "All Platforms"],
)

# Topic input
topic = st.text_input("Topic", placeholder="e.g., 5 Python tips every developer should know")

# Options row
col1, col2 = st.columns(2)
with col1:
    style = st.selectbox("Style", ["engaging", "educational", "controversial", "storytelling"])
with col2:
    num_variants = st.slider("A/B Variants", 1, 3, 1)

# Platform-specific options
carousel_platform = Platform.INSTAGRAM
num_slides = 7
num_tweets = 5

if content_type == "Carousel":
    col1, col2 = st.columns(2)
    with col1:
        plat_choice = st.selectbox("Platform", ["Instagram", "TikTok"])
        carousel_platform = Platform.INSTAGRAM if plat_choice == "Instagram" else Platform.TIKTOK
    with col2:
        num_slides = st.slider("Number of Slides", 3, 10, 7)

if content_type == "Thread":
    num_tweets = st.slider("Tweets in Thread", 3, 15, 5)

render_images = False
if content_type == "Carousel":
    render_images = st.checkbox("Render slide images", value=True)

st.markdown("---")

# --- Generate ---
if st.button("Generate Content", type="primary", use_container_width=True, disabled=not has_api_key):
    if not topic:
        st.warning("Please enter a topic first.")
    else:
        with st.spinner("Generating content..."):
            try:
                # Fetch latest intelligence if available
                from social_agent.research.analyzer import get_latest_intelligence
                intel = get_latest_intelligence()

                for variant_idx in range(num_variants):
                    variant_label = f" — Variant {variant_idx + 1}" if num_variants > 1 else ""

                    if content_type == "Tweet":
                        from social_agent.generators.tweet import generate_tweet
                        result = generate_tweet(topic, profile, style, intel)
                        st.markdown(f"### Tweet{variant_label}")
                        st.markdown(
                            f'<div class="card"><p style="font-size: 1.1rem; line-height: 1.6;">'
                            f'{result.text}</p>'
                            f'{"<p style=&quot;color: #6366F1;&quot;>#" + " #".join(result.hashtags) + "</p>" if result.hashtags else ""}'
                            f'<p style="color: #475569; font-size: 0.8rem;">{len(result.text)}/280 characters</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        # Save to session for scheduling
                        st.session_state[f"generated_tweet_{variant_idx}"] = result.model_dump()

                    elif content_type == "Thread":
                        from social_agent.generators.tweet import generate_thread
                        result = generate_thread(topic, profile, num_tweets, intel)
                        st.markdown(f"### Thread{variant_label}")
                        st.markdown(
                            f'<div class="card"><p style="font-weight: 600; color: #6366F1;">Hook:</p>'
                            f'<p style="font-size: 1.05rem;">{result.text}</p></div>',
                            unsafe_allow_html=True,
                        )
                        for j, t in enumerate(result.thread_tweets, 1):
                            st.markdown(
                                f'<div class="card" style="margin-left: 1.5rem; border-left: 3px solid #6366F140;">'
                                f'<p style="color: #94A3B8; font-size: 0.8rem;">Tweet {j + 1}</p>'
                                f'<p>{t}</p></div>',
                                unsafe_allow_html=True,
                            )
                        st.session_state[f"generated_thread_{variant_idx}"] = result.model_dump()

                    elif content_type == "Carousel":
                        from social_agent.generators.carousel import generate_carousel
                        result = generate_carousel(topic, profile, num_slides, carousel_platform, intel)
                        st.markdown(f"### Carousel{variant_label}")

                        # Show slide content
                        for i, slide in enumerate(result.slides):
                            col_a, col_b = st.columns([1, 3])
                            with col_a:
                                st.markdown(
                                    f'<div style="background: {profile.brand.primary_color}20; '
                                    f'border-radius: 8px; padding: 1rem; text-align: center;">'
                                    f'<span style="font-size: 1.5rem; font-weight: 700; '
                                    f'color: {profile.brand.primary_color};">{i + 1}</span></div>',
                                    unsafe_allow_html=True,
                                )
                            with col_b:
                                st.markdown(
                                    f'<div class="card">'
                                    f'<p style="font-weight: 600; font-size: 1.1rem;">{slide.heading}</p>'
                                    f'<p style="color: #CBD5E1;">{slide.body}</p></div>',
                                    unsafe_allow_html=True,
                                )

                        if result.caption:
                            st.markdown(f"**Caption:** {result.caption}")
                        if result.hashtags:
                            st.markdown(f'**Hashtags:** #{" #".join(result.hashtags)}')

                        # Render images
                        if render_images:
                            with st.spinner("Rendering slide images..."):
                                from social_agent.renderers.carousel_renderer import render_carousel
                                ensure_output_dirs()
                                paths = render_carousel(result, profile.brand)

                            st.markdown("#### Rendered Slides")
                            img_cols = st.columns(min(len(paths), 4))
                            for i, path in enumerate(paths):
                                with img_cols[i % 4]:
                                    st.image(str(path), caption=f"Slide {i + 1}", use_container_width=True)

                        st.session_state[f"generated_carousel_{variant_idx}"] = result.model_dump()

                    elif content_type == "TikTok Caption":
                        from social_agent.generators.tiktok import generate_tiktok_caption
                        result = generate_tiktok_caption(topic, profile, style, intel)
                        st.markdown(f"### TikTok Caption{variant_label}")
                        st.markdown(
                            f'<div class="card">'
                            f'<p style="font-size: 1.05rem; line-height: 1.6;">{result.caption}</p>'
                            f'{"<p style=&quot;color: #00F2EA;&quot;>#" + " #".join(result.hashtags) + "</p>" if result.hashtags else ""}'
                            f'{"<p style=&quot;color: #94A3B8;&quot;>Sound: " + result.sound_suggestion + "</p>" if result.sound_suggestion else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if result.script_notes:
                            with st.expander("Script Notes"):
                                st.markdown(result.script_notes)
                        st.session_state[f"generated_tiktok_{variant_idx}"] = result.model_dump()

                    elif content_type == "All Platforms":
                        from social_agent.generators.repurposer import repurpose_content
                        results = repurpose_content(topic, profile, intel)
                        st.markdown(f"### All Platforms{variant_label}")

                        if "twitter" in results:
                            tw = results["twitter"]
                            st.markdown(
                                f'<div class="card">'
                                f'<p style="color: #1DA1F2; font-weight: 600;">Twitter/X</p>'
                                f'<p style="font-size: 1.05rem;">{tw.text}</p>'
                                f'{"<p style=&quot;color: #1DA1F2;&quot;>#" + " #".join(tw.hashtags) + "</p>" if tw.hashtags else ""}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                        if "instagram" in results:
                            ig = results["instagram"]
                            st.markdown(
                                f'<div class="card">'
                                f'<p style="color: #E4405F; font-weight: 600;">Instagram Carousel ({len(ig.slides)} slides)</p>'
                                f'<p style="font-weight: 500;">{ig.title}</p>',
                                unsafe_allow_html=True,
                            )
                            for slide in ig.slides:
                                st.markdown(f"- **{slide.heading}**: {slide.body}")
                            if ig.caption:
                                st.markdown(f"**Caption:** {ig.caption}")

                        if "tiktok" in results:
                            tt = results["tiktok"]
                            st.markdown(
                                f'<div class="card">'
                                f'<p style="color: #00F2EA; font-weight: 600;">TikTok</p>'
                                f'<p>{tt.caption}</p>'
                                f'{"<p style=&quot;color: #00F2EA;&quot;>#" + " #".join(tt.hashtags) + "</p>" if tt.hashtags else ""}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                st.success("Content generated successfully!")

            except Exception as e:
                st.error(f"Generation failed: {e}")

# --- Save / Schedule section ---
st.markdown("---")
st.markdown("### Save to Queue")

save_col1, save_col2 = st.columns(2)
with save_col1:
    save_platform = st.selectbox("Platform", ["twitter", "instagram", "tiktok"], key="save_plat")
with save_col2:
    save_type = st.selectbox("Content Type", ["tweet", "thread", "carousel", "tiktok"], key="save_type")

content_to_save = st.text_area(
    "Content (paste or edit generated content)",
    height=120,
    placeholder="Paste generated content here, or it will auto-fill after generation...",
)

if st.button("Add to Approval Queue", use_container_width=True):
    if content_to_save.strip():
        session = get_session()
        try:
            record = ScheduledPostRecord(
                content_type=save_type,
                content_json=content_to_save,
                platform=save_platform,
                status="pending",
            )
            session.add(record)
            session.commit()
            st.success("Added to approval queue!")
        finally:
            session.close()
    else:
        st.warning("Enter or generate content first.")
