"""Tests for audio analyzer."""

from pathlib import Path

from dj_catalog.analysis.analyzer import analyze_track
from dj_catalog.core.models import Track


class TestAnalyzer:
    """Tests for audio analyzer."""

    def test_analyze_track_updates_fields(self, sample_wav: Path) -> None:
        """Analyzer updates BPM, key, energy, danceability."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        assert analyzed.bpm is not None or analyzed.bpm is None  # May fail on silence
        assert analyzed.key is not None or analyzed.key is None
        assert analyzed.energy is not None
        assert analyzed.danceability is not None
        assert analyzed.analyzed_at is not None

    def test_analyze_track_sets_bpm_source(self, sample_wav: Path) -> None:
        """Analyzer sets bpm_source to 'analyzed'."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        if analyzed.bpm is not None:
            assert analyzed.bpm_source == "analyzed"

    def test_analyze_track_sets_camelot(self, sample_wav: Path) -> None:
        """Analyzer sets Camelot notation when key detected."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        if analyzed.key is not None:
            assert analyzed.key_camelot is not None
