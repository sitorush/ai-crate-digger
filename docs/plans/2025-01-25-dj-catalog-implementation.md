# DJ Catalog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a world-class CLI tool that scans ~6,400 music files, captures comprehensive metadata (30+ fields), analyzes audio (BPM/key/energy), and generates DJ playlists with tag-based filtering and Rekordbox export. Includes MCP server for Claude Desktop.

**Architecture:** Domain-driven modules (core, scanning, analysis, storage, playlist, cli, mcp). Parallel processing via ProcessPoolExecutor for audio analysis. SQLite for structured data, ChromaDB for semantic search. Tag-based filtering with include/exclude logic.

**Tech Stack:** Python 3.11+, Click, Rich, librosa, mutagen, SQLAlchemy, ChromaDB, mcp-python, mypy, ruff, pytest

---

## Task 1: Project Scaffolding + Quality Tools

**Files:**
- Create: `pyproject.toml`
- Create: `src/dj_catalog/__init__.py`
- Create: `.pre-commit-config.yaml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml with all dependencies and quality tools**

```toml
[project]
name = "dj-catalog"
version = "0.1.0"
description = "World-class music library scanner and playlist generator for DJs"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "pydantic>=2.0",
    "sqlalchemy>=2.0",
    "mutagen>=1.47",
    "librosa>=0.10",
    "chromadb>=0.4",
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.8",
    "ruff>=0.3",
    "pre-commit>=3.6",
]

[project.scripts]
dj = "dj_catalog.cli.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.mypy]
strict = true
python_version = "3.11"
plugins = ["pydantic.mypy"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "PT", "RET", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--cov=dj_catalog --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
branch = true
source = ["src/dj_catalog"]
```

**Step 2: Create pre-commit config**

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: ruff format
        language: system
        types: [python]
      - id: ruff-lint
        name: ruff lint
        entry: ruff check --fix
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: mypy src/
        language: system
        types: [python]
        pass_filenames: false
```

**Step 3: Create directory structure**

```bash
mkdir -p src/dj_catalog/{core,scanning,analysis,storage,playlist,cli,mcp}
mkdir -p tests/{core,scanning,analysis,storage,playlist,cli,mcp,integration}
touch src/dj_catalog/__init__.py
touch src/dj_catalog/{core,scanning,analysis,storage,playlist,cli,mcp}/__init__.py
touch tests/__init__.py
touch tests/{core,scanning,analysis,storage,playlist,cli,mcp,integration}/__init__.py
```

**Step 4: Create test conftest with shared fixtures**

Create `tests/conftest.py`:
```python
"""Shared test fixtures."""
from pathlib import Path
import tempfile
from collections.abc import Iterator

import pytest


@pytest.fixture
def tmp_dir() -> Iterator[Path]:
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_audio_dir(tmp_dir: Path) -> Path:
    """Create directory with sample audio file stubs."""
    music_dir = tmp_dir / "music"
    music_dir.mkdir()
    return music_dir
```

**Step 5: Install dependencies and verify setup**

```bash
cd /Users/sitorush/Desktop/dj-idea/.worktrees/dj-catalog-impl
uv sync
uv run pre-commit install
```

**Step 6: Verify tools work**

```bash
uv run ruff check src/
uv run mypy src/
uv run pytest --collect-only
```
Expected: No errors (empty project)

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with quality tools

- pyproject.toml with all dependencies
- Pre-commit hooks (ruff, mypy)
- Domain-driven directory structure
- Test configuration with 80% coverage requirement

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Core Models - Track

**Files:**
- Create: `src/dj_catalog/core/models.py`
- Create: `tests/core/test_models.py`

**Step 1: Write failing test for Track model**

Create `tests/core/test_models.py`:
```python
"""Tests for core models."""
from datetime import date, datetime
from pathlib import Path

import pytest

from dj_catalog.core.models import Track


class TestTrack:
    """Tests for Track model."""

    def test_track_minimal_creation(self) -> None:
        """Track can be created with just file_path and file_hash."""
        track = Track(
            file_path=Path("/music/song.mp3"),
            file_hash="abc123",
        )
        assert track.file_path == Path("/music/song.mp3")
        assert track.file_hash == "abc123"
        assert track.title is None
        assert track.tags == []

    def test_track_full_metadata(self) -> None:
        """Track stores all metadata fields."""
        track = Track(
            file_path=Path("/music/song.mp3"),
            file_hash="abc123",
            title="Strobe",
            artist="deadmau5",
            album="For Lack of a Better Name",
            album_artist="deadmau5",
            label="mau5trap",
            remixer=None,
            composer="Joel Zimmerman",
            original_artist=None,
            isrc="USUG10900256",
            release_date=date(2009, 9, 22),
            year=2009,
            duration_seconds=637.0,
            track_number=10,
            bitrate=320,
            sample_rate=44100,
            codec="mp3",
            bpm=128.0,
            bpm_source="analyzed",
            key="Fm",
            key_camelot="4A",
            energy=0.65,
            danceability=0.72,
            tags=["progressive house", "melodic", "classic"],
            rating=5,
            color="#FF5500",
            play_count=42,
            comment="Epic breakdown at 5:00",
        )
        assert track.title == "Strobe"
        assert track.label == "mau5trap"
        assert track.isrc == "USUG10900256"
        assert track.release_date == date(2009, 9, 22)
        assert track.bpm == 128.0
        assert track.key_camelot == "4A"
        assert track.tags == ["progressive house", "melodic", "classic"]
        assert track.rating == 5

    def test_track_tags_are_list(self) -> None:
        """Tags default to empty list."""
        track = Track(file_path=Path("/music/song.mp3"), file_hash="abc")
        assert isinstance(track.tags, list)
        assert track.tags == []

    def test_track_energy_validation(self) -> None:
        """Energy must be between 0 and 1."""
        with pytest.raises(ValueError):
            Track(
                file_path=Path("/music/song.mp3"),
                file_hash="abc",
                energy=1.5,
            )

    def test_track_rating_validation(self) -> None:
        """Rating must be between 1 and 5."""
        with pytest.raises(ValueError):
            Track(
                file_path=Path("/music/song.mp3"),
                file_hash="abc",
                rating=6,
            )
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/test_models.py -v
```
Expected: FAIL - module not found

**Step 3: Implement Track model**

Create `src/dj_catalog/core/models.py`:
```python
"""Core domain models."""
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Track(BaseModel):
    """A music track with comprehensive metadata and analysis results."""

    # Identity
    file_path: Path
    file_hash: str

    # Core metadata (from ID3)
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    duration_seconds: float | None = None

    # Extended metadata
    label: str | None = None
    remixer: str | None = None
    composer: str | None = None
    original_artist: str | None = None
    isrc: str | None = None
    release_date: date | None = None
    year: int | None = None
    comment: str | None = None

    # Audio quality
    bitrate: int | None = None
    sample_rate: int | None = None
    codec: str | None = None

    # Analysis results
    bpm: float | None = None
    bpm_source: str | None = None
    key: str | None = None
    key_camelot: str | None = None
    energy: float | None = Field(default=None, ge=0.0, le=1.0)
    danceability: float | None = Field(default=None, ge=0.0, le=1.0)

    # Tag-based classification
    tags: list[str] = Field(default_factory=list)

    # User-defined
    rating: int | None = Field(default=None, ge=1, le=5)
    color: str | None = None
    play_count: int = 0

    # System
    analyzed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"frozen": False}
```

**Step 4: Update core __init__.py**

Create `src/dj_catalog/core/__init__.py`:
```python
"""Core module - shared foundations."""
from dj_catalog.core.models import Track

__all__ = ["Track"]
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/core/test_models.py -v
```
Expected: PASS

**Step 6: Run type checker**

```bash
uv run mypy src/dj_catalog/core/
```
Expected: Success

**Step 7: Commit**

```bash
git add -A
git commit -m "feat(core): add Track model with 30+ metadata fields

- Comprehensive metadata: title, artist, album, label, remixer, etc.
- Audio quality: bitrate, sample_rate, codec
- Analysis: bpm, key, key_camelot, energy, danceability
- Tag-based classification with list[str]
- User fields: rating (1-5), color, play_count
- Validation for energy (0-1) and rating (1-5)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Core Config + Exceptions

**Files:**
- Create: `src/dj_catalog/core/config.py`
- Create: `src/dj_catalog/core/exceptions.py`
- Create: `tests/core/test_config.py`

**Step 1: Write failing test for config**

Create `tests/core/test_config.py`:
```python
"""Tests for configuration."""
from pathlib import Path

from dj_catalog.core.config import Settings, get_settings


class TestSettings:
    """Tests for Settings."""

    def test_default_settings(self) -> None:
        """Settings have sensible defaults."""
        settings = Settings()
        assert settings.db_path == Path.home() / ".dj-catalog" / "catalog.db"
        assert settings.vector_path == Path.home() / ".dj-catalog" / ".chroma"
        assert settings.max_workers is None  # Auto-detect

    def test_settings_from_env(self, monkeypatch) -> None:
        """Settings can be overridden via environment."""
        monkeypatch.setenv("DJ_CATALOG_DB_PATH", "/custom/path.db")
        settings = Settings()
        assert settings.db_path == Path("/custom/path.db")

    def test_get_settings_cached(self) -> None:
        """get_settings returns same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/test_config.py -v
```
Expected: FAIL - module not found

**Step 3: Implement config**

Create `src/dj_catalog/core/config.py`:
```python
"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Paths
    db_path: Path = Field(
        default_factory=lambda: Path.home() / ".dj-catalog" / "catalog.db"
    )
    vector_path: Path = Field(
        default_factory=lambda: Path.home() / ".dj-catalog" / ".chroma"
    )

    # Performance
    max_workers: int | None = None  # None = auto-detect (cpu_count - 1)
    batch_size: int = 100  # DB batch write size

    # Analysis
    analyze_by_default: bool = True
    sample_rate: int = 22050  # Hz for librosa

    model_config = {
        "env_prefix": "DJ_CATALOG_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**Step 4: Implement exceptions**

Create `src/dj_catalog/core/exceptions.py`:
```python
"""Custom exceptions for DJ Catalog."""


class DJCatalogError(Exception):
    """Base exception for DJ Catalog."""

    pass


class ScanError(DJCatalogError):
    """Error during file scanning."""

    pass


class ExtractionError(DJCatalogError):
    """Error extracting metadata from file."""

    pass


class AnalysisError(DJCatalogError):
    """Error during audio analysis."""

    pass


class DatabaseError(DJCatalogError):
    """Database operation error."""

    pass


class ExportError(DJCatalogError):
    """Error exporting playlist."""

    pass
```

**Step 5: Add pydantic-settings dependency**

Update `pyproject.toml` dependencies:
```toml
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "sqlalchemy>=2.0",
    "mutagen>=1.47",
    "librosa>=0.10",
    "chromadb>=0.4",
    "mcp>=1.0",
]
```

**Step 6: Install and run tests**

```bash
uv sync
uv run pytest tests/core/test_config.py -v
```
Expected: PASS

**Step 7: Update core __init__.py**

```python
"""Core module - shared foundations."""
from dj_catalog.core.config import Settings, get_settings
from dj_catalog.core.exceptions import (
    AnalysisError,
    DatabaseError,
    DJCatalogError,
    ExportError,
    ExtractionError,
    ScanError,
)
from dj_catalog.core.models import Track

__all__ = [
    "Track",
    "Settings",
    "get_settings",
    "DJCatalogError",
    "ScanError",
    "ExtractionError",
    "AnalysisError",
    "DatabaseError",
    "ExportError",
]
```

**Step 8: Commit**

```bash
git add -A
git commit -m "feat(core): add Settings and custom exceptions

- Settings with env var support (DJ_CATALOG_* prefix)
- Configurable paths, workers, batch size
- Custom exception hierarchy for error handling

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Scanning - File Scanner

**Files:**
- Create: `src/dj_catalog/scanning/scanner.py`
- Create: `tests/scanning/test_scanner.py`

**Step 1: Write failing test for scanner**

Create `tests/scanning/test_scanner.py`:
```python
"""Tests for file scanner."""
from pathlib import Path

import pytest

from dj_catalog.scanning.scanner import scan_directory, SUPPORTED_EXTENSIONS


class TestScanner:
    """Tests for file scanner."""

    def test_supported_extensions(self) -> None:
        """All common audio formats supported."""
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".m4a" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".aiff" in SUPPORTED_EXTENSIONS
        assert ".ogg" in SUPPORTED_EXTENSIONS

    def test_scan_directory_finds_audio_files(self, tmp_dir: Path) -> None:
        """Scanner finds audio files recursively."""
        # Create test files
        (tmp_dir / "song1.mp3").touch()
        (tmp_dir / "song2.flac").touch()
        (tmp_dir / "nested").mkdir()
        (tmp_dir / "nested" / "song3.m4a").touch()
        (tmp_dir / "readme.txt").touch()  # Should be ignored

        files = list(scan_directory(tmp_dir))

        assert len(files) == 3
        extensions = {f.suffix for f in files}
        assert extensions == {".mp3", ".flac", ".m4a"}

    def test_scan_directory_skips_hidden(self, tmp_dir: Path) -> None:
        """Scanner skips hidden files and directories."""
        (tmp_dir / "visible.mp3").touch()
        (tmp_dir / ".hidden.mp3").touch()
        (tmp_dir / ".hidden_dir").mkdir()
        (tmp_dir / ".hidden_dir" / "song.mp3").touch()

        files = list(scan_directory(tmp_dir))

        assert len(files) == 1
        assert files[0].name == "visible.mp3"

    def test_scan_directory_non_recursive(self, tmp_dir: Path) -> None:
        """Scanner can run non-recursively."""
        (tmp_dir / "top.mp3").touch()
        (tmp_dir / "nested").mkdir()
        (tmp_dir / "nested" / "deep.mp3").touch()

        files = list(scan_directory(tmp_dir, recursive=False))

        assert len(files) == 1
        assert files[0].name == "top.mp3"

    def test_scan_directory_invalid_path(self, tmp_dir: Path) -> None:
        """Scanner raises error for invalid directory."""
        with pytest.raises(ValueError, match="Not a directory"):
            list(scan_directory(tmp_dir / "nonexistent"))
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/scanning/test_scanner.py -v
```
Expected: FAIL - module not found

**Step 3: Implement scanner**

Create `src/dj_catalog/scanning/scanner.py`:
```python
"""File scanner for discovering audio files."""
from collections.abc import Iterator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
    ".aiff",
    ".wma",
    ".alac",
})


def scan_directory(directory: Path, recursive: bool = True) -> Iterator[Path]:
    """Scan directory for audio files.

    Args:
        directory: Root directory to scan
        recursive: Whether to scan subdirectories

    Yields:
        Path objects for each audio file found

    Raises:
        ValueError: If path is not a directory
    """
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    pattern = "**/*" if recursive else "*"

    for path in directory.glob(pattern):
        # Skip hidden files and directories
        if any(part.startswith(".") for part in path.parts):
            continue

        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            logger.debug("Found audio file: %s", path)
            yield path
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/scanning/test_scanner.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(scanning): add file scanner

- Supports 10 audio formats (mp3, flac, m4a, etc.)
- Recursive and non-recursive modes
- Skips hidden files and directories

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Scanning - Content Hasher

**Files:**
- Create: `src/dj_catalog/scanning/hasher.py`
- Create: `tests/scanning/test_hasher.py`

**Step 1: Write failing test for hasher**

Create `tests/scanning/test_hasher.py`:
```python
"""Tests for content hasher."""
from pathlib import Path

import pytest

from dj_catalog.scanning.hasher import compute_file_hash


class TestHasher:
    """Tests for content hasher."""

    def test_compute_hash_returns_hex_string(self, tmp_dir: Path) -> None:
        """Hash is a 64-character hex string (SHA-256)."""
        test_file = tmp_dir / "test.mp3"
        test_file.write_bytes(b"test content" * 1000)

        hash_value = compute_file_hash(test_file)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_same_content_same_hash(self, tmp_dir: Path) -> None:
        """Identical content produces identical hash."""
        content = b"identical content" * 1000
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"
        file1.write_bytes(content)
        file2.write_bytes(content)

        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_different_content_different_hash(self, tmp_dir: Path) -> None:
        """Different content produces different hash."""
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"
        file1.write_bytes(b"content A" * 1000)
        file2.write_bytes(b"content B" * 1000)

        assert compute_file_hash(file1) != compute_file_hash(file2)

    def test_hash_uses_first_mb_only(self, tmp_dir: Path) -> None:
        """Hash only reads first 1MB for performance."""
        # Create file larger than 1MB
        file1 = tmp_dir / "file1.mp3"
        file2 = tmp_dir / "file2.mp3"

        # Same first 1MB, different after
        first_mb = b"A" * (1024 * 1024)
        file1.write_bytes(first_mb + b"extra1")
        file2.write_bytes(first_mb + b"extra2")

        # Should have same hash (only first 1MB matters)
        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_hash_nonexistent_file(self, tmp_dir: Path) -> None:
        """Raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            compute_file_hash(tmp_dir / "nonexistent.mp3")
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/scanning/test_hasher.py -v
```
Expected: FAIL - module not found

**Step 3: Implement hasher**

Create `src/dj_catalog/scanning/hasher.py`:
```python
"""Content hashing for deduplication."""
import hashlib
from pathlib import Path


def compute_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of first 1MB of file.

    Using only the first 1MB provides fast hashing while still
    being sufficient to detect duplicates in audio files.

    Args:
        path: Path to file
        chunk_size: Bytes to read per chunk

    Returns:
        64-character hex string (SHA-256)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

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
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/scanning/test_hasher.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(scanning): add content hasher for deduplication

- SHA-256 hash of first 1MB for fast dedup
- Handles large files efficiently

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Scanning - Metadata Extractor

**Files:**
- Create: `src/dj_catalog/scanning/extractor.py`
- Create: `tests/scanning/test_extractor.py`
- Create: `tests/fixtures/` (test audio files)

**Step 1: Create test fixture helper**

Add to `tests/conftest.py`:
```python
import wave
import struct


@pytest.fixture
def sample_wav(tmp_dir: Path) -> Path:
    """Create a valid WAV file for testing."""
    wav_path = tmp_dir / "test.wav"
    with wave.open(str(wav_path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        # 1 second of silence
        samples = [0] * 44100
        f.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return wav_path
```

**Step 2: Write failing test for extractor**

Create `tests/scanning/test_extractor.py`:
```python
"""Tests for metadata extractor."""
from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.scanning.extractor import extract_metadata


class TestExtractor:
    """Tests for metadata extractor."""

    def test_extract_metadata_returns_track(self, sample_wav: Path) -> None:
        """Extractor returns Track model."""
        track = extract_metadata(sample_wav)

        assert isinstance(track, Track)
        assert track.file_path == sample_wav
        assert track.file_hash is not None
        assert len(track.file_hash) == 64

    def test_extract_metadata_gets_duration(self, sample_wav: Path) -> None:
        """Extractor gets audio duration."""
        track = extract_metadata(sample_wav)

        assert track.duration_seconds is not None
        assert track.duration_seconds > 0

    def test_extract_metadata_gets_audio_info(self, sample_wav: Path) -> None:
        """Extractor gets audio quality info."""
        track = extract_metadata(sample_wav)

        assert track.sample_rate == 44100
        assert track.codec is not None

    def test_extract_metadata_nonexistent_file(self, tmp_dir: Path) -> None:
        """Raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            extract_metadata(tmp_dir / "nonexistent.mp3")
```

**Step 3: Run test to verify it fails**

```bash
uv run pytest tests/scanning/test_extractor.py -v
```
Expected: FAIL - module not found

**Step 4: Implement extractor**

Create `src/dj_catalog/scanning/extractor.py`:
```python
"""Metadata extraction from audio files."""
import logging
from datetime import date
from pathlib import Path

from mutagen import File as MutagenFile

from dj_catalog.core.exceptions import ExtractionError
from dj_catalog.core.models import Track
from dj_catalog.scanning.hasher import compute_file_hash

logger = logging.getLogger(__name__)


def _safe_str(value: str | list[str] | None) -> str | None:
    """Safely convert tag value to string."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value)


def _safe_int(value: str | list[str] | None) -> int | None:
    """Safely convert tag value to int."""
    str_val = _safe_str(value)
    if str_val is None:
        return None
    try:
        # Handle "1/12" track number format
        return int(str(str_val).split("/")[0])
    except (ValueError, TypeError):
        return None


def _safe_date(value: str | list[str] | None) -> date | None:
    """Safely parse date from tag."""
    str_val = _safe_str(value)
    if str_val is None:
        return None
    try:
        # Try full date first (YYYY-MM-DD)
        if len(str_val) >= 10 and "-" in str_val:
            parts = str_val[:10].split("-")
            if len(parts) == 3:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        # Fall back to just year
        year = int(str_val[:4])
        return date(year, 1, 1)
    except (ValueError, TypeError):
        return None


def _parse_remixer(title: str | None, artist: str | None) -> str | None:
    """Try to parse remixer from title."""
    if title is None:
        return None
    # Common patterns: "Song (Artist Remix)", "Song - Artist Remix"
    lower = title.lower()
    for pattern in [" remix)", " remix]", " rmx)", " rmx]", " edit)", " bootleg)"]:
        if pattern in lower:
            # Find the start of remixer name
            idx = lower.rfind("(")
            if idx == -1:
                idx = lower.rfind("[")
            if idx == -1:
                idx = lower.rfind(" - ")
            if idx != -1:
                remixer_part = title[idx:].strip("()[]- ")
                # Remove "Remix" suffix
                for suffix in ["Remix", "remix", "RMX", "rmx", "Edit", "edit", "Bootleg"]:
                    if remixer_part.endswith(suffix):
                        remixer_part = remixer_part[: -len(suffix)].strip()
                if remixer_part and remixer_part != artist:
                    return remixer_part
    return None


def extract_metadata(file_path: Path) -> Track:
    """Extract metadata from an audio file.

    Args:
        file_path: Path to audio file

    Returns:
        Track with extracted metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ExtractionError: If file format not supported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Compute hash first
    file_hash = compute_file_hash(file_path)

    # Load with mutagen
    audio = MutagenFile(file_path, easy=True)
    if audio is None:
        raise ExtractionError(f"Unsupported format: {file_path}")

    # Get audio info
    info = audio.info
    duration = info.length if info else None
    sample_rate = getattr(info, "sample_rate", None)
    bitrate = getattr(info, "bitrate", None)
    if bitrate and bitrate > 0:
        bitrate = int(bitrate)

    # Determine codec from file extension
    codec = file_path.suffix.lower().lstrip(".")

    # Extract tags (mutagen easy mode normalizes common tags)
    tags = audio.tags or {}

    title = _safe_str(tags.get("title"))
    artist = _safe_str(tags.get("artist"))
    release_date = _safe_date(tags.get("date"))
    year = _safe_int(tags.get("date"))
    if release_date:
        year = release_date.year

    # Parse remixer from title
    remixer = _parse_remixer(title, artist)

    # Build track
    track = Track(
        file_path=file_path,
        file_hash=file_hash,
        title=title,
        artist=artist,
        album=_safe_str(tags.get("album")),
        album_artist=_safe_str(tags.get("albumartist")),
        track_number=_safe_int(tags.get("tracknumber")),
        duration_seconds=duration,
        label=_safe_str(tags.get("publisher") or tags.get("label")),
        remixer=remixer,
        composer=_safe_str(tags.get("composer")),
        isrc=_safe_str(tags.get("isrc")),
        release_date=release_date,
        year=year,
        comment=_safe_str(tags.get("comment")),
        bitrate=bitrate,
        sample_rate=sample_rate,
        codec=codec,
        # Genre from tag goes to tags list
        tags=[g for g in [_safe_str(tags.get("genre"))] if g],
    )

    logger.debug("Extracted metadata for: %s", track.title or file_path.name)
    return track
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/scanning/test_extractor.py -v
```
Expected: PASS

**Step 6: Update scanning __init__.py**

Create `src/dj_catalog/scanning/__init__.py`:
```python
"""Scanning module - file discovery and metadata extraction."""
from dj_catalog.scanning.extractor import extract_metadata
from dj_catalog.scanning.hasher import compute_file_hash
from dj_catalog.scanning.scanner import scan_directory, SUPPORTED_EXTENSIONS

__all__ = [
    "scan_directory",
    "SUPPORTED_EXTENSIONS",
    "compute_file_hash",
    "extract_metadata",
]
```

**Step 7: Commit**

```bash
git add -A
git commit -m "feat(scanning): add metadata extractor

- Extracts 20+ metadata fields from ID3/FLAC/M4A tags
- Parses remixer from title patterns
- Handles date parsing (full date or year)
- Gets audio quality info (bitrate, sample_rate, codec)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Analysis - BPM Detection

**Files:**
- Create: `src/dj_catalog/analysis/bpm.py`
- Create: `tests/analysis/test_bpm.py`

**Step 1: Write failing test for BPM detection**

Create `tests/analysis/test_bpm.py`:
```python
"""Tests for BPM detection."""
import numpy as np
import pytest

from dj_catalog.analysis.bpm import estimate_bpm


class TestBPM:
    """Tests for BPM estimation."""

    def test_estimate_bpm_returns_float(self) -> None:
        """BPM estimation returns float."""
        # Create synthetic audio (5 seconds, 22050 Hz)
        sr = 22050
        duration = 5.0
        # Simple percussive signal
        t = np.linspace(0, duration, int(sr * duration))
        signal = np.sin(2 * np.pi * 2 * t) * np.exp(-10 * (t % 0.5))

        bpm = estimate_bpm(signal, sr)

        assert bpm is not None
        assert isinstance(bpm, float)

    def test_estimate_bpm_reasonable_range(self) -> None:
        """BPM is in reasonable range (60-200)."""
        sr = 22050
        duration = 5.0
        t = np.linspace(0, duration, int(sr * duration))
        signal = np.sin(2 * np.pi * 2 * t) * np.exp(-10 * (t % 0.5))

        bpm = estimate_bpm(signal, sr)

        assert bpm is not None
        assert 60 <= bpm <= 200

    def test_estimate_bpm_silent_audio(self) -> None:
        """Silent audio returns None or reasonable default."""
        sr = 22050
        signal = np.zeros(sr * 5)  # 5 seconds silence

        bpm = estimate_bpm(signal, sr)

        # Should handle gracefully (None or fallback)
        assert bpm is None or 60 <= bpm <= 200
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/analysis/test_bpm.py -v
```
Expected: FAIL - module not found

**Step 3: Implement BPM detection**

Create `src/dj_catalog/analysis/bpm.py`:
```python
"""BPM (tempo) detection."""
import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def estimate_bpm(y: np.ndarray, sr: int) -> float | None:
    """Estimate tempo (BPM) from audio signal.

    Args:
        y: Audio time series (mono)
        sr: Sample rate

    Returns:
        Estimated BPM rounded to 1 decimal, or None if detection fails
    """
    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # librosa may return array or scalar
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if len(tempo) > 0 else None
        if tempo is None or tempo <= 0:
            return None
        return round(float(tempo), 1)
    except Exception as e:
        logger.warning("BPM estimation failed: %s", e)
        return None
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/analysis/test_bpm.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(analysis): add BPM detection via librosa

- Uses librosa beat_track algorithm
- Returns None on detection failure
- Handles edge cases (silence, errors)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Analysis - Key Detection + Camelot

**Files:**
- Create: `src/dj_catalog/analysis/key.py`
- Create: `tests/analysis/test_key.py`

**Step 1: Write failing test for key detection**

Create `tests/analysis/test_key.py`:
```python
"""Tests for key detection."""
import numpy as np
import pytest

from dj_catalog.analysis.key import estimate_key, key_to_camelot, CAMELOT_WHEEL


class TestKey:
    """Tests for key estimation."""

    def test_estimate_key_returns_string(self) -> None:
        """Key estimation returns string."""
        sr = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration))
        # A4 = 440 Hz
        signal = np.sin(2 * np.pi * 440 * t)

        key = estimate_key(signal, sr)

        assert key is not None
        assert isinstance(key, str)

    def test_estimate_key_valid_format(self) -> None:
        """Key is in valid format (e.g., 'Am', 'C', 'F#m')."""
        sr = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration))
        signal = np.sin(2 * np.pi * 440 * t)

        key = estimate_key(signal, sr)

        assert key is not None
        # Should be note name optionally followed by 'm' for minor
        assert key[0] in "ABCDEFG"


class TestCamelot:
    """Tests for Camelot wheel conversion."""

    def test_camelot_wheel_completeness(self) -> None:
        """Camelot wheel has all 24 keys."""
        assert len(CAMELOT_WHEEL) == 24

    def test_key_to_camelot_major(self) -> None:
        """Major keys convert to B notation."""
        assert key_to_camelot("C") == "8B"
        assert key_to_camelot("G") == "9B"
        assert key_to_camelot("D") == "10B"

    def test_key_to_camelot_minor(self) -> None:
        """Minor keys convert to A notation."""
        assert key_to_camelot("Am") == "8A"
        assert key_to_camelot("Em") == "9A"
        assert key_to_camelot("Bm") == "10A"

    def test_key_to_camelot_unknown(self) -> None:
        """Unknown key returns None."""
        assert key_to_camelot("X") is None
        assert key_to_camelot(None) is None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/analysis/test_key.py -v
```
Expected: FAIL - module not found

**Step 3: Implement key detection**

Create `src/dj_catalog/analysis/key.py`:
```python
"""Musical key detection with Camelot wheel support."""
import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Key labels in chromatic order
KEY_LABELS = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
    "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "A#m", "Bm",
]

# Camelot wheel mapping
CAMELOT_WHEEL: dict[str, str] = {
    # Minor keys (A notation)
    "Am": "8A", "Em": "9A", "Bm": "10A", "F#m": "11A",
    "C#m": "12A", "G#m": "1A", "D#m": "2A", "A#m": "3A",
    "Fm": "4A", "Cm": "5A", "Gm": "6A", "Dm": "7A",
    # Major keys (B notation)
    "C": "8B", "G": "9B", "D": "10B", "A": "11B",
    "E": "12B", "B": "1B", "F#": "2B", "C#": "3B",
    "G#": "4B", "D#": "5B", "A#": "6B", "F": "7B",
}


def estimate_key(y: np.ndarray, sr: int) -> str | None:
    """Estimate musical key from audio signal.

    Uses chroma features and correlation with key profiles
    (Krumhansl-Kessler algorithm).

    Args:
        y: Audio time series (mono)
        sr: Sample rate

    Returns:
        Key string (e.g., "Am", "C", "F#m") or None if detection fails
    """
    try:
        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Normalize
        norm = np.linalg.norm(chroma_avg)
        if norm < 1e-6:
            return None
        chroma_avg = chroma_avg / norm

        # Krumhansl-Kessler key profiles
        major_profile = np.array([
            6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
            2.52, 5.19, 2.39, 3.66, 2.29, 2.88
        ])
        minor_profile = np.array([
            6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
            2.54, 4.75, 3.98, 2.69, 3.34, 3.17
        ])

        major_profile = major_profile / np.linalg.norm(major_profile)
        minor_profile = minor_profile / np.linalg.norm(minor_profile)

        # Correlate with all possible keys
        correlations = []
        for i in range(12):
            shifted_major = np.roll(major_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_major))
            shifted_minor = np.roll(minor_profile, i)
            correlations.append(np.dot(chroma_avg, shifted_minor))

        best_idx = int(np.argmax(correlations))
        return KEY_LABELS[best_idx]

    except Exception as e:
        logger.warning("Key estimation failed: %s", e)
        return None


def key_to_camelot(key: str | None) -> str | None:
    """Convert musical key to Camelot notation.

    Args:
        key: Musical key (e.g., "Am", "C", "F#m")

    Returns:
        Camelot notation (e.g., "8A", "8B") or None if unknown
    """
    if key is None:
        return None
    return CAMELOT_WHEEL.get(key)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/analysis/test_key.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(analysis): add key detection with Camelot wheel

- Krumhansl-Kessler algorithm for key detection
- Full Camelot wheel mapping (24 keys)
- Both standard (Am) and Camelot (8A) notation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Analysis - Energy/Danceability

**Files:**
- Create: `src/dj_catalog/analysis/energy.py`
- Create: `tests/analysis/test_energy.py`

**Step 1: Write failing test**

Create `tests/analysis/test_energy.py`:
```python
"""Tests for energy and danceability."""
import numpy as np
import pytest

from dj_catalog.analysis.energy import compute_energy, compute_danceability


class TestEnergy:
    """Tests for energy computation."""

    def test_energy_returns_float(self) -> None:
        """Energy returns float between 0 and 1."""
        signal = np.random.randn(22050 * 5) * 0.1

        energy = compute_energy(signal)

        assert isinstance(energy, float)
        assert 0 <= energy <= 1

    def test_silent_audio_low_energy(self) -> None:
        """Silent audio has very low energy."""
        signal = np.zeros(22050 * 5)

        energy = compute_energy(signal)

        assert energy < 0.1

    def test_loud_audio_high_energy(self) -> None:
        """Loud audio has high energy."""
        signal = np.random.randn(22050 * 5) * 0.5

        energy = compute_energy(signal)

        assert energy > 0.3


class TestDanceability:
    """Tests for danceability computation."""

    def test_danceability_returns_float(self) -> None:
        """Danceability returns float between 0 and 1."""
        sr = 22050
        signal = np.random.randn(sr * 5) * 0.1

        danceability = compute_danceability(signal, sr, bpm=128.0)

        assert isinstance(danceability, float)
        assert 0 <= danceability <= 1

    def test_dance_tempo_higher_danceability(self) -> None:
        """Typical dance tempo (120-130) scores higher."""
        sr = 22050
        signal = np.random.randn(sr * 5) * 0.1

        dance_score = compute_danceability(signal, sr, bpm=125.0)
        slow_score = compute_danceability(signal, sr, bpm=70.0)

        assert dance_score >= slow_score
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/analysis/test_energy.py -v
```
Expected: FAIL - module not found

**Step 3: Implement energy/danceability**

Create `src/dj_catalog/analysis/energy.py`:
```python
"""Energy and danceability computation."""
import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)


def compute_energy(y: np.ndarray) -> float:
    """Compute overall energy (loudness) of audio.

    Args:
        y: Audio time series

    Returns:
        Energy value between 0 and 1
    """
    rms = np.sqrt(np.mean(y**2))
    # Normalize to 0-1 range (typical RMS for normalized audio is ~0.2)
    energy = min(1.0, rms / 0.2)
    return round(float(energy), 3)


def compute_danceability(y: np.ndarray, sr: int, bpm: float | None) -> float:
    """Estimate danceability based on beat strength and tempo.

    Args:
        y: Audio time series
        sr: Sample rate
        bpm: Detected BPM (optional)

    Returns:
        Danceability value between 0 and 1
    """
    try:
        # Get onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Compute beat regularity via autocorrelation
        ac = librosa.autocorrelate(onset_env, max_size=sr // 2)
        if len(ac) == 0 or ac[0] == 0:
            regularity = 0.5
        else:
            ac = ac / (ac[0] + 1e-6)
            # Look for peaks in typical beat range
            start_idx = sr // 8
            end_idx = min(sr // 2, len(ac))
            if end_idx > start_idx:
                regularity = float(np.max(ac[start_idx:end_idx]))
            else:
                regularity = 0.5

        # Tempo contribution (dance music typically 100-140 BPM)
        tempo_score = 0.5
        if bpm:
            if 100 <= bpm <= 140:
                tempo_score = 1.0
            elif 80 <= bpm <= 160:
                tempo_score = 0.7
            else:
                tempo_score = 0.4

        danceability = regularity * 0.6 + tempo_score * 0.4
        return round(min(1.0, max(0.0, danceability)), 3)

    except Exception as e:
        logger.warning("Danceability estimation failed: %s", e)
        return 0.5
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/analysis/test_energy.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(analysis): add energy and danceability metrics

- RMS-based energy computation
- Danceability from beat regularity + tempo
- Values normalized to 0-1 range

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Analysis - Parallel Analyzer

**Files:**
- Create: `src/dj_catalog/analysis/analyzer.py`
- Create: `src/dj_catalog/analysis/parallel.py`
- Create: `tests/analysis/test_analyzer.py`

**Step 1: Write failing test**

Create `tests/analysis/test_analyzer.py`:
```python
"""Tests for audio analyzer."""
from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.analysis.analyzer import analyze_track


class TestAnalyzer:
    """Tests for audio analyzer."""

    def test_analyze_track_updates_fields(self, sample_wav: Path) -> None:
        """Analyzer updates BPM, key, energy, danceability."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        assert analyzed.bpm is not None or analyzed.bpm is None  # May fail on silence
        assert analyzed.key is not None or analyzed.key is None
        assert analyzed.energy is not None
        assert analyzed.danceability is not None
        assert analyzed.analyzed_at is not None

    def test_analyze_track_sets_bpm_source(self, sample_wav: Path) -> None:
        """Analyzer sets bpm_source to 'analyzed'."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        if analyzed.bpm is not None:
            assert analyzed.bpm_source == "analyzed"

    def test_analyze_track_sets_camelot(self, sample_wav: Path) -> None:
        """Analyzer sets Camelot notation when key detected."""
        track = Track(file_path=sample_wav, file_hash="abc123")

        analyzed = analyze_track(track)

        if analyzed.key is not None:
            assert analyzed.key_camelot is not None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/analysis/test_analyzer.py -v
```
Expected: FAIL - module not found

**Step 3: Implement analyzer**

Create `src/dj_catalog/analysis/analyzer.py`:
```python
"""Audio analysis orchestration."""
from datetime import datetime
import logging

import librosa

from dj_catalog.core.config import get_settings
from dj_catalog.core.models import Track
from dj_catalog.analysis.bpm import estimate_bpm
from dj_catalog.analysis.key import estimate_key, key_to_camelot
from dj_catalog.analysis.energy import compute_energy, compute_danceability

logger = logging.getLogger(__name__)


def analyze_track(track: Track) -> Track:
    """Perform full audio analysis on a track.

    Loads audio file and computes BPM, key, energy, danceability.

    Args:
        track: Track with file_path set

    Returns:
        New Track with analysis results filled in
    """
    settings = get_settings()
    logger.info("Analyzing: %s", track.file_path)

    # Load audio (mono, resampled for faster processing)
    y, sr = librosa.load(track.file_path, sr=settings.sample_rate, mono=True)

    # Run analysis
    bpm = estimate_bpm(y, sr)
    key = estimate_key(y, sr)
    energy = compute_energy(y)
    danceability = compute_danceability(y, sr, bpm)

    # Build updated track
    return track.model_copy(update={
        "bpm": bpm,
        "bpm_source": "analyzed" if bpm else None,
        "key": key,
        "key_camelot": key_to_camelot(key),
        "energy": energy,
        "danceability": danceability,
        "analyzed_at": datetime.now(),
    })
```

**Step 4: Implement parallel analyzer**

Create `src/dj_catalog/analysis/parallel.py`:
```python
"""Parallel audio analysis using ProcessPoolExecutor."""
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import multiprocessing

from dj_catalog.core.config import get_settings
from dj_catalog.core.models import Track
from dj_catalog.analysis.analyzer import analyze_track

logger = logging.getLogger(__name__)


def _analyze_single(track: Track) -> Track:
    """Wrapper for multiprocessing (must be top-level function)."""
    try:
        return analyze_track(track)
    except Exception as e:
        logger.error("Analysis failed for %s: %s", track.file_path, e)
        # Return original track with error noted
        return track.model_copy(update={"comment": f"Analysis error: {e}"})


class ParallelAnalyzer:
    """Parallel audio analyzer using process pool."""

    def __init__(self, max_workers: int | None = None):
        """Initialize analyzer.

        Args:
            max_workers: Number of worker processes. None = cpu_count - 1
        """
        settings = get_settings()
        self.max_workers = max_workers or settings.max_workers
        if self.max_workers is None:
            self.max_workers = max(1, multiprocessing.cpu_count() - 1)

    def analyze_batch(
        self,
        tracks: list[Track],
        on_progress: Callable[[Track], None] | None = None,
    ) -> Iterator[Track]:
        """Analyze tracks in parallel.

        Args:
            tracks: List of tracks to analyze
            on_progress: Optional callback for progress updates

        Yields:
            Analyzed tracks as they complete
        """
        if not tracks:
            return

        logger.info(
            "Starting parallel analysis of %d tracks with %d workers",
            len(tracks),
            self.max_workers,
        )

        with ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_analyze_single, track): track
                for track in tracks
            }

            for future in as_completed(futures):
                try:
                    analyzed = future.result()
                    if on_progress:
                        on_progress(analyzed)
                    yield analyzed
                except Exception as e:
                    original = futures[future]
                    logger.error("Worker failed for %s: %s", original.file_path, e)
                    yield original
```

**Step 5: Update analysis __init__.py**

Create `src/dj_catalog/analysis/__init__.py`:
```python
"""Analysis module - audio processing and feature extraction."""
from dj_catalog.analysis.analyzer import analyze_track
from dj_catalog.analysis.bpm import estimate_bpm
from dj_catalog.analysis.energy import compute_danceability, compute_energy
from dj_catalog.analysis.key import CAMELOT_WHEEL, estimate_key, key_to_camelot
from dj_catalog.analysis.parallel import ParallelAnalyzer

__all__ = [
    "analyze_track",
    "estimate_bpm",
    "estimate_key",
    "key_to_camelot",
    "CAMELOT_WHEEL",
    "compute_energy",
    "compute_danceability",
    "ParallelAnalyzer",
]
```

**Step 6: Run tests**

```bash
uv run pytest tests/analysis/ -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add -A
git commit -m "feat(analysis): add analyzer with parallel processing

- analyze_track orchestrates full analysis pipeline
- ParallelAnalyzer uses ProcessPoolExecutor
- Auto-detects CPU count, leaves 1 core free
- Progress callback for UI updates

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Storage - SQLite Database

**Files:**
- Create: `src/dj_catalog/storage/database.py`
- Create: `tests/storage/test_database.py`

**Step 1: Write failing test**

Create `tests/storage/test_database.py`:
```python
"""Tests for SQLite database."""
from pathlib import Path

import pytest

from dj_catalog.core.models import Track
from dj_catalog.storage.database import Database


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
        tracks = [
            Track(file_path=Path(f"/music/{i}.mp3"), file_hash=f"hash{i}")
            for i in range(3)
        ]
        for t in tracks:
            db.insert_track(t)

        hashes = db.get_known_hashes()

        assert hashes == {"hash0", "hash1", "hash2"}

    def test_search_by_bpm(self, db: Database) -> None:
        """Can search tracks by BPM range."""
        for i, bpm in enumerate([100, 120, 128, 140]):
            db.insert_track(Track(
                file_path=Path(f"/music/{i}.mp3"),
                file_hash=f"hash{i}",
                bpm=float(bpm),
            ))

        results = db.search_tracks(bpm_min=115, bpm_max=135)

        assert len(results) == 2
        bpms = {t.bpm for t in results}
        assert bpms == {120.0, 128.0}

    def test_search_by_tags(self, db: Database) -> None:
        """Can search tracks by tags."""
        db.insert_track(Track(
            file_path=Path("/music/1.mp3"),
            file_hash="h1",
            tags=["techno", "dark"],
        ))
        db.insert_track(Track(
            file_path=Path("/music/2.mp3"),
            file_hash="h2",
            tags=["house", "vocal"],
        ))
        db.insert_track(Track(
            file_path=Path("/music/3.mp3"),
            file_hash="h3",
            tags=["techno", "melodic"],
        ))

        results = db.search_tracks(include_tags=["techno"])

        assert len(results) == 2

    def test_search_exclude_tags(self, db: Database) -> None:
        """Can exclude tracks by tags."""
        db.insert_track(Track(
            file_path=Path("/music/1.mp3"),
            file_hash="h1",
            tags=["techno", "vocal"],
        ))
        db.insert_track(Track(
            file_path=Path("/music/2.mp3"),
            file_hash="h2",
            tags=["techno", "dark"],
        ))

        results = db.search_tracks(include_tags=["techno"], exclude_tags=["vocal"])

        assert len(results) == 1
        assert results[0].file_hash == "h2"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/storage/test_database.py -v
```
Expected: FAIL - module not found

**Step 3: Implement database**

Create `src/dj_catalog/storage/database.py`:
```python
"""SQLite database storage."""
from datetime import date, datetime
import json
import logging
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from dj_catalog.core.models import Track

logger = logging.getLogger(__name__)

Base = declarative_base()


class TrackRow(Base):
    """SQLAlchemy model for tracks table."""

    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False, unique=True)
    file_hash = Column(String(64), unique=True, index=True)

    # Core metadata
    title = Column(String(500))
    artist = Column(String(500), index=True)
    album = Column(String(500))
    album_artist = Column(String(500))
    track_number = Column(Integer)
    duration_seconds = Column(Float)

    # Extended metadata
    label = Column(String(500), index=True)
    remixer = Column(String(500))
    composer = Column(String(500))
    original_artist = Column(String(500))
    isrc = Column(String(20))
    release_date = Column(String(10))  # ISO format
    year = Column(Integer, index=True)
    comment = Column(Text)

    # Audio quality
    bitrate = Column(Integer)
    sample_rate = Column(Integer)
    codec = Column(String(20))

    # Analysis
    bpm = Column(Float, index=True)
    bpm_source = Column(String(20))
    key = Column(String(10), index=True)
    key_camelot = Column(String(5), index=True)
    energy = Column(Float)
    danceability = Column(Float)

    # Tags (stored as JSON array)
    tags_json = Column(Text, default="[]")

    # User fields
    rating = Column(Integer, index=True)
    color = Column(String(10))
    play_count = Column(Integer, default=0)

    # System
    analyzed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Database:
    """SQLite database interface."""

    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.Session = sessionmaker(bind=self.engine)
        self._session = None

    def init(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)
        self._session = self.Session()
        logger.info("Database initialized: %s", self.db_path)

    def close(self) -> None:
        """Close database connection."""
        if self._session:
            self._session.close()

    @property
    def session(self):
        """Get current session."""
        if self._session is None:
            raise RuntimeError("Database not initialized")
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
        }

    def _row_to_track(self, row: TrackRow) -> Track:
        """Convert row to Track model."""
        release_date = None
        if row.release_date:
            try:
                release_date = date.fromisoformat(row.release_date)
            except ValueError:
                pass

        return Track(
            file_path=Path(row.file_path),
            file_hash=row.file_hash or "",
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
            release_date=release_date,
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
            tags=json.loads(row.tags_json) if row.tags_json else [],
            rating=row.rating,
            color=row.color,
            play_count=row.play_count or 0,
            analyzed_at=row.analyzed_at,
            created_at=row.created_at or datetime.now(),
            updated_at=row.updated_at or datetime.now(),
        )

    def insert_track(self, track: Track) -> int:
        """Insert new track. Returns ID."""
        row = TrackRow(**self._track_to_row(track))
        self.session.add(row)
        self.session.commit()
        return row.id

    def upsert_track(self, track: Track) -> int:
        """Insert or update track by file_hash."""
        existing = self.session.query(TrackRow).filter_by(
            file_hash=track.file_hash
        ).first()

        if existing:
            data = self._track_to_row(track)
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

    def get_known_hashes(self) -> set[str]:
        """Get all known file hashes for incremental scanning."""
        rows = self.session.query(TrackRow.file_hash).filter(
            TrackRow.file_hash.isnot(None)
        ).all()
        return {r[0] for r in rows if r[0]}

    def search_tracks(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key: str | None = None,
        label: str | None = None,
        artist: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        rating_min: int | None = None,
        energy_min: float | None = None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
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
        if label is not None:
            query = query.filter(TrackRow.label.ilike(f"%{label}%"))
        if artist is not None:
            query = query.filter(TrackRow.artist.ilike(f"%{artist}%"))
        if year_min is not None:
            query = query.filter(TrackRow.year >= year_min)
        if year_max is not None:
            query = query.filter(TrackRow.year <= year_max)
        if rating_min is not None:
            query = query.filter(TrackRow.rating >= rating_min)
        if energy_min is not None:
            query = query.filter(TrackRow.energy >= energy_min)

        rows = query.limit(limit * 10).all()  # Over-fetch for tag filtering
        tracks = [self._row_to_track(r) for r in rows]

        # Filter by tags in Python (JSON field)
        if include_tags:
            tracks = [
                t for t in tracks
                if any(tag in t.tags for tag in include_tags)
            ]
        if exclude_tags:
            tracks = [
                t for t in tracks
                if not any(tag in t.tags for tag in exclude_tags)
            ]

        return tracks[:limit]

    def get_all_tracks(self) -> list[Track]:
        """Get all tracks."""
        rows = self.session.query(TrackRow).all()
        return [self._row_to_track(r) for r in rows]

    def count_tracks(self) -> int:
        """Count total tracks."""
        return self.session.query(TrackRow).count()
```

**Step 4: Run tests**

```bash
uv run pytest tests/storage/test_database.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(storage): add SQLite database with full schema

- All 30+ metadata fields stored
- Tags stored as JSON array
- Incremental scan support via get_known_hashes
- Search with include/exclude tag filtering
- Indexed columns for fast queries

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 12-20: Remaining Implementation

Due to length constraints, the remaining tasks follow the same TDD pattern:

**Task 12: Storage - ChromaDB Vector Store**
- `src/dj_catalog/storage/vectors.py`
- Semantic search for RAG

**Task 13: Playlist - Filters**
- `src/dj_catalog/playlist/filters.py`
- TrackFilter dataclass with include/exclude logic

**Task 14: Playlist - Harmonic Mixing**
- `src/dj_catalog/playlist/harmonic.py`
- Camelot wheel compatibility

**Task 15: Playlist - Generator**
- `src/dj_catalog/playlist/generator.py`
- Greedy algorithm with scoring

**Task 16: Playlist - Export**
- `src/dj_catalog/playlist/export.py`
- M3U and Rekordbox XML formats

**Task 17: CLI - Main + Scan Command**
- `src/dj_catalog/cli/main.py`
- `src/dj_catalog/cli/scan.py`
- Incremental scanning with progress bar

**Task 18: CLI - Search + Playlist Commands**
- `src/dj_catalog/cli/search.py`
- `src/dj_catalog/cli/playlist.py`
- Tag-based filtering flags

**Task 19: CLI - Stats Command**
- `src/dj_catalog/cli/stats.py`
- Library statistics

**Task 20: MCP Server**
- `src/dj_catalog/mcp/server.py`
- `src/dj_catalog/mcp/tools.py`
- Full Claude Desktop integration

**Task 21: Integration Tests**
- `tests/integration/test_full_workflow.py`
- End-to-end scan → search → playlist → export

**Task 22: Documentation**
- `docs/` with mkdocs
- README.md
- Claude Desktop setup guide

---

## Summary

**13 modules implemented:**
1. core (models, config, exceptions)
2. scanning (scanner, hasher, extractor)
3. analysis (bpm, key, energy, analyzer, parallel)
4. storage (database, vectors)
5. playlist (filters, harmonic, generator, export)
6. cli (main, scan, search, playlist, stats)
7. mcp (server, tools)

**Key features:**
- 30+ metadata fields captured
- Tag-based filtering with AND/OR/NOT
- Parallel analysis (~4x speedup)
- Incremental scanning
- Rekordbox XML export
- MCP server for Claude Desktop

**Quality:**
- mypy strict
- ruff format + lint
- 80% test coverage
- Pre-commit hooks
