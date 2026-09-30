"""Tests for project selector."""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import (
    ConfigData,
    ContextConfig,
    Project,
    ProviderConfig,
    Selection,
)
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
    mock_process.communicate.return_value = (_picked(choice_str), b"")
    mock_popen.return_value = mock_process

    result = select_project([project])

    assert result is not None
    assert result.project.path == project_path


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


def _picked(row, key=""):
    """Picker output: fzf --expect prints the key first, empty for Enter."""
    return f"{key}\n{row}\n".encode()


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
    # Cleared before fzf and again on the way out: fzf may have left its screen up.
    assert mock_clear.call_count == 2


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

    action_row = "__ACTION__\t\t🔧 Configuration"
    mock_popen.side_effect = [
        _make_popen_mock(_picked(action_row)),
        _make_popen_mock(_picked(choice_str)),
    ]

    result = select_project([project])
    assert result == Selection(project)


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

    mock_popen.side_effect = [
        _make_popen_mock(_picked("__SPACE__\t\t")),
        _make_popen_mock(_picked(choice_str)),
    ]

    result = select_project([project])
    assert result == Selection(project)


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
        _make_popen_mock(_picked(header_str)),
        _make_popen_mock(_picked(choice_str)),
    ]

    result = select_project([project])
    assert result == Selection(project)


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
    mock_popen.return_value = _make_popen_mock(_picked(choice_str))

    result = select_project(
        [proj_a],
        scan_paths=[
            tmp_path / "workspace" / "proj-a",
            tmp_path / "workspace" / "proj-b",
        ],
    )
    assert result == Selection(proj_a)


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
    mock_popen.return_value = _make_popen_mock(_picked(choice_str))

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
    # Cleared before fzf and again on the way out: --no-clear leaves its screen up.
    assert mock_clear.call_count == 2


# --- Open With list (Ctrl-O) -------------------------------------------------

CONFIG_ROW = "__ACTION__\t\t🔧 Configuration"


def _provider(name, display_name):
    provider = MagicMock()
    provider.metadata.name = name
    provider.metadata.display_name = display_name
    return provider


AIDER = ("aider", "Aider")
CLAUDE = ("claude-code", "Claude Code")
GEMINI = ("gemini", "Gemini CLI")
ALL_TOOLS = [AIDER, CLAUDE, GEMINI]


@pytest.fixture
def picker(tmp_path):
    """A one-project picker with fzf, the tree view and the registry mocked.

    `installed` sets which tools the registry reports; `run` plays a sequence
    of fzf results and returns what select_project() gave back.
    """
    project_path = tmp_path / "my-proj"
    project_path.mkdir()
    folder = tmp_path / "parent-dir"
    folder.mkdir()
    project = Project.from_path(project_path, is_manual=False)
    choice = f"{project_path}\t\tmy-proj"
    rows = {
        "project": choice,
        "config": CONFIG_ROW,
        "folder": f"{folder}\t\tparent-dir/",
    }
    registry = MagicMock()

    # Every tool is registered; `installed` sets which ones are on this machine.
    registered = {name: _provider(name, label) for name, label in ALL_TOOLS}
    # clears[i] and greys[i]: how often the screen had been cleared, and greyed
    # out, when fzf run i started
    state = SimpleNamespace(procs=[], clears=[], greys=[])

    def installed(*tools):
        registry.list_installed.return_value = [registered[name] for name, _ in tools]

    installed(*ALL_TOOLS)

    with patch("subprocess.Popen") as popen, patch(
        "ai_launcher.ui.selector.build_tree_view",
        return_value=([choice], {choice: project}),
    ), patch("ai_launcher.ui.selector.clear_screen") as clear, patch(
        "ai_launcher.ui.selector.get_registry", return_value=registry
    ), patch(
        "ai_launcher.ui.selector.shutil.get_terminal_size",
        return_value=os.terminal_size((100, 24)),
    ), patch("ai_launcher.ui.selector._grey_out_screen") as grey:

        def run(steps, default="claude-code"):
            from ai_launcher.ui.selector import select_project

            procs = []
            for kind, value, key in steps:
                if kind == "pick":
                    procs.append(_make_popen_mock(_picked(rows[value], key)))
                elif value is None:  # Esc in the Open With list
                    procs.append(_make_popen_mock(b"", returncode=key))
                else:
                    procs.append(_make_popen_mock(f"{value}\n".encode()))
            state.procs = procs
            state.clears = []
            state.greys = []
            pending = iter(procs)

            def start_fzf(*args, **kwargs):
                state.clears.append(clear.call_count)
                state.greys.append(grey.call_count)
                return next(pending)

            popen.side_effect = start_fzf
            config = ConfigData(provider=ProviderConfig(default=default))
            return select_project([project], config=config)

        def rows_sent(call_index):
            """The rows piped to the fzf run at `call_index`."""
            sent = state.procs[call_index].communicate.call_args.kwargs["input"]
            return sent.decode("utf-8").splitlines()

        yield SimpleNamespace(
            project=project,
            popen=popen,
            installed=installed,
            run=run,
            rows_sent=rows_sent,
            state=state,
            grey=grey,
        )


def _pick(row, key=""):
    """A picker result: Enter (or `key`) on the project, config or folder row."""
    return ("pick", row, key)


def _open_with(row):
    """An Open With list result: Enter on the row with this text."""
    return ("list", row, None)


def _leave_list(returncode):
    """Esc (1) or Ctrl-C (130) in the Open With list."""
    return ("list", None, returncode)


@pytest.mark.parametrize(
    "steps,expected",
    [
        pytest.param([_pick("project")], {}, id="enter-launches-default"),
        pytest.param(
            [_pick("project", "ctrl-o"), _open_with("Claude Code   (default)")],
            {},
            id="ctrl-o-default-row-is-enter",
        ),
        pytest.param(
            [_pick("project", "ctrl-o"), _open_with("Gemini CLI")],
            {"provider": "gemini"},
            id="ctrl-o-other-tool",
        ),
        pytest.param(
            [_pick("project", "ctrl-o"), _open_with("Shell")],
            {"use_shell": True},
            id="ctrl-o-shell",
        ),
        pytest.param(
            [_pick("project", "ctrl-o"), _leave_list(1), _pick("project")],
            {},
            id="esc-in-list-returns-to-picker",
        ),
        pytest.param(
            [_pick("project", "ctrl-o"), _leave_list(130), _pick("project")],
            {},
            id="ctrl-c-in-list-returns-to-picker",
        ),
        pytest.param(
            [_pick("project", "ctrl-o"), _open_with("not a row"), _pick("project")],
            {},
            id="unknown-row-returns-to-picker",
        ),
        pytest.param(
            [_pick("config", "ctrl-o"), _pick("project")],
            {},
            id="ctrl-o-on-configuration-row-loops-back",
        ),
        pytest.param(
            [_pick("folder", "ctrl-o"), _pick("project")],
            {},
            id="ctrl-o-on-folder-header-loops-back",
        ),
    ],
)
def test_open_with_selection(picker, steps, expected):
    """Each key and row combination returns the right thing to open."""
    result = picker.run(steps)

    assert result == Selection(picker.project, **expected)
    # Every scripted fzf run was used: nothing opened a list it should not have.
    assert picker.popen.call_count == len(steps)


@pytest.mark.parametrize(
    "installed,default,expected_rows",
    [
        pytest.param(
            ALL_TOOLS,
            "claude-code",
            ["Claude Code   (default)", "Aider", "Gemini CLI", "Shell"],
            id="default-first-and-marked",
        ),
        pytest.param(
            ALL_TOOLS,
            "gemini",
            ["Gemini CLI   (default)", "Aider", "Claude Code", "Shell"],
            id="default-follows-the-subcommand",
        ),
        pytest.param(
            [AIDER, GEMINI],
            "claude-code",
            ["Aider", "Gemini CLI", "Shell"],
            id="default-not-installed",
        ),
        pytest.param([], "claude-code", ["Shell"], id="nothing-installed"),
    ],
)
def test_open_with_rows(picker, installed, default, expected_rows):
    """The list shows installed tools, the default first, then Shell."""
    picker.installed(*installed)

    picker.run([_pick("project", "ctrl-o"), _open_with("Shell")], default=default)

    assert picker.rows_sent(call_index=1) == expected_rows


def test_open_with_list_is_a_plain_list(picker):
    """The list names the project in its border and has no preview pane."""
    picker.run([_pick("project", "ctrl-o"), _open_with("Shell")])

    list_cmd = picker.popen.call_args_list[1].args[0]
    assert "--border-label= Open my-proj with " in list_cmd
    assert not any(arg.startswith("--preview") for arg in list_cmd)
    assert not any(arg.startswith("--expect") for arg in list_cmd)


def test_open_with_list_is_drawn_over_the_picker(picker, capsys):
    """The picker's frame is left on screen and the list is a box on top of it."""
    picker.run([_pick("project", "ctrl-o"), _open_with("Shell")])

    picker_cmd, list_cmd = (call.args[0] for call in picker.popen.call_args_list)
    # The picker leaves its last frame behind, one row down (fzf clears row 1).
    assert "--no-clear" in picker_cmd
    assert "--margin=1,0,0,0" in picker_cmd
    # Nothing clears the screen between the picker and the list...
    assert picker.state.clears == [1, 1]
    # ...the whole screen is greyed once, before the box is drawn on it...
    assert picker.state.greys == [0, 1]
    picker.grey.assert_called_once_with(os.terminal_size((100, 24)))
    # ...and the list draws only its own box: height mode, from the top row,
    # 4 rows in a 100x24 terminal.
    assert "--no-clear" in list_cmd
    assert "--height=23" in list_cmd
    assert "--margin=7,25,8,25" in list_cmd
    assert "\033[H" in capsys.readouterr().out


@pytest.mark.parametrize(
    "rows,label_width,columns,lines,expected",
    [
        pytest.param(4, 20, 100, 24, (23, "7,25,8,25"), id="100x24"),
        pytest.param(4, 20, 150, 40, (39, "15,50,16,50"), id="150x40"),
        pytest.param(2, 20, 100, 24, (23, "8,25,9,25"), id="fewer-rows"),
        pytest.param(4, 70, 100, 24, (23, "7,13,8,13"), id="long-project-name"),
        pytest.param(4, 20, 40, 10, (9, "0,0,1,0"), id="narrower-than-the-box"),
        pytest.param(4, 20, 100, 6, (5, "0,25,0,25"), id="shorter-than-the-box"),
    ],
)
def test_dialog_geometry(rows, label_width, columns, lines, expected):
    """A box of fixed size is centred; a small terminal is filled instead."""
    from ai_launcher.ui.selector import _dialog_geometry

    size = os.terminal_size((columns, lines))
    assert _dialog_geometry(rows, label_width, size) == expected


def test_grey_out_screen_recolours_the_whole_screen(capsys):
    """One DECCARA sequence gives every cell on screen a grey foreground."""
    from ai_launcher.ui.selector import _grey_out_screen

    _grey_out_screen(os.terminal_size((100, 24)))

    assert capsys.readouterr().out == "\033[1;1;24;100;38;5;240$r"


def test_clear_screen_leaves_the_picker_screen(capsys):
    """clear_screen() also leaves the alternate screen --no-clear stays on."""
    from ai_launcher.ui.selector import clear_screen

    clear_screen()

    assert capsys.readouterr().out == "\033[?1049l\033[H\033[2J"


def test_picker_header_has_the_ctrl_o_hint(picker):
    """The header names the one new key, and the picker listens for it."""
    picker.run([_pick("project")])

    picker_cmd = picker.popen.call_args_list[0].args[0]
    header = next(arg for arg in picker_cmd if arg.startswith("--header="))
    assert "Ctrl-O for other tools" in header.splitlines()
    # Enter is the obvious key: the header does not spend a line on it.
    assert not any(line.startswith("Enter") for line in header.splitlines())
    assert "--expect=ctrl-o" in picker_cmd


@pytest.mark.parametrize(
    "output,expected",
    [
        pytest.param(b"\nrow\n", ("", "row"), id="enter"),
        pytest.param(b"ctrl-o\nrow\n", ("ctrl-o", "row"), id="ctrl-o"),
        pytest.param(b"ctrl-o\r\nrow\r\n", ("ctrl-o", "row"), id="windows-newlines"),
        pytest.param(b"", ("", ""), id="nothing"),
        pytest.param(b"ctrl-o\n", ("ctrl-o", ""), id="key-without-row"),
        pytest.param(
            "\n/p/odd\x0cname\t\todd\u2028name\n".encode(),
            ("", "/p/odd\x0cname\t\todd\u2028name"),
            id="row-with-other-line-breaks",
        ),
    ],
)
def test_parse_picker_output(output, expected):
    """The key is the first line and the row the second, split on newlines only."""
    from ai_launcher.ui.selector import _parse_picker_output

    assert _parse_picker_output(output) == expected
