"""Tests for settings preview helper.

Author: Solent Labs™
"""

import sys
from unittest.mock import patch

from ai_launcher.ui._settings_preview import format_description, generate_preview, main


class TestGeneratePreview:
    """Tests for generate_preview()."""

    def test_no_tabs_returns_no_preview(self):
        line = "just a plain line without tabs"
        result = generate_preview(line)
        assert result == "No preview available"

    def test_header_returns_empty(self):
        line = "__HEADER__\t\tSome header"
        result = generate_preview(line)
        assert result == ""

    def test_standard_format_no_double_colon(self):
        # The actual settings format uses single colons, so "::" check
        # doesn't match and returns "No description available"
        line = "__SETTING__:cleanup_enabled:DESC||description\t\tDisplay"
        result = generate_preview(line)
        assert result == "No description available"

    def test_no_description_separator(self):
        line = "__SETTING__:id:no-double-pipe\t\tDisplay"
        result = generate_preview(line)
        assert result == "No description available"

    def test_malformed_metadata(self):
        line = "garbage\t\tDisplay"
        result = generate_preview(line)
        assert result == "No description available"

    def test_double_colon_format_with_description(self):
        # When "::" is present in metadata, description is extracted
        line = "__SETTING__::id:DESC||This is a description\t\tDisplay text"
        result = generate_preview(line)
        assert "This is a description" in result
        assert "Setting Details" in result

    def test_double_colon_format_escaped_newlines(self):
        line = "__SETTING__::id:DESC||Line1\\nLine2\\nLine3\t\tDisplay"
        result = generate_preview(line)
        assert "Line1" in result
        assert "Line2" in result
        assert "Line3" in result

    def test_double_colon_no_pipe(self):
        line = "__SETTING__::id:no-pipe-separator\t\tDisplay"
        result = generate_preview(line)
        assert result == "No description available"


class TestFormatDescription:
    """Tests for format_description()."""

    def test_adds_border(self):
        result = format_description("Hello world")
        assert "╭─" in result
        assert "Setting Details" in result
        assert "╰─" in result
        assert "Hello world" in result

    def test_escaped_newlines_converted(self):
        result = format_description("Line1\\nLine2")
        assert "Line1" in result
        assert "Line2" in result


class TestMain:
    """Tests for main() entry point."""

    def test_main_with_arg(self, capsys):
        # Uses double-colon format so description is parsed
        line = "__SETTING__::id:DESC||Test description\t\tDisplay"
        with patch.object(sys, "argv", ["_settings_preview.py", line]):
            main()
        captured = capsys.readouterr()
        assert "Test description" in captured.out

    def test_main_with_header(self, capsys):
        with patch.object(sys, "argv", ["_settings_preview.py", "__HEADER__\t\tTitle"]):
            main()
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_main_without_args(self, capsys):
        with patch.object(sys, "argv", ["_settings_preview.py"]):
            main()
        captured = capsys.readouterr()
        assert "No preview available" in captured.out
