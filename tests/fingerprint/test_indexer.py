"""Tests for library fingerprinting."""

from pathlib import Path

import numpy as np

from ai_crate_digger.core.models import Track
from ai_crate_digger.fingerprint.index import get_library_index
from ai_crate_digger.fingerprint.indexer import fingerprint_audio, index_library
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION
from tests.fingerprint.library import Library
from tests.fingerprint.synth import make_track


def test_fingerprint_audio_returns_parallel_arrays() -> None:
    hashes, times = fingerprint_audio(make_track(1, 20))
    assert len(hashes) == len(times) > 0
    assert hashes.dtype == np.uint32
    assert times.dtype == np.int32


def test_indexes_every_track_then_skips_them(library: Library) -> None:
    first = index_library(library.db, workers=1)
    assert (first.indexed, first.skipped, first.failed) == (4, 0, [])
    assert library.db.count_fingerprints(FINGERPRINT_VERSION) == 4

    second = index_library(library.db, workers=1)
    assert (second.indexed, second.skipped) == (0, 4)


def test_force_reindexes_everything(library: Library) -> None:
    index_library(library.db, workers=1)
    report = index_library(library.db, workers=1, force=True)
    assert report.indexed == 4
    assert report.skipped == 0


def test_reports_progress(library: Library) -> None:
    seen: list[tuple[int, int]] = []
    index_library(library.db, workers=1, on_progress=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_unreadable_track_is_reported_and_others_continue(library: Library) -> None:
    library.db.upsert_track(Track(file_path=Path("/nope/missing.mp3"), file_hash="ghost"))
    report = index_library(library.db, workers=1)
    assert report.indexed == 4
    assert [path for path, _ in report.failed] == ["/nope/missing.mp3"]


def test_worker_pool_indexes_tracks(library: Library) -> None:
    report = index_library(library.db, workers=2)
    assert report.indexed == 4
    assert library.db.count_fingerprints(FINGERPRINT_VERSION) == 4


def test_reindexing_invalidates_the_cached_library_index(library: Library) -> None:
    index_library(library.db, workers=1)
    first = get_library_index(library.db)
    assert len(first) == 4

    index_library(library.db, workers=1, force=True)
    assert get_library_index(library.db) is not first
