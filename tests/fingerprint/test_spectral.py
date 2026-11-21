"""Tests for spectrogram peak extraction."""

import numpy as np

from ai_crate_digger.fingerprint.params import FingerprintParams
from ai_crate_digger.fingerprint.spectral import extract_peaks
from tests.fingerprint.synth import SR, make_track

PARAMS = FingerprintParams()


def test_sine_peaks_sit_on_the_tone_bin() -> None:
    t = np.arange(3 * SR) / SR
    audio = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    peaks = extract_peaks(audio, PARAMS)
    expected_bin = round(1000 / (SR / PARAMS.n_fft))
    assert len(peaks.t) > 0
    assert np.all(np.abs(peaks.f - expected_bin) <= 1)


def test_silence_has_no_peaks() -> None:
    peaks = extract_peaks(np.zeros(3 * SR, dtype=np.float32), PARAMS)
    assert len(peaks.t) == 0
    assert peaks.n_frames > 0


def test_audio_shorter_than_one_frame_is_empty() -> None:
    peaks = extract_peaks(np.zeros(100, dtype=np.float32), PARAMS)
    assert len(peaks.t) == 0
    assert peaks.n_frames == 0


def test_peaks_per_block_are_capped() -> None:
    rng = np.random.default_rng(0)
    audio = rng.normal(0, 0.3, 10 * SR).astype(np.float32)
    peaks = extract_peaks(audio, PARAMS)
    counts = np.bincount(peaks.t // PARAMS.block_frames)
    assert counts.max() <= PARAMS.peaks_per_block


def test_peaks_are_sorted_by_time() -> None:
    peaks = extract_peaks(make_track(1, 10), PARAMS)
    assert np.all(np.diff(peaks.t) >= 0)


def test_extraction_is_deterministic() -> None:
    audio = make_track(2, 10)
    a, b = extract_peaks(audio, PARAMS), extract_peaks(audio, PARAMS)
    assert np.array_equal(a.t, b.t)
    assert np.array_equal(a.f, b.f)


def test_chunk_boundaries_do_not_change_peaks() -> None:
    audio = make_track(3, 20)
    whole = extract_peaks(audio, PARAMS)
    chunked = extract_peaks(audio, FingerprintParams(chunk_frames=43 * 5))
    assert np.array_equal(whole.t, chunked.t)
    assert np.array_equal(whole.f, chunked.f)
