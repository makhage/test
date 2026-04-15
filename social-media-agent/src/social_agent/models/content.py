"""Pydantic models defining the data contract between all components."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---


class Platform(str, Enum):
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class PostStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class CommentCategory(str, Enum):
    QUESTION = "question"
    COMPLIMENT = "compliment"
    CRITICISM = "criticism"
    SPAM = "spam"
    GENERAL = "general"


# --- Influencer Profile ---


class VoiceConfig(BaseModel):
    description: str
    tone: list[str] = []
    avoid: list[str] = []
    example_posts: list[str] = []


class BrandConfig(BaseModel):
    name: str = ""
    primary_color: str = "#6366F1"
    secondary_color: str = "#EC4899"
    accent_color: str = "#10B981"
    background_color: str = "#0F172A"
    text_color: str = "#F8FAFC"
    heading_font: str = "Inter-Bold"
    body_font: str = "Inter-Regular"
    logo_path: str = ""


class PlatformSettings(BaseModel):
    enabled: bool = True
    max_hashtags: int = 5
    default_cta: str = ""


class TwitterSettings(PlatformSettings):
    thread_style: str = "numbered"


class InstagramSettings(PlatformSettings):
    carousel_slides: int = 7
    slide_dimensions: list[int] = Field(default_factory=lambda: [1080, 1350])
    caption_max_length: int = 2200


class TikTokSettings(PlatformSettings):
    caption_max_length: int = 4000


class ContentSettings(BaseModel):
    voice_score_threshold: int = 7
    max_rewrite_attempts: int = 3
    default_variants: int = 2
    posting_times: dict[str, list[str]] = Field(default_factory=dict)


class RedditConfig(BaseModel):
    subreddits: list[str] = []
    min_upvotes: int = 100
    include_comments: bool = True
    max_comment_depth: int = 3


class CompetitorConfig(BaseModel):
    twitter: list[str] = []
    instagram: list[str] = []
    tiktok: list[str] = []


class InfluencerProfile(BaseModel):
    voice: VoiceConfig
    brand: BrandConfig = Field(default_factory=BrandConfig)
    platforms: dict[str, PlatformSettings] = Field(default_factory=dict)
    topics: dict[str, list[str]] = Field(default_factory=dict)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    competitors: CompetitorConfig = Field(default_factory=CompetitorConfig)
    content_settings: ContentSettings = Field(default_factory=ContentSettings)


# --- Content Models ---


class Tweet(BaseModel):
    text: str = Field(max_length=280)
    hashtags: list[str] = []
    media_paths: list[str] = []
    is_thread: bool = False
    thread_tweets: list[str] = []


class CarouselSlide(BaseModel):
    heading: str
    body: str
    background_color: Optional[str] = None
    image_prompt: Optional[str] = None
    image_path: Optional[str] = None


class Carousel(BaseModel):
    title: str
    slides: list[CarouselSlide]
    platform: Platform = Platform.INSTAGRAM
    caption: str = ""
    hashtags: list[str] = []
    output_dir: Optional[str] = None


class TikTokCaption(BaseModel):
    caption: str
    hashtags: list[str] = []
    sound_suggestion: Optional[str] = None
    script_notes: Optional[str] = None


class ContentBrief(BaseModel):
    topic: str
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.TWITTER])
    instructions: str = ""
    num_variants: int = 1


# --- Scheduling ---


class ScheduledPost(BaseModel):
    id: Optional[int] = None
    content_type: str  # "tweet", "carousel", "tiktok"
    content_json: str  # serialized content
    platform: Platform
    scheduled_time: Optional[datetime] = None
    status: PostStatus = PostStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None


# --- Research / Viral Content ---


class ViralPost(BaseModel):
    id: Optional[int] = None
    platform: Platform
    author: str = ""
    text: str
    likes: int = 0
    shares: int = 0
    comments: int = 0
    impressions: int = 0
    url: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    hashtags: list[str] = []
    content_type: str = ""  # "tweet", "carousel", "thread", "reel"


class HookPattern(BaseModel):
    pattern: str
    example: str
    frequency: int = 0
    avg_engagement: float = 0.0


class NicheIntelligence(BaseModel):
    trending_topics: list[str] = []
    winning_hooks: list[HookPattern] = []
    top_formats: list[str] = []
    engagement_benchmarks: dict[str, float] = Field(default_factory=dict)
    audience_questions: list[str] = []
    hot_takes: list[str] = []
    authentic_phrases: list[str] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_post_count: int = 0


# --- A/B Testing ---


class ContentVariant(BaseModel):
    id: Optional[int] = None
    parent_content_id: Optional[int] = None
    variant_label: str = ""  # "hook_a", "casual_tone", etc.
    content_type: str = ""
    content_json: str = ""
    platform: Platform = Platform.TWITTER
    engagement_score: Optional[float] = None
    is_winner: bool = False


# --- Competitors ---


class CompetitorProfile(BaseModel):
    handle: str
    platform: Platform
    avg_likes: float = 0.0
    avg_shares: float = 0.0
    avg_comments: float = 0.0
    top_topics: list[str] = []
    posting_frequency: str = ""
    last_analyzed: Optional[datetime] = None


# --- Voice Scoring ---


class VoiceScore(BaseModel):
    score: int = Field(ge=1, le=10)
    feedback: str = ""
    rewrite_count: int = 0
    passed: bool = False


# --- Engagement / Replies ---


class ReplyDraft(BaseModel):
    id: Optional[int] = None
    platform: Platform
    original_comment_author: str = ""
    original_comment_text: str
    suggested_reply: str = ""
    category: CommentCategory = CommentCategory.GENERAL
    priority: int = 0  # higher = more important
    status: PostStatus = PostStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
