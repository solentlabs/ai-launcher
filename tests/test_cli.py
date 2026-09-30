"""Tests for CLI interface.

Author: Solent Labs™
"""

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_launcher.cli import app, find_shell, launch_ai, launch_shell
from ai_launcher.core.models import ConfigData, Selection, UIConfig

runner = CliRunner()


def test_version_command():
    """Test --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ai-launcher" in result.stdout


@pytest.mark.parametrize(
    "command",
    ["claude", "gemini", "cursor", "aider", "copilot"],
)
def test_provider_command_no_path(command):
    """Test that provider commands without path argument show error."""
    result = runner.invoke(app, [command])
    assert result.exit_code == 1
    assert "No directory specified" in result.output


@pytest.mark.parametrize(
    "has_project,expected_text",
    [
        pytest.param(True, "myproject", id="with-projects"),
        pytest.param(False, "No projects found", id="empty"),
    ],
)
def test_list_flag(has_project, expected_text, tmp_path):
    """Test --list flag with and without discovered projects."""
    if has_project:
        proj = tmp_path / "myproject"
        proj.mkdir()
        (proj / ".git").mkdir()

    result = runner.invoke(app, ["claude", str(tmp_path), "--list"])
    assert result.exit_code == 0
    assert expected_text in result.output


@patch("ai_launcher.ui.selector.select_project", return_value=None)
@patch("ai_launcher.utils.fzf.ensure_fzf", return_value=True)
def test_no_project_selected(mock_fzf, mock_select, tmp_path):
    """Test when user cancels project selection."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").mkdir()

    result = runner.invoke(app, ["claude", str(tmp_path)])
    assert result.exit_code == 0
    assert "No project selected" in result.output


def test_discover(tmp_path):
    """Test --discover flag runs discovery report and exits."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").mkdir()

    result = runner.invoke(app, ["claude", str(tmp_path), "--discover"])
    # sys.exit(0) inside typer raises SystemExit which CliRunner catches
    assert result.exit_code in (0, 1)
    assert "Traceback" not in result.output


def test_check_permissions_flag(tmp_path):
    """--check-permissions runs the permission report and exits cleanly."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").mkdir()

    result = runner.invoke(app, ["claude", str(tmp_path), "--check-permissions"])
    assert result.exit_code in (0, 1)
    assert "Traceback" not in result.output
    # The permission report prints this header regardless of whether projects
    # have settings — guards against regressing the wiring between the CLI
    # flag and ui.permissions_report.check_project_permissions.
    assert "Permission Health Check" in result.output


def test_global_files_parsing(tmp_path):
    """Test --global-files are parsed and passed to config."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").mkdir()

    result = runner.invoke(
        app, ["claude", str(tmp_path), "--list", "--global-files", "a.md,b.md"]
    )
    assert result.exit_code == 0


def test_manual_paths(tmp_path):
    """Test --manual-paths adds projects."""
    manual = tmp_path / "manual-proj"
    manual.mkdir()

    result = runner.invoke(
        app,
        ["claude", str(tmp_path), "--list", "--manual-paths", str(manual)],
    )
    assert result.exit_code == 0
    assert "manual-proj" in result.output


@patch("ai_launcher.providers.registry.get_provider")
@patch("ai_launcher.cli.display_launch_info")
def test_launch_ai_basic(mock_display, mock_get_provider, tmp_path):
    """Test launch_ai with a valid project path."""
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    launch_ai(tmp_path)

    mock_provider.cleanup_environment.assert_called_once()
    mock_display.assert_called_once()
    mock_provider.launch_with_title.assert_called_once()


@patch("ai_launcher.providers.registry.get_provider")
@patch("ai_launcher.cli.display_launch_info")
def test_launch_ai_nonexistent_path(mock_display, mock_get_provider):
    """Test launch_ai with a non-existent path exits."""
    with pytest.raises(SystemExit):
        launch_ai(Path("/nonexistent/path/xyz"))


@patch("ai_launcher.providers.registry.get_provider")
@patch("ai_launcher.cli.display_launch_info")
def test_launch_ai_per_project_override(mock_display, mock_get_provider, tmp_path):
    """Test launch_ai uses per-project provider override."""
    from ai_launcher.core.models import (
        CleanupConfig,
        ConfigData,
        ContextConfig,
        ProviderConfig,
        ScanConfig,
        UIConfig,
    )

    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    config = ConfigData(
        scan=ScanConfig(paths=[], max_depth=5, prune_dirs=[]),
        ui=UIConfig(),
        cleanup=CleanupConfig(enabled=False),
        context=ContextConfig(global_files=[]),
        provider=ProviderConfig(
            default="claude-code",
            per_project={str(tmp_path): "gemini"},
        ),
    )

    launch_ai(tmp_path, config=config)

    mock_get_provider.assert_called_once_with("gemini")


@patch("ai_launcher.cli.launch_ai")
@patch("ai_launcher.cli.select_project")
@patch("ai_launcher.utils.fzf.ensure_fzf", return_value=True)
def test_launch_passes_scope_roots(mock_fzf, mock_select, mock_launch, tmp_path):
    """The scan root and manual projects become the guarded roots."""
    scan = tmp_path / "scan"
    (scan / "proj" / ".git").mkdir(parents=True)
    manual = tmp_path / "manual-proj"
    manual.mkdir()
    mock_select.side_effect = lambda projects, *args, **kwargs: Selection(projects[0])

    result = runner.invoke(app, ["claude", str(scan), "--manual-paths", str(manual)])

    assert result.exit_code == 0, result.output
    assert mock_launch.call_args.kwargs["scope_roots"] == [scan.resolve(), manual]
    assert mock_launch.call_args.kwargs["scope_exempt"] == []


@patch("ai_launcher.cli.launch_ai")
@patch("ai_launcher.cli.select_project")
@patch("ai_launcher.utils.fzf.ensure_fzf", return_value=True)
@pytest.mark.parametrize("command", ["claude", "gemini"])
def test_allow_writes_become_scope_exempt(
    mock_fzf, mock_select, mock_launch, tmp_path, monkeypatch, command
):
    """--allow-writes folders (with ~) are passed on as exempt from the guard."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    scan = tmp_path / "scan"
    (scan / "proj" / ".git").mkdir(parents=True)
    mock_select.side_effect = lambda projects, *args, **kwargs: Selection(projects[0])

    result = runner.invoke(
        app, [command, str(scan), "--allow-writes", "~/journal, /srv/notes ,"]
    )

    assert result.exit_code == 0, result.output
    assert mock_launch.call_args.kwargs["scope_exempt"] == [
        tmp_path / "journal",
        Path("/srv/notes"),
    ]


@patch("ai_launcher.providers.registry.get_provider")
@patch("ai_launcher.cli.display_launch_info")
def test_launch_ai_forwards_scope_roots(mock_display, mock_get_provider, tmp_path):
    """launch_ai hands the roots to both the launch box and the provider."""
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider
    roots = [tmp_path.parent]

    exempt = [tmp_path.parent / "journal"]

    launch_ai(tmp_path, scope_roots=roots, scope_exempt=exempt)

    for call in (mock_display.call_args, mock_provider.launch_with_title.call_args):
        assert call.kwargs["scope_roots"] == roots
        assert call.kwargs["scope_exempt"] == exempt


# --- Open With list: routing and the shell ------------------------------------


@patch("ai_launcher.providers.registry.get_provider")
@patch("ai_launcher.cli.launch_shell")
@patch("ai_launcher.cli.launch_ai")
@patch("ai_launcher.cli.select_project")
@patch("ai_launcher.utils.fzf.ensure_fzf", return_value=True)
@pytest.mark.parametrize(
    "picked,expected",
    [
        pytest.param({}, "default", id="default-tool"),
        pytest.param({"provider": "gemini"}, "provider", id="another-tool"),
        pytest.param({"use_shell": True}, "shell", id="shell"),
    ],
)
def test_selection_routes_to_launch(
    mock_fzf,
    mock_select,
    mock_launch,
    mock_shell,
    mock_get_provider,
    tmp_path,
    picked,
    expected,
):
    """What the picker returned decides what is launched, and with which guard."""
    scan = tmp_path / "scan"
    project = scan / "proj"
    (project / ".git").mkdir(parents=True)
    mock_select.side_effect = lambda projects, *args, **kwargs: Selection(
        projects[0], **picked
    )

    result = runner.invoke(app, ["claude", str(scan), "--allow-writes", "/srv/notes"])

    assert result.exit_code == 0, result.output
    if expected == "shell":
        mock_launch.assert_not_called()
        assert mock_shell.call_args.args[0] == project.resolve()
        return

    mock_shell.assert_not_called()
    assert mock_launch.call_args.args == (project.resolve(),)
    launched = mock_launch.call_args.kwargs
    # A tool from the list gets the same guard arguments as the default.
    assert launched["scope_roots"] == [scan.resolve()]
    assert launched["scope_exempt"] == [Path("/srv/notes")]
    if expected == "default":
        assert launched.get("provider") is None
        mock_get_provider.assert_not_called()
    else:
        mock_get_provider.assert_called_once_with("gemini")
        assert launched["provider"] is mock_get_provider.return_value


@pytest.mark.parametrize(
    "env,found,expected",
    [
        pytest.param(
            {"SHELL": "/bin/zsh", "COMSPEC": "cmd.exe"},
            {"/bin/zsh", "cmd.exe", "/bin/sh"},
            "/bin/zsh",
            id="shell-wins",
        ),
        pytest.param(
            {"COMSPEC": "cmd.exe"}, {"cmd.exe"}, "cmd.exe", id="windows-comspec"
        ),
        pytest.param(
            {"SHELL": "/usr/bin/bash", "COMSPEC": "cmd.exe"},
            {"cmd.exe"},
            "cmd.exe",
            id="unrunnable-shell-is-skipped",
        ),
        pytest.param({}, {"/bin/sh"}, "/bin/sh", id="neither-set"),
        pytest.param({"SHELL": ""}, {"/bin/sh"}, "/bin/sh", id="empty-shell"),
        pytest.param({"SHELL": "/bin/zsh"}, set(), None, id="nothing-found"),
    ],
)
def test_find_shell(monkeypatch, env, found, expected):
    """The first of $SHELL, %COMSPEC% and /bin/sh that can be run is used."""
    for name in ("SHELL", "COMSPEC"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with patch(
        "ai_launcher.cli.shutil.which",
        side_effect=lambda candidate: candidate if candidate in found else None,
    ):
        assert find_shell() == expected


@pytest.fixture
def shell_run(tmp_path, monkeypatch):
    """launch_shell() with the shell, chdir and the terminal title mocked.

    The working directory is tmp_path, set before chdir is mocked. The mocked
    run records the SIGINT handler in force while the shell runs.
    """
    monkeypatch.chdir(tmp_path)
    with patch("ai_launcher.cli.find_shell", return_value="/bin/zsh"), patch(
        "ai_launcher.cli.subprocess.run"
    ) as run, patch("ai_launcher.cli.os.chdir") as chdir, patch(
        "ai_launcher.cli.set_terminal_title"
    ) as title:
        run.sigint_during = []

        def fake_run(*args, **kwargs):
            run.sigint_during.append(signal.getsignal(signal.SIGINT))
            return MagicMock(returncode=run.exit_status)

        run.exit_status = 0
        run.side_effect = fake_run
        yield MagicMock(run=run, chdir=chdir, title=title)


@pytest.mark.parametrize(
    "set_title,expected_titles",
    [
        pytest.param(True, ["proj → Shell"], id="title-set"),
        pytest.param(False, [], id="title-off"),
    ],
)
def test_launch_shell_runs_shell_in_project(
    shell_run, tmp_path, capsys, set_title, expected_titles
):
    """The shell starts in the project, and Ctrl-C is the shell's while it runs."""
    project = tmp_path / "proj"
    project.mkdir()
    before = signal.getsignal(signal.SIGINT)

    launch_shell(project, ConfigData(ui=UIConfig(set_terminal_title=set_title)))

    shell_run.chdir.assert_called_once_with(project)
    assert shell_run.run.call_args.args == (["/bin/zsh"],)
    assert [call.args[0] for call in shell_run.title.call_args_list] == expected_titles
    assert "exit" in capsys.readouterr().out
    assert shell_run.run.sigint_during[0] not in (
        before,
        signal.SIG_IGN,
        signal.SIG_DFL,
    )
    assert signal.getsignal(signal.SIGINT) is before


@pytest.mark.parametrize(
    "as_relative",
    [
        pytest.param(False, id="absolute-path"),
        pytest.param(True, id="relative-manual-path"),
    ],
)
def test_launch_shell_pwd_is_the_listed_path(shell_run, tmp_path, capsys, as_relative):
    """PWD is the project's path as listed, made absolute so shells accept it."""
    (tmp_path / "proj").mkdir()
    listed = str(Path.cwd() / "proj")

    launch_shell(Path("proj") if as_relative else Path(listed))

    assert shell_run.run.call_args.kwargs["env"]["PWD"] == listed
    assert listed in capsys.readouterr().out


@pytest.mark.parametrize("status", [0, 7], ids=["clean-exit", "failed-exit"])
def test_launch_shell_passes_on_exit_status(shell_run, tmp_path, status):
    """The launcher exits with the shell's status, as the bash prototype does."""
    shell_run.run.exit_status = status

    if status == 0:
        launch_shell(tmp_path)
        return

    with pytest.raises(SystemExit) as exit_info:
        launch_shell(tmp_path)
    assert exit_info.value.code == status


@patch("ai_launcher.cli.subprocess.run")
@pytest.mark.parametrize(
    "project_exists,shell,expected_error",
    [
        pytest.param(False, "/bin/zsh", "Directory not found", id="missing-project"),
        pytest.param(True, None, "No shell found", id="no-shell"),
    ],
)
def test_launch_shell_errors(
    mock_run, tmp_path, capsys, project_exists, shell, expected_error
):
    """A missing project or shell is reported and nothing is started."""
    project = tmp_path / "proj"
    if project_exists:
        project.mkdir()

    with patch("ai_launcher.cli.find_shell", return_value=shell), pytest.raises(
        SystemExit
    ) as exit_info:
        launch_shell(project)

    assert exit_info.value.code == 1
    assert expected_error in capsys.readouterr().out
    mock_run.assert_not_called()
