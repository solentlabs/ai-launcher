"""Tests for CLI interface."""

import pytest
from typer.testing import CliRunner

from ai_launcher.cli import app

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
