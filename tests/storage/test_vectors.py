"""Tests for ChromaDB vector store."""

from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.storage.vectors import VectorStore


@pytest.fixture
def vector_store(tmp_dir: Path):
    """Create temporary vector store."""
    store = VectorStore(tmp_dir / ".chroma")
    store.init()
    return store


class TestVectorStore:
    """Tests for VectorStore."""

    def test_add_and_search(self, vector_store: VectorStore) -> None:
        """Can add track and search for it."""
        track = Track(
            file_path=Path("/music/test.mp3"),
            file_hash="abc123",
            title="Strobe",
            artist="deadmau5",
            tags=["progressive house", "melodic"],
        )
        vector_store.add_track(track)

        results = vector_store.search("deadmau5 progressive")

        assert "abc123" in results

    def test_search_by_tags(self, vector_store: VectorStore) -> None:
        """Can search by tags."""
        track = Track(
            file_path=Path("/music/dark.mp3"),
            file_hash="dark123",
            title="Dark Track",
            tags=["techno", "dark", "industrial"],
        )
        vector_store.add_track(track)

        results = vector_store.search("dark techno")

        assert "dark123" in results

    def test_count(self, vector_store: VectorStore) -> None:
        """Can count tracks."""
        assert vector_store.count() == 0

        vector_store.add_track(
            Track(
                file_path=Path("/music/1.mp3"),
                file_hash="h1",
            )
        )

        assert vector_store.count() == 1

    def test_delete_track(self, vector_store: VectorStore) -> None:
        """Can delete track."""
        vector_store.add_track(
            Track(
                file_path=Path("/music/1.mp3"),
                file_hash="h1",
            )
        )
        assert vector_store.count() == 1

        vector_store.delete_track("h1")

        assert vector_store.count() == 0

    def test_not_initialized_raises(self, tmp_dir: Path) -> None:
        """Accessing collection before init raises RuntimeError."""
        store = VectorStore(tmp_dir / ".chroma")
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = store.collection

    def test_upsert_updates_existing(self, vector_store: VectorStore) -> None:
        """Adding same track twice updates rather than duplicates."""
        track = Track(
            file_path=Path("/music/1.mp3"),
            file_hash="h1",
            title="Original Title",
        )
        vector_store.add_track(track)
        assert vector_store.count() == 1

        track.title = "Updated Title"
        vector_store.add_track(track)

        assert vector_store.count() == 1
