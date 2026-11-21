"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Paths
    db_path: Path = Field(default_factory=lambda: Path.home() / ".ai-crate-digger" / "catalog.db")
    vector_path: Path = Field(default_factory=lambda: Path.home() / ".ai-crate-digger" / ".chroma")
    output_path: Path = Field(
        default_factory=lambda: Path.home() / "Downloads",
        description="Default directory for exported playlists",
    )
    music_path: Path = Field(
        default_factory=lambda: Path.home() / "Music" / "mp3",
        description="Default directory for music library scanning",
    )

    inbox_path: Path = Field(
        default_factory=lambda: Path.home() / "Music" / "mixes",
        description="Folder where recorded mixes are dropped for identification",
    )

    # Performance
    max_workers: int | None = None  # None = auto-detect (cpu_count - 1)
    batch_size: int = 100  # DB batch write size

    # Analysis
    analyze_by_default: bool = True
    sample_rate: int = 22050  # Hz for librosa

    # Mix identification
    mix_min_seconds: float = 30.0
    mix_speed_range: float = 0.08
    mix_speed_step: float = 0.01
    mix_high_support: float = 0.12
    mix_medium_support: float = 0.05
    mix_low_support: float = 0.02

    model_config = {
        "env_prefix": "CRATE_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
