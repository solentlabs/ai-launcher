"""Tests for file preview helper.

Author: Solent Labs™
"""

from unittest.mock import patch

from ai_launcher.ui._file_preview import main


def test_no_args(capsys):
    """Test with no arguments — exits silently."""
    with patch("sys.argv", ["_file_preview.py"]):
        main()
    assert capsys.readouterr().out == ""


def test_existing_file(capsys, tmp_path):
    """Test previewing an existing file."""
    f = tmp_path / "readme.md"
    f.write_text("# Hello World\n")

    with patch("sys.argv", ["_file_preview.py", str(f)]):
        main()

    assert "Hello World" in capsys.readouterr().out


def test_missing_file(capsys, tmp_path):
    """Test previewing a non-existent file."""
    with patch("sys.argv", ["_file_preview.py", str(tmp_path / "nope.md")]):
        main()

    assert "File not found" in capsys.readouterr().out


def test_tilde_expansion(capsys, tmp_path):
    """Test that ~ paths are expanded."""
    f = tmp_path / "test.md"
    f.write_text("content")

    with patch("sys.argv", ["_file_preview.py", str(f)]):
        main()

    assert "content" in capsys.readouterr().out
