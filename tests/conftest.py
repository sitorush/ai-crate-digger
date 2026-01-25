"""Shared test fixtures."""

import struct
import tempfile
import wave
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
