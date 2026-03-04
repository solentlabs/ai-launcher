"""Tests for browser preview helper.

Author: Solent Labs™
"""

from unittest.mock import patch

from ai_launcher.ui._browser_preview import main


def test_no_args(capsys):
    """Test with no arguments — exits silently."""
    with patch("sys.argv", ["_browser_preview.py"]):
        main()
    assert capsys.readouterr().out == ""


def test_select_current(capsys, tmp_path):
    """Test selecting '.' shows current directory."""
    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), "."]):
        main()
    assert f"Select: {tmp_path}" in capsys.readouterr().out


def test_select_parent(capsys, tmp_path):
    """Test selecting '..' shows parent."""
    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), ".."]):
        main()
    assert f"Go to: {tmp_path.parent}" in capsys.readouterr().out


def test_subdirectory_listing(capsys, tmp_path):
    """Test listing a subdirectory's contents."""
    sub = tmp_path / "mydir"
    sub.mkdir()
    (sub / "file.txt").write_text("hello")
    (sub / "child").mkdir()

    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), "mydir"]):
        main()

    out = capsys.readouterr().out
    assert "child/" in out
    assert "file.txt" in out


def test_symlink_indicator(capsys, tmp_path):
    """Test symlink directory shows resolve target."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)

    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), "link@"]):
        main()

    out = capsys.readouterr().out
    assert "Symlink to:" in out


def test_file_target(capsys, tmp_path):
    """Test selecting a file shows its name."""
    (tmp_path / "note.txt").write_text("hi")

    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), "note.txt"]):
        main()

    assert "note.txt" in capsys.readouterr().out


def test_truncation_at_20(capsys, tmp_path):
    """Test that listing truncates after 20 items."""
    sub = tmp_path / "big"
    sub.mkdir()
    for i in range(25):
        (sub / f"file{i:02d}.txt").write_text("")

    with patch("sys.argv", ["_browser_preview.py", str(tmp_path), "big"]):
        main()

    out = capsys.readouterr().out
    assert "and 5 more" in out
