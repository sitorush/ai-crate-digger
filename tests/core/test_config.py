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


def test_settings_default_output_path():
    """Test default output_path is ~/Downloads."""
    settings = Settings()
    assert settings.output_path == Path.home() / "Downloads"


def test_settings_custom_output_path(monkeypatch, tmp_path):
    """Test custom output_path via env var."""
    monkeypatch.setenv("DJ_CATALOG_OUTPUT_PATH", str(tmp_path))
    settings = Settings()
    assert settings.output_path == tmp_path
