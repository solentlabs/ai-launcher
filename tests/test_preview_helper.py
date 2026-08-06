"""Tests for preview helper script.

Author: Solent Labs™
"""

import os
from unittest.mock import patch

import pytest

from ai_launcher.ui._preview_helper import main, show_configuration_preview

# Base environment with all keys cleared
_BASE_ENV = {
    "AI_LAUNCHER_PROVIDER": "claude-code",
    "AI_LAUNCHER_SCAN_PATHS": "",
    "AI_LAUNCHER_MANUAL_PATHS": "",
    "AI_LAUNCHER_GLOBAL_FILES": "",
}


class TestShowConfigurationPreview:
    """Tests for show_configuration_preview()."""

    def test_default_output(self, capsys):
        """Test basic output with no env vars set."""
        with patch.dict(os.environ, _BASE_ENV, clear=False):
            show_configuration_preview()

        out = capsys.readouterr().out
        assert "Configuration" in out
        assert "Provider:" in out

    @pytest.mark.parametrize(
        "env_override,expected",
        [
            pytest.param(
                {"AI_LAUNCHER_PROVIDER": "gemini"},
                "gemini",
                id="provider-name",
            ),
            pytest.param(
                {"AI_LAUNCHER_SCAN_PATHS": "/tmp/scan"},
                "Scan paths: 1",
                id="scan-paths",
            ),
            pytest.param(
                {"AI_LAUNCHER_GLOBAL_FILES": "~/a.md,~/b.md"},
                "Configured: 2",
                id="global-files",
            ),
            pytest.param(
                {"AI_LAUNCHER_MANUAL_PATHS": "/tmp/manual"},
                "Manual paths: 1",
                id="manual-paths",
            ),
        ],
    )
    def test_env_var_rendering(self, env_override, expected, capsys):
        """Test that each environment variable renders in the output."""
        env = {**_BASE_ENV, **env_override}
        with patch.dict(os.environ, env, clear=False):
            show_configuration_preview()

        assert expected in capsys.readouterr().out


class TestMain:
    """Tests for main() entry point."""

    def test_no_args(self, capsys):
        """Test with no selection argument."""
        with patch("sys.argv", ["_preview_helper.py"]):
            main()
        assert "No selection" in capsys.readouterr().out

    def test_configuration_action(self, capsys):
        """Test configuration action triggers config preview."""
        with patch(
            "sys.argv",
            ["_preview_helper.py", "__ACTION__\t\t\u2699\ufe0f Configuration"],
        ):
            with patch.dict(os.environ, {"AI_LAUNCHER_PROVIDER": "claude-code"}):
                main()

        assert "Configuration" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "selection",
        [
            pytest.param("__SPACE__\t\tfoo", id="spacer"),
            pytest.param("__ACTION__\t\tSomething", id="non-config-action"),
            pytest.param("no-tabs-here", id="malformed"),
        ],
    )
    def test_silent_selections(self, selection, capsys):
        """Test that non-project selections produce no output."""
        with patch("sys.argv", ["_preview_helper.py", selection]):
            main()
        assert capsys.readouterr().out == ""

    def test_project_directory(self, capsys, tmp_path):
        """Test preview of a git project directory."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "README.md").write_text("# Test")

        env = {"AI_LAUNCHER_PROVIDER": "claude-code"}
        with patch("sys.argv", ["_preview_helper.py", f"{tmp_path}\t\tproject"]):
            with patch.dict(os.environ, env, clear=False):
                main()

        out = capsys.readouterr().out
        assert str(tmp_path) in out

    def test_directory_header(self, capsys, tmp_path):
        """Test preview of a non-git directory (folder header)."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("hi")

        with patch("sys.argv", ["_preview_helper.py", f"{sub}\t\tsub"]):
            main()

        out = capsys.readouterr().out
        assert "Contents:" in out
        assert "file.txt" in out

    def test_scan_root_provider_failure_is_reported(self, capsys, tmp_path):
        """A provider failure while previewing a scan root prints an inline error.

        The scan-root branch loads provider context lazily and swallows any
        failure so the preview pane still renders. Without this test the
        recovery path is never exercised.
        """
        scan_root = tmp_path / "projects"
        scan_root.mkdir()

        env = {
            "AI_LAUNCHER_PROVIDER": "claude-code",
            "AI_LAUNCHER_SCAN_PATHS": str(scan_root),
            "AI_LAUNCHER_MANUAL_PATHS": "",
            "AI_LAUNCHER_GLOBAL_FILES": "",
        }

        with patch("sys.argv", ["_preview_helper.py", f"{scan_root}\t\tprojects"]):
            with patch.dict(os.environ, env, clear=False):
                with patch(
                    "ai_launcher.providers.registry.ProviderRegistry.get",
                    side_effect=RuntimeError("provider exploded"),
                ):
                    main()

        out = capsys.readouterr().out
        assert "❗ Error loading provider context: provider exploded" in out
