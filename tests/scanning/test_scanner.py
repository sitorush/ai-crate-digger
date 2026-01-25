"""Tests for file scanner."""

from pathlib import Path

import pytest

from dj_catalog.scanning.scanner import SUPPORTED_EXTENSIONS, scan_directory


class TestScanner:
    """Tests for file scanner."""

    def test_supported_extensions(self) -> None:
        """All common audio formats supported."""
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".m4a" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".aiff" in SUPPORTED_EXTENSIONS
        assert ".ogg" in SUPPORTED_EXTENSIONS

    def test_scan_directory_finds_audio_files(self, tmp_dir: Path) -> None:
        """Scanner finds audio files recursively."""
        # Create test files
        (tmp_dir / "song1.mp3").touch()
        (tmp_dir / "song2.flac").touch()
        (tmp_dir / "nested").mkdir()
        (tmp_dir / "nested" / "song3.m4a").touch()
        (tmp_dir / "readme.txt").touch()  # Should be ignored

        files = list(scan_directory(tmp_dir))

        assert len(files) == 3
        extensions = {f.suffix for f in files}
        assert extensions == {".mp3", ".flac", ".m4a"}

    def test_scan_directory_skips_hidden(self, tmp_dir: Path) -> None:
        """Scanner skips hidden files and directories."""
        (tmp_dir / "visible.mp3").touch()
        (tmp_dir / ".hidden.mp3").touch()
        (tmp_dir / ".hidden_dir").mkdir()
        (tmp_dir / ".hidden_dir" / "song.mp3").touch()

        files = list(scan_directory(tmp_dir))

        assert len(files) == 1
        assert files[0].name == "visible.mp3"

    def test_scan_directory_non_recursive(self, tmp_dir: Path) -> None:
        """Scanner can run non-recursively."""
        (tmp_dir / "top.mp3").touch()
        (tmp_dir / "nested").mkdir()
        (tmp_dir / "nested" / "deep.mp3").touch()

        files = list(scan_directory(tmp_dir, recursive=False))

        assert len(files) == 1
        assert files[0].name == "top.mp3"

    def test_scan_directory_invalid_path(self, tmp_dir: Path) -> None:
        """Scanner raises error for invalid directory."""
        with pytest.raises(ValueError, match="Not a directory"):
            list(scan_directory(tmp_dir / "nonexistent"))
