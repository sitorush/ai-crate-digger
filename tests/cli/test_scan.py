"""Tests for scan CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dj_catalog.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    """CLI test runner."""
    return CliRunner()


class TestScanCommand:
    """Tests for scan command."""

    def test_scan_help(self, runner: CliRunner) -> None:
        """Shows help text."""
        result = runner.invoke(main, ["scan", "--help"])

        assert result.exit_code == 0
        assert "Scan directory for music files" in result.output

    def test_scan_requires_directory(self, runner: CliRunner) -> None:
        """Requires directory argument."""
        result = runner.invoke(main, ["scan"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_scan_nonexistent_directory(self, runner: CliRunner) -> None:
        """Error on nonexistent directory."""
        result = runner.invoke(main, ["scan", "/nonexistent/path"])

        assert result.exit_code != 0

    @patch("dj_catalog.cli.scan.Database")
    @patch("dj_catalog.cli.scan.VectorStore")
    @patch("dj_catalog.cli.scan.scan_directory")
    def test_scan_empty_directory(
        self,
        mock_scan: MagicMock,
        mock_vector: MagicMock,
        mock_db: MagicMock,
        runner: CliRunner,
        tmp_dir: Path,
    ) -> None:
        """Handles empty directory."""
        mock_scan.return_value = []
        mock_db_instance = MagicMock()
        mock_db_instance.get_known_hashes.return_value = set()
        mock_db.return_value = mock_db_instance

        result = runner.invoke(main, ["scan", str(tmp_dir)])

        assert "Found 0 audio files" in result.output


class TestMainCLI:
    """Tests for main CLI group."""

    def test_version(self, runner: CliRunner) -> None:
        """Shows version."""
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner: CliRunner) -> None:
        """Shows help."""
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "DJ Catalog" in result.output
