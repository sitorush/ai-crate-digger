"""Tests for result summaries and playlist ordering."""

from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.fingerprint.matcher import Band, MixResult, MixSegment
from ai_crate_digger.fingerprint.report import describe_result, format_time, playlist_hashes
from ai_crate_digger.storage import Database


def _segment(start: float, end: float, track: str, band: Band) -> MixSegment:
    return MixSegment(
        start_sec=start,
        end_sec=end,
        track_hash=track,
        confidence=0.2,
        confidence_band=band,
        tempo_shift_pct=1.5,
        mode="pitch",
    )


RESULT = MixResult(
    duration_sec=3700.0,
    segments=[
        _segment(300, 500, "b", "low"),
        _segment(0, 200, "a", "high"),
        _segment(600, 800, "a", "medium"),
    ],
    unmatched=[(200.0, 300.0)],
)


@pytest.mark.parametrize(
    ("seconds", "expected"), [(0, "0:00"), (65, "1:05"), (3599, "59:59"), (3725, "1:02:05")]
)
def test_format_time(seconds: float, expected: str) -> None:
    assert format_time(seconds) == expected


def test_playlist_hashes_follow_mix_order_and_dedupe() -> None:
    assert playlist_hashes(RESULT, "low") == ["a", "b"]
    assert playlist_hashes(RESULT, "low", dedupe=False) == ["a", "b", "a"]


def test_playlist_hashes_respect_confidence_floor() -> None:
    assert playlist_hashes(RESULT, "medium") == ["a"]
    assert playlist_hashes(RESULT, "high") == ["a"]


def test_describe_result_names_tracks_and_hides_weak_matches(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    db.init()
    db.upsert_track(
        Track(file_path=Path("/m/a.mp3"), file_hash="a", artist="Artist A", title="Title A")
    )
    summary = describe_result(RESULT, db, "medium")
    db.close()

    assert summary["duration"] == "1:01:40"
    assert summary["hidden_below_min_confidence"] == 1
    first = summary["segments"][0]
    assert (first["start"], first["end"]) == ("0:00", "3:20")
    assert (first["artist"], first["title"]) == ("Artist A", "Title A")
    assert summary["unmatched"] == [
        {"start": "3:20", "end": "5:00", "start_sec": 200.0, "end_sec": 300.0}
    ]
