"""Tests for BPM detection."""

import numpy as np

from dj_catalog.analysis.bpm import estimate_bpm


def _create_click_track(sr: int, duration: float, bpm: float) -> np.ndarray:
    """Create a click track at specified BPM for testing.

    Args:
        sr: Sample rate
        duration: Duration in seconds
        bpm: Beats per minute

    Returns:
        Audio signal with clicks at regular intervals
    """
    n_samples = int(sr * duration)
    signal = np.zeros(n_samples)

    # Samples per beat
    samples_per_beat = int(60 * sr / bpm)

    # Add clicks (short impulses) at each beat
    click_length = int(sr * 0.01)  # 10ms click
    click = np.exp(-np.linspace(0, 10, click_length)) * np.sin(
        2 * np.pi * 1000 * np.linspace(0, 0.01, click_length)
    )

    for i in range(0, n_samples - click_length, samples_per_beat):
        signal[i : i + click_length] = click

    return signal.astype(np.float32)


class TestBPM:
    """Tests for BPM estimation."""

    def test_estimate_bpm_returns_float(self) -> None:
        """BPM estimation returns float."""
        sr = 22050
        duration = 10.0
        signal = _create_click_track(sr, duration, bpm=120.0)

        bpm = estimate_bpm(signal, sr)

        assert bpm is not None
        assert isinstance(bpm, float)

    def test_estimate_bpm_reasonable_range(self) -> None:
        """BPM is in reasonable range (60-200)."""
        sr = 22050
        duration = 10.0
        signal = _create_click_track(sr, duration, bpm=120.0)

        bpm = estimate_bpm(signal, sr)

        assert bpm is not None
        assert 60 <= bpm <= 200

    def test_estimate_bpm_silent_audio(self) -> None:
        """Silent audio returns None or reasonable default."""
        sr = 22050
        signal = np.zeros(sr * 5)  # 5 seconds silence

        bpm = estimate_bpm(signal, sr)

        # Should handle gracefully (None or fallback)
        assert bpm is None or 60 <= bpm <= 200
