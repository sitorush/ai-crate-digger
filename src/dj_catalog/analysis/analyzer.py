"""Audio analysis orchestration."""

import logging
from datetime import UTC, datetime

import librosa

from dj_catalog.analysis.bpm import estimate_bpm
from dj_catalog.analysis.energy import compute_danceability, compute_energy
from dj_catalog.analysis.key import estimate_key, key_to_camelot
from dj_catalog.core.config import get_settings
from dj_catalog.core.models import Track

logger = logging.getLogger(__name__)


def analyze_track(track: Track) -> Track:
    """Perform full audio analysis on a track.

    Loads audio file and computes BPM, key, energy, danceability.

    Args:
        track: Track with file_path set

    Returns:
        New Track with analysis results filled in
    """
    settings = get_settings()
    logger.info("Analyzing: %s", track.file_path)

    # Load audio (mono, resampled for faster processing)
    y, sr = librosa.load(track.file_path, sr=settings.sample_rate, mono=True)
    sr = int(sr)  # librosa.load returns int | float, ensure int

    # Run analysis
    bpm = estimate_bpm(y, sr)
    key = estimate_key(y, sr)
    energy = compute_energy(y)
    danceability = compute_danceability(y, sr, bpm)

    # Build updated track
    return track.model_copy(
        update={
            "bpm": bpm,
            "bpm_source": "analyzed" if bpm else None,
            "key": key,
            "key_camelot": key_to_camelot(key),
            "energy": energy,
            "danceability": danceability,
            "analyzed_at": datetime.now(tz=UTC),
        }
    )
