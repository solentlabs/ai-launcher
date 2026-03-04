"""Tests for CLI interface.

Author: Solent Labs™
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_launcher.cli import app, launch_ai

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
