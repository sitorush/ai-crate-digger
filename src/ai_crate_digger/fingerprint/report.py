"""Turn match results into JSON-friendly summaries and playlist orderings."""

from typing import Any

from ai_crate_digger.fingerprint.matcher import Band, MixResult
from ai_crate_digger.storage import Database

BAND_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def format_time(seconds: float) -> str:
    """Format seconds as ``m:ss`` or ``h:mm:ss``."""
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def describe_result(result: MixResult, db: Database, min_confidence: Band) -> dict[str, Any]:
    """Describe a mix result with track names, hiding matches below ``min_confidence``."""
    floor = BAND_RANK[min_confidence]
    shown: list[dict[str, Any]] = []
    for seg in result.segments:
        if BAND_RANK[seg.confidence_band] < floor:
            continue
        track = db.get_track_by_hash(seg.track_hash)
        shown.append(
            {
                "start": format_time(seg.start_sec),
                "end": format_time(seg.end_sec),
                "start_sec": seg.start_sec,
                "end_sec": seg.end_sec,
                "hash": seg.track_hash,
                "artist": track.artist if track else None,
                "title": track.title if track else None,
                "confidence": seg.confidence,
                "confidence_band": seg.confidence_band,
                "tempo_shift_pct": seg.tempo_shift_pct,
                "mode": seg.mode,
            }
        )
    return {
        "duration": format_time(result.duration_sec),
        "duration_sec": result.duration_sec,
        "segments": shown,
        "hidden_below_min_confidence": len(result.segments) - len(shown),
        "unmatched": [
            {
                "start": format_time(a),
                "end": format_time(b),
                "start_sec": a,
                "end_sec": b,
            }
            for a, b in result.unmatched
        ],
    }


def playlist_hashes(result: MixResult, min_confidence: Band, *, dedupe: bool = True) -> list[str]:
    """Track hashes in mix order at or above ``min_confidence``."""
    floor = BAND_RANK[min_confidence]
    hashes: list[str] = []
    for seg in sorted(result.segments, key=lambda s: s.start_sec):
        if BAND_RANK[seg.confidence_band] < floor:
            continue
        if dedupe and seg.track_hash in hashes:
            continue
        hashes.append(seg.track_hash)
    return hashes
