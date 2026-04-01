"""Musical key detection with Camelot wheel support."""

import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Key labels in chromatic order
KEY_LABELS = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
    "Cm",
    "C#m",
    "Dm",
    "D#m",
    "Em",
    "Fm",
    "F#m",
    "Gm",
    "G#m",
    "Am",
    "A#m",
    "Bm",
]

# Camelot wheel mapping
CAMELOT_WHEEL: dict[str, str] = {
    # Minor keys (A notation)
    "Am": "8A",
    "Em": "9A",
    "Bm": "10A",
    "F#m": "11A",
    "C#m": "12A",
    "G#m": "1A",
    "D#m": "2A",
    "A#m": "3A",
    "Fm": "4A",
    "Cm": "5A",
    "Gm": "6A",
    "Dm": "7A",
    # Major keys (B notation)
    "C": "8B",
    "G": "9B",
    "D": "10B",
    "A": "11B",
    "E": "12B",
    "B": "1B",
    "F#": "2B",
    "C#": "3B",
    "G#": "4B",
    "D#": "5B",
    "A#": "6B",
    "F": "7B",
}


def estimate_key(y: np.ndarray, sr: int) -> str | None:
    """Estimate musical key from audio signal.

    Uses chroma features and correlation with key profiles
    (Krumhansl-Kessler algorithm).

    Args:
        y: Audio time series (mono)
        sr: Sample rate

    Returns:
        Key string (e.g., "Am", "C", "F#m") or None if detection fails
    """
    try:
        # tuning=0.0 skips librosa's estimate_tuning() call which goes through
        # piptrack -> localmax -> numba gufunc and segfaults on macOS 26 / M4 Max.
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, tuning=0.0)
        chroma_avg = np.mean(chroma, axis=1)

        # Normalize
        norm = np.linalg.norm(chroma_avg)
        if norm < 1e-6:
            return None
        chroma_avg = chroma_avg / norm

        # Krumhansl-Kessler key profiles
        major_profile = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        )
        minor_profile = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        )

        major_profile = major_profile / np.linalg.norm(major_profile)
        minor_profile = minor_profile / np.linalg.norm(minor_profile)

        # Correlate with all possible keys
        correlations = []
        for i in range(12):
            shifted_major = np.roll(major_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_major))
            shifted_minor = np.roll(minor_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_minor))

        best_idx = int(np.argmax(correlations))
        return KEY_LABELS[best_idx]

    except Exception as e:
        logger.warning("Key estimation failed: %s", e)
        return None


def key_to_camelot(key: str | None) -> str | None:
    """Convert musical key to Camelot notation.

    Args:
        key: Musical key (e.g., "Am", "C", "F#m")

    Returns:
        Camelot notation (e.g., "8A", "8B") or None if unknown
    """
    if key is None:
        return None
    return CAMELOT_WHEEL.get(key)
