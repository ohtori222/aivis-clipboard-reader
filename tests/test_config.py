import json
from unittest.mock import patch

import pytest

# Import src modules (mocks from conftest.py should be active)
from aivis_reader import ConfigManager


class TestConfigManager:
    @pytest.fixture
    def mock_fs(self, tmp_path):
        """Mock file system for config tests"""
        # Create dummy config files
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"volume": 0.5, "speed": 1.2}), encoding="utf-8"
        )

        local_config_path = tmp_path / "config.local.json"
        local_config_path.write_text(json.dumps({"volume": 0.8}), encoding="utf-8")

        return tmp_path

    def test_default_config(self):
        """Test default configuration values"""
        cfg = ConfigManager()
        # Ensure we are not picking up actual config files during this specific test
        # (This is tricky if ConfigManager auto-loads in __init__.
        #  We might need to patch get_project_root or the open calls.)

        # Verify some defaults
        assert cfg["port"] == 10101
        assert cfg["speed"] == 1.0

    def test_config_load_merge(self, mock_fs):
        """Test loading and merging of config files"""
        with patch("aivis_reader.get_project_root", return_value=str(mock_fs)):
            cfg = ConfigManager()

            # config.local.json (volume: 0.8) should override config.json (volume: 0.5)
            assert cfg["volume"] == 0.8
            # config.json (speed: 1.2) should override default (speed: 1.0)
            assert cfg["speed"] == 1.2
            # Default value should persist if not in files
            assert cfg["port"] == 10101

    def test_artwork_auto_detection(self, mock_fs):
        """Test automatic artwork detection logic"""
        with patch("aivis_reader.get_project_root", return_value=str(mock_fs)):
            # setup assets dir in mock_fs
            assets_dir = mock_fs / "assets"
            assets_dir.mkdir()
            (assets_dir / "cover_sample.jpg").touch()

            # Ensure config artwork path does NOT exist so auto-detection kicks in
            # Default is "cover.jpg", we ensure it doesn't exist in root

            cfg = ConfigManager()

            # Should fallback to assets/cover_sample.jpg
            assert "assets" in cfg["artwork_path"]
            assert "cover_sample.jpg" in cfg["artwork_path"]
