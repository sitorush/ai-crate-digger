"""Tests for track filters."""

from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.playlist.filters import TrackFilter, filter_tracks


@pytest.fixture
def sample_tracks() -> list[Track]:
    """Sample tracks for testing."""
    return [
        Track(
            file_path=Path("/1.mp3"), file_hash="h1", tags=["techno", "dark"], bpm=130.0, rating=5
        ),
        Track(
            file_path=Path("/2.mp3"), file_hash="h2", tags=["house", "vocal"], bpm=124.0, rating=3
        ),
        Track(
            file_path=Path("/3.mp3"),
            file_hash="h3",
            tags=["techno", "melodic"],
            bpm=128.0,
            rating=4,
        ),
        Track(file_path=Path("/4.mp3"), file_hash="h4", tags=["trance"], bpm=138.0, artist="Armin"),
    ]


class TestTrackFilter:
    """Tests for TrackFilter."""

    def test_empty_filter_matches_all(self, sample_tracks: list[Track]) -> None:
        """Empty filter matches all tracks."""
        f = TrackFilter()
        assert all(f.matches(t) for t in sample_tracks)

    def test_include_tags(self, sample_tracks: list[Track]) -> None:
        """Include tags filters correctly."""
        f = TrackFilter(include_tags=["techno"])
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 2

    def test_exclude_tags(self, sample_tracks: list[Track]) -> None:
        """Exclude tags filters correctly."""
        f = TrackFilter(include_tags=["techno"], exclude_tags=["dark"])
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 1
        assert results[0].file_hash == "h3"

    def test_bpm_range(self, sample_tracks: list[Track]) -> None:
        """BPM range filters correctly."""
        f = TrackFilter(bpm_range=(125, 132))
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 2

    def test_rating_min(self, sample_tracks: list[Track]) -> None:
        """Minimum rating filters correctly."""
        f = TrackFilter(rating_min=4)
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 2

    def test_exclude_artists(self, sample_tracks: list[Track]) -> None:
        """Exclude artists works."""
        f = TrackFilter(exclude_artists=["Armin"])
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 3

    def test_combined_filters(self, sample_tracks: list[Track]) -> None:
        """Multiple filters combine correctly."""
        f = TrackFilter(
            include_tags=["techno"],
            exclude_tags=["dark"],
            bpm_range=(125, 135),
            rating_min=4,
        )
        results = filter_tracks(sample_tracks, f)
        assert len(results) == 1
        assert results[0].file_hash == "h3"
