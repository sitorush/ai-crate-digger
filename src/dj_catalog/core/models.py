"""Core domain models."""

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Track(BaseModel):
    """A music track with comprehensive metadata and analysis results."""

    # Identity
    file_path: Path
    file_hash: str

    # Core metadata (from ID3)
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    duration_seconds: float | None = None

    # Extended metadata
    label: str | None = None
    remixer: str | None = None
    composer: str | None = None
    original_artist: str | None = None
    isrc: str | None = None
    release_date: date | None = None
    year: int | None = None
    comment: str | None = None

    # Audio quality
    bitrate: int | None = None
    sample_rate: int | None = None
    codec: str | None = None

    # Analysis results
    bpm: float | None = None
    bpm_source: str | None = None
    key: str | None = None
    key_camelot: str | None = None
    energy: float | None = Field(default=None, ge=0.0, le=1.0)
    danceability: float | None = Field(default=None, ge=0.0, le=1.0)

    # Tag-based classification
    tags: list[str] = Field(default_factory=list)

    # User-defined
    rating: int | None = Field(default=None, ge=1, le=5)
    color: str | None = None
    play_count: int = 0

    # System
    analyzed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"frozen": False}
