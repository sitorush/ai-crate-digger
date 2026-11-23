"""Tests for the fingerprint and identify commands."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_crate_digger.cli.main import main
from ai_crate_digger.core.config import get_settings
from tests.fingerprint.library import Library, write_wav
from tests.fingerprint.synth import SR, place


@pytest.fixture
def runner(library: Library, monkeypatch: pytest.MonkeyPatch) -> Iterator[CliRunner]:
    monkeypatch.setenv("CRATE_DB_PATH", str(library.settings.db_path))
    monkeypatch.setenv("CRATE_INBOX_PATH", str(library.settings.inbox_path))
    monkeypatch.setenv("CRATE_MAX_WORKERS", "1")
    get_settings.cache_clear()
    yield CliRunner()
    get_settings.cache_clear()


def test_commands_are_registered(runner: CliRunner) -> None:
    for command in ("fingerprint", "identify"):
        result = runner.invoke(main, [command, "--help"])
        assert result.exit_code == 0


def test_fingerprint_then_identify(runner: CliRunner, library: Library) -> None:
    result = runner.invoke(main, ["fingerprint"])
    assert result.exit_code == 0
    assert "Indexed 4" in result.output

    mix = write_wav(library.root / "set.wav", place(library.audio["hash2"][: 30 * SR], 0, 32))
    result = runner.invoke(main, ["identify", str(mix)])
    assert result.exit_code == 0
    assert "Title2" in result.output


def test_identify_without_an_index_fails_cleanly(runner: CliRunner, library: Library) -> None:
    mix = write_wav(library.root / "set.wav", place(library.audio["hash2"][: 30 * SR], 0, 32))
    result = runner.invoke(main, ["identify", str(mix)])
    assert result.exit_code != 0
    assert "index_fingerprints" in result.output


def test_identify_missing_file_fails_cleanly(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["identify", str(tmp_path / "nope.mp3")])
    assert result.exit_code != 0
    assert "not found" in result.output
