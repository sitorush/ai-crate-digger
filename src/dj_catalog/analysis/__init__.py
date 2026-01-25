"""Analysis module - audio processing and feature extraction."""

from dj_catalog.analysis.analyzer import analyze_track
from dj_catalog.analysis.bpm import estimate_bpm
from dj_catalog.analysis.energy import compute_danceability, compute_energy
from dj_catalog.analysis.key import CAMELOT_WHEEL, estimate_key, key_to_camelot
from dj_catalog.analysis.parallel import ParallelAnalyzer

__all__ = [
    "analyze_track",
    "estimate_bpm",
    "estimate_key",
    "key_to_camelot",
    "CAMELOT_WHEEL",
    "compute_energy",
    "compute_danceability",
    "ParallelAnalyzer",
]
