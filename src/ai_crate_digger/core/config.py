"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Paths
    db_path: Path = Field(default_factory=lambda: Path.home() / ".dj-catalog" / "catalog.db")
    vector_path: Path = Field(default_factory=lambda: Path.home() / ".dj-catalog" / ".chroma")
    output_path: Path = Field(
        default_factory=lambda: Path.home() / "Downloads",
        description="Default directory for exported playlists",
    )
    music_path: Path = Field(
        default_factory=lambda: Path.home() / "Music" / "mp3",
        description="Default directory for music library scanning",
    )

    # Performance
    max_workers: int | None = None  # None = auto-detect (cpu_count - 1)
    batch_size: int = 100  # DB batch write size

    # Analysis
    analyze_by_default: bool = True
    sample_rate: int = 22050  # Hz for librosa

    model_config = {
        "env_prefix": "DJ_CATALOG_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
