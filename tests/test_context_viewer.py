"""Tests for context viewer UI.

Author: Solent Labs™
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import Project, ProviderInfo
from ai_launcher.ui.context_viewer import show_context_viewer


def _make_provider(name, installed=True, version="1.0"):
    ctx = MagicMock()
    ctx.version = version
    return ProviderInfo(name=name, command=name, context=ctx if installed else None)


def _make_project(path, is_git=True):
    return Project(
        path=Path(path),
        name=Path(path).name,
        parent_path=Path(path).parent,
        is_git_repo=is_git,
        is_manual=False,
    )


@pytest.mark.parametrize(
    "providers,projects,expected_in_input",
    [
        pytest.param(
            [_make_provider("claude-code")],
            [_make_project("/tmp/proj")],
            None,
            id="basic",
        ),
        pytest.param(
            [_make_provider("gemini", installed=False)],
            [],
            "not installed",
            id="uninstalled-provider",
        ),
        pytest.param(
            [],
            [_make_project(f"/tmp/proj{i}") for i in range(25)],
            "5 more",
            id="truncates-projects",
        ),
    ],
)
@patch("subprocess.Popen")
def test_viewer_scenarios(mock_popen, providers, projects, expected_in_input):
    """Test context viewer renders providers and projects correctly."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    show_context_viewer(providers, projects)

    mock_popen.assert_called_once()
    input_bytes = mock_process.communicate.call_args[1]["input"]
    assert isinstance(input_bytes, bytes)

    if expected_in_input:
        assert expected_in_input in input_bytes.decode("utf-8")


@patch("subprocess.Popen", side_effect=FileNotFoundError)
def test_viewer_fzf_not_found(mock_popen, capsys):
    """Test handling when fzf is not installed."""
    with pytest.raises(SystemExit):
        show_context_viewer([], [])

    assert "fzf not found" in capsys.readouterr().out
