# DJ Music Catalog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that scans local music files, analyzes them for tempo/key/genre, stores metadata in SQLite + vectors in ChromaDB, and generates playlists by criteria.

**Architecture:** Scanner finds audio files, extractor pulls ID3 metadata, analyzer computes tempo/key/energy via librosa, classifier predicts genre. All data stored in SQLite (structured) and ChromaDB (embeddings for future RAG). CLI exposes scan, analyze, playlist, and search commands.

**Tech Stack:** Python 3.11+, Click, librosa, mutagen, SQLAlchemy, ChromaDB, Pydantic

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/dj_catalog/__init__.py`
- Create: `src/dj_catalog/cli.py`
- Create: `tests/__init__.py`
- Create: `tests/test_cli.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "dj-catalog"
version = "0.1.0"
description = "Music library scanner and playlist generator"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "pydantic>=2.0",
    "sqlalchemy>=2.0",
    "mutagen>=1.47",
    "librosa>=0.10",
    "chromadb>=0.4",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.1",
]

[project.scripts]
dj = "dj_catalog.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create directory structure**

```bash
mkdir -p src/dj_catalog tests
touch src/dj_catalog/__init__.py tests/__init__.py
```

**Step 3: Write failing CLI test**

Create `tests/test_cli.py`:
```python
from click.testing import CliRunner

from dj_catalog.cli import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
```

**Step 4: Run test to verify it fails**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: FAIL - module not found

**Step 5: Implement minimal CLI**

Create `src/dj_catalog/cli.py`:
```python
import click


@click.group()
@click.version_option(version="0.1.0", prog_name="dj-catalog")
def main() -> None:
    """DJ Music Catalog - scan, analyze, and create playlists."""
    pass


if __name__ == "__main__":
    main()
```

**Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git init
echo "__pycache__/\n*.pyc\n.venv/\n*.db\n.chroma/" > .gitignore
git add .
git commit -m "feat: project scaffolding with CLI skeleton"
```

---

## Task 2: Track Data Model

**Files:**
- Create: `src/dj_catalog/models.py`
- Create: `tests/test_models.py`

**Step 1: Write failing test for Track model**

Create `tests/test_models.py`:
```python
from pathlib import Path

from dj_catalog.models import Track


def test_track_model_creation():
    track = Track(
        file_path=Path("/music/song.mp3"),
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration_seconds=180.5,
    )
    assert track.title == "Test Song"
    assert track.file_path == Path("/music/song.mp3")
    assert track.duration_seconds == 180.5


def test_track_with_analysis():
    track = Track(
        file_path=Path("/music/song.mp3"),
        title="Test Song",
        artist="Test Artist",
        bpm=128.0,
        key="Am",
        energy=0.75,
        genre="house",
    )
    assert track.bpm == 128.0
    assert track.key == "Am"
    assert track.energy == 0.75
    assert track.genre == "house"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_models.py -v
```
Expected: FAIL - models module not found

**Step 3: Implement Track model**

Create `src/dj_catalog/models.py`:
```python
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, Field


class Track(BaseModel):
    """A music track with metadata and analysis results."""

    file_path: Path
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    year: int | None = None
    duration_seconds: float | None = None

    # Audio analysis fields
    bpm: float | None = None
    key: str | None = None
    energy: float | None = Field(default=None, ge=0.0, le=1.0)
    danceability: float | None = Field(default=None, ge=0.0, le=1.0)

    # Classification
    genre: str | None = None
    mood: str | None = None

    # System fields
    file_hash: str | None = None
    analyzed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = False
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_models.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Track pydantic model"
```

---

## Task 3: File Scanner

**Files:**
- Create: `src/dj_catalog/scanner.py`
- Create: `tests/test_scanner.py`
- Create: `tests/fixtures/` (test audio files)

**Step 1: Write failing test for scanner**

Create `tests/test_scanner.py`:
```python
from pathlib import Path
import tempfile

from dj_catalog.scanner import scan_directory, SUPPORTED_EXTENSIONS


def test_supported_extensions():
    assert ".mp3" in SUPPORTED_EXTENSIONS
    assert ".flac" in SUPPORTED_EXTENSIONS
    assert ".m4a" in SUPPORTED_EXTENSIONS
    assert ".wav" in SUPPORTED_EXTENSIONS


def test_scan_directory_finds_audio_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        # Create fake audio files
        (base / "song1.mp3").touch()
        (base / "song2.flac").touch()
        (base / "nested").mkdir()
        (base / "nested" / "song3.m4a").touch()
        # Create non-audio file
        (base / "readme.txt").touch()

        files = list(scan_directory(base))

        assert len(files) == 3
        extensions = {f.suffix for f in files}
        assert extensions == {".mp3", ".flac", ".m4a"}


def test_scan_directory_skips_hidden():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / "visible.mp3").touch()
        (base / ".hidden.mp3").touch()
        (base / ".hidden_dir").mkdir()
        (base / ".hidden_dir" / "song.mp3").touch()

        files = list(scan_directory(base))

        assert len(files) == 1
        assert files[0].name == "visible.mp3"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_scanner.py -v
```
Expected: FAIL - scanner module not found

**Step 3: Implement scanner**

Create `src/dj_catalog/scanner.py`:
```python
from pathlib import Path
from collections.abc import Iterator
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus",
    ".wav", ".aiff", ".wma", ".alac",
})


def scan_directory(directory: Path, recursive: bool = True) -> Iterator[Path]:
    """Scan directory for audio files, yielding paths.

    Args:
        directory: Root directory to scan
        recursive: Whether to scan subdirectories

    Yields:
        Path objects for each audio file found
    """
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    pattern = "**/*" if recursive else "*"

    for path in directory.glob(pattern):
        # Skip hidden files and directories
        if any(part.startswith(".") for part in path.parts):
            continue

        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            logger.debug(f"Found audio file: {path}")
            yield path
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_scanner.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add audio file scanner"
```

---

## Task 4: Metadata Extractor

**Files:**
- Create: `src/dj_catalog/extractor.py`
- Create: `tests/test_extractor.py`
- Download: test fixture audio file

**Step 1: Download test fixture**

```bash
mkdir -p tests/fixtures
# Create a minimal valid MP3 for testing (1 second of silence)
python -c "
import wave
import struct

# Create WAV first
with wave.open('tests/fixtures/test.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(44100)
    f.writeframes(struct.pack('<' + 'h' * 44100, *([0] * 44100)))
"
```

**Step 2: Write failing test for extractor**

Create `tests/test_extractor.py`:
```python
from pathlib import Path

import pytest

from dj_catalog.extractor import extract_metadata
from dj_catalog.models import Track


@pytest.fixture
def test_wav() -> Path:
    return Path(__file__).parent / "fixtures" / "test.wav"


def test_extract_metadata_from_wav(test_wav: Path):
    if not test_wav.exists():
        pytest.skip("Test fixture not available")

    track = extract_metadata(test_wav)

    assert isinstance(track, Track)
    assert track.file_path == test_wav
    assert track.duration_seconds is not None
    assert track.duration_seconds > 0


def test_extract_metadata_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        extract_metadata(Path("/nonexistent/file.mp3"))
```

**Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_extractor.py -v
```
Expected: FAIL - extractor module not found

**Step 4: Implement extractor**

Create `src/dj_catalog/extractor.py`:
```python
from pathlib import Path
import hashlib
import logging

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

from dj_catalog.models import Track

logger = logging.getLogger(__name__)


def _compute_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of first 1MB of file for deduplication."""
    hasher = hashlib.sha256()
    bytes_read = 0
    max_bytes = 1024 * 1024  # 1MB

    with open(path, "rb") as f:
        while bytes_read < max_bytes:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_read += len(chunk)

    return hasher.hexdigest()


def _safe_int(value: str | list | None) -> int | None:
    """Safely convert tag value to int."""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    try:
        # Handle "1/12" track number format
        return int(str(value).split("/")[0])
    except (ValueError, TypeError):
        return None


def _safe_str(value: str | list | None) -> str | None:
    """Safely convert tag value to string."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value)


def extract_metadata(file_path: Path) -> Track:
    """Extract metadata from an audio file.

    Args:
        file_path: Path to audio file

    Returns:
        Track with extracted metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format not supported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    audio = MutagenFile(file_path, easy=True)

    if audio is None:
        raise ValueError(f"Unsupported format: {file_path}")

    # Get duration
    duration = audio.info.length if audio.info else None

    # Extract common tags (mutagen easy mode normalizes these)
    tags = audio.tags or {}

    track = Track(
        file_path=file_path,
        title=_safe_str(tags.get("title")),
        artist=_safe_str(tags.get("artist")),
        album=_safe_str(tags.get("album")),
        album_artist=_safe_str(tags.get("albumartist")),
        track_number=_safe_int(tags.get("tracknumber")),
        year=_safe_int(tags.get("date")),
        duration_seconds=duration,
        genre=_safe_str(tags.get("genre")),
        file_hash=_compute_file_hash(file_path),
    )

    logger.debug(f"Extracted metadata for: {track.title or file_path.name}")
    return track
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_extractor.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add metadata extractor using mutagen"
```

---

## Task 5: Audio Analyzer (BPM/Key)

**Files:**
- Create: `src/dj_catalog/analyzer.py`
- Create: `tests/test_analyzer.py`

**Step 1: Write failing test for analyzer**

Create `tests/test_analyzer.py`:
```python
from pathlib import Path

import pytest
import numpy as np

from dj_catalog.analyzer import analyze_audio, estimate_bpm, estimate_key
from dj_catalog.models import Track


def test_estimate_bpm_returns_valid_range():
    # Create synthetic audio signal (1 second, 44100 Hz)
    sr = 44100
    duration = 5.0
    # Generate click track at 120 BPM (2 beats per second)
    t = np.linspace(0, duration, int(sr * duration))
    # 120 BPM = 2 Hz
    signal = np.sin(2 * np.pi * 2 * t) * np.exp(-10 * (t % 0.5))

    bpm = estimate_bpm(signal, sr)

    assert bpm is not None
    assert 60 <= bpm <= 200  # Reasonable BPM range


def test_estimate_key_returns_valid_key():
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration))
    # A4 = 440 Hz (A major/minor)
    signal = np.sin(2 * np.pi * 440 * t)

    key = estimate_key(signal, sr)

    assert key is not None
    # Should be some key notation
    assert any(note in key for note in ["A", "B", "C", "D", "E", "F", "G"])


def test_analyze_audio_updates_track():
    track = Track(
        file_path=Path("/fake/path.mp3"),
        title="Test",
    )

    # Create synthetic audio
    sr = 22050
    duration = 5.0
    signal = np.random.randn(int(sr * duration)) * 0.1

    updated = analyze_audio(track, signal, sr)

    assert updated.bpm is not None
    assert updated.key is not None
    assert updated.energy is not None
    assert 0 <= updated.energy <= 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_analyzer.py -v
```
Expected: FAIL - analyzer module not found

**Step 3: Implement analyzer**

Create `src/dj_catalog/analyzer.py`:
```python
from datetime import datetime
import logging

import numpy as np
import librosa

from dj_catalog.models import Track

logger = logging.getLogger(__name__)

# Key labels for Krumhansl-Schmuckler algorithm
KEY_LABELS = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
    "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "A#m", "Bm",
]


def estimate_bpm(y: np.ndarray, sr: int) -> float | None:
    """Estimate tempo (BPM) from audio signal.

    Args:
        y: Audio time series
        sr: Sample rate

    Returns:
        Estimated BPM or None if detection fails
    """
    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # tempo can be array or scalar depending on librosa version
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if len(tempo) > 0 else None
        return round(float(tempo), 1) if tempo else None
    except Exception as e:
        logger.warning(f"BPM estimation failed: {e}")
        return None


def estimate_key(y: np.ndarray, sr: int) -> str | None:
    """Estimate musical key from audio signal.

    Uses chroma features and correlation with key profiles.

    Args:
        y: Audio time series
        sr: Sample rate

    Returns:
        Key string (e.g., "Am", "C") or None if detection fails
    """
    try:
        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Normalize
        chroma_avg = chroma_avg / (np.linalg.norm(chroma_avg) + 1e-6)

        # Major and minor key profiles (Krumhansl-Kessler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        major_profile = major_profile / np.linalg.norm(major_profile)
        minor_profile = minor_profile / np.linalg.norm(minor_profile)

        # Correlate with all possible keys
        correlations = []
        for i in range(12):
            # Major key
            shifted_major = np.roll(major_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_major))
            # Minor key
            shifted_minor = np.roll(minor_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_minor))

        best_key_idx = np.argmax(correlations)
        return KEY_LABELS[best_key_idx]

    except Exception as e:
        logger.warning(f"Key estimation failed: {e}")
        return None


def compute_energy(y: np.ndarray) -> float:
    """Compute overall energy/loudness of audio.

    Returns value between 0 and 1.
    """
    rms = np.sqrt(np.mean(y**2))
    # Normalize to 0-1 range (typical RMS for normalized audio)
    energy = min(1.0, rms / 0.2)
    return round(energy, 3)


def compute_danceability(y: np.ndarray, sr: int, bpm: float | None) -> float:
    """Estimate danceability based on beat strength and tempo.

    Returns value between 0 and 1.
    """
    try:
        # Get onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Compute beat regularity via autocorrelation
        ac = librosa.autocorrelate(onset_env, max_size=sr // 2)
        ac = ac / (ac[0] + 1e-6)  # Normalize

        # Beat regularity score
        regularity = np.max(ac[sr // 8:sr // 2]) if len(ac) > sr // 2 else 0.5

        # Tempo contribution (dance music typically 100-140 BPM)
        tempo_score = 0.5
        if bpm:
            if 100 <= bpm <= 140:
                tempo_score = 1.0
            elif 80 <= bpm <= 160:
                tempo_score = 0.7
            else:
                tempo_score = 0.4

        danceability = (regularity * 0.6 + tempo_score * 0.4)
        return round(min(1.0, max(0.0, danceability)), 3)

    except Exception as e:
        logger.warning(f"Danceability estimation failed: {e}")
        return 0.5


def analyze_audio(track: Track, y: np.ndarray, sr: int) -> Track:
    """Perform full audio analysis on a track.

    Args:
        track: Track model with file path
        y: Audio time series
        sr: Sample rate

    Returns:
        Updated Track with analysis results
    """
    bpm = estimate_bpm(y, sr)
    key = estimate_key(y, sr)
    energy = compute_energy(y)
    danceability = compute_danceability(y, sr, bpm)

    return track.model_copy(update={
        "bpm": bpm,
        "key": key,
        "energy": energy,
        "danceability": danceability,
        "analyzed_at": datetime.now(),
    })


def load_and_analyze(track: Track) -> Track:
    """Load audio file and perform analysis.

    Args:
        track: Track with file_path set

    Returns:
        Track with analysis results
    """
    logger.info(f"Analyzing: {track.file_path}")

    # Load audio (mono, 22050 Hz for faster processing)
    y, sr = librosa.load(track.file_path, sr=22050, mono=True)

    return analyze_audio(track, y, sr)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_analyzer.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add audio analyzer for BPM, key, energy"
```

---

## Task 6: Database Layer (SQLite)

**Files:**
- Create: `src/dj_catalog/database.py`
- Create: `tests/test_database.py`

**Step 1: Write failing test for database**

Create `tests/test_database.py`:
```python
from pathlib import Path
import tempfile

import pytest

from dj_catalog.database import Database, TrackRow
from dj_catalog.models import Track


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        database.init()
        yield database
        database.close()


def test_database_insert_and_get(db: Database):
    track = Track(
        file_path=Path("/music/test.mp3"),
        title="Test Song",
        artist="Test Artist",
        bpm=128.0,
        key="Am",
    )

    track_id = db.insert_track(track)

    assert track_id is not None
    assert track_id > 0

    retrieved = db.get_track(track_id)
    assert retrieved is not None
    assert retrieved.title == "Test Song"
    assert retrieved.bpm == 128.0


def test_database_upsert_by_hash(db: Database):
    track1 = Track(
        file_path=Path("/music/test.mp3"),
        title="Original",
        file_hash="abc123",
    )
    track2 = Track(
        file_path=Path("/music/test.mp3"),
        title="Updated",
        file_hash="abc123",
        bpm=130.0,
    )

    id1 = db.upsert_track(track1)
    id2 = db.upsert_track(track2)

    assert id1 == id2  # Same record updated

    retrieved = db.get_track(id1)
    assert retrieved.title == "Updated"
    assert retrieved.bpm == 130.0


def test_database_search_by_bpm(db: Database):
    tracks = [
        Track(file_path=Path(f"/music/{i}.mp3"), title=f"Song {i}",
              bpm=bpm, file_hash=f"hash{i}")
        for i, bpm in enumerate([100, 120, 125, 140, 160])
    ]
    for t in tracks:
        db.insert_track(t)

    results = db.search_tracks(bpm_min=115, bpm_max=145)

    assert len(results) == 3
    bpms = {t.bpm for t in results}
    assert bpms == {120, 125, 140}
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_database.py -v
```
Expected: FAIL - database module not found

**Step 3: Implement database**

Create `src/dj_catalog/database.py`:
```python
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
import logging

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.sqlite import insert

from dj_catalog.models import Track

logger = logging.getLogger(__name__)

Base = declarative_base()


class TrackRow(Base):
    """SQLAlchemy model for tracks table."""

    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False, unique=True)
    file_hash = Column(String(64), unique=True, index=True)

    title = Column(String(500))
    artist = Column(String(500), index=True)
    album = Column(String(500))
    album_artist = Column(String(500))
    track_number = Column(Integer)
    year = Column(Integer, index=True)
    duration_seconds = Column(Float)

    bpm = Column(Float, index=True)
    key = Column(String(10), index=True)
    energy = Column(Float)
    danceability = Column(Float)

    genre = Column(String(100), index=True)
    mood = Column(String(100), index=True)

    analyzed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Database:
    """Database interface for track storage."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.Session = sessionmaker(bind=self.engine)
        self._session = None

    def init(self) -> None:
        """Initialize database schema."""
        Base.metadata.create_all(self.engine)
        self._session = self.Session()
        logger.info(f"Database initialized: {self.db_path}")

    def close(self) -> None:
        """Close database connection."""
        if self._session:
            self._session.close()

    @property
    def session(self):
        if self._session is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session

    def _track_to_row(self, track: Track) -> dict:
        """Convert Track model to row dict."""
        return {
            "file_path": str(track.file_path),
            "file_hash": track.file_hash,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "album_artist": track.album_artist,
            "track_number": track.track_number,
            "year": track.year,
            "duration_seconds": track.duration_seconds,
            "bpm": track.bpm,
            "key": track.key,
            "energy": track.energy,
            "danceability": track.danceability,
            "genre": track.genre,
            "mood": track.mood,
            "analyzed_at": track.analyzed_at,
            "created_at": track.created_at,
        }

    def _row_to_track(self, row: TrackRow) -> Track:
        """Convert row to Track model."""
        return Track(
            file_path=Path(row.file_path),
            file_hash=row.file_hash,
            title=row.title,
            artist=row.artist,
            album=row.album,
            album_artist=row.album_artist,
            track_number=row.track_number,
            year=row.year,
            duration_seconds=row.duration_seconds,
            bpm=row.bpm,
            key=row.key,
            energy=row.energy,
            danceability=row.danceability,
            genre=row.genre,
            mood=row.mood,
            analyzed_at=row.analyzed_at,
            created_at=row.created_at,
        )

    def insert_track(self, track: Track) -> int:
        """Insert a new track. Returns track ID."""
        row = TrackRow(**self._track_to_row(track))
        self.session.add(row)
        self.session.commit()
        return row.id

    def upsert_track(self, track: Track) -> int:
        """Insert or update track by file_hash. Returns track ID."""
        data = self._track_to_row(track)

        # Check if exists
        existing = self.session.query(TrackRow).filter_by(
            file_hash=track.file_hash
        ).first()

        if existing:
            for key, value in data.items():
                if value is not None:
                    setattr(existing, key, value)
            self.session.commit()
            return existing.id
        else:
            return self.insert_track(track)

    def get_track(self, track_id: int) -> Track | None:
        """Get track by ID."""
        row = self.session.query(TrackRow).filter_by(id=track_id).first()
        return self._row_to_track(row) if row else None

    def get_track_by_path(self, file_path: Path) -> Track | None:
        """Get track by file path."""
        row = self.session.query(TrackRow).filter_by(
            file_path=str(file_path)
        ).first()
        return self._row_to_track(row) if row else None

    def search_tracks(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key: str | None = None,
        genre: str | None = None,
        artist: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        energy_min: float | None = None,
        limit: int = 100,
    ) -> list[Track]:
        """Search tracks by criteria."""
        query = self.session.query(TrackRow)

        if bpm_min is not None:
            query = query.filter(TrackRow.bpm >= bpm_min)
        if bpm_max is not None:
            query = query.filter(TrackRow.bpm <= bpm_max)
        if key is not None:
            query = query.filter(TrackRow.key == key)
        if genre is not None:
            query = query.filter(TrackRow.genre.ilike(f"%{genre}%"))
        if artist is not None:
            query = query.filter(TrackRow.artist.ilike(f"%{artist}%"))
        if year_min is not None:
            query = query.filter(TrackRow.year >= year_min)
        if year_max is not None:
            query = query.filter(TrackRow.year <= year_max)
        if energy_min is not None:
            query = query.filter(TrackRow.energy >= energy_min)

        rows = query.limit(limit).all()
        return [self._row_to_track(r) for r in rows]

    def get_all_tracks(self) -> list[Track]:
        """Get all tracks."""
        rows = self.session.query(TrackRow).all()
        return [self._row_to_track(r) for r in rows]

    def count_tracks(self) -> int:
        """Count total tracks."""
        return self.session.query(TrackRow).count()

    def get_known_hashes(self) -> set[str]:
        """Get all file hashes in database for incremental scanning."""
        rows = self.session.query(TrackRow.file_hash).filter(
            TrackRow.file_hash.isnot(None)
        ).all()
        return {r[0] for r in rows}

    def is_file_known(self, file_hash: str) -> bool:
        """Check if file hash already exists in database."""
        return self.session.query(TrackRow).filter_by(
            file_hash=file_hash
        ).first() is not None
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_database.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add SQLite database layer"
```

---

## Task 7: Vector Store (ChromaDB)

**Files:**
- Create: `src/dj_catalog/vectors.py`
- Create: `tests/test_vectors.py`

**Step 1: Write failing test for vector store**

Create `tests/test_vectors.py`:
```python
from pathlib import Path
import tempfile

import pytest

from dj_catalog.vectors import VectorStore
from dj_catalog.models import Track


@pytest.fixture
def vector_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(Path(tmpdir) / ".chroma")
        yield store


def test_vector_store_add_and_search(vector_store: VectorStore):
    tracks = [
        Track(
            file_path=Path(f"/music/{i}.mp3"),
            title=f"Song {i}",
            artist="Artist",
            genre=genre,
            mood="energetic" if i % 2 == 0 else "chill",
            file_hash=f"hash{i}",
        )
        for i, genre in enumerate(["house", "techno", "trance", "ambient"])
    ]

    for track in tracks:
        vector_store.add_track(track)

    # Search for dance music
    results = vector_store.search("upbeat electronic dance music", n_results=2)

    assert len(results) == 2
    # Should find house/techno before ambient


def test_vector_store_upsert(vector_store: VectorStore):
    track = Track(
        file_path=Path("/music/test.mp3"),
        title="Original",
        file_hash="hash123",
    )

    vector_store.add_track(track)

    # Update same track
    track_updated = track.model_copy(update={"title": "Updated"})
    vector_store.add_track(track_updated)

    # Should not duplicate
    results = vector_store.search("Updated", n_results=10)
    matching = [r for r in results if r.file_hash == "hash123"]
    assert len(matching) == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_vectors.py -v
```
Expected: FAIL - vectors module not found

**Step 3: Implement vector store**

Create `src/dj_catalog/vectors.py`:
```python
from pathlib import Path
import logging

import chromadb
from chromadb.config import Settings

from dj_catalog.models import Track

logger = logging.getLogger(__name__)


def _track_to_text(track: Track) -> str:
    """Convert track metadata to searchable text."""
    parts = []

    if track.title:
        parts.append(f"title: {track.title}")
    if track.artist:
        parts.append(f"artist: {track.artist}")
    if track.album:
        parts.append(f"album: {track.album}")
    if track.genre:
        parts.append(f"genre: {track.genre}")
    if track.mood:
        parts.append(f"mood: {track.mood}")
    if track.bpm:
        tempo = "slow" if track.bpm < 100 else "medium" if track.bpm < 130 else "fast"
        parts.append(f"tempo: {tempo} ({track.bpm} bpm)")
    if track.key:
        parts.append(f"key: {track.key}")
    if track.energy is not None:
        energy_level = "low" if track.energy < 0.4 else "medium" if track.energy < 0.7 else "high"
        parts.append(f"energy: {energy_level}")
    if track.year:
        decade = (track.year // 10) * 10
        parts.append(f"era: {decade}s")

    return " | ".join(parts)


def _track_to_metadata(track: Track) -> dict:
    """Convert track to ChromaDB metadata."""
    meta = {
        "file_path": str(track.file_path),
        "file_hash": track.file_hash or "",
    }

    if track.title:
        meta["title"] = track.title
    if track.artist:
        meta["artist"] = track.artist
    if track.genre:
        meta["genre"] = track.genre
    if track.bpm:
        meta["bpm"] = track.bpm
    if track.key:
        meta["key"] = track.key
    if track.energy is not None:
        meta["energy"] = track.energy
    if track.year:
        meta["year"] = track.year

    return meta


class VectorStore:
    """ChromaDB vector store for semantic track search."""

    COLLECTION_NAME = "tracks"

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Vector store initialized: {persist_dir}")

    def add_track(self, track: Track) -> None:
        """Add or update track in vector store."""
        if not track.file_hash:
            logger.warning(f"Track has no hash, skipping: {track.file_path}")
            return

        doc_id = track.file_hash
        text = _track_to_text(track)
        metadata = _track_to_metadata(track)

        # Upsert (add will update if ID exists)
        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )
        logger.debug(f"Added to vector store: {track.title or track.file_path}")

    def search(self, query: str, n_results: int = 10) -> list[Track]:
        """Search tracks by semantic query.

        Args:
            query: Natural language query (e.g., "upbeat dance music from the 90s")
            n_results: Maximum number of results

        Returns:
            List of matching Track objects
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        tracks = []
        if results["metadatas"]:
            for meta in results["metadatas"][0]:
                track = Track(
                    file_path=Path(meta["file_path"]),
                    file_hash=meta.get("file_hash"),
                    title=meta.get("title"),
                    artist=meta.get("artist"),
                    genre=meta.get("genre"),
                    bpm=meta.get("bpm"),
                    key=meta.get("key"),
                    energy=meta.get("energy"),
                    year=meta.get("year"),
                )
                tracks.append(track)

        return tracks

    def delete_track(self, file_hash: str) -> None:
        """Remove track from vector store."""
        self.collection.delete(ids=[file_hash])

    def count(self) -> int:
        """Count tracks in vector store."""
        return self.collection.count()
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_vectors.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add ChromaDB vector store for semantic search"
```

---

## Task 8: CLI Scan Command

**Files:**
- Modify: `src/dj_catalog/cli.py`
- Create: `tests/test_cli_scan.py`

**Step 1: Write failing test for scan command**

Create `tests/test_cli_scan.py`:
```python
from pathlib import Path
import tempfile

from click.testing import CliRunner

from dj_catalog.cli import main


def test_scan_command_requires_path():
    runner = CliRunner()
    result = runner.invoke(main, ["scan"])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "PATH" in result.output


def test_scan_command_with_empty_dir():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["scan", tmpdir])
        assert result.exit_code == 0
        assert "0" in result.output or "no" in result.output.lower()


def test_scan_command_finds_files():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        # Create fake audio files
        (base / "song1.mp3").touch()
        (base / "song2.flac").touch()

        result = runner.invoke(main, ["scan", tmpdir, "--dry-run"])

        assert result.exit_code == 0
        assert "2" in result.output or "song1" in result.output


def test_scan_incremental_skips_existing():
    """Test that re-scanning skips already-processed files."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db_path = base / "test.db"

        # Create initial file
        (base / "song1.wav").write_bytes(b"RIFF" + b"\x00" * 100)

        # First scan
        result1 = runner.invoke(main, [
            "scan", str(base),
            "--db", str(db_path),
            "--no-analyze",
        ])
        assert "1" in result1.output or "Processed" in result1.output

        # Second scan - should skip existing
        result2 = runner.invoke(main, [
            "scan", str(base),
            "--db", str(db_path),
            "--no-analyze",
        ])
        assert "Skipped" in result2.output or "0" in result2.output

        # Add new file and scan again
        (base / "song2.wav").write_bytes(b"RIFF" + b"\x00" * 50)
        result3 = runner.invoke(main, [
            "scan", str(base),
            "--db", str(db_path),
            "--no-analyze",
        ])
        # Should process only the new file
        assert "1" in result3.output  # 1 new processed
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_scan.py -v
```
Expected: FAIL - scan command not found

**Step 3: Implement scan command**

Update `src/dj_catalog/cli.py`:
```python
from pathlib import Path
import logging

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from dj_catalog.scanner import scan_directory
from dj_catalog.extractor import extract_metadata
from dj_catalog.analyzer import load_and_analyze
from dj_catalog.database import Database
from dj_catalog.vectors import VectorStore

console = Console()
logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".dj-catalog" / "catalog.db"
DEFAULT_VECTOR_PATH = Path.home() / ".dj-catalog" / ".chroma"


def get_db(db_path: Path | None = None) -> Database:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    db.init()
    return db


def get_vectors(vector_path: Path | None = None) -> VectorStore:
    path = vector_path or DEFAULT_VECTOR_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return VectorStore(path)


@click.group()
@click.version_option(version="0.1.0", prog_name="dj-catalog")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def main(verbose: bool) -> None:
    """DJ Music Catalog - scan, analyze, and create playlists."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="List files without processing")
@click.option("--analyze/--no-analyze", default=True, help="Run audio analysis")
@click.option("--force", is_flag=True, help="Re-process files even if already in catalog")
@click.option("--db", type=click.Path(path_type=Path), help="Database path")
def scan(path: Path, dry_run: bool, analyze: bool, force: bool, db: Path | None) -> None:
    """Scan directory for music files and add to catalog.

    By default, only NEW files are processed. Files already in the catalog
    (identified by content hash) are skipped. Use --force to re-process all.

    Examples:

        dj scan /path/to/music

        dj scan /path/to/music --force  # Re-analyze everything

        dj scan /path/to/music --no-analyze  # Fast scan, metadata only
    """
    console.print(f"[bold]Scanning:[/bold] {path}")

    files = list(scan_directory(path))

    if not files:
        console.print("[yellow]No audio files found.[/yellow]")
        return

    console.print(f"Found [green]{len(files)}[/green] audio files")

    if dry_run:
        for f in files[:20]:
            console.print(f"  {f.name}")
        if len(files) > 20:
            console.print(f"  ... and {len(files) - 20} more")
        return

    database = get_db(db)
    vectors = get_vectors()

    # Get known file hashes for incremental scanning
    known_hashes = database.get_known_hashes() if not force else set()
    if known_hashes:
        console.print(f"[dim]Catalog has {len(known_hashes)} existing tracks[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=len(files))

        processed = 0
        skipped = 0
        errors = 0

        for file_path in files:
            try:
                # Quick hash check for incremental scanning
                from dj_catalog.extractor import _compute_file_hash
                file_hash = _compute_file_hash(file_path)

                if file_hash in known_hashes:
                    skipped += 1
                    progress.advance(task)
                    continue

                # Extract metadata
                track = extract_metadata(file_path)

                # Analyze audio if requested
                if analyze:
                    track = load_and_analyze(track)

                # Store in database
                database.upsert_track(track)

                # Store in vector DB
                vectors.add_track(track)

                processed += 1

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                errors += 1

            progress.advance(task)

    database.close()

    console.print(f"\n[green]Processed:[/green] {processed} new tracks")
    if skipped:
        console.print(f"[dim]Skipped:[/dim] {skipped} (already in catalog)")
    if errors:
        console.print(f"[red]Errors:[/red] {errors}")
    console.print(f"[blue]Total in catalog:[/blue] {database.count_tracks()}")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_scan.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add scan CLI command"
```

---

## Task 9: CLI Search Command

**Files:**
- Modify: `src/dj_catalog/cli.py`
- Create: `tests/test_cli_search.py`

**Step 1: Write failing test for search command**

Create `tests/test_cli_search.py`:
```python
from click.testing import CliRunner

from dj_catalog.cli import main


def test_search_command_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["search", "--help"])
    assert result.exit_code == 0
    assert "query" in result.output.lower() or "QUERY" in result.output


def test_search_with_bpm_filter():
    runner = CliRunner()
    result = runner.invoke(main, ["search", "--bpm-min", "120", "--bpm-max", "130"])
    # Should not crash even with empty DB
    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_search.py -v
```
Expected: FAIL - search command not found

**Step 3: Add search command to CLI**

Add to `src/dj_catalog/cli.py`:
```python
@main.command()
@click.argument("query", required=False)
@click.option("--bpm-min", type=float, help="Minimum BPM")
@click.option("--bpm-max", type=float, help="Maximum BPM")
@click.option("--key", type=str, help="Musical key (e.g., Am, C)")
@click.option("--genre", type=str, help="Genre filter")
@click.option("--artist", type=str, help="Artist filter")
@click.option("--year-min", type=int, help="Minimum year")
@click.option("--year-max", type=int, help="Maximum year")
@click.option("--energy-min", type=float, help="Minimum energy (0-1)")
@click.option("--limit", type=int, default=20, help="Max results")
@click.option("--db", type=click.Path(path_type=Path), help="Database path")
def search(
    query: str | None,
    bpm_min: float | None,
    bpm_max: float | None,
    key: str | None,
    genre: str | None,
    artist: str | None,
    year_min: int | None,
    year_max: int | None,
    energy_min: float | None,
    limit: int,
    db: Path | None,
) -> None:
    """Search tracks by query or filters.

    Use natural language QUERY for semantic search, or filters for precise matching.

    Examples:

        dj search "upbeat dance music from the 90s"

        dj search --bpm-min 120 --bpm-max 130 --key Am

        dj search --genre house --energy-min 0.7
    """
    database = get_db(db)

    if query:
        # Semantic search
        vectors = get_vectors()
        tracks = vectors.search(query, n_results=limit)
        console.print(f"[bold]Semantic search:[/bold] {query}\n")
    else:
        # Filter search
        tracks = database.search_tracks(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            key=key,
            genre=genre,
            artist=artist,
            year_min=year_min,
            year_max=year_max,
            energy_min=energy_min,
            limit=limit,
        )
        console.print("[bold]Filter search[/bold]\n")

    database.close()

    if not tracks:
        console.print("[yellow]No tracks found.[/yellow]")
        return

    console.print(f"Found [green]{len(tracks)}[/green] tracks:\n")

    for i, track in enumerate(tracks, 1):
        title = track.title or track.file_path.name
        artist = track.artist or "Unknown"
        bpm = f"{track.bpm:.0f}" if track.bpm else "?"
        key_str = track.key or "?"

        console.print(f"  {i:2}. [cyan]{title}[/cyan] - {artist}")
        console.print(f"      BPM: {bpm} | Key: {key_str} | Genre: {track.genre or '?'}")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_search.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add search CLI command with semantic and filter modes"
```

---

## Task 10: CLI Playlist Command

**Files:**
- Modify: `src/dj_catalog/cli.py`
- Create: `src/dj_catalog/playlist.py`
- Create: `tests/test_playlist.py`

**Step 1: Write failing test for playlist generator**

Create `tests/test_playlist.py`:
```python
from pathlib import Path

import pytest

from dj_catalog.playlist import generate_playlist, PlaylistCriteria
from dj_catalog.models import Track


@pytest.fixture
def sample_tracks() -> list[Track]:
    return [
        Track(file_path=Path(f"/music/{i}.mp3"), title=f"Song {i}",
              bpm=bpm, key=key, energy=energy, genre=genre, file_hash=f"h{i}")
        for i, (bpm, key, energy, genre) in enumerate([
            (120, "Am", 0.8, "house"),
            (122, "Am", 0.75, "house"),
            (125, "Cm", 0.9, "techno"),
            (128, "Am", 0.85, "techno"),
            (90, "C", 0.3, "ambient"),
        ])
    ]


def test_generate_playlist_by_bpm(sample_tracks):
    criteria = PlaylistCriteria(bpm_range=(118, 126))

    playlist = generate_playlist(sample_tracks, criteria, max_tracks=10)

    assert len(playlist) == 3
    for track in playlist:
        assert 118 <= track.bpm <= 126


def test_generate_playlist_harmonic_mixing(sample_tracks):
    criteria = PlaylistCriteria(
        bpm_range=(115, 130),
        harmonic_mixing=True,
        start_key="Am",
    )

    playlist = generate_playlist(sample_tracks, criteria, max_tracks=3)

    # Should prefer tracks in compatible keys
    assert len(playlist) >= 1
    # First track should be in Am or compatible key
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_playlist.py -v
```
Expected: FAIL - playlist module not found

**Step 3: Implement playlist generator**

Create `src/dj_catalog/playlist.py`:
```python
from dataclasses import dataclass, field
from pathlib import Path
import logging

from dj_catalog.models import Track

logger = logging.getLogger(__name__)

# Camelot wheel for harmonic mixing
CAMELOT_WHEEL = {
    "Am": "8A", "Em": "9A", "Bm": "10A", "F#m": "11A",
    "C#m": "12A", "G#m": "1A", "D#m": "2A", "A#m": "3A",
    "Fm": "4A", "Cm": "5A", "Gm": "6A", "Dm": "7A",
    "C": "8B", "G": "9B", "D": "10B", "A": "11B",
    "E": "12B", "B": "1B", "F#": "2B", "C#": "3B",
    "G#": "4B", "D#": "5B", "A#": "6B", "F": "7B",
}

CAMELOT_TO_KEY = {v: k for k, v in CAMELOT_WHEEL.items()}


def get_compatible_keys(key: str) -> set[str]:
    """Get harmonically compatible keys (Camelot wheel neighbors)."""
    if key not in CAMELOT_WHEEL:
        return {key}

    camelot = CAMELOT_WHEEL[key]
    num = int(camelot[:-1])
    letter = camelot[-1]

    compatible = set()

    # Same position
    compatible.add(key)

    # +1 / -1 on wheel
    for offset in [-1, 1]:
        new_num = ((num - 1 + offset) % 12) + 1
        neighbor = f"{new_num}{letter}"
        if neighbor in CAMELOT_TO_KEY:
            compatible.add(CAMELOT_TO_KEY[neighbor])

    # Parallel major/minor
    other_letter = "B" if letter == "A" else "A"
    parallel = f"{num}{other_letter}"
    if parallel in CAMELOT_TO_KEY:
        compatible.add(CAMELOT_TO_KEY[parallel])

    return compatible


@dataclass
class PlaylistCriteria:
    """Criteria for generating a playlist."""

    bpm_range: tuple[float, float] | None = None
    key: str | None = None
    genre: str | None = None
    mood: str | None = None
    energy_range: tuple[float, float] | None = None
    year_range: tuple[int, int] | None = None

    harmonic_mixing: bool = False
    start_key: str | None = None

    # BPM tolerance for transitions (percentage)
    bpm_tolerance: float = 0.06  # 6%


def score_track(track: Track, criteria: PlaylistCriteria, prev_track: Track | None = None) -> float:
    """Score a track based on criteria and previous track."""
    score = 1.0

    # BPM range check
    if criteria.bpm_range and track.bpm:
        bpm_min, bpm_max = criteria.bpm_range
        if bpm_min <= track.bpm <= bpm_max:
            # Prefer tracks in the middle of the range
            mid = (bpm_min + bpm_max) / 2
            score += 0.5 * (1 - abs(track.bpm - mid) / (bpm_max - bpm_min))
        else:
            return 0  # Out of range

    # Genre match
    if criteria.genre and track.genre:
        if criteria.genre.lower() in track.genre.lower():
            score += 1.0

    # Energy range
    if criteria.energy_range and track.energy is not None:
        e_min, e_max = criteria.energy_range
        if e_min <= track.energy <= e_max:
            score += 0.5
        else:
            score *= 0.5

    # Mood match
    if criteria.mood and track.mood:
        if criteria.mood.lower() in track.mood.lower():
            score += 1.5

    # Harmonic mixing with previous track
    if criteria.harmonic_mixing and prev_track and prev_track.key and track.key:
        compatible = get_compatible_keys(prev_track.key)
        if track.key in compatible:
            score += 2.0  # Big bonus for harmonic compatibility
        else:
            score *= 0.3  # Penalty for key clash

    # BPM transition smoothness
    if prev_track and prev_track.bpm and track.bpm:
        bpm_diff = abs(track.bpm - prev_track.bpm) / prev_track.bpm
        if bpm_diff <= criteria.bpm_tolerance:
            score += 1.0
        elif bpm_diff <= criteria.bpm_tolerance * 2:
            score += 0.5
        else:
            score *= 0.5

    return score


def generate_playlist(
    tracks: list[Track],
    criteria: PlaylistCriteria,
    max_tracks: int = 20,
) -> list[Track]:
    """Generate a playlist from available tracks based on criteria.

    Uses greedy algorithm: always pick the highest-scoring next track.
    """
    if not tracks:
        return []

    # Filter by hard constraints first
    candidates = []
    for track in tracks:
        if criteria.bpm_range and track.bpm:
            bpm_min, bpm_max = criteria.bpm_range
            if not (bpm_min <= track.bpm <= bpm_max):
                continue
        if criteria.year_range and track.year:
            y_min, y_max = criteria.year_range
            if not (y_min <= track.year <= y_max):
                continue
        candidates.append(track)

    if not candidates:
        return []

    playlist: list[Track] = []
    used_hashes: set[str] = set()

    # Pick first track
    if criteria.harmonic_mixing and criteria.start_key:
        # Find best starting track in the specified key
        start_candidates = [t for t in candidates
                          if t.key == criteria.start_key and t.file_hash not in used_hashes]
        if start_candidates:
            first = max(start_candidates, key=lambda t: score_track(t, criteria))
        else:
            first = max(candidates, key=lambda t: score_track(t, criteria))
    else:
        first = max(candidates, key=lambda t: score_track(t, criteria))

    playlist.append(first)
    if first.file_hash:
        used_hashes.add(first.file_hash)

    # Greedily add tracks
    while len(playlist) < max_tracks:
        prev = playlist[-1]
        remaining = [t for t in candidates if t.file_hash not in used_hashes]

        if not remaining:
            break

        # Score all remaining tracks
        scored = [(t, score_track(t, criteria, prev)) for t in remaining]
        scored = [(t, s) for t, s in scored if s > 0]

        if not scored:
            break

        # Pick best
        best_track, _ = max(scored, key=lambda x: x[1])
        playlist.append(best_track)
        if best_track.file_hash:
            used_hashes.add(best_track.file_hash)

    return playlist
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_playlist.py -v
```
Expected: PASS

**Step 5: Add playlist command to CLI**

Add to `src/dj_catalog/cli.py`:
```python
from dj_catalog.playlist import generate_playlist, PlaylistCriteria
from dj_catalog.export import export_m3u, export_rekordbox_xml


@main.command()
@click.option("--bpm-min", type=float, help="Minimum BPM")
@click.option("--bpm-max", type=float, help="Maximum BPM")
@click.option("--key", type=str, help="Starting key for harmonic mixing")
@click.option("--genre", type=str, help="Genre filter")
@click.option("--mood", type=str, help="Mood filter (e.g., 'peak', 'chill', 'dark')")
@click.option("--energy-min", type=float, help="Minimum energy (0-1)")
@click.option("--energy-max", type=float, help="Maximum energy (0-1)")
@click.option("--harmonic/--no-harmonic", default=True, help="Use harmonic mixing")
@click.option("--count", type=int, default=20, help="Number of tracks")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--format", "fmt", type=click.Choice(["m3u", "rekordbox"]), default="m3u",
              help="Output format: m3u (standard) or rekordbox (XML for Rekordbox import)")
@click.option("--db", type=click.Path(path_type=Path), help="Database path")
def playlist(
    bpm_min: float | None,
    bpm_max: float | None,
    key: str | None,
    genre: str | None,
    mood: str | None,
    energy_min: float | None,
    energy_max: float | None,
    harmonic: bool,
    count: int,
    output: Path | None,
    fmt: str,
    db: Path | None,
) -> None:
    """Generate a playlist based on criteria.

    Supports natural DJ criteria like genre, BPM range, mood, and energy level.
    Exports to M3U (standard) or Rekordbox XML format for direct import.

    Examples:

        dj playlist --genre techno --bpm-min 128 --bpm-max 132 --mood peak

        dj playlist --genre house --energy-min 0.7 -o party.m3u

        dj playlist --genre techno --format rekordbox -o set.xml
    """
    database = get_db(db)
    all_tracks = database.get_all_tracks()
    database.close()

    if not all_tracks:
        console.print("[yellow]No tracks in catalog. Run 'dj scan' first.[/yellow]")
        return

    criteria = PlaylistCriteria(
        bpm_range=(bpm_min, bpm_max) if bpm_min and bpm_max else None,
        key=key,
        genre=genre,
        mood=mood,
        energy_range=(energy_min or 0, energy_max or 1) if energy_min or energy_max else None,
        harmonic_mixing=harmonic,
        start_key=key,
    )

    tracks = generate_playlist(all_tracks, criteria, max_tracks=count)

    if not tracks:
        console.print("[yellow]No tracks match criteria.[/yellow]")
        return

    console.print(f"\n[bold]Generated playlist:[/bold] {len(tracks)} tracks\n")

    for i, track in enumerate(tracks, 1):
        title = track.title or track.file_path.name
        artist = track.artist or "Unknown"
        bpm = f"{track.bpm:.0f}" if track.bpm else "?"

        console.print(f"  {i:2}. [cyan]{title}[/cyan] - {artist}")
        console.print(f"      BPM: {bpm} | Key: {track.key or '?'} | Mood: {track.mood or '?'}")

    if output:
        if fmt == "rekordbox":
            export_rekordbox_xml(tracks, output)
            console.print(f"\n[green]Saved Rekordbox XML to:[/green] {output}")
            console.print("[dim]Import in Rekordbox: File > Import > rekordbox xml[/dim]")
        else:
            export_m3u(tracks, output)
            console.print(f"\n[green]Saved M3U to:[/green] {output}")
```

**Step 6: Run all tests**

```bash
uv run pytest -v
```
Expected: All PASS

**Step 7: Commit**

```bash
git add .
git commit -m "feat: add playlist generator with harmonic mixing and mood filter"
```

---

## Task 11: Export Module (M3U + Rekordbox XML)

**Files:**
- Create: `src/dj_catalog/export.py`
- Create: `tests/test_export.py`

**Step 1: Write failing test for export**

Create `tests/test_export.py`:
```python
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

import pytest

from dj_catalog.export import export_m3u, export_rekordbox_xml
from dj_catalog.models import Track


@pytest.fixture
def sample_tracks() -> list[Track]:
    return [
        Track(
            file_path=Path("/music/track1.mp3"),
            title="Track One",
            artist="Artist A",
            album="Album 1",
            duration_seconds=240.0,
            bpm=128.0,
            key="Am",
            file_hash="hash1",
        ),
        Track(
            file_path=Path("/music/track2.mp3"),
            title="Track Two",
            artist="Artist B",
            album="Album 2",
            duration_seconds=300.0,
            bpm=130.0,
            key="Cm",
            file_hash="hash2",
        ),
    ]


def test_export_m3u(sample_tracks):
    with tempfile.NamedTemporaryFile(suffix=".m3u", delete=False) as f:
        output = Path(f.name)

    export_m3u(sample_tracks, output)

    content = output.read_text()
    assert "#EXTM3U" in content
    assert "Track One" in content
    assert "/music/track1.mp3" in content
    assert "#EXTINF:240" in content

    output.unlink()


def test_export_rekordbox_xml(sample_tracks):
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        output = Path(f.name)

    export_rekordbox_xml(sample_tracks, output)

    # Parse and validate XML structure
    tree = ET.parse(output)
    root = tree.getroot()

    assert root.tag == "DJ_PLAYLISTS"
    assert root.attrib.get("Version") == "1.0.0"

    # Check COLLECTION
    collection = root.find("COLLECTION")
    assert collection is not None
    tracks = collection.findall("TRACK")
    assert len(tracks) == 2

    # Check track attributes
    track1 = tracks[0]
    assert track1.attrib["Name"] == "Track One"
    assert track1.attrib["Artist"] == "Artist A"
    assert "128" in track1.attrib.get("AverageBpm", "")

    # Check PLAYLISTS
    playlists = root.find("PLAYLISTS")
    assert playlists is not None

    output.unlink()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_export.py -v
```
Expected: FAIL - export module not found

**Step 3: Implement export module**

Create `src/dj_catalog/export.py`:
```python
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
import logging

from dj_catalog.models import Track

logger = logging.getLogger(__name__)


def export_m3u(tracks: list[Track], output_path: Path) -> None:
    """Export playlist to M3U format.

    Args:
        tracks: List of tracks to export
        output_path: Path to write M3U file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for track in tracks:
            duration = int(track.duration_seconds or 0)
            title = track.title or track.file_path.name
            artist = track.artist or "Unknown"
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")
            f.write(f"{track.file_path}\n")

    logger.info(f"Exported {len(tracks)} tracks to M3U: {output_path}")


def export_rekordbox_xml(
    tracks: list[Track],
    output_path: Path,
    playlist_name: str = "DJ Catalog Export",
) -> None:
    """Export playlist to Rekordbox XML format.

    Creates a Rekordbox-compatible XML file that can be imported via:
    File > Import > rekordbox xml

    Args:
        tracks: List of tracks to export
        output_path: Path to write XML file
        playlist_name: Name of the playlist in Rekordbox
    """
    # Root element
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")

    # Product info
    product = ET.SubElement(root, "PRODUCT")
    product.set("Name", "dj-catalog")
    product.set("Version", "0.1.0")
    product.set("Company", "")

    # Collection (all tracks)
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(tracks)))

    for i, track in enumerate(tracks, 1):
        track_elem = ET.SubElement(collection, "TRACK")

        # Required attributes
        track_elem.set("TrackID", str(i))
        track_elem.set("Name", track.title or track.file_path.stem)
        track_elem.set("Artist", track.artist or "")
        track_elem.set("Album", track.album or "")
        track_elem.set("Genre", track.genre or "")

        # File location (file:// URI for Rekordbox)
        location = f"file://localhost{track.file_path}"
        track_elem.set("Location", location)

        # Duration in seconds
        if track.duration_seconds:
            track_elem.set("TotalTime", str(int(track.duration_seconds)))

        # BPM
        if track.bpm:
            track_elem.set("AverageBpm", f"{track.bpm:.2f}")

        # Key (Rekordbox uses different notation, but accepts standard too)
        if track.key:
            track_elem.set("Tonality", track.key)

        # Year
        if track.year:
            track_elem.set("Year", str(track.year))

        # Track number
        if track.track_number:
            track_elem.set("TrackNumber", str(track.track_number))

    # Playlists section
    playlists = ET.SubElement(root, "PLAYLISTS")

    # Root folder
    root_node = ET.SubElement(
        playlists, "NODE",
        Type="0",  # 0 = folder
        Name="ROOT",
        Count="1"
    )

    # The actual playlist
    playlist_node = ET.SubElement(
        root_node, "NODE",
        Type="1",  # 1 = playlist
        Name=playlist_name,
        KeyType="0",
        Entries=str(len(tracks))
    )

    # Add track references to playlist
    for i in range(1, len(tracks) + 1):
        ET.SubElement(playlist_node, "TRACK", Key=str(i))

    # Write with XML declaration
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")  # Pretty print

    with open(output_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    logger.info(f"Exported {len(tracks)} tracks to Rekordbox XML: {output_path}")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_export.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add export module with M3U and Rekordbox XML formats"
```

---

## Task 12: CLI Stats Command

**Files:**
- Modify: `src/dj_catalog/cli.py`
- Create: `tests/test_cli_stats.py`

**Step 1: Write failing test for stats command**

Create `tests/test_cli_stats.py`:
```python
from click.testing import CliRunner

from dj_catalog.cli import main


def test_stats_command_exists():
    runner = CliRunner()
    result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0


def test_stats_shows_counts():
    runner = CliRunner()
    result = runner.invoke(main, ["stats"])
    # Should show some statistics even if empty
    assert "track" in result.output.lower() or "catalog" in result.output.lower()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_stats.py -v
```
Expected: FAIL - stats command not found

**Step 3: Add stats command**

Add to `src/dj_catalog/cli.py`:
```python
from collections import Counter


@main.command()
@click.option("--db", type=click.Path(path_type=Path), help="Database path")
def stats(db: Path | None) -> None:
    """Show catalog statistics."""
    database = get_db(db)
    tracks = database.get_all_tracks()
    database.close()

    if not tracks:
        console.print("[yellow]Catalog is empty. Run 'dj scan' first.[/yellow]")
        return

    # Basic counts
    total = len(tracks)
    analyzed = sum(1 for t in tracks if t.bpm is not None)

    console.print(f"\n[bold]Catalog Statistics[/bold]\n")
    console.print(f"  Total tracks:    [green]{total}[/green]")
    console.print(f"  Analyzed:        [green]{analyzed}[/green]")

    # Genre distribution
    genres = Counter(t.genre for t in tracks if t.genre)
    if genres:
        console.print(f"\n[bold]Top Genres:[/bold]")
        for genre, count in genres.most_common(10):
            console.print(f"    {genre}: {count}")

    # BPM distribution
    bpms = [t.bpm for t in tracks if t.bpm]
    if bpms:
        console.print(f"\n[bold]BPM Range:[/bold]")
        console.print(f"    Min: {min(bpms):.0f}")
        console.print(f"    Max: {max(bpms):.0f}")
        console.print(f"    Avg: {sum(bpms)/len(bpms):.0f}")

    # Key distribution
    keys = Counter(t.key for t in tracks if t.key)
    if keys:
        console.print(f"\n[bold]Top Keys:[/bold]")
        for key, count in keys.most_common(5):
            console.print(f"    {key}: {count}")

    # Year distribution
    years = [t.year for t in tracks if t.year]
    if years:
        console.print(f"\n[bold]Year Range:[/bold]")
        console.print(f"    {min(years)} - {max(years)}")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_stats.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add stats CLI command"
```

---

## Task 13: Final Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

Create `tests/test_integration.py`:
```python
"""End-to-end integration test."""
from pathlib import Path
import tempfile
import wave
import struct

import pytest
from click.testing import CliRunner

from dj_catalog.cli import main


@pytest.fixture
def music_dir():
    """Create a temp directory with test audio files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        music = base / "music"
        music.mkdir()

        # Create valid WAV files
        for i, name in enumerate(["track1.wav", "track2.wav", "track3.wav"]):
            filepath = music / name
            with wave.open(str(filepath), 'w') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(22050)
                # 2 seconds of audio
                samples = [int(32767 * 0.5 * ((i + j) % 100) / 100)
                          for j in range(22050 * 2)]
                f.writeframes(struct.pack('<' + 'h' * len(samples), *samples))

        yield base


def test_full_workflow(music_dir: Path):
    """Test: scan -> stats -> search -> playlist."""
    runner = CliRunner()
    db_path = music_dir / "test.db"
    music_path = music_dir / "music"

    # 1. Scan
    result = runner.invoke(main, [
        "scan", str(music_path),
        "--db", str(db_path),
        "--no-analyze",  # Skip analysis for speed
    ])
    assert result.exit_code == 0, f"Scan failed: {result.output}"
    assert "3" in result.output or "Processed" in result.output

    # 2. Stats
    result = runner.invoke(main, ["stats", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "3" in result.output or "Total" in result.output

    # 3. Search
    result = runner.invoke(main, ["search", "--db", str(db_path)])
    assert result.exit_code == 0

    # 4. Playlist (with output file)
    playlist_path = music_dir / "test.m3u"
    result = runner.invoke(main, [
        "playlist",
        "--db", str(db_path),
        "--no-harmonic",
        "-o", str(playlist_path),
    ])
    assert result.exit_code == 0
    assert playlist_path.exists()

    # Verify M3U content
    content = playlist_path.read_text()
    assert "#EXTM3U" in content
```

**Step 2: Run integration test**

```bash
uv run pytest tests/test_integration.py -v
```
Expected: PASS

**Step 3: Run full test suite**

```bash
uv run pytest -v --tb=short
```
Expected: All PASS

**Step 4: Final commit**

```bash
git add .
git commit -m "test: add integration tests"
```

---

## Summary

The implementation includes:

1. **Project scaffolding** - pyproject.toml with all dependencies
2. **Track model** - Pydantic model with all metadata fields
3. **File scanner** - Finds audio files recursively
4. **Metadata extractor** - Reads ID3/FLAC/M4A tags via mutagen
5. **Audio analyzer** - BPM, key, energy via librosa
6. **SQLite database** - Structured storage with search + incremental scan support
7. **ChromaDB vectors** - Semantic search ready for RAG
8. **Playlist generator** - Genre, BPM, mood, energy, harmonic mixing
9. **Export module** - M3U + Rekordbox XML for DJ software import
10. **CLI commands** - scan (incremental), search, playlist, stats

**Key features:**
- **Incremental scanning** - Only new files processed on re-scan (hash-based dedup)
- **Rekordbox export** - Native XML format for direct import to Rekordbox
- **Mood/energy filtering** - Build playlists by "peak dance floor", "chill", etc.
- **Harmonic mixing** - Camelot wheel-based key compatibility

**Future enhancements** (not in this POC):
- Genre classification ML model
- Mood auto-detection from audio
- Web UI
- Spotify/Apple Music import
- RAG chat interface ("find songs like X")
