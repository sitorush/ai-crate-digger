"""Tests for the in-memory library index."""

from pathlib import Path

import numpy as np
import pytest

from ai_crate_digger.core.exceptions import FingerprintError
from ai_crate_digger.fingerprint import index as index_module
from ai_crate_digger.fingerprint.index import (
    LibraryIndex,
    get_library_index,
    invalidate_index_cache,
)
from ai_crate_digger.fingerprint.params import FINGERPRINT_VERSION
from ai_crate_digger.storage import Database


def _arr(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.uint32)


def _times(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.int32)


def _index() -> LibraryIndex:
    return LibraryIndex.build(
        [
            ("aaa", _arr(5, 9, 5), _times(10, 20, 30)),
            ("bbb", _arr(9, 7), _times(100, 200)),
        ]
    )


def test_lookup_returns_every_track_with_the_hash() -> None:
    matches = _index().lookup(_arr(9), max_matches=10)
    assert sorted(zip(matches.track_idx.tolist(), matches.track_t.tolist(), strict=True)) == [
        (0, 20),
        (1, 100),
    ]
    assert matches.query_idx.tolist() == [0, 0]


def test_lookup_keeps_query_positions() -> None:
    matches = _index().lookup(_arr(7, 5), max_matches=10)
    pairs = sorted(zip(matches.query_idx.tolist(), matches.track_t.tolist(), strict=True))
    assert pairs == [(0, 200), (1, 10), (1, 30)]


def test_unknown_hash_matches_nothing() -> None:
    matches = _index().lookup(_arr(12345), max_matches=10)
    assert len(matches.query_idx) == 0


def test_max_matches_caps_popular_hashes() -> None:
    matches = _index().lookup(_arr(9), max_matches=1)
    assert len(matches.query_idx) == 1


def test_track_hashes_and_max_frames() -> None:
    index = _index()
    assert index.track_hashes == ["aaa", "bbb"]
    assert len(index) == 2
    assert index.max_track_frames == 200


def test_empty_index_is_empty_and_lookup_safe() -> None:
    index = LibraryIndex.build([])
    assert len(index) == 0
    assert len(index.lookup(_arr(1), max_matches=5).query_idx) == 0


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init()
    invalidate_index_cache()
    return database


def test_library_index_is_loaded_from_the_database(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5, 9), _times(10, 20), FINGERPRINT_VERSION)
    index = get_library_index(db)
    assert index.track_hashes == ["aaa"]
    assert index.lookup(_arr(9), max_matches=5).track_t.tolist() == [20]


def test_library_index_is_cached_until_the_fingerprint_count_changes(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5), _times(10), FINGERPRINT_VERSION)
    first = get_library_index(db)
    assert get_library_index(db) is first

    db.upsert_fingerprint("bbb", _arr(6), _times(10), FINGERPRINT_VERSION)
    second = get_library_index(db)
    assert second is not first
    assert len(second) == 2


def test_invalidate_forces_a_reload(db: Database) -> None:
    db.upsert_fingerprint("aaa", _arr(5), _times(10), FINGERPRINT_VERSION)
    first = get_library_index(db)
    invalidate_index_cache()
    assert get_library_index(db) is not first


def test_oversized_index_is_refused(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    db.upsert_fingerprint("aaa", _arr(1, 2, 3), _times(1, 2, 3), FINGERPRINT_VERSION)
    monkeypatch.setattr(index_module, "MAX_INDEX_HASHES", 2)
    with pytest.raises(FingerprintError, match="safety limit"):
        get_library_index(db)
