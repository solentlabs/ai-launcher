"""Tests for project selector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_launcher.core.models import ConfigData, ContextConfig, Project
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


def _make_popen_mock(output_bytes, returncode=0):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate.return_value = (output_bytes, b"")
    return proc


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_generic_exception(
    mock_clear, mock_tree, mock_popen, tmp_path, capsys
):
    """Generic exception during Popen returns None and prints error."""
    from ai_launcher.ui.selector import select_project

    project = Project.from_path(tmp_path / "p", is_manual=False)
    choice_str = f"{tmp_path / 'p'}\t\tp"
    mock_tree.return_value = ([choice_str], {choice_str: project})
    mock_popen.side_effect = RuntimeError("unexpected")

    result = select_project([project])

    assert result is None
    assert "Error" in capsys.readouterr().out


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_configuration_action_then_select(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """Selecting the Configuration action item loops back; next selection succeeds."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "my-proj"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)
    choice_str = f"{project_path}\t\tmy-proj"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    action_bytes = "__ACTION__\t\t🔧 Configuration".encode()
    mock_popen.side_effect = [
        _make_popen_mock(action_bytes + b"\n"),
        _make_popen_mock(f"{choice_str}\n".encode()),
    ]

    result = select_project([project])
    assert result == project


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_space_action_then_select(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """Selecting a __SPACE__ separator loops back; next selection succeeds."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "my-proj"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)
    choice_str = f"{project_path}\t\tmy-proj"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    space_bytes = b"__SPACE__\t\t\n"
    mock_popen.side_effect = [
        _make_popen_mock(space_bytes),
        _make_popen_mock(f"{choice_str}\n".encode()),
    ]

    result = select_project([project])
    assert result == project


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_directory_header_loops_back(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """Selecting a directory header (path is a dir with no .git) loops back."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "my-proj"
    project_path.mkdir()
    dir_header = tmp_path / "parent-dir"
    dir_header.mkdir()
    project = Project.from_path(project_path, is_manual=False)

    choice_str = f"{project_path}\t\tmy-proj"
    mock_tree.return_value = ([choice_str], {choice_str: project})

    header_str = f"{dir_header}\t\tparent-dir/"
    mock_popen.side_effect = [
        _make_popen_mock(f"{header_str}\n".encode()),
        _make_popen_mock(f"{choice_str}\n".encode()),
    ]

    result = select_project([project])
    assert result == project


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_multiple_scan_paths_common_base(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """Multiple scan_paths triggers common-base calculation (lines 66-67)."""
    from ai_launcher.ui.selector import select_project

    path_a = tmp_path / "workspace" / "proj-a"
    path_b = tmp_path / "workspace" / "proj-b"
    path_a.mkdir(parents=True)
    path_b.mkdir(parents=True)

    proj_a = Project.from_path(path_a, is_manual=False)
    choice_str = f"{path_a}\t\tproj-a"
    mock_tree.return_value = ([choice_str], {choice_str: proj_a})
    mock_popen.return_value = _make_popen_mock(f"{choice_str}\n".encode())

    result = select_project(
        [proj_a],
        scan_paths=[
            tmp_path / "workspace" / "proj-a",
            tmp_path / "workspace" / "proj-b",
        ],
    )
    assert result == proj_a


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_env_vars_global_files_and_manual_paths(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """config.context.global_files and manual_paths populate env vars (lines 109, 111)."""
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "proj"
    project_path.mkdir()
    project = Project.from_path(project_path, is_manual=False)
    choice_str = f"{project_path}\t\tproj"
    mock_tree.return_value = ([choice_str], {choice_str: project})
    mock_popen.return_value = _make_popen_mock(f"{choice_str}\n".encode())

    config = ConfigData(context=ContextConfig(global_files=["~/notes.md"]))

    select_project([project], config=config, manual_paths=["/extra/path"])

    env = mock_popen.call_args[1]["env"]
    assert "AI_LAUNCHER_GLOBAL_FILES" in env
    assert "~/notes.md" in env["AI_LAUNCHER_GLOBAL_FILES"]
    assert "AI_LAUNCHER_MANUAL_PATHS" in env
    assert "/extra/path" in env["AI_LAUNCHER_MANUAL_PATHS"]


@patch("subprocess.Popen")
@patch("ai_launcher.ui.selector.build_tree_view")
@patch("ai_launcher.ui.selector.clear_screen")
def test_select_project_empty_stdout_returns_none(
    mock_clear, mock_tree, mock_popen, tmp_path
):
    """Empty stdout after fzf exits normally returns None (line 162)."""
    from ai_launcher.ui.selector import select_project

    project = Project.from_path(tmp_path / "proj", is_manual=False)
    choice_str = f"{tmp_path / 'proj'}\t\tproj"
    mock_tree.return_value = ([choice_str], {choice_str: project})
    mock_popen.return_value = _make_popen_mock(b"")

    result = select_project([project])
    assert result is None
