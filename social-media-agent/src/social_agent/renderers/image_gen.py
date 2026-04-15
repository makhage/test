"""DALL-E background image generation for carousel slides."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from social_agent.config import get_settings


def generate_background(
    prompt: str,
    style: str = "abstract gradient",
    brand_colors: Optional[list[str]] = None,
    size: str = "1024x1024",
) -> Optional[Image.Image]:
    """Generate a background image using DALL-E.

    Args:
        prompt: Description of the desired background.
        style: Visual style modifier.
        brand_colors: List of hex colors to incorporate.
        size: Image size (DALL-E supported sizes).

    Returns:
        PIL Image or None if generation fails.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    color_hint = ""
    if brand_colors:
        color_hint = f" Color palette: {', '.join(brand_colors)}."

    full_prompt = (
        f"Abstract background for a social media carousel slide. "
        f"Style: {style}. Theme: {prompt}.{color_hint} "
        f"No text, no logos, subtle and modern, suitable as a background for overlaid text."
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size=size,
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        return Image.open(io.BytesIO(img_response.content))
    except Exception:
        return None


def generate_backgrounds_for_carousel(
    slide_prompts: list[str],
    style: str = "abstract gradient",
    brand_colors: Optional[list[str]] = None,
) -> list[Optional[Image.Image]]:
    """Generate background images for multiple carousel slides."""
    return [
        generate_background(prompt, style=style, brand_colors=brand_colors)
        for prompt in slide_prompts
    ]
