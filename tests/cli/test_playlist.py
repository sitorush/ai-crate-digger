"""Tests for playlist CLI command."""

import pytest
from click.testing import CliRunner

from dj_catalog.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestPlaylistCommand:
    def test_playlist_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["playlist", "--help"])
        assert result.exit_code == 0
        assert "Generate a playlist" in result.output

    def test_playlist_options(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["playlist", "--help"])
        assert "--duration" in result.output
        assert "--tags" in result.output
        assert "--no-harmonic" in result.output
        assert "--output" in result.output
        assert "--format" in result.output
        assert "--name" in result.output
        assert "--bpm-min" in result.output
        assert "--bpm-max" in result.output
        assert "--key" in result.output
        assert "--rating-min" in result.output
        assert "--energy-min" in result.output
