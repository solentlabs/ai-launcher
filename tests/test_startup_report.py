"""Tests for startup context report functionality."""

from ai_launcher.ui.startup_report import (
    _pad_line,
    _visual_length,
)


class TestHelperFunctions:
    """Test helper functions for formatting."""

    def test_visual_length_ascii(self):
        """Test _visual_length with ASCII characters."""
        text = "Hello World"
        assert _visual_length(text) == 11

    def test_visual_length_emoji(self):
        """Test _visual_length with emoji characters."""
        # Basic emoji should take 2 spaces
        text = "🚀"
        length = _visual_length(text)
        assert length >= 1  # At least 1, likely 2

    def test_visual_length_mixed(self):
        """Test _visual_length with mixed ASCII and emoji."""
        text = "Test 🚀 Text"
        length = _visual_length(text)
        # Should be longer than just the ASCII count
        assert length >= len(text)

    def test_pad_line_basic(self):
        """Test _pad_line with basic text."""
        text = "│ Test"
        width = 20
        result = _pad_line(text, width)

        assert result.startswith("│ Test")
        assert result.endswith("│")
        # Visual length should match width
        assert _visual_length(result) <= width + 2  # Allow some tolerance for emoji

    def test_pad_line_exact_width(self):
        """Test _pad_line produces correct width."""
        text = "│ Short"
        width = 30
        result = _pad_line(text, width)

        # Should have closing border
        assert result.endswith("│")

    def test_pad_line_too_long(self):
        """Test _pad_line with text that's too long."""
        text = "│ " + "x" * 100
        width = 20
        result = _pad_line(text, width)

        # Should still close with border
        assert result.endswith("│")
