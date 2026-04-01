"""Integration test for AI playlist workflow."""

import json
from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.mcp.tools import _build_playlist, _get_candidate_pool, _validate_playlist_order
from ai_crate_digger.storage import Database


@pytest.fixture
def db_with_workflow_tracks(tmp_path):
    """Create database with diverse tracks for workflow testing."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        # House tracks (compatible)
        Track(
            file_path=Path("/music/house1.mp3"),
            file_hash="house001",
            title="House Track 1",
            artist="DJ House",
            bpm=128.0,
            key_camelot="8A",
            energy=0.8,
            danceability=0.7,
            tags=["House", "Deep House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/house2.mp3"),
            file_hash="house002",
            title="House Track 2",
            artist="DJ House",
            bpm=127.0,
            key_camelot="8B",
            energy=0.7,
            danceability=0.8,
            tags=["House", "Tech House"],
            duration_seconds=200.0,
        ),
        Track(
            file_path=Path("/music/house3.mp3"),
            file_hash="house003",
            title="House Track 3",
            artist="DJ House",
            bpm=126.0,
            key_camelot="9A",
            energy=0.6,
            danceability=0.75,
            tags=["House"],
            duration_seconds=190.0,
        ),
        # Techno track (incompatible)
        Track(
            file_path=Path("/music/techno1.mp3"),
            file_hash="techno001",
            title="Techno Track",
            artist="DJ Techno",
            bpm=140.0,
            key_camelot="1A",
            energy=0.95,
            danceability=0.6,
            tags=["Techno"],
            duration_seconds=240.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    return db


@pytest.mark.asyncio
async def test_ai_workflow_get_candidates_to_export(db_with_workflow_tracks, tmp_path):
    """Test full AI workflow: get_candidate_pool → validate → build."""

    # Step 1: Get candidate pool filtered by tags and BPM
    pool_result = await _get_candidate_pool(
        db_with_workflow_tracks,
        tags=["House"],
        bpm_min=125.0,
        bpm_max=130.0,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="bpm_desc",
        limit=50,
    )
    pool_data = json.loads(pool_result)

    # Should get 3 house tracks, sorted by BPM descending
    assert len(pool_data) == 3
    assert pool_data[0]["bpm"] > pool_data[1]["bpm"] > pool_data[2]["bpm"]

    # Step 2: AI picks tracks (simulated - just use first 2)
    selected_hashes = [pool_data[0]["hash"], pool_data[1]["hash"]]

    # Step 3: Validate the order
    validate_args = {"hashes": selected_hashes}
    validate_result = await _validate_playlist_order(db_with_workflow_tracks, validate_args)
    validate_data = json.loads(validate_result[0].text)

    # Should be valid (compatible BPMs and keys)
    assert validate_data["valid"] is True
    assert validate_data["track_count"] == 2

    # Step 4: Build and export playlist
    output_path = tmp_path / "ai_playlist.m3u"
    build_args = {
        "name": "AI Generated Playlist",
        "hashes": selected_hashes,
        "output_path": str(output_path),
        "validate": True,
    }
    build_result = await _build_playlist(db_with_workflow_tracks, build_args)
    build_data = json.loads(build_result[0].text)

    # Should succeed and include validation
    assert build_data["success"] is True
    assert build_data["track_count"] == 2
    assert "validation" in build_data
    assert build_data["validation"]["valid"] is True
    assert output_path.exists()


@pytest.mark.asyncio
async def test_ai_workflow_with_incompatible_tracks(db_with_workflow_tracks, tmp_path):
    """Test workflow catches incompatible tracks."""

    # Step 1: Get mixed tracks (house + techno)
    pool_result = await _get_candidate_pool(
        db_with_workflow_tracks,
        tags=None,
        bpm_min=None,
        bpm_max=None,
        energy_min=None,
        reference_key=None,
        exclude_hashes=[],
        sort_by="random",
        limit=10,
    )
    pool_data = json.loads(pool_result)

    # Step 2: AI picks incompatible tracks (house -> techno)
    # Specifically select house001 (8A) for deterministic testing
    house_track = next(t for t in pool_data if t["hash"] == "house001")
    techno_track = next(t for t in pool_data if "Techno" in t["tags"])
    selected_hashes = [house_track["hash"], techno_track["hash"]]

    # Step 3: Validate should catch issues
    validate_args = {"hashes": selected_hashes}
    validate_result = await _validate_playlist_order(db_with_workflow_tracks, validate_args)
    validate_data = json.loads(validate_result[0].text)

    # Under new validation rules:
    # - 8A→1A is distance 5 with same mode = semitone shift (info severity)
    # - BPM jump of 12 = warning
    # - Tag mismatch = warning
    # Only errors make valid=False, so this playlist is technically valid but has issues
    assert validate_data["valid"] is True  # No error-severity issues
    assert (
        len(validate_data["issues"]) >= 2
    )  # BPM jump (warning) + tag mismatch (warning) + semitone (info)

    # Step 4: AI would fix issues here (simulated - skip export)
