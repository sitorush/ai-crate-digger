"""Shared test fixtures."""

import tempfile
from collections.abc import Iterator
from pathlib import Path

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
