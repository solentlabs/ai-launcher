"""Tests for project selector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_launcher.core.models import Project
from ai_launcher.ui.selector import show_project_list


def test_show_project_list_empty(capsys):
    """Test showing empty project list."""
    show_project_list([])

    captured = capsys.readouterr()
    assert "No projects found" in captured.out


def test_show_project_list_with_projects(capsys):
    """Test showing project list with projects."""
    projects = [
        Project(
            path=Path("/home/user/project1"),
            name="project1",
            parent_path=Path("/home/user"),
            is_git_repo=True,
            is_manual=False,
        ),
        Project(
            path=Path("/home/user/project2"),
            name="project2",
            parent_path=Path("/home/user"),
            is_git_repo=False,
            is_manual=True,
        ),
    ]

    show_project_list(projects)

    captured = capsys.readouterr()
    assert "2 project(s)" in captured.out
    assert str(Path("/home/user/project1")) in captured.out
    assert str(Path("/home/user/project2")) in captured.out
    assert "[git]" in captured.out
    assert "[manual]" in captured.out


def test_alphabetical_sorting():
    """Test that projects are expected to be sorted alphabetically."""
    projects = [
        Project.from_path(Path("/a/project"), is_manual=False),
        Project.from_path(Path("/b/project"), is_manual=False),
        Project.from_path(Path("/c/project"), is_manual=False),
    ]

    paths = [str(p.path) for p in projects]
    assert paths == sorted(paths)


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_with_selection(mock_clear, mock_tree, mock_popen, tmp_path):
    """Test successful project selection."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "test-project"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)

    # Mock build_tree_view to return known choices
    choice_str = f"{project_path}\t\ttest-project"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    # Mock fzf to return the selected choice
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (f"{choice_str}\n".encode(), b"")
    mock_popen.return_value = mock_process

    result = select_project([project])

    assert result is not None
    assert result.path == project_path


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_cancelled(mock_clear, mock_tree, mock_popen, tmp_path):
    """Test project selection when user cancels."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "test-project"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)

    choice_str = f"{project_path}\t\ttest-project"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    # Mock fzf cancellation (exit code 1)
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (b"", b"")
    mock_popen.return_value = mock_process

    result = select_project([project])

    assert result is None


def test_select_project_empty_list(capsys):
    """Test selecting from empty project list."""
    from ai_launcher.ui.selector import select_project

    result = select_project([])

    assert result is None
    captured = capsys.readouterr()
    assert "No projects found" in captured.out


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_fzf_not_found(
    mock_clear, mock_tree, mock_popen, tmp_path, capsys
):
    """Test handling when fzf is not installed."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "test-project"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)

    choice_str = f"{project_path}\t\ttest-project"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    # Mock fzf not found
    mock_popen.side_effect = FileNotFoundError("fzf not found")

    result = select_project([project])

    assert result is None
    captured = capsys.readouterr()
    assert "fzf" in captured.out.lower()
