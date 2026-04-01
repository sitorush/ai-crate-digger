"""Tests for SQLite database."""

from pathlib import Path

import pytest

from ai_crate_digger.core.models import Track
from ai_crate_digger.storage.database import Database


@pytest.fixture
def db(tmp_dir: Path):
    """Create temporary database."""
    db_path = tmp_dir / "test.db"
    database = Database(db_path)
    database.init()
    yield database
    database.close()


class TestDatabase:
    """Tests for Database."""

    def test_insert_and_get(self, db: Database) -> None:
        """Can insert and retrieve track."""
        track = Track(
            file_path=Path("/music/test.mp3"),
            file_hash="abc123",
            title="Test Song",
            artist="Test Artist",
            bpm=128.0,
            tags=["techno", "dark"],
        )

        track_id = db.insert_track(track)
        retrieved = db.get_track(track_id)

        assert retrieved is not None
        assert retrieved.title == "Test Song"
        assert retrieved.bpm == 128.0
        assert retrieved.tags == ["techno", "dark"]

    def test_upsert_by_hash(self, db: Database) -> None:
        """Upsert updates existing track by hash."""
        track1 = Track(
            file_path=Path("/music/test.mp3"),
            file_hash="abc123",
            title="Original",
        )
        track2 = Track(
            file_path=Path("/music/test.mp3"),
            file_hash="abc123",
            title="Updated",
            bpm=130.0,
        )

        id1 = db.upsert_track(track1)
        id2 = db.upsert_track(track2)

        assert id1 == id2
        retrieved = db.get_track(id1)
        assert retrieved is not None
        assert retrieved.title == "Updated"
        assert retrieved.bpm == 130.0

    def test_get_known_hashes(self, db: Database) -> None:
        """Can get set of known hashes for incremental scan."""
        tracks = [Track(file_path=Path(f"/music/{i}.mp3"), file_hash=f"hash{i}") for i in range(3)]
        for t in tracks:
            db.insert_track(t)

        hashes = db.get_known_hashes()

        assert hashes == {"hash0", "hash1", "hash2"}

    def test_search_by_bpm(self, db: Database) -> None:
        """Can search tracks by BPM range."""
        for i, bpm in enumerate([100, 120, 128, 140]):
            db.insert_track(
                Track(
                    file_path=Path(f"/music/{i}.mp3"),
                    file_hash=f"hash{i}",
                    bpm=float(bpm),
                )
            )

        results = db.search_tracks(bpm_min=115, bpm_max=135)

        assert len(results) == 2
        bpms = {t.bpm for t in results}
        assert bpms == {120.0, 128.0}

    def test_search_by_tags(self, db: Database) -> None:
        """Can search tracks by tags."""
        db.insert_track(
            Track(
                file_path=Path("/music/1.mp3"),
                file_hash="h1",
                tags=["techno", "dark"],
            )
        )
        db.insert_track(
            Track(
                file_path=Path("/music/2.mp3"),
                file_hash="h2",
                tags=["house", "vocal"],
            )
        )
        db.insert_track(
            Track(
                file_path=Path("/music/3.mp3"),
                file_hash="h3",
                tags=["techno", "melodic"],
            )
        )

        results = db.search_tracks(include_tags=["techno"])

        assert len(results) == 2

    def test_search_exclude_tags(self, db: Database) -> None:
        """Can exclude tracks by tags."""
        db.insert_track(
            Track(
                file_path=Path("/music/1.mp3"),
                file_hash="h1",
                tags=["techno", "vocal"],
            )
        )
        db.insert_track(
            Track(
                file_path=Path("/music/2.mp3"),
                file_hash="h2",
                tags=["techno", "dark"],
            )
        )

        results = db.search_tracks(include_tags=["techno"], exclude_tags=["vocal"])

        assert len(results) == 1
        assert results[0].file_hash == "h2"
