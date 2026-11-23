"""Tests for mix identification using synthetic audio."""

import numpy as np
import pytest

from ai_crate_digger.fingerprint.hashing import hash_peaks
from ai_crate_digger.fingerprint.index import LibraryIndex
from ai_crate_digger.fingerprint.matcher import MatchParams, MixResult, hypotheses, identify_mix
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks
from tests.fingerprint.synth import (
    SR,
    Audio,
    add_noise,
    make_track,
    place,
    stretch_keylock,
    stretch_pitch,
)

FP = FingerprintParams()
MP = MatchParams()
TRACK_SECONDS = 45


@pytest.fixture(scope="module")
def tracks() -> dict[str, Audio]:
    return {f"t{i}": make_track(i, TRACK_SECONDS) for i in range(6)}


@pytest.fixture(scope="module")
def index(tracks: dict[str, Audio]) -> LibraryIndex:
    items = []
    for name, audio in tracks.items():
        hs = hash_peaks(
            extract_peaks(audio, FP),
            FP,
            rank_min=FP.index_rank_min,
            rank_max=FP.index_rank_max,
        )
        items.append((name, hs.hashes, hs.anchor_t.astype(np.int32)))
    return LibraryIndex.build(items)


def _identify(index: LibraryIndex, mix: Audio) -> MixResult:
    return identify_mix(index, extract_peaks(mix, FP), FP, MP)


def test_hypotheses_cover_identity_and_both_modes() -> None:
    plan = hypotheses(MatchParams(speed_range=0.02, speed_step=0.01))
    assert (1.0, "keylock") in plan
    assert (1.02, "pitch") in plan
    assert (0.98, "keylock") in plan
    assert len(plan) == 1 + 2 * 2 * 2


def test_identifies_unshifted_track(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(tracks["t2"][: 30 * SR], 5, 45)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t2"]
    seg = result.segments[0]
    assert seg.confidence_band == "high"
    assert abs(seg.start_sec - 5) <= 5
    assert abs(seg.tempo_shift_pct) < 1.0


def test_identifies_pitch_shifted_track(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(stretch_pitch(tracks["t1"][: 40 * SR], 1.04), 0, 40)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t1"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(4.0, abs=1.0)
    assert result.segments[0].mode == "pitch"


def test_identifies_key_locked_tempo_change(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = place(stretch_keylock(tracks["t3"][: 40 * SR], 0.96), 0, 42)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t3"]
    assert result.segments[0].tempo_shift_pct == pytest.approx(-4.0, abs=1.5)
    assert result.segments[0].mode == "keylock"


def test_survives_background_noise(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    mix = add_noise(place(tracks["t4"][: 30 * SR], 0, 30), 0.05)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t4"]


def test_overlapping_transition_finds_both_tracks(
    index: LibraryIndex, tracks: dict[str, Audio]
) -> None:
    mix = place(tracks["t0"][: 30 * SR], 0, 60) + place(tracks["t5"][: 30 * SR], 25, 60)
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t0", "t5"]
    assert result.segments[0].end_sec > result.segments[1].start_sec - 1


def test_unknown_audio_is_reported_as_unmatched(index: LibraryIndex) -> None:
    mix = make_track(9999, 40)
    result = _identify(index, mix)
    assert result.segments == []
    assert len(result.unmatched) == 1
    assert result.unmatched[0][0] == 0.0
    assert result.unmatched[0][1] == pytest.approx(result.duration_sec)


def test_gap_between_known_tracks_is_unmatched(
    index: LibraryIndex, tracks: dict[str, Audio]
) -> None:
    mix = (
        place(tracks["t0"][: 30 * SR], 0, 100)
        + place(make_track(9999, 30), 30, 100)
        + place(tracks["t1"][: 30 * SR], 60, 100)
    )
    result = _identify(index, mix)
    assert [s.track_hash for s in result.segments] == ["t0", "t1"]
    assert any(a < 40 and b > 55 for a, b in result.unmatched)


def test_empty_index_marks_everything_unmatched() -> None:
    mix = make_track(1, 20)
    result = identify_mix(LibraryIndex.build([]), extract_peaks(mix, FP), FP, MP)
    assert result.segments == []
    assert len(result.unmatched) == 1


def test_progress_reaches_one(index: LibraryIndex, tracks: dict[str, Audio]) -> None:
    seen: list[float] = []
    mix = place(tracks["t2"][: 20 * SR], 0, 20)
    identify_mix(index, extract_peaks(mix, FP), FP, MP, on_progress=seen.append)
    assert seen == sorted(seen)
    assert seen[-1] == pytest.approx(1.0)


def test_time_slicing_does_not_change_results(
    index: LibraryIndex, tracks: dict[str, Audio]
) -> None:
    mix = place(tracks["t0"][: 30 * SR], 0, 60) + place(tracks["t5"][: 30 * SR], 25, 60)
    peaks = extract_peaks(mix, FP)
    default = identify_mix(index, peaks, FP, MP)
    sliced = identify_mix(index, peaks, FP, MatchParams(slice_blocks=1))

    def summary(result: MixResult) -> list[tuple[str, float, float, str, float]]:
        return [
            (s.track_hash, s.start_sec, s.end_sec, s.confidence_band, s.tempo_shift_pct)
            for s in result.segments
        ]

    assert [s.track_hash for s in default.segments] == ["t0", "t5"]
    assert summary(sliced) == summary(default)
    assert sliced == default
