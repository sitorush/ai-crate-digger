"""Tests for key detection."""

import numpy as np

from ai_crate_digger.analysis.key import CAMELOT_WHEEL, estimate_key, key_to_camelot


class TestKey:
    """Tests for key estimation."""

    def test_estimate_key_returns_string(self) -> None:
        """Key estimation returns string."""
        sr = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration))
        # A4 = 440 Hz
        signal = np.sin(2 * np.pi * 440 * t)

        key = estimate_key(signal, sr)

        assert key is not None
        assert isinstance(key, str)

    def test_estimate_key_valid_format(self) -> None:
        """Key is in valid format (e.g., 'Am', 'C', 'F#m')."""
        sr = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration))
        signal = np.sin(2 * np.pi * 440 * t)

        key = estimate_key(signal, sr)

        assert key is not None
        # Should be note name optionally followed by 'm' for minor
        assert key[0] in "ABCDEFG"


class TestCamelot:
    """Tests for Camelot wheel conversion."""

    def test_camelot_wheel_completeness(self) -> None:
        """Camelot wheel has all 24 keys."""
        assert len(CAMELOT_WHEEL) == 24

    def test_key_to_camelot_major(self) -> None:
        """Major keys convert to B notation."""
        assert key_to_camelot("C") == "8B"
        assert key_to_camelot("G") == "9B"
        assert key_to_camelot("D") == "10B"

    def test_key_to_camelot_minor(self) -> None:
        """Minor keys convert to A notation."""
        assert key_to_camelot("Am") == "8A"
        assert key_to_camelot("Em") == "9A"
        assert key_to_camelot("Bm") == "10A"

    def test_key_to_camelot_unknown(self) -> None:
        """Unknown key returns None."""
        assert key_to_camelot("X") is None
        assert key_to_camelot(None) is None
