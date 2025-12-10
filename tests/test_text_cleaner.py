from unittest.mock import MagicMock, patch

import pytest

from aivis_reader import ConfigManager, TaskManager


class TestTextCleaner:
    @pytest.fixture
    def task_manager(self):
        # Mock dependencies for TaskManager
        mock_synth = MagicMock()
        mock_player = MagicMock()
        return TaskManager(mock_synth, mock_player)

    def test_clean_text_basic(self, task_manager):
        """Test basic text cleaning"""
        # Setup config
        with patch("aivis_reader.cfg", new_callable=ConfigManager) as mock_cfg:
            mock_cfg.data["dictionary"] = {}
            mock_cfg.data["require_hiragana"] = False

            raw = "  Hello World  "
            cleaned = task_manager._clean_text(raw)
            assert cleaned == "Hello World"

    def test_clean_text_replacements(self, task_manager):
        """Test dictionary replacements and formatting removal"""
        with patch("aivis_reader.cfg", new_callable=ConfigManager) as mock_cfg:
            mock_cfg.data["dictionary"] = {"foo": "bar"}
            mock_cfg.data["require_hiragana"] = False

            # Dictionary replace
            assert task_manager._clean_text("foo world") == "bar world"

            # Markdown/URL removal
            assert task_manager._clean_text("Link: http://example.com") == "Link:"
            assert (
                task_manager._clean_text("Some text [link](http://url)")
                == "Some text link"
            )

    def test_clean_text_hiragana_filter(self, task_manager):
        """Test hiragana requirement filter"""
        with patch("aivis_reader.cfg", new_callable=ConfigManager) as mock_cfg:
            mock_cfg.data["dictionary"] = {}
            mock_cfg.data["require_hiragana"] = True

            # Should pass (contains hiragana)
            assert task_manager._clean_text("こんにちは") == "こんにちは"

            # Should fail (no hiragana)
            assert task_manager._clean_text("Hello World") is None

            # Should fail (only katakana/kanji)
            assert task_manager._clean_text("漢字カタカナ") is None
