"""Tests for search CLI command."""

import pytest
from click.testing import CliRunner

from dj_catalog.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSearchCommand:
    def test_search_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["search", "--help"])
        assert result.exit_code == 0
        assert "Search for tracks" in result.output

    def test_search_options(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["search", "--help"])
        assert "--tags" in result.output
        assert "--bpm-min" in result.output
        assert "--semantic" in result.output
        assert "--artist" in result.output
        assert "--key" in result.output
        assert "--label" in result.output
        assert "--rating-min" in result.output
        assert "--limit" in result.output
