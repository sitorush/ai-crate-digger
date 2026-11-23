"""Tests for locating mix recordings."""

import os
from pathlib import Path

import pytest

from ai_crate_digger.fingerprint.inbox import resolve_mix_path


def _touch(path: Path, mtime: int) -> Path:
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return path


def test_explicit_path_is_used(tmp_path: Path) -> None:
    mix = _touch(tmp_path / "set.mp3", 100)
    assert resolve_mix_path(str(mix), tmp_path / "inbox") == mix


def test_missing_explicit_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Mix file not found"):
        resolve_mix_path(str(tmp_path / "nope.mp3"), tmp_path)


@pytest.mark.parametrize("value", [None, "latest", "LATEST"])
def test_latest_picks_the_newest_audio_file(tmp_path: Path, value: str | None) -> None:
    _touch(tmp_path / "old.mp3", 100)
    newest = _touch(tmp_path / "new.WAV", 300)
    _touch(tmp_path / "notes.txt", 500)
    assert resolve_mix_path(value, tmp_path) == newest


def test_latest_needs_an_inbox_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Inbox folder not found"):
        resolve_mix_path("latest", tmp_path / "missing")


def test_latest_needs_at_least_one_audio_file(tmp_path: Path) -> None:
    _touch(tmp_path / "notes.txt", 100)
    with pytest.raises(FileNotFoundError, match="No audio files"):
        resolve_mix_path(None, tmp_path)
