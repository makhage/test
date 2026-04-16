"""Gemini Imagen background image generation for carousel slides."""

from __future__ import annotations

import io
from typing import Optional

from PIL import Image

from social_agent.config import get_settings


def generate_background(
    prompt: str,
    style: str = "abstract gradient",
    brand_colors: Optional[list[str]] = None,
    size: str = "1024x1024",
) -> Optional[Image.Image]:
    """Generate a background image using Gemini Imagen.

    Args:
        prompt: Description of the desired background.
        style: Visual style modifier.
        brand_colors: List of hex colors to incorporate.
        size: Image size (ignored — Imagen uses aspect ratios).

    Returns:
        PIL Image or None if generation fails.
    """
    settings = get_settings()
    if not settings.google_api_key:
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
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )

        if not response.generated_images:
            return None

        image_bytes = response.generated_images[0].image.image_bytes
        return Image.open(io.BytesIO(image_bytes))
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
