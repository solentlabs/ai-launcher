"""Tests for terminal utilities."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_launcher.utils.terminal import (
    _supports_title_setting,
    format_terminal_title,
    get_terminal_info,
    set_terminal_title,
)


class TestFormatTerminalTitle:
    """Tests for format_terminal_title()."""

    @pytest.mark.parametrize(
        "fmt,expected",
        [
            ("{project} \u2192 {provider}", "my-app \u2192 Claude Code"),
            ("{parent}/{project} - {provider}", "projects/my-app - Claude Code"),
            ("{path}", "/home/user/projects/my-app"),
            ("{project}", "my-app"),
            ("{provider}", "Claude Code"),
            ("\U0001f916 {project} | {provider}", "\U0001f916 my-app | Claude Code"),
        ],
        ids=[
            "basic_arrow",
            "parent_slash",
            "full_path",
            "project_only",
            "provider_only",
            "with_emoji",
        ],
    )
    def test_format_patterns(self, fmt, expected):
        """Test various format string patterns produce expected titles."""
        result = format_terminal_title(
            fmt,
            Path("/home/user/projects/my-app"),
            "Claude Code",
        )
        assert result == expected

    def test_format_invalid_variable(self):
        """Test that invalid format variables raise ValueError."""
        with pytest.raises(ValueError, match="Invalid format string variable"):
            format_terminal_title(
                "{unknown_variable}",
                Path("/home/user/projects/my-app"),
                "Claude Code",
            )

    def test_format_multiple_invalid_variables(self):
        """Test error message lists valid variables."""
        with pytest.raises(ValueError, match="Valid variables"):
            format_terminal_title(
                "{foo} and {bar}",
                Path("/home/user/projects/my-app"),
                "Claude Code",
            )

    def test_format_strips_ansi_from_project_name(self):
        """Test that ANSI codes in project name are removed."""
        result = format_terminal_title(
            "{project}",
            Path("/home/user/\x1b[31mmy-app\x1b[0m"),
            "Claude Code",
        )
        assert "\x1b[" not in result
        assert result == "my-app"

    def test_format_strips_ansi_from_provider_name(self):
        """Test that ANSI codes in provider name are removed."""
        result = format_terminal_title(
            "{provider}",
            Path("/home/user/my-app"),
            "\x1b[32mClaude Code\x1b[0m",
        )
        assert "\x1b[" not in result
        assert result == "Claude Code"

    def test_format_strips_ansi_from_format_string(self):
        """Test that ANSI codes in format string are removed."""
        result = format_terminal_title(
            "\x1b[H\x1b[2J{project}",
            Path("/home/user/my-app"),
            "Claude Code",
        )
        assert "\x1b[H" not in result
        assert "\x1b[2J" not in result
        assert "my-app" in result

    def test_format_strips_osc_sequences(self):
        """Test that OSC (Operating System Command) sequences are removed."""
        result = format_terminal_title(
            "\x1b]0;Malicious\x07{project}",
            Path("/home/user/my-app"),
            "Claude Code",
        )
        assert "\x1b]" not in result
        assert "Malicious" not in result
        assert result == "my-app"

    def test_format_root_directory(self):
        """Test formatting with root directory path."""
        result = format_terminal_title(
            "{project} \u2192 {provider}",
            Path("/"),
            "Claude Code",
        )
        assert result != " \u2192 Claude Code"
        assert "/" in result or result.startswith("/")
        assert "\u2192 Claude Code" in result

    def test_format_current_directory(self):
        """Test formatting with current directory."""
        result = format_terminal_title("{project}", Path(), "Claude Code")
        assert result != ""
        assert len(result) > 0


class TestSupportsTerminalTitle:
    """Tests for _supports_title_setting()."""

    @patch("sys.stdout.isatty")
    def test_not_tty(self, mock_isatty):
        """Test that non-tty returns False."""
        mock_isatty.return_value = False
        assert _supports_title_setting() is False

    @pytest.mark.parametrize(
        "env_var,env_value",
        [
            ("TERM", "xterm-256color"),
            ("TERM", "screen"),
            ("TERM", "tmux-256color"),
            ("TERM", "alacritty"),
            ("TERM", "kitty"),
            ("TERM_PROGRAM", "iTerm.app"),
            ("TERM_PROGRAM", "vscode"),
            ("WT_SESSION", "some-session-id"),
        ],
        ids=[
            "xterm",
            "screen",
            "tmux",
            "alacritty",
            "kitty",
            "iterm",
            "vscode",
            "windows_terminal",
        ],
    )
    @patch("sys.stdout.isatty")
    def test_supported_terminals(self, mock_isatty, env_var, env_value):
        """Test that known terminal types are supported."""
        mock_isatty.return_value = True
        with patch.dict(os.environ, {env_var: env_value}):
            assert _supports_title_setting() is True

    @patch("sys.stdout.isatty")
    @patch.dict(os.environ, {"TERM": "dumb"}, clear=True)
    def test_unsupported_terminal(self, mock_isatty):
        """Test that unsupported terminal returns False."""
        mock_isatty.return_value = True
        assert _supports_title_setting() is False


class TestSetTerminalTitle:
    """Tests for set_terminal_title()."""

    @patch("ai_launcher.utils.terminal._supports_title_setting")
    def test_unsupported_terminal(self, mock_supports):
        """Test that unsupported terminal returns False."""
        mock_supports.return_value = False
        assert set_terminal_title("Test Title") is False

    @patch("ai_launcher.utils.terminal._supports_title_setting")
    @patch("sys.stdout")
    def test_set_title_success(self, mock_stdout, mock_supports):
        """Test successful title setting."""
        mock_supports.return_value = True
        assert set_terminal_title("Test Title") is True
        mock_stdout.write.assert_called_once()
        call_args = mock_stdout.write.call_args[0][0]
        assert "Test Title" in call_args
        assert "\033]0;" in call_args
        assert "\007" in call_args

    @patch("ai_launcher.utils.terminal._supports_title_setting")
    @patch("sys.stdout")
    @patch.dict(os.environ, {"TMUX": "some-session"})
    def test_set_title_tmux(self, mock_stdout, mock_supports):
        """Test title setting in tmux uses different sequence."""
        mock_supports.return_value = True
        assert set_terminal_title("Test Title") is True
        mock_stdout.write.assert_called_once()
        call_args = mock_stdout.write.call_args[0][0]
        assert "Test Title" in call_args
        assert "\033k" in call_args
        assert "\033\\" in call_args

    @patch("ai_launcher.utils.terminal._supports_title_setting")
    @patch("sys.stdout")
    def test_set_title_exception(self, mock_stdout, mock_supports):
        """Test that exceptions are handled gracefully."""
        mock_supports.return_value = True
        mock_stdout.write.side_effect = Exception("Test error")
        assert set_terminal_title("Test Title") is False


class TestGetTerminalInfo:
    """Tests for get_terminal_info()."""

    @patch("sys.stdout.isatty")
    @patch.dict(os.environ, {"TERM": "xterm-256color", "TERM_PROGRAM": "iTerm.app"})
    def test_get_terminal_info(self, mock_isatty):
        """Test getting terminal information."""
        mock_isatty.return_value = True
        info = get_terminal_info()

        assert info["term"] == "xterm-256color"
        assert info["term_program"] == "iTerm.app"
        assert info["is_tty"] is True
        assert isinstance(info["supports_title"], bool)
        assert "wt_session" in info
        assert "tmux" in info

    @patch("sys.stdout.isatty")
    @patch.dict(os.environ, {}, clear=True)
    def test_get_terminal_info_no_env(self, mock_isatty):
        """Test terminal info with no environment variables."""
        mock_isatty.return_value = False
        info = get_terminal_info()

        assert info["term"] == "unknown"
        assert info["term_program"] == "unknown"
        assert info["is_tty"] is False
        assert info["supports_title"] is False
        assert info["wt_session"] is None
        assert info["tmux"] is False

    @patch("sys.stdout.isatty")
    @patch.dict(os.environ, {"TMUX": "session-id", "WT_SESSION": "wt-id"})
    def test_get_terminal_info_special_terminals(self, mock_isatty):
        """Test terminal info for tmux and Windows Terminal."""
        mock_isatty.return_value = True
        info = get_terminal_info()

        assert info["tmux"] is True
        assert info["wt_session"] == "wt-id"
