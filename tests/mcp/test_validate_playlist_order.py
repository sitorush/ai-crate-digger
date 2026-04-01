"""Test validate_playlist_order MCP tool."""

import json
from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.mcp.tools import _validate_playlist_order
from ai_crate_digger.storage import Database


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
    # BPM jumps are warnings, not errors - they don't affect valid field
    # But this playlist also has a key clash (8A -> 12A, distance 4) which IS an error
    assert data["valid"] is False  # Due to key clash, not BPM jump
    bpm_issues = [i for i in data["issues"] if i["type"] == "bpm_jump"]
    assert len(bpm_issues) == 1
    assert "7.0" in bpm_issues[0]["detail"]
    assert bpm_issues[0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_validate_key_clash(db_with_playlist_tracks):
    """Test key clash detection (distance 3-6 are errors)."""
    args = {"hashes": ["hash001", "hash003"]}  # 8A -> 12A (distance 4)
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert data["valid"] is False
    key_issues = [i for i in data["issues"] if i["type"] == "key_clash"]
    assert len(key_issues) == 1
    assert key_issues[0]["severity"] == "error"
    assert "distance 4" in key_issues[0]["detail"]


@pytest.mark.asyncio
async def test_validate_tag_mismatch(db_with_playlist_tracks):
    """Test tag mismatch detection (zero overlap)."""
    args = {"hashes": ["hash001", "hash003"]}  # House -> Techno
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    tag_issues = [i for i in data["issues"] if i["type"] == "tag_mismatch"]
    assert len(tag_issues) == 1
    assert tag_issues[0]["severity"] == "warning"
    # Tag mismatches alone don't make valid=False (but this has a key clash too)


@pytest.mark.asyncio
async def test_validate_total_duration(db_with_playlist_tracks):
    """Test total duration calculation."""
    args = {"hashes": ["hash001", "hash002"]}  # 180s + 200s = 380s = 6.33min
    result = await _validate_playlist_order(db_with_playlist_tracks, args)

    data = json.loads(result[0].text)
    assert abs(data["total_duration_min"] - 6.33) < 0.1


@pytest.mark.asyncio
async def test_validate_energy_shift_allowed(tmp_path):
    """Test distance 2 energy shift is allowed (no flag)."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="hash001",
            title="Track 1",
            artist="Artist",
            bpm=128.0,
            key_camelot="4A",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="hash002",
            title="Track 2",
            artist="Artist",
            bpm=128.0,
            key_camelot="6A",  # Distance 2 from 4A (energy shift)
            tags=["House"],
            duration_seconds=180.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    args = {"hashes": ["hash001", "hash002"]}
    result = await _validate_playlist_order(db, args)

    data = json.loads(result[0].text)
    assert data["valid"] is True  # Distance 2 is allowed
    key_issues = [i for i in data["issues"] if "key" in i["type"]]
    assert len(key_issues) == 0  # No key-related issues


@pytest.mark.asyncio
async def test_validate_diagonal_allowed(tmp_path):
    """Test diagonal moves (number +/-1 with A/B flip) are allowed."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="hash001",
            title="Track 1",
            artist="Artist",
            bpm=128.0,
            key_camelot="1B",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="hash002",
            title="Track 2",
            artist="Artist",
            bpm=128.0,
            key_camelot="2A",  # Diagonal from 1B
            tags=["House"],
            duration_seconds=180.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    args = {"hashes": ["hash001", "hash002"]}
    result = await _validate_playlist_order(db, args)

    data = json.loads(result[0].text)
    assert data["valid"] is True  # Diagonal is allowed
    key_issues = [i for i in data["issues"] if "key" in i["type"]]
    assert len(key_issues) == 0  # No key-related issues


@pytest.mark.asyncio
async def test_validate_semitone_shift_info(tmp_path):
    """Test distance 7 semitone shift flagged as info, not error."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="hash001",
            title="Track 1",
            artist="Artist",
            bpm=128.0,
            key_camelot="4A",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="hash002",
            title="Track 2",
            artist="Artist",
            bpm=128.0,
            key_camelot="11A",  # Distance 7 from 4A (semitone shift)
            tags=["House"],
            duration_seconds=180.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    args = {"hashes": ["hash001", "hash002"]}
    result = await _validate_playlist_order(db, args)

    data = json.loads(result[0].text)
    assert data["valid"] is True  # Semitone shift doesn't make valid=False
    semitone_issues = [i for i in data["issues"] if i["type"] == "key_semitone"]
    assert len(semitone_issues) == 1
    assert semitone_issues[0]["severity"] == "info"
    assert "distance 5" in semitone_issues[0]["detail"]


@pytest.mark.asyncio
async def test_validate_warnings_dont_affect_valid(tmp_path):
    """Test that warnings (BPM jump, tag mismatch) don't make valid=False."""
    db = Database(tmp_path / "test.db")
    db.init()

    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="hash001",
            title="Track 1",
            artist="Artist",
            bpm=120.0,
            key_camelot="8A",
            tags=["House"],
            duration_seconds=180.0,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="hash002",
            title="Track 2",
            artist="Artist",
            bpm=128.0,  # BPM jump of 8
            key_camelot="8B",  # Compatible key (distance 1)
            tags=["Techno"],  # Tag mismatch
            duration_seconds=180.0,
        ),
    ]

    for track in tracks:
        db.upsert_track(track)

    args = {"hashes": ["hash001", "hash002"]}
    result = await _validate_playlist_order(db, args)

    data = json.loads(result[0].text)
    assert data["valid"] is True  # Warnings don't affect validity
    assert len(data["issues"]) == 2  # BPM jump + tag mismatch
    assert all(i["severity"] == "warning" for i in data["issues"])
