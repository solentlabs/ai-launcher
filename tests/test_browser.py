"""Tests for directory browser."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_launcher.ui.browser import browse_directory


@patch("subprocess.Popen")
def test_browse_directory_navigation(mock_popen):
    """Test directory browser navigation - user cancels."""
    mock_process = MagicMock()
    mock_process.returncode = 1  # User cancelled
    mock_process.communicate.return_value = (b"", b"")
    mock_popen.return_value = mock_process

    result = browse_directory(Path.home())

    assert result is None


@patch("subprocess.Popen")
def test_browse_directory_select_current(mock_popen, tmp_path):
    """Test selecting current directory in browser."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b".\n", b"")
    mock_popen.return_value = mock_process

    result = browse_directory(test_dir)

    assert result == test_dir


@patch("subprocess.Popen")
def test_browse_directory_navigate_into(mock_popen, tmp_path):
    """Test navigating into a subdirectory then cancelling."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # First call: user selects subdir (navigates into it)
    mock_process_1 = MagicMock()
    mock_process_1.returncode = 0
    mock_process_1.communicate.return_value = (b"subdir\n", b"")

    # Second call: user cancels
    mock_process_2 = MagicMock()
    mock_process_2.returncode = 1
    mock_process_2.communicate.return_value = (b"", b"")

    mock_popen.side_effect = [mock_process_1, mock_process_2]

    result = browse_directory(tmp_path)

    assert result is None
    assert mock_popen.call_count == 2


@patch("subprocess.Popen")
def test_browse_directory_select_subdirectory(mock_popen, tmp_path):
    """Test navigating into a subdirectory and selecting it."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # First call: user selects subdir (navigates into it)
    mock_process_1 = MagicMock()
    mock_process_1.returncode = 0
    mock_process_1.communicate.return_value = (b"subdir\n", b"")

    # Second call: user selects "." (selects current = subdir)
    mock_process_2 = MagicMock()
    mock_process_2.returncode = 0
    mock_process_2.communicate.return_value = (b".\n", b"")

    mock_popen.side_effect = [mock_process_1, mock_process_2]

    result = browse_directory(tmp_path)

    assert result == subdir


@patch("subprocess.Popen")
def test_browse_directory_navigate_up(mock_popen, tmp_path):
    """Test navigating to parent directory."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # First: user selects ".." (parent)
    mock_process_1 = MagicMock()
    mock_process_1.returncode = 0
    mock_process_1.communicate.return_value = (b"..\n", b"")

    # Second: user cancels
    mock_process_2 = MagicMock()
    mock_process_2.returncode = 1
    mock_process_2.communicate.return_value = (b"", b"")

    mock_popen.side_effect = [mock_process_1, mock_process_2]

    result = browse_directory(subdir)

    assert result is None


@patch("subprocess.Popen")
def test_browse_directory_empty_directory(mock_popen, tmp_path):
    """Test browsing an empty directory and selecting it."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    # User selects "." to pick this empty directory
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b".\n", b"")
    mock_popen.return_value = mock_process

    result = browse_directory(empty_dir)

    assert result == empty_dir


def test_browse_directory_permission_error(tmp_path):
    """Test handling permission denied error."""
    with patch("pathlib.Path.iterdir", side_effect=PermissionError):
        result = browse_directory(tmp_path)

    assert result is None
