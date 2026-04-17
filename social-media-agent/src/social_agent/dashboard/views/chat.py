"""Chat mode — talk to the agent naturally.

You say "plan this week around Ramadan" or "give me 3 hot takes on tajweed"
and the agent figures out what to do, using the full knowledge base.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import json
import streamlit as st

from social_agent.dashboard.theme import inject_custom_css
from social_agent.config import get_settings


CHAT_SYSTEM = """You are a conversational content strategist helping a creator plan and generate social media content.

You can and should answer questions like:
- "What should I post tomorrow?"
- "Give me 3 hot takes on X"
- "Plan a thread about Y"
- "What does my audience care about right now?"
- "Why should I post about Z?"

Use the creator soul + knowledge base (prepended to this prompt) to ground every answer. When suggesting content:
- Tie each suggestion to a specific audience signal or trend you know about
- Be opinionated and specific — never generic
- If you're about to output content the creator could actually post, format it so it's copy-ready
- If you don't have enough data to answer, say so and suggest running the relevant research step

Respond conversationally. Short, direct, no preamble.
"""


def render() -> None:
    st.markdown("# Chat with the agent")
    st.caption(
        "Ask anything — the agent uses your knowledge base, identity files, and full history."
    )

    settings = get_settings()
    if not settings.google_api_key:
        st.warning("Add your Gemini API key in Settings first.")
        return

    # Per-creator chat history
    from social_agent.creators import current_slug
    slug = current_slug()
    history_key = f"chat_history_{slug}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    history = st.session_state[history_key]

    # ── Display history ─────────────────────────────────────────────────────
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Input ───────────────────────────────────────────────────────────────
    if prompt := st.chat_input("What do you want to talk about?"):
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Build conversation text for Gemini
        conversation = "\n\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    from social_agent.ai import chat
                    response = chat(
                        system=CHAT_SYSTEM,
                        user=conversation,
                        max_tokens=2000,
                    )
                except Exception as e:
                    response = f"Something went wrong: {e}"

            st.markdown(response)
            history.append({"role": "assistant", "content": response})

    # ── Quick prompts ───────────────────────────────────────────────────────
    if not history:
        st.markdown("")
        st.caption("Try one of these:")
        quick_prompts = [
            "What should I post tomorrow?",
            "Give me 3 hot takes my audience would react to",
            "Plan this week's content",
            "What does my audience struggle with most?",
            "Draft a thread based on a real Reddit question",
        ]
        cols = st.columns(len(quick_prompts))
        for col, qp in zip(cols, quick_prompts):
            with col:
                if st.button(qp, use_container_width=True, key=f"quick_{qp}"):
                    st.session_state["chat_quick_prompt"] = qp
                    st.rerun()

        if "chat_quick_prompt" in st.session_state:
            qp = st.session_state.pop("chat_quick_prompt")
            history.append({"role": "user", "content": qp})
            with st.chat_message("user"):
                st.markdown(qp)
            conversation = f"USER: {qp}"
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        from social_agent.ai import chat
                        response = chat(
                            system=CHAT_SYSTEM,
                            user=conversation,
                            max_tokens=2000,
                        )
                    except Exception as e:
                        response = f"Something went wrong: {e}"
                st.markdown(response)
                history.append({"role": "assistant", "content": response})
            st.rerun()

    # Clear history button
    if history:
        if st.button("Clear conversation"):
            st.session_state[history_key] = []
            st.rerun()
