"""Environment loading and path resolution."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    google_api_key: str = ""

    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""

    instagram_access_token: str = ""
    instagram_business_account_id: str = ""

    tiktok_access_token: str = ""
    tiktok_open_id: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "social-agent/0.1"

    profile_path: str = "profiles/default.yaml"
    database_url: str = f"sqlite:///{DATA_DIR / 'social_agent.db'}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()


def ensure_output_dirs() -> None:
    for subdir in ["tweets", "carousels", "tiktok"]:
        (OUTPUT_DIR / subdir).mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_env_var(key: str, value: str) -> None:
    """Save or update a key=value pair in the project .env file."""
    env_path = PROJECT_ROOT / ".env"
    lines: list[str] = []
    found = False

    if env_path.exists():
        lines = env_path.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break

    if not found:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")
    # Update current process env so get_settings() picks it up
    os.environ[key] = value
