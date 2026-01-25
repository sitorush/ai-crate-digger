"""Tests for content hasher."""

from pathlib import Path

import pytest

from dj_catalog.scanning.hasher import compute_file_hash


class TestHasher:
    """Tests for content hasher."""

    def test_compute_hash_returns_hex_string(self, tmp_dir: Path) -> None:
        """Hash is a 64-character hex string (SHA-256)."""
        test_file = tmp_dir / "test.mp3"
        test_file.write_bytes(b"test content" * 1000)

        hash_value = compute_file_hash(test_file)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_same_content_same_hash(self, tmp_dir: Path) -> None:
        """Identical content produces identical hash."""
        content = b"identical content" * 1000
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"
        file1.write_bytes(content)
        file2.write_bytes(content)

        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_different_content_different_hash(self, tmp_dir: Path) -> None:
        """Different content produces different hash."""
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"
        file1.write_bytes(b"content A" * 1000)
        file2.write_bytes(b"content B" * 1000)

        assert compute_file_hash(file1) != compute_file_hash(file2)

    def test_hash_uses_first_mb_only(self, tmp_dir: Path) -> None:
        """Hash only reads first 1MB for performance."""
        # Create file larger than 1MB
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"

        # Same first 1MB, different after
        first_mb = b"A" * (1024 * 1024)
        file1.write_bytes(first_mb + b"extra1")
        file2.write_bytes(first_mb + b"extra2")

        # Should have same hash (only first 1MB matters)
        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_hash_nonexistent_file(self, tmp_dir: Path) -> None:
        """Raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            compute_file_hash(tmp_dir / "nonexistent.mp3")
