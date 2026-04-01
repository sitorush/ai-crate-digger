"""Tests for playlist export."""

from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.playlist.export import export_m3u, export_playlist, export_rekordbox_xml
from ai_crate_digger.playlist.generator import Playlist


@pytest.fixture
def sample_playlist() -> Playlist:
    """Sample playlist for testing."""
    tracks = [
        Track(
            file_path=Path("/music/track1.mp3"),
            file_hash="h1",
            title="First Track",
            artist="Artist One",
            album="Album",
            bpm=128.0,
            key="Am",
            duration_seconds=240,
            tags=["techno"],
            rating=4,
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            file_hash="h2",
            title="Second Track",
            artist="Artist Two",
            bpm=130.0,
            duration_seconds=300,
        ),
    ]
    return Playlist(name="Test Playlist", tracks=tracks, total_duration=540)


class TestM3UExport:
    """Tests for M3U export."""

    def test_creates_valid_m3u(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Creates valid M3U file."""
        output = tmp_dir / "playlist.m3u"
        export_m3u(sample_playlist, output)

        content = output.read_text()
        assert content.startswith("#EXTM3U")
        assert "#PLAYLIST:Test Playlist" in content

    def test_includes_track_info(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Includes track information."""
        output = tmp_dir / "playlist.m3u"
        export_m3u(sample_playlist, output)

        content = output.read_text()
        assert "Artist One - First Track" in content
        assert "/music/track1.mp3" in content

    def test_handles_missing_metadata(self, tmp_dir: Path) -> None:
        """Handles tracks with missing metadata."""
        playlist = Playlist(
            name="Minimal",
            tracks=[Track(file_path=Path("/song.mp3"), file_hash="h1")],
            total_duration=0,
        )
        output = tmp_dir / "minimal.m3u"
        export_m3u(playlist, output)

        content = output.read_text()
        assert "Unknown - song" in content


class TestRekordboxExport:
    """Tests for Rekordbox XML export."""

    def test_creates_valid_xml(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Creates valid XML file."""
        output = tmp_dir / "playlist.xml"
        export_rekordbox_xml(sample_playlist, output)

        content = output.read_text()
        assert "<?xml version" in content
        assert "<DJ_PLAYLISTS" in content

    def test_includes_collection(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Includes track collection."""
        output = tmp_dir / "playlist.xml"
        export_rekordbox_xml(sample_playlist, output)

        content = output.read_text()
        assert 'COLLECTION Entries="2"' in content
        assert 'Name="First Track"' in content

    def test_includes_bpm_and_key(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Includes BPM and key."""
        output = tmp_dir / "playlist.xml"
        export_rekordbox_xml(sample_playlist, output)

        content = output.read_text()
        assert 'AverageBpm="128.00"' in content
        assert 'Tonality="Am"' in content


class TestExportPlaylist:
    """Tests for export_playlist dispatcher."""

    def test_m3u_format(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Exports M3U format."""
        output = tmp_dir / "test.m3u"
        export_playlist(sample_playlist, output, output_format="m3u")

        assert output.exists()
        assert output.read_text().startswith("#EXTM3U")

    def test_rekordbox_format(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Exports Rekordbox format."""
        output = tmp_dir / "test.xml"
        export_playlist(sample_playlist, output, output_format="rekordbox")

        assert output.exists()
        assert "<DJ_PLAYLISTS" in output.read_text()

    def test_unknown_format_raises(self, sample_playlist: Playlist, tmp_dir: Path) -> None:
        """Unknown format raises error."""
        with pytest.raises(ValueError, match="Unknown export format"):
            export_playlist(sample_playlist, tmp_dir / "test.txt", output_format="unknown")
