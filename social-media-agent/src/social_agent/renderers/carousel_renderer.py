"""Pillow-based carousel image renderer with branded templates."""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from social_agent.config import OUTPUT_DIR, TEMPLATES_DIR, ensure_output_dirs
from social_agent.models.content import BrandConfig, Carousel, CarouselSlide, Platform


FONTS_DIR = TEMPLATES_DIR / "fonts"

# Slide dimensions per platform
DIMENSIONS = {
    Platform.INSTAGRAM: (1080, 1350),
    Platform.TIKTOK: (1080, 1920),
    Platform.TWITTER: (1200, 675),
}


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font_path = FONTS_DIR / f"{name}.ttf"
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _draw_rounded_rect(
    draw: ImageDraw.Draw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...],
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = font.getbbox(test_line)
            if bbox[2] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
    return lines


def render_slide(
    slide: CarouselSlide,
    slide_number: int,
    total_slides: int,
    brand: BrandConfig,
    platform: Platform,
    background_image: Optional[Image.Image] = None,
) -> Image.Image:
    """Render a single carousel slide as a Pillow Image."""
    width, height = DIMENSIONS.get(platform, DIMENSIONS[Platform.INSTAGRAM])
    bg_color = _hex_to_rgb(slide.background_color or brand.background_color)
    text_color = _hex_to_rgb(brand.text_color)
    accent_color = _hex_to_rgb(brand.accent_color)
    primary_color = _hex_to_rgb(brand.primary_color)

    # Create base image
    if background_image:
        img = background_image.resize((width, height), Image.LANCZOS)
        # Add dark overlay for text readability
        overlay = Image.new("RGBA", (width, height), (*bg_color, 180))
        img = Image.alpha_composite(img.convert("RGBA"), overlay)
    else:
        img = Image.new("RGB", (width, height), bg_color)

    draw = ImageDraw.Draw(img if img.mode == "RGB" else img)

    # Margins
    margin_x = int(width * 0.08)
    margin_top = int(height * 0.12)
    content_width = width - (margin_x * 2)

    # Load fonts
    heading_size = int(width * 0.065)
    body_size = int(width * 0.038)
    heading_font = _load_font(brand.heading_font, heading_size)
    body_font = _load_font(brand.body_font, body_size)

    # Draw accent bar at top
    bar_height = 6
    draw.rectangle(
        [margin_x, margin_top - 30, margin_x + int(content_width * 0.3), margin_top - 30 + bar_height],
        fill=primary_color,
    )

    # Draw heading
    heading_lines = _wrap_text(slide.heading, heading_font, content_width)
    y = margin_top
    for line in heading_lines:
        draw.text((margin_x, y), line, font=heading_font, fill=text_color)
        bbox = heading_font.getbbox(line)
        y += bbox[3] - bbox[1] + 10

    y += 30  # gap between heading and body

    # Draw body text
    body_lines = _wrap_text(slide.body, body_font, content_width)
    for line in body_lines:
        draw.text((margin_x, y), line, font=body_font, fill=(*text_color[:2], text_color[2]))
        bbox = body_font.getbbox(line)
        y += bbox[3] - bbox[1] + 8

    # Draw slide indicator dots
    dot_y = height - int(height * 0.06)
    dot_radius = 6
    dot_spacing = 24
    total_width = total_slides * dot_spacing
    start_x = (width - total_width) // 2
    for i in range(total_slides):
        x = start_x + i * dot_spacing + dot_radius
        fill = accent_color if i == slide_number else (*text_color[:2], text_color[2] // 3)
        draw.ellipse(
            [x - dot_radius, dot_y - dot_radius, x + dot_radius, dot_y + dot_radius],
            fill=fill,
        )

    # Draw brand watermark
    watermark_font = _load_font(brand.body_font, int(width * 0.025))
    watermark_text = brand.name
    wm_bbox = watermark_font.getbbox(watermark_text)
    wm_x = width - margin_x - (wm_bbox[2] - wm_bbox[0])
    wm_y = height - int(height * 0.04)
    draw.text(
        (wm_x, wm_y),
        watermark_text,
        font=watermark_font,
        fill=(*text_color[:2], text_color[2] // 2),
    )

    return img.convert("RGB") if img.mode != "RGB" else img


def render_carousel(
    carousel: Carousel,
    brand: BrandConfig,
    background_images: Optional[list[Image.Image]] = None,
) -> list[Path]:
    """Render all slides in a carousel and save to output directory."""
    ensure_output_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(carousel.output_dir) if carousel.output_dir else OUTPUT_DIR / "carousels" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i, slide in enumerate(carousel.slides):
        bg = background_images[i] if background_images and i < len(background_images) else None
        img = render_slide(
            slide=slide,
            slide_number=i,
            total_slides=len(carousel.slides),
            brand=brand,
            platform=carousel.platform,
            background_image=bg,
        )
        path = output_dir / f"slide_{i + 1:02d}.png"
        img.save(str(path), "PNG", quality=95)
        paths.append(path)

    return paths
