"""Tests for metadata extractor."""

from pathlib import Path

import pytest

from dj_catalog.core.exceptions import ExtractionError
from dj_catalog.core.models import Track
from dj_catalog.scanning.extractor import (
    _parse_remixer,
    _safe_date,
    _safe_int,
    _safe_str,
    extract_metadata,
)


class TestExtractor:
    """Tests for metadata extractor."""

    def test_extract_metadata_returns_track(self, sample_wav: Path) -> None:
        """Extractor returns Track model."""
        track = extract_metadata(sample_wav)

        assert isinstance(track, Track)
        assert track.file_path == sample_wav
        assert track.file_hash is not None
        assert len(track.file_hash) == 64

    def test_extract_metadata_gets_duration(self, sample_wav: Path) -> None:
        """Extractor gets audio duration."""
        track = extract_metadata(sample_wav)

        assert track.duration_seconds is not None
        assert track.duration_seconds > 0

    def test_extract_metadata_gets_audio_info(self, sample_wav: Path) -> None:
        """Extractor gets audio quality info."""
        track = extract_metadata(sample_wav)

        assert track.sample_rate == 44100
        assert track.codec is not None

    def test_extract_metadata_nonexistent_file(self, tmp_dir: Path) -> None:
        """Raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            extract_metadata(tmp_dir / "nonexistent.mp3")

    def test_extract_metadata_unsupported_format(self, tmp_dir: Path) -> None:
        """Raises error for unsupported file format."""
        txt_file = tmp_dir / "test.txt"
        txt_file.write_text("not audio")
        with pytest.raises(ExtractionError):
            extract_metadata(txt_file)


class TestSafeStr:
    """Tests for _safe_str helper."""

    def test_none(self) -> None:
        assert _safe_str(None) is None

    def test_string(self) -> None:
        assert _safe_str("hello") == "hello"

    def test_list_single(self) -> None:
        assert _safe_str(["one"]) == "one"

    def test_list_multiple(self) -> None:
        assert _safe_str(["first", "second"]) == "first"

    def test_empty_list(self) -> None:
        assert _safe_str([]) is None


class TestSafeInt:
    """Tests for _safe_int helper."""

    def test_none(self) -> None:
        assert _safe_int(None) is None

    def test_string_int(self) -> None:
        assert _safe_int("42") == 42

    def test_track_number_format(self) -> None:
        assert _safe_int("5/12") == 5

    def test_list(self) -> None:
        assert _safe_int(["7"]) == 7

    def test_invalid(self) -> None:
        assert _safe_int("not a number") is None


class TestSafeDate:
    """Tests for _safe_date helper."""

    def test_none(self) -> None:
        assert _safe_date(None) is None

    def test_full_date(self) -> None:
        result = _safe_date("2023-05-15")
        assert result is not None
        assert result.year == 2023
        assert result.month == 5
        assert result.day == 15

    def test_year_only(self) -> None:
        result = _safe_date("2020")
        assert result is not None
        assert result.year == 2020
        assert result.month == 1

    def test_invalid(self) -> None:
        assert _safe_date("not a date") is None

    def test_list(self) -> None:
        result = _safe_date(["2022-01-01"])
        assert result is not None
        assert result.year == 2022


class TestParseRemixer:
    """Tests for _parse_remixer helper."""

    def test_none_title(self) -> None:
        assert _parse_remixer(None, "Artist") is None

    def test_no_remix_pattern(self) -> None:
        assert _parse_remixer("Regular Song", "Artist") is None

    def test_remix_in_parens(self) -> None:
        assert _parse_remixer("Song (DJ Name Remix)", "Original") == "DJ Name"

    def test_rmx_in_brackets(self) -> None:
        assert _parse_remixer("Song [DJ Name RMX]", "Original") == "DJ Name"

    def test_edit_in_parens(self) -> None:
        assert _parse_remixer("Song (DJ Name Edit)", "Original") == "DJ Name"

    def test_bootleg_in_parens(self) -> None:
        assert _parse_remixer("Song (DJ Name Bootleg)", "Original") == "DJ Name"

    def test_remixer_same_as_artist(self) -> None:
        # Should return None if remixer == artist
        assert _parse_remixer("Song (Artist Remix)", "Artist") is None
