"""BPM (tempo) detection."""

import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def estimate_bpm(y: np.ndarray, sr: int) -> float | None:
    """Estimate tempo (BPM) from audio signal.

    Args:
        y: Audio time series (mono)
        sr: Sample rate

    Returns:
        Estimated BPM rounded to 1 decimal, or None if detection fails
    """
    try:
        raw_tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # librosa may return array or scalar
        tempo_val: float | None
        if isinstance(raw_tempo, np.ndarray):
            tempo_val = float(raw_tempo[0]) if len(raw_tempo) > 0 else None
        else:
            tempo_val = float(raw_tempo)
        if tempo_val is None or tempo_val <= 0:
            return None
        return round(tempo_val, 1)
    except Exception as e:
        logger.warning("BPM estimation failed: %s", e)
        return None
