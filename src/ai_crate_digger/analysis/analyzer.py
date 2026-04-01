"""Audio analysis orchestration."""

import logging
from datetime import UTC, datetime

import librosa

from ai_crate_digger.analysis.bpm import estimate_bpm
from ai_crate_digger.analysis.energy import compute_danceability, compute_energy
from ai_crate_digger.analysis.genre import classify_genre, extract_folder_hint
from ai_crate_digger.analysis.key import estimate_key, key_to_camelot
from ai_crate_digger.core.config import get_settings
from ai_crate_digger.core.models import Track

logger = logging.getLogger(__name__)


def analyze_track(track: Track, skip_genre: bool = False) -> Track:
    """Perform full audio analysis on a track.

    Loads audio file and computes BPM, key, energy, danceability.
    Also adds folder hint to tags and runs Essentia genre classification
    for tracks without existing genre tags.

    Args:
        track: Track with file_path set
        skip_genre: If True, skip Essentia genre classification (faster)

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

    # Build tags list (already normalized from extractor)
    tags = list(track.tags) if track.tags else []
    tags_lower = {t.lower() for t in tags}

    # Always add folder hints (normalized)
    folder_hints = extract_folder_hint(track.file_path)
    for hint in folder_hints:
        if hint.lower() not in tags_lower:
            tags.append(hint)
            tags_lower.add(hint.lower())
    if folder_hints:
        logger.debug("Added folder hint tags: %s", folder_hints)

    # Run Essentia genre classification if no existing genre tags
    if not skip_genre and len(track.tags) == 0:
        logger.debug("Running Essentia genre classification for %s", track.file_path.name)
        essentia_genres = classify_genre(track.file_path, top_n=2, min_confidence=0.15)
        for genre in essentia_genres:
            if genre.lower() not in tags_lower:
                tags.append(genre)
                tags_lower.add(genre.lower())
        if essentia_genres:
            logger.debug("Added Essentia genres: %s", essentia_genres)

    # Build updated track
    return track.model_copy(
        update={
            "bpm": bpm,
            "bpm_source": "analyzed" if bpm else None,
            "key": key,
            "key_camelot": key_to_camelot(key),
            "energy": energy,
            "danceability": danceability,
            "tags": tags,
            "analyzed_at": datetime.now(tz=UTC),
        }
    )
