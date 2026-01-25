"""Tests for core models."""

from datetime import date
from pathlib import Path

import pytest

from dj_catalog.core.models import Track


class TestTrack:
    """Tests for Track model."""

    def test_track_minimal_creation(self) -> None:
        """Track can be created with just file_path and file_hash."""
        track = Track(
            file_path=Path("/music/song.mp3"),
            file_hash="abc123",
        )
        assert track.file_path == Path("/music/song.mp3")
        assert track.file_hash == "abc123"
        assert track.title is None
        assert track.tags == []

    def test_track_full_metadata(self) -> None:
        """Track stores all metadata fields."""
        track = Track(
            file_path=Path("/music/song.mp3"),
            file_hash="abc123",
            title="Strobe",
            artist="deadmau5",
            album="For Lack of a Better Name",
            album_artist="deadmau5",
            label="mau5trap",
            remixer=None,
            composer="Joel Zimmerman",
            original_artist=None,
            isrc="USUG10900256",
            release_date=date(2009, 9, 22),
            year=2009,
            duration_seconds=637.0,
            track_number=10,
            bitrate=320,
            sample_rate=44100,
            codec="mp3",
            bpm=128.0,
            bpm_source="analyzed",
            key="Fm",
            key_camelot="4A",
            energy=0.65,
            danceability=0.72,
            tags=["progressive house", "melodic", "classic"],
            rating=5,
            color="#FF5500",
            play_count=42,
            comment="Epic breakdown at 5:00",
        )
        assert track.title == "Strobe"
        assert track.label == "mau5trap"
        assert track.isrc == "USUG10900256"
        assert track.release_date == date(2009, 9, 22)
        assert track.bpm == 128.0
        assert track.key_camelot == "4A"
        assert track.tags == ["progressive house", "melodic", "classic"]
        assert track.rating == 5

    def test_track_tags_are_list(self) -> None:
        """Tags default to empty list."""
        track = Track(file_path=Path("/music/song.mp3"), file_hash="abc")
        assert isinstance(track.tags, list)
        assert track.tags == []

    def test_track_energy_validation(self) -> None:
        """Energy must be between 0 and 1."""
        with pytest.raises(ValueError, match="less than or equal to 1"):
            Track(
                file_path=Path("/music/song.mp3"),
                file_hash="abc",
                energy=1.5,
            )

    def test_track_rating_validation(self) -> None:
        """Rating must be between 1 and 5."""
        with pytest.raises(ValueError, match="less than or equal to 5"):
            Track(
                file_path=Path("/music/song.mp3"),
                file_hash="abc",
                rating=6,
            )
