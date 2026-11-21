"""Tests for fingerprint storage."""

from pathlib import Path

import numpy as np
import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.storage import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init()
    return database


def _hashes(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.uint32)


def _times(*values: int) -> np.ndarray:
    return np.array(values, dtype=np.int32)


def test_round_trip(db: Database) -> None:
    db.upsert_fingerprint("h1", _hashes(5, 9, 5), _times(10, 20, 30), version=1)
    [(track_hash, hashes, times)] = list(db.iter_fingerprints(1))
    assert track_hash == "h1"
    assert hashes.tolist() == [5, 9, 5]
    assert times.tolist() == [10, 20, 30]


def test_upsert_replaces_existing_fingerprint(db: Database) -> None:
    db.upsert_fingerprint("h1", _hashes(1, 2), _times(1, 2), version=1)
    db.upsert_fingerprint("h1", _hashes(7), _times(70), version=1)
    [(_, hashes, times)] = list(db.iter_fingerprints(1))
    assert hashes.tolist() == [7]
    assert times.tolist() == [70]
    assert db.count_fingerprints(1) == 1


def test_version_filters_everything(db: Database) -> None:
    db.upsert_fingerprint("old", _hashes(1), _times(1), version=1)
    db.upsert_fingerprint("new", _hashes(1, 2, 3), _times(1, 2, 3), version=2)
    assert db.get_fingerprinted_hashes(2) == {"new"}
    assert db.count_fingerprints(1) == 1
    assert db.sum_fingerprint_hashes(2) == 3
    assert [t for t, _, _ in db.iter_fingerprints(1)] == ["old"]


def test_empty_database_totals_are_zero(db: Database) -> None:
    assert db.count_fingerprints(1) == 0
    assert db.sum_fingerprint_hashes(1) == 0
    assert list(db.iter_fingerprints(1)) == []


def test_deleting_a_track_deletes_its_fingerprint(db: Database) -> None:
    track_id = db.insert_track(Track(file_path=Path("/music/a.mp3"), file_hash="h1"))
    db.upsert_fingerprint("h1", _hashes(1), _times(1), version=1)
    db.upsert_fingerprint("h2", _hashes(2), _times(2), version=1)
    assert db.delete_track(track_id) is True
    assert db.get_fingerprinted_hashes(1) == {"h2"}


def test_deleting_a_track_without_fingerprint_still_works(db: Database) -> None:
    track_id = db.insert_track(Track(file_path=Path("/music/a.mp3"), file_hash="h1"))
    assert db.delete_track(track_id) is True
