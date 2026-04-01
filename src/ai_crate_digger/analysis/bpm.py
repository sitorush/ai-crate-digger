"""BPM (tempo) detection using Essentia."""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def estimate_bpm(y: np.ndarray, sr: int) -> float | None:
    """Estimate tempo (BPM) from a pre-loaded audio array.

    NOTE: Prefer estimate_bpm_from_file when you have a file path -- it loads
    at 44100 Hz which is what RhythmExtractor2013 requires.  Passing a 22050 Hz
    array here will silently reduce accuracy.

    Args:
        y: Audio time series (mono, float32)
        sr: Sample rate

    Returns:
        Estimated BPM rounded to 1 decimal, or None if detection fails
    """
    try:
        from essentia.standard import RhythmExtractor2013

        y_es = y.astype(np.float32) if y.dtype != np.float32 else y
        rhythm = RhythmExtractor2013()
        bpm, _, confidence, _, _ = rhythm(y_es)

        if not (40 <= bpm <= 400):
            return None

        logger.debug("BPM (essentia): %.1f (confidence: %.2f)", bpm, confidence)
        return round(float(bpm), 1)

    except Exception as e:
        logger.warning("Essentia BPM estimation failed: %s", e)
        return None


def estimate_bpm_from_file(file_path: Path) -> float | None:
    """Estimate BPM directly from audio file.

    More accurate than estimate_bpm() as it loads at optimal sample rate.

    Args:
        file_path: Path to audio file

    Returns:
        Estimated BPM rounded to 1 decimal, or None if detection fails
    """
    try:
        from essentia.standard import MonoLoader, RhythmExtractor2013

        # Load at 44100 Hz for best rhythm detection
        audio = MonoLoader(filename=str(file_path), sampleRate=44100)()

        # RhythmExtractor2013 has an internal buffer limit -- long tracks overflow it.
        # 60 seconds from the middle of the track is more than enough for BPM detection.
        max_samples = 44100 * 60
        if len(audio) > max_samples:
            mid = len(audio) // 2
            audio = audio[mid - max_samples // 2 : mid + max_samples // 2]

        rhythm = RhythmExtractor2013()
        bpm, _, confidence, _, _ = rhythm(audio)

        if not (40 <= bpm <= 400):
            return None

        logger.debug("BPM for %s: %.1f (confidence: %.2f)", file_path.name, bpm, confidence)
        return round(float(bpm), 1)

    except Exception as e:
        logger.warning("BPM estimation failed for %s: %s", file_path, e)
        return None
