"""Tests for preset configuration loading."""

import json
from pathlib import Path

import pytest

from leropilot.core.app_config import AppConfigManager


def test_preset_config_loaded_for_first_time_user(tmp_path: Path) -> None:
    """Test that preset configuration is loaded for first-time users."""
    # Create a temporary config path (doesn't exist yet)
    config_path = tmp_path / "config.yaml"

    # Create config manager
    manager = AppConfigManager(config_path)

    # Load config (first time, so presets should be applied)
    config = manager.load()

    # Verify preset PyPI mirrors are loaded
    assert len(config.pypi.mirrors) > 0
    mirror_names = [m.name for m in config.pypi.mirrors]
    assert "Tsinghua University/清华大学" in mirror_names
    assert "Aliyun/阿里云" in mirror_names

    # Verify all mirrors are disabled by default
    assert all(not m.enabled for m in config.pypi.mirrors)

    # Verify Official repository exists
    assert len(config.repositories.lerobot_sources) >= 1
    official_repo = next((r for r in config.repositories.lerobot_sources if r.name == "Official/官方仓库"), None)
    assert official_repo is not None
    assert official_repo.is_default


def test_preset_config_not_applied_to_existing_users(tmp_path: Path) -> None:
    """Test that preset configuration is NOT applied to existing users."""
    config_path = tmp_path / "config.yaml"

    # Create an existing config file with custom mirrors
    existing_config = {
        "pypi": {
            "mirrors": [{"name": "My Custom Mirror", "url": "https://my-mirror.example.com/simple", "enabled": True}]
        }
    }

    import yaml

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(existing_config, f)

    # Load config
    manager = AppConfigManager(config_path)
    config = manager.load()

    # Verify custom mirror is preserved
    assert len(config.pypi.mirrors) == 1
    assert config.pypi.mirrors[0].name == "My Custom Mirror"
    assert config.pypi.mirrors[0].enabled


def test_preset_config_file_structure() -> None:
    """Test that preset config file has correct structure."""
    preset_path = Path(__file__).parent.parent / "src" / "leropilot" / "resources" / "default_config.json"

    assert preset_path.exists(), "Preset config file should exist"

    with open(preset_path, encoding="utf-8") as f:
        preset_data = json.load(f)

    # Verify structure
    assert "pypi_mirrors" in preset_data
    assert "repositories" in preset_data

    # Verify PyPI mirrors structure
    for mirror in preset_data["pypi_mirrors"]:
        assert "name" in mirror
        assert "url" in mirror
        assert "enabled" in mirror
        assert mirror["url"].endswith("/simple") or mirror["url"].endswith("/simple/")
        assert not mirror["enabled"]  # All should be disabled by default

    # Verify repositories structure
    assert "lerobot_sources" in preset_data["repositories"]
    for repo in preset_data["repositories"]["lerobot_sources"]:
        assert "id" in repo
        assert "name" in repo
        assert "url" in repo
        assert "is_default" in repo

    # Verify at least one default repository
    assert any(r["is_default"] for r in preset_data["repositories"]["lerobot_sources"])


def test_preset_config_graceful_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that config loading continues even if preset file is missing/invalid."""
    config_path = tmp_path / "config.yaml"

    # Mock preset path to non-existent file
    def mock_init(self: AppConfigManager, config_path: Path | None = None) -> None:
        self.config_path = config_path or tmp_path / "config.yaml"
        self._config = None

    monkeypatch.setattr(AppConfigManager, "__init__", mock_init)

    manager = AppConfigManager(config_path)

    # Should not raise error even if preset file doesn't exist
    config = manager.load()

    # Should still create valid config with defaults
    assert config is not None
    assert config.server.port == 8000
