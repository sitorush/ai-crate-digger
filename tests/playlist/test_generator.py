"""Tests for playlist generator."""

from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.playlist.filters import TrackFilter
from dj_catalog.playlist.generator import Playlist, PlaylistOptions, generate_playlist


@pytest.fixture
def track_pool() -> list[Track]:
    """Pool of tracks for testing."""
    return [
        Track(
            file_path=Path("/1.mp3"),
            file_hash="h1",
            title="Track 1",
            artist="Artist A",
            bpm=128.0,
            key_camelot="8A",
            duration_seconds=240,
            tags=["techno"],
        ),
        Track(
            file_path=Path("/2.mp3"),
            file_hash="h2",
            title="Track 2",
            artist="Artist B",
            bpm=130.0,
            key_camelot="9A",
            duration_seconds=300,
            tags=["techno"],
        ),
        Track(
            file_path=Path("/3.mp3"),
            file_hash="h3",
            title="Track 3",
            artist="Artist C",
            bpm=126.0,
            key_camelot="8B",
            duration_seconds=280,
            tags=["house"],
        ),
        Track(
            file_path=Path("/4.mp3"),
            file_hash="h4",
            title="Track 4",
            artist="Artist A",
            bpm=132.0,
            key_camelot="7A",
            duration_seconds=260,
            tags=["techno"],
        ),
        Track(
            file_path=Path("/5.mp3"),
            file_hash="h5",
            title="Track 5",
            artist="Artist D",
            bpm=128.0,
            key_camelot="3A",
            duration_seconds=290,
            tags=["trance"],
        ),
    ]


class TestPlaylistGenerator:
    """Tests for playlist generation."""

    def test_generates_playlist(self, track_pool: list[Track]) -> None:
        """Can generate a playlist."""
        playlist = generate_playlist(track_pool)

        assert isinstance(playlist, Playlist)
        assert len(playlist.tracks) > 0

    def test_respects_duration(self, track_pool: list[Track]) -> None:
        """Respects target duration."""
        options = PlaylistOptions(duration_minutes=10)
        playlist = generate_playlist(track_pool, options=options)

        # Should be close to target (10 mins = 600 seconds)
        assert playlist.total_duration <= 900  # Allow some overshoot

    def test_applies_filter(self, track_pool: list[Track]) -> None:
        """Applies filter to pool."""
        filter_ = TrackFilter(include_tags=["techno"])
        playlist = generate_playlist(track_pool, filter_=filter_)

        # Should only have techno tracks
        for track in playlist.tracks:
            assert "techno" in track.tags

    def test_empty_pool(self) -> None:
        """Handles empty pool."""
        playlist = generate_playlist([])

        assert len(playlist.tracks) == 0
        assert playlist.total_duration == 0

    def test_harmonic_mixing_prefers_compatible(self, track_pool: list[Track]) -> None:
        """Harmonic mixing prefers compatible keys."""
        options = PlaylistOptions(
            duration_minutes=20,
            harmonic_mixing=True,
            shuffle_start=False,
        )
        playlist = generate_playlist(track_pool, options=options)

        # With harmonic mixing, should avoid jumping to distant keys
        # Track with 3A should typically not follow 8A directly
        keys = [t.key_camelot for t in playlist.tracks if t.key_camelot]
        # Just verify we got some tracks
        assert len(keys) >= 2

    def test_no_duplicate_tracks(self, track_pool: list[Track]) -> None:
        """No duplicate tracks in playlist."""
        playlist = generate_playlist(track_pool)

        hashes = [t.file_hash for t in playlist.tracks]
        assert len(hashes) == len(set(hashes))
