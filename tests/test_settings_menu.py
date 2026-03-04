"""Tests for settings menu UI.

Author: Solent Labs™
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import ConfigData
from ai_launcher.ui.settings import (
    _build_settings_choices,
    _toggle_setting,
    show_settings_menu,
)


class TestBuildSettingsChoices:
    """Tests for _build_settings_choices()."""

    def test_cleanup_section_present(self):
        config = ConfigData()
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        assert "Cleanup Settings" in text

    def test_cleanup_enabled_shown(self):
        config = ConfigData()
        config.cleanup.enabled = True
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        assert "Auto-cleanup before launch" in text

    def test_cleanup_disabled_shows_fewer_options(self):
        config = ConfigData()
        config.cleanup.enabled = False
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        # When cleanup is disabled, sub-settings should NOT be present
        assert "Clean provider files" not in text
        assert "Clean npm cache" not in text

    def test_cleanup_enabled_shows_sub_settings(self):
        config = ConfigData()
        config.cleanup.enabled = True
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        assert "Clean provider files" in text
        assert "Clean ~/.cache" in text
        assert "Clean npm cache" in text

    def test_global_files_section_present(self):
        config = ConfigData()
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        assert "Global Files" in text
        assert "Add global files" in text
        assert "Remove global files" in text

    def test_back_button_present(self):
        config = ConfigData()
        choices = _build_settings_choices(config)
        text = "\n".join(choices)
        assert "Back to project selector" in text

    def test_all_choices_have_tabs(self):
        config = ConfigData()
        choices = _build_settings_choices(config)
        for choice in choices:
            assert "\t\t" in choice


class TestToggleSetting:
    """Tests for _toggle_setting()."""

    @pytest.mark.parametrize(
        "setting_name,attr_name,initial_value",
        [
            ("cleanup_enabled", "enabled", False),
            ("clean_provider_files", "clean_provider_files", True),
            ("clean_system_cache", "clean_system_cache", False),
            ("clean_npm_cache", "clean_npm_cache", False),
        ],
    )
    def test_toggle_setting(self, setting_name, attr_name, initial_value):
        """Test that toggling a setting flips its boolean value."""
        config = ConfigData()
        assert getattr(config.cleanup, attr_name) is initial_value
        config = _toggle_setting(config, setting_name)
        assert getattr(config.cleanup, attr_name) is (not initial_value)

    def test_toggle_cleanup_enabled_round_trip(self):
        """Test that toggling cleanup_enabled twice returns to original."""
        config = ConfigData()
        assert config.cleanup.enabled is False
        config = _toggle_setting(config, "cleanup_enabled")
        assert config.cleanup.enabled is True
        config = _toggle_setting(config, "cleanup_enabled")
        assert config.cleanup.enabled is False

    def test_toggle_unknown_setting(self):
        config = ConfigData()
        orig_enabled = config.cleanup.enabled
        config = _toggle_setting(config, "unknown_setting")
        assert config.cleanup.enabled == orig_enabled


class TestShowSettingsMenu:
    """Tests for show_settings_menu()."""

    def test_fzf_not_found(self, capsys):
        config_manager = MagicMock()
        config_manager.load.return_value = ConfigData()

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = show_settings_menu(config_manager)

        assert result is False
        captured = capsys.readouterr()
        assert "fzf not found" in captured.out

    def test_user_cancels(self):
        config_manager = MagicMock()
        config_manager.load.return_value = ConfigData()

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 130  # Ctrl+C

        with patch("subprocess.Popen", return_value=mock_process):
            result = show_settings_menu(config_manager)

        assert result is False

    def test_user_esc(self):
        config_manager = MagicMock()
        config_manager.load.return_value = ConfigData()

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 1  # ESC

        with patch("subprocess.Popen", return_value=mock_process):
            result = show_settings_menu(config_manager)

        assert result is False

    def test_generic_exception(self, capsys):
        config_manager = MagicMock()
        config_manager.load.return_value = ConfigData()

        with patch("subprocess.Popen", side_effect=Exception("unexpected error")):
            result = show_settings_menu(config_manager)

        assert result is False
        captured = capsys.readouterr()
        assert "Error in settings menu" in captured.out
