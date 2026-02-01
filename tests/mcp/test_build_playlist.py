"""Test build_playlist MCP tool."""

import json
from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.mcp.tools import _build_playlist
from dj_catalog.storage import Database


@pytest.fixture
def db_with_export_tracks(tmp_path):
    """Create database with tracks for export testing."""
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
    ]

    for track in tracks:
        db.upsert_track(track)

    return db


@pytest.mark.asyncio
async def test_build_playlist_with_path(db_with_export_tracks, tmp_path):
    """Test export with user-provided path."""
    output_path = tmp_path / "test_playlist.m3u"
    args = {
        "name": "Test Playlist",
        "hashes": ["hash001", "hash002"],
        "output_path": str(output_path),
        "validate": False,
    }
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["track_count"] == 2
    assert Path(data["output_path"]) == output_path
    assert output_path.exists()


@pytest.mark.asyncio
async def test_build_playlist_default_path(db_with_export_tracks, tmp_path, monkeypatch):
    """Test export with default path (~/Downloads)."""
    # Mock output_path setting

    monkeypatch.setenv("DJ_CATALOG_OUTPUT_PATH", str(tmp_path))

    args = {"name": "Test Playlist", "hashes": ["hash001", "hash002"], "validate": False}
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert tmp_path in Path(data["output_path"]).parents


@pytest.mark.asyncio
async def test_build_playlist_with_validation(db_with_export_tracks, tmp_path):
    """Test export with validation enabled."""
    output_path = tmp_path / "test_playlist.m3u"
    args = {
        "name": "Test Playlist",
        "hashes": ["hash001", "hash002"],
        "output_path": str(output_path),
        "validate": True,
    }
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "validation" in data
    assert data["validation"]["valid"] is True


@pytest.mark.asyncio
async def test_build_playlist_rekordbox_format(db_with_export_tracks, tmp_path):
    """Test export to Rekordbox XML format."""
    output_path = tmp_path / "test_playlist.xml"
    args = {
        "name": "Test Playlist",
        "hashes": ["hash001", "hash002"],
        "output_path": str(output_path),
        "format": "rekordbox",
        "validate": False,
    }
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert data["success"] is True
    assert output_path.exists()


@pytest.mark.asyncio
async def test_build_playlist_no_tracks_found(db_with_export_tracks, tmp_path):
    """Test error handling when no tracks found."""
    output_path = tmp_path / "test_playlist.m3u"
    args = {
        "name": "Test Playlist",
        "hashes": ["nonexistent"],
        "output_path": str(output_path),
        "validate": False,
    }
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "error" in data


@pytest.mark.asyncio
async def test_build_playlist_duration_calculation(db_with_export_tracks, tmp_path):
    """Test total duration calculation."""
    output_path = tmp_path / "test_playlist.m3u"
    args = {
        "name": "Test Playlist",
        "hashes": ["hash001", "hash002"],  # 180s + 200s = 380s = 6.33min
        "output_path": str(output_path),
        "validate": False,
    }
    result = await _build_playlist(db_with_export_tracks, args)

    data = json.loads(result[0].text)
    assert abs(data["total_duration_min"] - 6.33) < 0.1
