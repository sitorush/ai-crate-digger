"""Tests for harmonic mixing."""

from dj_catalog.playlist.harmonic import (
    camelot_to_standard,
    get_compatible_keys,
    harmonic_distance,
    is_compatible,
)


class TestCompatibleKeys:
    """Tests for get_compatible_keys."""

    def test_returns_four_keys(self) -> None:
        """Returns 4 compatible keys."""
        keys = get_compatible_keys("8A")
        assert len(keys) == 4

    def test_includes_same_key(self) -> None:
        """Includes the same key."""
        keys = get_compatible_keys("8A")
        assert "8A" in keys

    def test_includes_adjacent_keys(self) -> None:
        """Includes adjacent keys on wheel."""
        keys = get_compatible_keys("8A")
        assert "7A" in keys
        assert "9A" in keys

    def test_includes_relative_major_minor(self) -> None:
        """Includes relative major/minor."""
        keys = get_compatible_keys("8A")
        assert "8B" in keys

    def test_wraparound_at_12(self) -> None:
        """Handles wraparound at 12."""
        keys = get_compatible_keys("12A")
        assert "11A" in keys
        assert "1A" in keys

    def test_wraparound_at_1(self) -> None:
        """Handles wraparound at 1."""
        keys = get_compatible_keys("1B")
        assert "12B" in keys
        assert "2B" in keys

    def test_invalid_key(self) -> None:
        """Returns empty for invalid key."""
        assert get_compatible_keys("X") == []
        assert get_compatible_keys("") == []
        assert get_compatible_keys(None) == []


class TestCamelotToStandard:
    """Tests for camelot_to_standard."""

    def test_converts_minor(self) -> None:
        """Converts minor keys."""
        assert camelot_to_standard("8A") == "Am"
        assert camelot_to_standard("9A") == "Em"

    def test_converts_major(self) -> None:
        """Converts major keys."""
        assert camelot_to_standard("8B") == "C"
        assert camelot_to_standard("9B") == "G"

    def test_unknown_returns_none(self) -> None:
        """Unknown key returns None."""
        assert camelot_to_standard("99A") is None


class TestIsCompatible:
    """Tests for is_compatible."""

    def test_same_key(self) -> None:
        """Same key is compatible."""
        assert is_compatible("8A", "8A") is True

    def test_adjacent_keys(self) -> None:
        """Adjacent keys are compatible."""
        assert is_compatible("8A", "7A") is True
        assert is_compatible("8A", "9A") is True

    def test_relative_key(self) -> None:
        """Relative major/minor is compatible."""
        assert is_compatible("8A", "8B") is True

    def test_incompatible(self) -> None:
        """Distant keys are incompatible."""
        assert is_compatible("8A", "3A") is False

    def test_unknown_keys(self) -> None:
        """Unknown keys considered compatible."""
        assert is_compatible(None, "8A") is True
        assert is_compatible("8A", None) is True


class TestHarmonicDistance:
    """Tests for harmonic_distance."""

    def test_same_key_zero(self) -> None:
        """Same key has distance 0."""
        assert harmonic_distance("8A", "8A") == 0

    def test_compatible_keys_one(self) -> None:
        """Compatible keys have distance 1."""
        assert harmonic_distance("8A", "7A") == 1
        assert harmonic_distance("8A", "8B") == 1

    def test_distant_keys(self) -> None:
        """Distant keys have higher distance."""
        dist = harmonic_distance("8A", "3A")
        assert dist > 1

    def test_unknown_keys(self) -> None:
        """Unknown keys have high distance."""
        assert harmonic_distance(None, "8A") == 99
