"""SQLite database storage for track metadata."""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ai_crate_digger.core.models import Track

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class TrackRow(Base):
    """SQLAlchemy model for track storage."""

    __tablename__ = "tracks"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Core metadata
    title: Mapped[str | None] = mapped_column(String(512))
    artist: Mapped[str | None] = mapped_column(String(512), index=True)
    album: Mapped[str | None] = mapped_column(String(512))
    album_artist: Mapped[str | None] = mapped_column(String(512))
    track_number: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # Extended metadata
    label: Mapped[str | None] = mapped_column(String(256))
    remixer: Mapped[str | None] = mapped_column(String(256))
    composer: Mapped[str | None] = mapped_column(String(256))
    original_artist: Mapped[str | None] = mapped_column(String(256))
    isrc: Mapped[str | None] = mapped_column(String(32))
    release_date: Mapped[str | None] = mapped_column(String(16))  # Stored as ISO string
    year: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)

    # Audio quality
    bitrate: Mapped[int | None] = mapped_column(Integer)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    codec: Mapped[str | None] = mapped_column(String(32))

    # Analysis results
    bpm: Mapped[float | None] = mapped_column(Float, index=True)
    bpm_source: Mapped[str | None] = mapped_column(String(32))
    key: Mapped[str | None] = mapped_column(String(8), index=True)
    key_camelot: Mapped[str | None] = mapped_column(String(4), index=True)
    energy: Mapped[float | None] = mapped_column(Float, index=True)
    danceability: Mapped[float | None] = mapped_column(Float)

    # Tags stored as JSON array
    tags_json: Mapped[str] = mapped_column(Text, default="[]")

    # User-defined
    rating: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(16))
    play_count: Mapped[int] = mapped_column(Integer, default=0)

    # System
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tracks_bpm_key", "bpm", "key"),
        Index("ix_tracks_energy_danceability", "energy", "danceability"),
    )


def _row_to_track(row: TrackRow) -> Track:
    """Convert database row to Track model."""
    tags: list[str] = json.loads(row.tags_json) if row.tags_json else []

    release_date_val: date | None = None
    if row.release_date:
        with contextlib.suppress(ValueError):
            release_date_val = date.fromisoformat(row.release_date)

    return Track(
        file_path=Path(row.file_path),
        file_hash=row.file_hash,
        title=row.title,
        artist=row.artist,
        album=row.album,
        album_artist=row.album_artist,
        track_number=row.track_number,
        duration_seconds=row.duration_seconds,
        label=row.label,
        remixer=row.remixer,
        composer=row.composer,
        original_artist=row.original_artist,
        isrc=row.isrc,
        release_date=release_date_val,
        year=row.year,
        comment=row.comment,
        bitrate=row.bitrate,
        sample_rate=row.sample_rate,
        codec=row.codec,
        bpm=row.bpm,
        bpm_source=row.bpm_source,
        key=row.key,
        key_camelot=row.key_camelot,
        energy=row.energy,
        danceability=row.danceability,
        tags=tags,
        rating=row.rating,
        color=row.color,
        play_count=row.play_count,
        analyzed_at=row.analyzed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _track_to_dict(track: Track) -> dict[str, Any]:
    """Convert Track model to dict for database insert/update."""
    return {
        "file_path": str(track.file_path),
        "file_hash": track.file_hash,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "album_artist": track.album_artist,
        "track_number": track.track_number,
        "duration_seconds": track.duration_seconds,
        "label": track.label,
        "remixer": track.remixer,
        "composer": track.composer,
        "original_artist": track.original_artist,
        "isrc": track.isrc,
        "release_date": track.release_date.isoformat() if track.release_date else None,
        "year": track.year,
        "comment": track.comment,
        "bitrate": track.bitrate,
        "sample_rate": track.sample_rate,
        "codec": track.codec,
        "bpm": track.bpm,
        "bpm_source": track.bpm_source,
        "key": track.key,
        "key_camelot": track.key_camelot,
        "energy": track.energy,
        "danceability": track.danceability,
        "tags_json": json.dumps(track.tags),
        "rating": track.rating,
        "color": track.color,
        "play_count": track.play_count,
        "analyzed_at": track.analyzed_at,
        "created_at": track.created_at,
        "updated_at": datetime.now(tz=UTC),
    }


class Database:
    """SQLite database for track storage and retrieval."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._session: Session | None = None

    def init(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)
        self._session = self._session_factory()

    def close(self) -> None:
        """Close database session."""
        if self._session:
            self._session.close()
            self._session = None
        if self._engine:
            self._engine.dispose()
            self._engine = None

    @property
    def session(self) -> Session:
        """Get current session, raising if not initialized."""
        if self._session is None:
            msg = "Database not initialized. Call init() first."
            raise RuntimeError(msg)
        return self._session

    def insert_track(self, track: Track) -> int:
        """Insert a track into the database.

        Args:
            track: Track to insert

        Returns:
            Database ID of inserted track
        """
        data = _track_to_dict(track)
        row = TrackRow(**data)
        self.session.add(row)
        self.session.commit()
        return row.id

    def upsert_track(self, track: Track) -> int:
        """Insert or update track by file hash.

        Args:
            track: Track to upsert

        Returns:
            Database ID of track
        """
        stmt = select(TrackRow).where(TrackRow.file_hash == track.file_hash)
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            data = _track_to_dict(track)
            for key, value in data.items():
                if key != "created_at":  # Preserve original creation time
                    setattr(existing, key, value)
            self.session.commit()
            return existing.id
        return self.insert_track(track)

    def get_track(self, track_id: int) -> Track | None:
        """Get track by database ID.

        Args:
            track_id: Database ID

        Returns:
            Track or None if not found
        """
        stmt = select(TrackRow).where(TrackRow.id == track_id)
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_track(row)

    def get_track_by_hash(self, file_hash: str) -> Track | None:
        """Get track by file hash.

        Args:
            file_hash: SHA-256 hash of file content

        Returns:
            Track or None if not found
        """
        stmt = select(TrackRow).where(TrackRow.file_hash == file_hash)
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_track(row)

    def get_known_hashes(self) -> set[str]:
        """Get set of all known file hashes.

        Useful for incremental scanning to skip already-processed files.

        Returns:
            Set of file hashes
        """
        stmt = select(TrackRow.file_hash)
        result = self.session.execute(stmt).scalars().all()
        return set(result)

    def search_tracks(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key: str | None = None,
        key_camelot: str | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        artist: str | None = None,
        directory: str | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        """Search tracks by various criteria.

        Args:
            bpm_min: Minimum BPM (inclusive)
            bpm_max: Maximum BPM (inclusive)
            key: Musical key (e.g., "C major")
            key_camelot: Camelot notation (e.g., "8B")
            energy_min: Minimum energy (0-1)
            energy_max: Maximum energy (0-1)
            include_tags: Tracks must have ALL these tags
            exclude_tags: Tracks must NOT have ANY of these tags
            artist: Artist name (case-insensitive contains)
            directory: Filter to tracks from this directory path (prefix match on file_path)
            limit: Maximum number of results

        Returns:
            List of matching tracks
        """
        stmt = select(TrackRow)

        if bpm_min is not None:
            stmt = stmt.where(TrackRow.bpm >= bpm_min)
        if bpm_max is not None:
            stmt = stmt.where(TrackRow.bpm <= bpm_max)
        if key is not None:
            stmt = stmt.where(TrackRow.key == key)
        if key_camelot is not None:
            stmt = stmt.where(TrackRow.key_camelot == key_camelot)
        if energy_min is not None:
            stmt = stmt.where(TrackRow.energy >= energy_min)
        if energy_max is not None:
            stmt = stmt.where(TrackRow.energy <= energy_max)
        if artist is not None:
            stmt = stmt.where(TrackRow.artist.ilike(f"%{artist}%"))
        if directory is not None:
            stmt = stmt.where(TrackRow.file_path.like(f"{directory}%"))

        # Pre-filter by tags in SQL if provided (for performance)
        if include_tags:
            for tag in include_tags:
                stmt = stmt.where(TrackRow.tags_json.ilike(f"%{tag}%"))

        rows = list(self.session.execute(stmt).scalars().all())

        # Filter by tags in Python (JSON column)
        # Uses fuzzy matching: "garage" matches "UK Garage", "Garage", etc.
        results: list[Track] = []
        for row in rows:
            tags = json.loads(row.tags_json) if row.tags_json else []
            tags_lower = [t.lower() for t in tags]

            # Check include_tags - must have ALL (fuzzy: substring match)
            if include_tags:
                all_match = True
                for search_tag in include_tags:
                    search_lower = search_tag.lower()
                    # Match if search term is contained in any tag
                    if not any(search_lower in t for t in tags_lower):
                        all_match = False
                        break
                if not all_match:
                    continue

            # Check exclude_tags - must NOT have ANY (fuzzy)
            if exclude_tags:
                any_match = False
                for search_tag in exclude_tags:
                    search_lower = search_tag.lower()
                    if any(search_lower in t for t in tags_lower):
                        any_match = True
                        break
                if any_match:
                    continue

            results.append(_row_to_track(row))

        # Apply limit after filtering
        if limit is not None:
            results = results[:limit]

        return results

    def get_all_tracks(self) -> list[Track]:
        """Get all tracks in the database.

        Returns:
            List of all tracks
        """
        stmt = select(TrackRow)
        rows = self.session.execute(stmt).scalars().all()
        return [_row_to_track(row) for row in rows]

    def count_tracks(self) -> int:
        """Count total tracks in database.

        Returns:
            Number of tracks
        """
        stmt = select(TrackRow)
        return len(list(self.session.execute(stmt).scalars().all()))

    def delete_track(self, track_id: int) -> bool:
        """Delete track by ID.

        Args:
            track_id: Database ID

        Returns:
            True if deleted, False if not found
        """
        stmt = select(TrackRow).where(TrackRow.id == track_id)
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True
