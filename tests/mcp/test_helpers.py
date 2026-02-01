"""Test helper functions for AI playlist tools."""

from dj_catalog.core.models import Track
from dj_catalog.mcp.tools import _compact_track, _sort_candidates, _strip_remix_markers


def test_strip_remix_markers():
    """Test stripping parentheses and brackets from titles."""
    assert _strip_remix_markers("Track Name (Remix)") == "track name"
    assert _strip_remix_markers("Track [VIP]") == "track"
    assert _strip_remix_markers("Track  (Extended)  [2023]") == "track"
    assert _strip_remix_markers("Simple Title") == "simple title"
    assert _strip_remix_markers("Multiple (Remix) [VIP] (Edit)") == "multiple"


def test_compact_track(sample_track):
    """Test compact track representation."""
    result = _compact_track(sample_track)
    assert result == {
        "title": sample_track.title,
        "bpm": sample_track.bpm,
        "key": sample_track.key_camelot,
        "tags": sample_track.tags,
    }


def test_sort_candidates_random():
    """Test random sorting."""
    tracks = [
        Track(file_path="/a.mp3", file_hash="aaa", bpm=120.0),
        Track(file_path="/b.mp3", file_hash="bbb", bpm=125.0),
        Track(file_path="/c.mp3", file_hash="ccc", bpm=130.0),
    ]
    result = _sort_candidates(tracks, "random")
    assert len(result) == 3
    # Can't test randomness reliably, just check all tracks present
    assert {t.file_hash for t in result} == {"aaa", "bbb", "ccc"}


def test_sort_candidates_bpm_asc():
    """Test BPM ascending sort."""
    tracks = [
        Track(file_path="/a.mp3", file_hash="aaa", bpm=130.0),
        Track(file_path="/b.mp3", file_hash="bbb", bpm=120.0),
        Track(file_path="/c.mp3", file_hash="ccc", bpm=125.0),
    ]
    result = _sort_candidates(tracks, "bpm_asc")
    assert [t.bpm for t in result] == [120.0, 125.0, 130.0]


def test_sort_candidates_bpm_desc():
    """Test BPM descending sort."""
    tracks = [
        Track(file_path="/a.mp3", file_hash="aaa", bpm=120.0),
        Track(file_path="/b.mp3", file_hash="bbb", bpm=125.0),
        Track(file_path="/c.mp3", file_hash="ccc", bpm=130.0),
    ]
    result = _sort_candidates(tracks, "bpm_desc")
    assert [t.bpm for t in result] == [130.0, 125.0, 120.0]


def test_sort_candidates_energy_desc():
    """Test energy descending sort."""
    tracks = [
        Track(file_path="/a.mp3", file_hash="aaa", energy=0.5),
        Track(file_path="/b.mp3", file_hash="bbb", energy=0.9),
        Track(file_path="/c.mp3", file_hash="ccc", energy=0.7),
    ]
    result = _sort_candidates(tracks, "energy_desc")
    assert [t.energy for t in result] == [0.9, 0.7, 0.5]


def test_sort_candidates_danceability_desc():
    """Test danceability descending sort."""
    tracks = [
        Track(file_path="/a.mp3", file_hash="aaa", danceability=0.6),
        Track(file_path="/b.mp3", file_hash="bbb", danceability=0.8),
        Track(file_path="/c.mp3", file_hash="ccc", danceability=0.4),
    ]
    result = _sort_candidates(tracks, "danceability_desc")
    assert [t.danceability for t in result] == [0.8, 0.6, 0.4]
