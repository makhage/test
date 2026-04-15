"""Tests for carousel rendering."""

from pathlib import Path

from PIL import Image

from social_agent.models.content import BrandConfig, Carousel, CarouselSlide, Platform
from social_agent.renderers.carousel_renderer import render_carousel, render_slide


def _brand():
    return BrandConfig(
        name="TestBrand",
        primary_color="#6366F1",
        secondary_color="#EC4899",
        accent_color="#10B981",
        background_color="#0F172A",
        text_color="#F8FAFC",
        heading_font="Inter-Bold",
        body_font="Inter-Regular",
    )


def _slides():
    return [
        CarouselSlide(heading="5 Python Tips", body="You need to know these"),
        CarouselSlide(heading="Tip 1: List Comprehensions", body="They're faster and more readable than loops."),
        CarouselSlide(heading="Tip 2: F-Strings", body="Stop using .format() — f-strings are cleaner."),
        CarouselSlide(heading="Follow Me!", body="Save this for later and follow for more tips."),
    ]


def test_render_single_slide():
    slide = CarouselSlide(heading="Test Heading", body="Test body content")
    brand = _brand()
    img = render_slide(slide, 0, 1, brand, Platform.INSTAGRAM)
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1350)


def test_render_slide_twitter_dimensions():
    slide = CarouselSlide(heading="Twitter", body="Tweet image")
    brand = _brand()
    img = render_slide(slide, 0, 1, brand, Platform.TWITTER)
    assert img.size == (1200, 675)


def test_render_slide_tiktok_dimensions():
    slide = CarouselSlide(heading="TikTok", body="TikTok slide")
    brand = _brand()
    img = render_slide(slide, 0, 1, brand, Platform.TIKTOK)
    assert img.size == (1080, 1920)


def test_render_carousel_saves_files(tmp_path):
    carousel = Carousel(
        title="Test Carousel",
        slides=_slides(),
        platform=Platform.INSTAGRAM,
        output_dir=str(tmp_path),
    )
    brand = _brand()
    paths = render_carousel(carousel, brand)
    assert len(paths) == 4
    for p in paths:
        assert Path(p).exists()
        img = Image.open(p)
        assert img.size == (1080, 1350)


def test_render_with_background_image(tmp_path):
    bg = Image.new("RGB", (512, 512), (100, 50, 200))
    slide = CarouselSlide(heading="With BG", body="Has background")
    brand = _brand()
    img = render_slide(slide, 0, 1, brand, Platform.INSTAGRAM, background_image=bg)
    assert img.size == (1080, 1350)


def test_long_text_wraps():
    slide = CarouselSlide(
        heading="This is a very long heading that should wrap across multiple lines on the slide",
        body="And this is an even longer body text that definitely needs to wrap. " * 5,
    )
    brand = _brand()
    img = render_slide(slide, 0, 1, brand, Platform.INSTAGRAM)
    assert img.size == (1080, 1350)
