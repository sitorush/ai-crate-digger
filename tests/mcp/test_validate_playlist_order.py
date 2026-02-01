"""Test validate_playlist_order MCP tool."""

import json
from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.mcp.tools import _validate_playlist_order
from dj_catalog.storage import Database


@pytest.fixture
def db_with_playlist_tracks(tmp_path):
    """Create database with tracks for playlist validation."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="hash001",
            title="Track One",
            artist="Artist A",
            bpm=128.0,
            key_camelot="8A",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="hash002",
            title="Track Two",
            artist="Artist B",
            bpm=127.0,
            key_camelot="8B",
            tags=["House"],
            duration_seconds=200.0,
        ),
        Track(
            file_path=Path("/music/track3.mp3"),
            file_hash="hash003",
            title="Track Three",
            artist="Artist C",
            bpm=135.0,  # Big BPM jump
            key_camelot="12A",  # Key clash
            tags=["Techno"],  # Tag mismatch
            duration_seconds=240.0,
        ),
        Track(
            file_path=Path("/music/remix1.mp3"),
            file_hash="hash004",
            title="Same Song (Remix A)",
            artist="Artist D",
            bpm=128.0,
            key_camelot="8A",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/remix2.mp3"),
            file_hash="hash005",
            title="Same Song (Remix B)",
            artist="Artist E",
            bpm=128.0,
            key_camelot="8A",
            tags=["House"],
            duration_seconds=190.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    return db


@pytest.mark.asyncio
async def test_validate_playlist_order_valid(db_with_playlist_tracks):
    """Test validation passes for clean playlist."""
    args = {"hashes": ["hash001", "hash002"]}
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is True
    assert data["track_count"] == 2
    assert data["issues"] == []
    assert data["duplicates"] == []
    assert data["same_song_duplicates"] == []


@pytest.mark.asyncio
async def test_validate_exact_duplicates(db_with_playlist_tracks):
    """Test exact duplicate detection."""
    args = {"hashes": ["hash001", "hash002", "hash001"]}
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is False
    assert len(data["duplicates"]) == 1
    assert data["duplicates"][0]["hash"] == "hash001"
    assert data["duplicates"][0]["positions"] == [0, 2]


@pytest.mark.asyncio
async def test_validate_same_song_duplicates(db_with_playlist_tracks):
    """Test same-song duplicate detection (different remixes)."""
    args = {"hashes": ["hash004", "hash005"]}
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is False
    assert len(data["same_song_duplicates"]) == 1
    dup = data["same_song_duplicates"][0]
    assert dup["base_title"] == "same song"
    assert len(dup["tracks"]) == 2


@pytest.mark.asyncio
async def test_validate_bpm_jump(db_with_playlist_tracks):
    """Test BPM jump detection (threshold > 2.0)."""
    args = {"hashes": ["hash001", "hash003"]}  # 128 -> 135 BPM
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is False
    bpm_issues = [i for i in data["issues"] if i["type"] == "bpm_jump"]
    assert len(bpm_issues) == 1
    assert "7.0" in bpm_issues[0]["detail"]


@pytest.mark.asyncio
async def test_validate_key_clash(db_with_playlist_tracks):
    """Test key clash detection (harmonic_distance > 1)."""
    args = {"hashes": ["hash001", "hash003"]}  # 8A -> 12A
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is False
    key_issues = [i for i in data["issues"] if i["type"] == "key_clash"]
    assert len(key_issues) == 1


@pytest.mark.asyncio
async def test_validate_tag_mismatch(db_with_playlist_tracks):
    """Test tag mismatch detection (zero overlap)."""
    args = {"hashes": ["hash001", "hash003"]}  # House -> Techno
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    tag_issues = [i for i in data["issues"] if i["type"] == "tag_mismatch"]
    assert len(tag_issues) == 1


@pytest.mark.asyncio
async def test_validate_total_duration(db_with_playlist_tracks):
    """Test total duration calculation."""
    args = {"hashes": ["hash001", "hash002"]}  # 180s + 200s = 380s = 6.33min
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert abs(data["total_duration_min"] - 6.33) < 0.1
