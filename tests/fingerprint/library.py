"""Helpers for tests that need a small library of synthetic tracks on disk."""

from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from ai_crate_digger.core.config import Settings
from ai_crate_digger.core.models import Track
from ai_crate_digger.storage import Database
from tests.fingerprint.synth import SR, Audio, make_track


@dataclass
class Library:
    """A catalogue database plus the audio behind each track."""

    db: Database
    settings: Settings
    audio: dict[str, Audio]  # file_hash -> audio
    root: Path


def write_wav(path: Path, audio: Audio) -> Path:
    """Write ``audio`` as a mono WAV at the fingerprint sample rate."""
    sf.write(str(path), audio, SR)
    return path


def build_library(root: Path, n_tracks: int = 4, seconds: float = 40) -> Library:
    """Create ``n_tracks`` WAV files and a catalogue database describing them."""
    db_path = root / "catalog.db"
    db = Database(db_path)
    db.init()
    music = root / "music"
    music.mkdir()
    audio: dict[str, Audio] = {}
    for i in range(n_tracks):
        samples = make_track(i, seconds)
        path = write_wav(music / f"track{i}.wav", samples)
        db.upsert_track(
            Track(file_path=path, file_hash=f"hash{i}", title=f"Title{i}", artist=f"Artist{i}")
        )
        audio[f"hash{i}"] = samples
    settings = Settings(db_path=db_path, inbox_path=root / "inbox", max_workers=1)
    return Library(db=db, settings=settings, audio=audio, root=root)
