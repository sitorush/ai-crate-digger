"""Energy and danceability computation."""

import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def compute_energy(y: np.ndarray) -> float:
    """Compute overall energy (loudness) of audio.

    Args:
        y: Audio time series

    Returns:
        Energy value between 0 and 1
    """
    rms = np.sqrt(np.mean(y**2))
    # Normalize to 0-1 range (typical RMS for normalized audio is ~0.2)
    energy = min(1.0, rms / 0.2)
    return round(float(energy), 3)


def compute_danceability(y: np.ndarray, sr: int, bpm: float | None) -> float:
    """Estimate danceability based on beat strength and tempo.

    Args:
        y: Audio time series
        sr: Sample rate
        bpm: Detected BPM (optional)

    Returns:
        Danceability value between 0 and 1
    """
    try:
        # Get onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Compute beat regularity via autocorrelation
        ac = librosa.autocorrelate(onset_env, max_size=sr // 2)
        if len(ac) == 0 or ac[0] == 0:
            regularity = 0.5
        else:
            ac = ac / (ac[0] + 1e-6)
            # Look for peaks in typical beat range
            start_idx = sr // 8
            end_idx = min(sr // 2, len(ac))
            regularity = float(np.max(ac[start_idx:end_idx])) if end_idx > start_idx else 0.5

        # Tempo contribution (dance music typically 100-140 BPM)
        tempo_score = 0.5
        if bpm:
            if 100 <= bpm <= 140:
                tempo_score = 1.0
            elif 80 <= bpm <= 160:
                tempo_score = 0.7
            else:
                tempo_score = 0.4

        danceability = regularity * 0.6 + tempo_score * 0.4
        return round(min(1.0, max(0.0, danceability)), 3)

    except Exception as e:
        logger.warning("Danceability estimation failed: %s", e)
        return 0.5
