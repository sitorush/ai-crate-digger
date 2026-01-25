"""Tests for stats CLI command."""

import pytest
from click.testing import CliRunner

from dj_catalog.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestStatsCommand:
    def test_stats_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "--help"])
        assert result.exit_code == 0
        assert "Show library statistics" in result.output

    def test_stats_options(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["stats", "--help"])
        assert "--by" in result.output
        assert "tags" in result.output
        assert "artist" in result.output
        assert "label" in result.output
