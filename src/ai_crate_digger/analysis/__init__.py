"""Analysis module - audio processing and feature extraction."""

from ai_crate_digger.analysis.analyzer import analyze_track
from ai_crate_digger.analysis.bpm import estimate_bpm
from ai_crate_digger.analysis.energy import compute_danceability, compute_energy
from ai_crate_digger.analysis.genre import classify_genre, extract_folder_hint
from ai_crate_digger.analysis.key import CAMELOT_WHEEL, estimate_key, key_to_camelot
from ai_crate_digger.analysis.parallel import ParallelAnalyzer

__all__ = [
    "analyze_track",
    "estimate_bpm",
    "estimate_key",
    "key_to_camelot",
    "CAMELOT_WHEEL",
    "compute_energy",
    "compute_danceability",
    "classify_genre",
    "extract_folder_hint",
    "ParallelAnalyzer",
]
