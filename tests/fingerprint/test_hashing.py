"""Tests for landmark hashing."""

import numpy as np

from ai_crate_digger.fingerprint.hashing import _band, hash_peaks
from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import Peaks

PARAMS = FingerprintParams()


def _peaks(t: list[int], f: list[int]) -> Peaks:
    return Peaks(t=np.array(t, dtype=np.int32), f=np.array(f, dtype=np.int32), n_frames=max(t) + 1)


def test_hash_packs_both_bands_and_the_time_gap() -> None:
    hs = hash_peaks(_peaks([0, 10], [100, 200]), PARAMS, rank_min=1, rank_max=1)
    assert len(hs.hashes) == 1
    value = int(hs.hashes[0])
    assert value & 63 == 10
    assert (value >> 6) & 511 == _band(np.array([200.0]), PARAMS.band_width)[0]
    assert (value >> 15) & 511 == _band(np.array([100.0]), PARAMS.band_width)[0]
    assert hs.anchor_t[0] == 0


def test_pairs_outside_the_time_window_are_dropped() -> None:
    peaks = _peaks([0, 1, 100], [10, 20, 30])  # dt 1 is too small, dt 99 too large
    hs = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=2)
    assert len(hs.hashes) == 0


def test_rank_range_controls_pair_count() -> None:
    peaks = _peaks(list(range(0, 100, 5)), [50] * 20)
    one = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1)
    three = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=3)
    assert len(one.hashes) == 19
    assert len(three.hashes) == 19 + 18 + 17


def test_time_scale_stretches_the_gap() -> None:
    peaks = _peaks([0, 10], [100, 200])
    hs = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1, time_scale=2.0)
    assert int(hs.hashes[0]) & 63 == 20
    assert hs.source_t[0] == 0


def test_freq_scale_moves_the_band() -> None:
    peaks = _peaks([0, 10], [100, 200])
    scaled = hash_peaks(peaks, PARAMS, rank_min=1, rank_max=1, freq_scale=1.1)
    shifted = hash_peaks(_peaks([0, 10], [110, 220]), PARAMS, rank_min=1, rank_max=1)
    assert scaled.hashes[0] == shifted.hashes[0]


def test_no_peaks_gives_empty_hash_set() -> None:
    hs = hash_peaks(_peaks([0], [5]), PARAMS, rank_min=1, rank_max=3)
    assert len(hs.hashes) == 0
    assert len(hs.anchor_t) == 0
