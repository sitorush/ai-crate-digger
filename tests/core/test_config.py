"""Tests for configuration."""

from pathlib import Path

import pytest

from ai_crate_digger.core.config import Settings, get_settings


class TestSettings:
    """Tests for Settings."""

    def test_default_settings(self) -> None:
        """Settings have sensible defaults."""
        settings = Settings()
        assert settings.db_path == Path.home() / ".ai-crate-digger" / "catalog.db"
        assert settings.vector_path == Path.home() / ".ai-crate-digger" / ".chroma"
        assert settings.max_workers is None  # Auto-detect

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings can be overridden via environment."""
        monkeypatch.setenv("CRATE_DB_PATH", "/custom/path.db")
        settings = Settings()
        assert settings.db_path == Path("/custom/path.db")

    def test_get_settings_cached(self) -> None:
        """get_settings returns same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_default_output_path(self) -> None:
        """Test default output_path is ~/Downloads."""
        settings = Settings()
        assert settings.output_path == Path.home() / "Downloads"

    def test_settings_custom_output_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test custom output_path via env var."""
        get_settings.cache_clear()  # Clear any cached settings

        monkeypatch.setenv("CRATE_OUTPUT_PATH", str(tmp_path))
        settings = Settings()
        assert settings.output_path == tmp_path

    def test_mix_identification_defaults(self) -> None:
        """Mix identification settings have defaults."""
        settings = Settings()
        assert settings.inbox_path == Path.home() / "Music" / "mixes"
        assert settings.mix_min_seconds == 30.0
        assert settings.mix_speed_range == 0.08
        assert settings.mix_speed_step == 0.01
        assert settings.mix_high_support > settings.mix_medium_support > settings.mix_low_support

    def test_inbox_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The inbox folder can be overridden via environment."""
        monkeypatch.setenv("CRATE_INBOX_PATH", "/recordings")
        assert Settings().inbox_path == Path("/recordings")
