"""Tests for get_candidate_pool MCP tool."""

import json
from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.mcp.tools import _get_candidate_pool
from ai_crate_digger.storage import Database


@pytest.fixture
def db_with_tracks(tmp_dir):
    """Create database with diverse test tracks."""
    db_path = tmp_dir / "test.db"
    db = Database(db_path)
    db.init()

    # Create diverse tracks for filtering
    tracks = [
        # Afro House tracks
        Track(
            file_path=Path("/music/afro1.mp3"),
            file_hash="afro1hash",
            title="Afro Track 1",
            artist="DJ Afro",
            bpm=120.0,
            key_camelot="8A",
            energy=0.8,
            danceability=0.85,
            tags=["Afro House"],
            duration_seconds=300.0,
        ),
        Track(
            file_path=Path("/music/afro2.mp3"),
            file_hash="afro2hash",
            title="Afro Track 2",
            artist="DJ Afro",
            bpm=122.0,
            key_camelot="9A",
            energy=0.75,
            danceability=0.8,
            tags=["Afro House"],
            duration_seconds=320.0,
        ),
        # Tech House tracks
        Track(
            file_path=Path("/music/tech1.mp3"),
            file_hash="tech1hash",
            title="Tech Track 1",
            artist="Tech DJ",
            bpm=125.0,
            key_camelot="8A",
            energy=0.9,
            danceability=0.75,
            tags=["Tech House"],
            duration_seconds=280.0,
        ),
        Track(
            file_path=Path("/music/tech2.mp3"),
            file_hash="tech2hash",
            title="Tech Track 2",
            artist="Tech DJ",
            bpm=128.0,
            key_camelot="7A",
            energy=0.85,
            danceability=0.7,
            tags=["Tech House"],
            duration_seconds=290.0,
        ),
        # Stem file (should be excluded)
        Track(
            file_path=Path("/music/stem.stem.mp4"),
            file_hash="stemhash",
            title="Stem Track",
            artist="Stem Artist",
            bpm=126.0,
            key_camelot="8A",
            energy=0.8,
            danceability=0.8,
            tags=["Tech House"],
            duration_seconds=300.0,
        ),
        # Unknown artist (should be excluded)
        Track(
            file_path=Path("/music/unknown.mp3"),
            file_hash="unknownhash",
            title="Unknown Track",
            artist=None,
            bpm=124.0,
            key_camelot="8A",
            energy=0.7,
            danceability=0.75,
            tags=["Tech House"],
            duration_seconds=310.0,
        ),
        # Track outside BPM range
        Track(
            file_path=Path("/music/slow.mp3"),
            file_hash="slowhash",
            title="Slow Track",
            artist="Slow DJ",
            bpm=110.0,
            key_camelot="8A",
            energy=0.6,
            danceability=0.65,
            tags=["Afro House"],
            duration_seconds=330.0,
        ),
        # Track with incompatible key (far from 8A)
        Track(
            file_path=Path("/music/offkey.mp3"),
            file_hash="offkeyhash",
            title="Off Key Track",
            artist="Off Key DJ",
            bpm=125.0,
            key_camelot="3B",
            energy=0.8,
            danceability=0.8,
            tags=["Afro House"],
            duration_seconds=300.0,
        ),
        # Track with no tags (should be excluded when filtering by tags)
        Track(
            file_path=Path("/music/notags.mp3"),
            file_hash="notagshash",
            title="No Tags Track",
            artist="No Tags DJ",
            bpm=123.0,
            key_camelot="8A",
            energy=0.75,
            danceability=0.7,
            tags=[],
            duration_seconds=295.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    yield db
    db.close()


@pytest.mark.asyncio
async def test_get_candidate_pool_basic_filtering(db_with_tracks):
    """Test basic tag filtering."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    # Should get: afro1, afro2, slow, offkey (all have "Afro House" tag)
    # Should NOT get: tech1, tech2 (Tech House tag), stem (excluded), unknown (no artist)
    assert len(data) == 4
    assert all(t["artist"] is not None for t in data)  # Unknown artists excluded
    assert all(".stem." not in str(t["title"]).lower() for t in data)  # Stems excluded
    # Verify all have Afro House tag
    assert all("Afro House" in t["tags"] for t in data)


@pytest.mark.asyncio
async def test_get_candidate_pool_bpm_filtering(db_with_tracks):
    """Test BPM range filtering."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=120.0,
        bpm_max=126.0,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    # Should get: afro1 (120), afro2 (122), tech1 (125), offkey (125)
    # Should NOT get: tech2 (128), slow (110), stem (excluded), unknown (no artist)
    assert len(data) == 4
    assert all(120.0 <= t["bpm"] <= 126.0 for t in data)


@pytest.mark.asyncio
async def test_get_candidate_pool_energy_filtering(db_with_tracks):
    """Test energy minimum filtering."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=0.8,
        reference_key=None,
        exclude_hashes=[],
        sort_by="energy_desc",
        limit=10,
    )

    data = json.loads(result)
    # Should get tracks with energy >= 0.8: tech1 (0.9), tech2 (0.85), afro1 (0.8), offkey (0.8)
    # Should NOT get: afro2 (0.75), slow (0.6)
    assert len(data) == 4
    assert all(t["energy"] >= 0.8 for t in data)


@pytest.mark.asyncio
async def test_get_candidate_pool_key_compatibility(db_with_tracks):
    """Test harmonic key filtering."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key="8A",
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    # Compatible with 8A: 8A (same), 7A, 9A (adjacent), 8B (relative)
    # Should include: afro1 (8A), afro2 (9A), tech1 (8A), tech2 (7A)
    # Should NOT include: offkey (3B - distance > 1)
    keys = {t["key"] for t in data}
    assert "3B" not in keys  # Incompatible key excluded


@pytest.mark.asyncio
async def test_get_candidate_pool_exclude_hashes(db_with_tracks):
    """Test excluding specific hashes."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=["afro1hash"],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    hashes = {t["hash"] for t in data}
    assert "afro1hash" not in hashes


@pytest.mark.asyncio
async def test_get_candidate_pool_sort_bpm_asc(db_with_tracks):
    """Test sorting by BPM ascending."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=120.0,
        bpm_max=130.0,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    bpms = [t["bpm"] for t in data]
    assert bpms == sorted(bpms)  # Ascending order


@pytest.mark.asyncio
async def test_get_candidate_pool_sort_energy_desc(db_with_tracks):
    """Test sorting by energy descending."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Tech House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="energy_desc",
        limit=10,
    )

    data = json.loads(result)
    energies = [t["energy"] for t in data]
    assert energies == sorted(energies, reverse=True)  # Descending order


@pytest.mark.asyncio
async def test_get_candidate_pool_sort_random(db_with_tracks):
    """Test random sorting (just verify it doesn't crash)."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="random",
        limit=10,
    )

    data = json.loads(result)
    assert len(data) > 0
    # Can't test randomness, just ensure it returns valid data


@pytest.mark.asyncio
async def test_get_candidate_pool_limit(db_with_tracks):
    """Test result limit."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House", "Tech House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=2,
    )

    data = json.loads(result)
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_get_candidate_pool_compact_json_format(db_with_tracks):
    """Test that output contains only required fields."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["Afro House"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    assert len(data) > 0

    # Check required fields
    required_fields = {
        "hash",
        "artist",
        "title",
        "bpm",
        "key",
        "energy",
        "danceability",
        "tags",
        "duration_sec",
    }
    for track in data:
        assert set(track.keys()) == required_fields


@pytest.mark.asyncio
async def test_get_candidate_pool_empty_result(db_with_tracks):
    """Test handling empty results."""
    result = await _get_candidate_pool(
        db_with_tracks,
        tags=["NonExistentTag"],
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_asc",
        limit=10,
    )

    data = json.loads(result)
    assert data == []
