"""Vector storage for semantic search using ChromaDB."""

import logging
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from dj_catalog.core.models import Track

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-based vector store for semantic track search."""

    def __init__(self, persist_dir: Path):
        """Initialize vector store.

        Args:
            persist_dir: Directory to persist ChromaDB data
        """
        self.persist_dir = persist_dir
        self._client: ClientAPI | None = None
        self._collection: Collection | None = None

    def init(self) -> None:
        """Initialize ChromaDB client and collection."""
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="tracks",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store initialized at %s", self.persist_dir)

    @property
    def collection(self) -> Collection:
        """Get the tracks collection."""
        if self._collection is None:
            raise RuntimeError("Vector store not initialized")
        return self._collection

    def _track_to_document(self, track: Track) -> str:
        """Convert track to searchable document text."""
        parts = []
        if track.title:
            parts.append(track.title)
        if track.artist:
            parts.append(f"by {track.artist}")
        if track.album:
            parts.append(f"from album {track.album}")
        if track.label:
            parts.append(f"on {track.label}")
        if track.tags:
            parts.append(f"tags: {', '.join(track.tags)}")
        if track.year:
            parts.append(f"released {track.year}")
        if track.bpm:
            parts.append(f"{track.bpm} BPM")
        if track.key:
            parts.append(f"key {track.key}")
        return " ".join(parts) or track.file_path.name

    def add_track(self, track: Track) -> None:
        """Add or update track in vector store."""
        document = self._track_to_document(track)
        metadata = {
            "file_hash": track.file_hash,
            "title": track.title or "",
            "artist": track.artist or "",
            "bpm": track.bpm or 0,
            "key": track.key or "",
        }
        self.collection.upsert(
            ids=[track.file_hash],
            documents=[document],
            metadatas=[metadata],
        )

    def search(self, query: str, limit: int = 10) -> list[str]:
        """Search tracks by natural language query.

        Args:
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            List of file hashes for matching tracks
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
        )
        return results["ids"][0] if results["ids"] else []

    def delete_track(self, file_hash: str) -> None:
        """Remove track from vector store."""
        self.collection.delete(ids=[file_hash])

    def count(self) -> int:
        """Get number of tracks in vector store."""
        return self.collection.count()
