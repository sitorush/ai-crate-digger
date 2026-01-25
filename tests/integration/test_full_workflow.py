"""Integration tests for full workflow."""

import struct
import wave
from pathlib import Path

import pytest

from dj_catalog.analysis import analyze_track
from dj_catalog.core.models import Track
from dj_catalog.playlist import (
    PlaylistOptions,
    TrackFilter,
    export_playlist,
    generate_playlist,
)
from dj_catalog.scanning import compute_file_hash, extract_metadata, scan_directory
from dj_catalog.storage import Database, VectorStore


@pytest.fixture
def music_library(tmp_dir: Path) -> Path:
    """Create a temporary music library with WAV files."""
    music_dir = tmp_dir / "music"
    music_dir.mkdir()

    # Create several WAV files
    for i in range(5):
        wav_path = music_dir / f"track_{i}.wav"
        with wave.open(str(wav_path), "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            # Create varying length files (1-5 seconds)
            duration = (i + 1) * 44100
            samples = [int(32767 * 0.5 * ((j % 1000) / 500 - 1)) for j in range(duration)]
            f.writeframes(struct.pack("<" + "h" * len(samples), *samples))

    return music_dir


@pytest.fixture
def test_db(tmp_dir: Path) -> Database:
    """Create test database."""
    db = Database(tmp_dir / "test.db")
    db.init()
    yield db
    db.close()


@pytest.fixture
def test_vectors(tmp_dir: Path) -> VectorStore:
    """Create test vector store."""
    store = VectorStore(tmp_dir / ".chroma")
    store.init()
    return store


class TestScanWorkflow:
    """Tests for scan workflow."""

    def test_scan_finds_audio_files(self, music_library: Path) -> None:
        """Scan finds all audio files."""
        files = list(scan_directory(music_library))
        assert len(files) == 5

    def test_extract_metadata_from_wav(self, music_library: Path) -> None:
        """Can extract metadata from WAV files."""
        files = list(scan_directory(music_library))
        track = extract_metadata(files[0])

        assert track.file_path == files[0]
        assert track.file_hash is not None
        assert track.duration_seconds is not None
        assert track.duration_seconds > 0

    def test_analyze_track_computes_features(self, music_library: Path) -> None:
        """Analyze computes audio features."""
        files = list(scan_directory(music_library))
        track = extract_metadata(files[0])
        analyzed = analyze_track(track)

        assert analyzed.analyzed_at is not None
        assert analyzed.energy is not None
        assert analyzed.danceability is not None


class TestDatabaseWorkflow:
    """Tests for database workflow."""

    def test_store_and_retrieve_tracks(self, music_library: Path, test_db: Database) -> None:
        """Can store and retrieve tracks."""
        files = list(scan_directory(music_library))

        # Extract and store
        for f in files:
            track = extract_metadata(f)
            test_db.upsert_track(track)

        # Retrieve
        assert test_db.count_tracks() == 5

        all_tracks = test_db.get_all_tracks()
        assert len(all_tracks) == 5

    def test_incremental_scan_detects_known(self, music_library: Path, test_db: Database) -> None:
        """Incremental scan skips known files."""
        files = list(scan_directory(music_library))

        # First scan - store all
        for f in files[:3]:
            track = extract_metadata(f)
            test_db.upsert_track(track)

        known_hashes = test_db.get_known_hashes()
        assert len(known_hashes) == 3

        # Check which files are new
        new_files = []
        for f in files:
            h = compute_file_hash(f)
            if h not in known_hashes:
                new_files.append(f)

        assert len(new_files) == 2


class TestPlaylistWorkflow:
    """Tests for playlist workflow."""

    def test_generate_playlist_from_tracks(self, test_db: Database) -> None:
        """Can generate playlist from tracks."""
        # Add sample tracks
        for i in range(10):
            track = Track(
                file_path=Path(f"/music/track_{i}.mp3"),
                file_hash=f"hash_{i}",
                title=f"Track {i}",
                artist=f"Artist {i % 3}",
                bpm=120.0 + i * 2,
                key_camelot=f"{8 + i % 4}A",
                duration_seconds=240.0,
                tags=["techno"] if i % 2 == 0 else ["house"],
            )
            test_db.upsert_track(track)

        tracks = test_db.get_all_tracks()

        # Generate playlist
        options = PlaylistOptions(duration_minutes=15, harmonic_mixing=True)
        playlist = generate_playlist(tracks, options=options)

        assert len(playlist.tracks) > 0
        assert playlist.total_duration > 0

    def test_filter_and_generate(self, test_db: Database) -> None:
        """Can filter tracks before generating playlist."""
        # Add tracks with different tags
        for i in range(10):
            track = Track(
                file_path=Path(f"/music/track_{i}.mp3"),
                file_hash=f"hash_{i}",
                bpm=128.0,
                duration_seconds=240.0,
                tags=["techno"] if i < 5 else ["house"],
            )
            test_db.upsert_track(track)

        tracks = test_db.get_all_tracks()
        filter_ = TrackFilter(include_tags=["techno"])
        playlist = generate_playlist(tracks, filter_=filter_)

        # All tracks should be techno
        for track in playlist.tracks:
            assert "techno" in track.tags

    def test_export_playlist_m3u(self, test_db: Database, tmp_dir: Path) -> None:
        """Can export playlist to M3U."""
        # Add sample tracks
        for i in range(3):
            track = Track(
                file_path=Path(f"/music/track_{i}.mp3"),
                file_hash=f"hash_{i}",
                title=f"Track {i}",
                artist=f"Artist {i}",
                duration_seconds=240.0,
            )
            test_db.upsert_track(track)

        tracks = test_db.get_all_tracks()
        playlist = generate_playlist(tracks, name="Test Playlist")

        # Export
        output = tmp_dir / "playlist.m3u"
        export_playlist(playlist, output, output_format="m3u")

        assert output.exists()
        content = output.read_text()
        assert "#EXTM3U" in content
        assert "Test Playlist" in content


class TestVectorSearchWorkflow:
    """Tests for vector search workflow."""

    def test_semantic_search(self, test_vectors: VectorStore, test_db: Database) -> None:
        """Can perform semantic search."""
        # Add tracks
        track1 = Track(
            file_path=Path("/music/dark_techno.mp3"),
            file_hash="h1",
            title="Dark Industrial Beat",
            artist="Techno Artist",
            tags=["techno", "dark", "industrial"],
        )
        track2 = Track(
            file_path=Path("/music/happy_house.mp3"),
            file_hash="h2",
            title="Happy Summer Vibes",
            artist="House Artist",
            tags=["house", "vocal", "summer"],
        )

        test_db.upsert_track(track1)
        test_db.upsert_track(track2)
        test_vectors.add_track(track1)
        test_vectors.add_track(track2)

        # Search for dark techno
        results = test_vectors.search("dark industrial techno")
        assert "h1" in results
