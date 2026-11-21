"""Identify tracks in a mix recording against the library index."""

import logging
from collections.abc import Callable
from pathlib import Path

from ai_crate_digger.core.config import Settings
from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.matcher import MatchParams, MixResult, identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks, load_audio
from ai_crate_digger.storage import Database

logger = logging.getLogger(__name__)


def match_params_from_settings(settings: Settings) -> MatchParams:
    """Build matcher parameters from application settings."""
    return MatchParams(
        speed_range=settings.mix_speed_range,
        speed_step=settings.mix_speed_step,
        high_support=settings.mix_high_support,
        medium_support=settings.mix_medium_support,
        low_support=settings.mix_low_support,
    )


def identify_mix_file(
    path: Path,
    settings: Settings,
    on_progress: Callable[[float], None] | None = None,
) -> MixResult:
    """Decode a mix recording and match it against the library.

    Raises:
        FingerprintError: If the file cannot be read, is too short, or the index is empty
    """
    params = FingerprintParams()
    try:
        audio = load_audio(path, params.sample_rate)
    except Exception as exc:
        msg = f"Could not read audio file {path}: {exc}"
        raise FingerprintError(msg) from exc

    seconds = len(audio) / params.sample_rate
    if seconds < settings.mix_min_seconds:
        msg = (
            f"Recording is {seconds:.0f}s long. Mixes shorter than "
            f"{settings.mix_min_seconds:.0f}s are not supported."
        )
        raise FingerprintError(msg)

    peaks = extract_peaks(audio, params)
    del audio

    db = Database(settings.db_path)
    try:
        db.init()
        index = get_library_index(db)
    finally:
        db.close()
    if len(index) == 0:
        msg = "The fingerprint index is empty. Run index_fingerprints first."
        raise FingerprintError(msg)

    logger.info("Matching %s (%.0fs) against %d tracks", path.name, seconds, len(index))
    return identify_mix(index, peaks, params, match_params_from_settings(settings), on_progress)
