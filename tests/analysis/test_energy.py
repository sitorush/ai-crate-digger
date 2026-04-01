"""Tests for energy and danceability."""

import numpy as np

from ai_crate_digger.analysis.energy import compute_danceability, compute_energy


class TestEnergy:
    """Tests for energy computation."""

    def test_energy_returns_float(self) -> None:
        """Energy returns float between 0 and 1."""
        signal = np.random.randn(22050 * 5) * 0.1

        energy = compute_energy(signal)

        assert isinstance(energy, float)
        assert 0 <= energy <= 1

    def test_silent_audio_low_energy(self) -> None:
        """Silent audio has very low energy."""
        signal = np.zeros(22050 * 5)

        energy = compute_energy(signal)

        assert energy < 0.1

    def test_loud_audio_high_energy(self) -> None:
        """Loud audio has high energy."""
        signal = np.random.randn(22050 * 5) * 0.5

        energy = compute_energy(signal)

        assert energy > 0.3


class TestDanceability:
    """Tests for danceability computation."""

    def test_danceability_returns_float(self) -> None:
        """Danceability returns float between 0 and 1."""
        sr = 22050
        signal = np.random.randn(sr * 5) * 0.1

        danceability = compute_danceability(signal, sr, bpm=128.0)

        assert isinstance(danceability, float)
        assert 0 <= danceability <= 1

    def test_dance_tempo_higher_danceability(self) -> None:
        """Typical dance tempo (120-130) scores higher."""
        sr = 22050
        signal = np.random.randn(sr * 5) * 0.1

        dance_score = compute_danceability(signal, sr, bpm=125.0)
        slow_score = compute_danceability(signal, sr, bpm=70.0)

        assert dance_score >= slow_score
