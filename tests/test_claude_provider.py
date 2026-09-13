"""Tests for Claude provider implementation.

Author: Solent Labs™
Created: 2026-02-12
Updated: 2026-03-03 (Cross-platform compatibility: mock_home fixture, os.sep)
"""

import json
import os
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.claude import ClaudeProvider, _shell_quote


class TestClaudeCleanup:
    """Tests for Claude provider cleanup functionality."""

    @pytest.fixture
    def provider(self):
        """Create Claude provider instance."""
        return ClaudeProvider()

    @pytest.fixture
    def cleanup_config(self):
        """Create cleanup config with provider files enabled."""
        return CleanupConfig(
            enabled=True,
            clean_provider_files=True,
            clean_system_cache=False,
            clean_npm_cache=False,
            debug_logs_max_age_days=7,
        )

    def test_cleanup_disabled_when_no_config(self, provider, mock_home):
        """Test cleanup does nothing when config is None."""
        # Create some files that would be cleaned
        backup = mock_home / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=None)

        # File should still exist
        assert backup.exists()

    def test_cleanup_disabled_when_config_disabled(self, provider, mock_home):
        """Test cleanup does nothing when config.enabled is False."""
        config = CleanupConfig(enabled=False)
        backup = mock_home / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=config)

        # File should still exist
        assert backup.exists()

    def test_cleanup_disabled_when_provider_files_disabled(self, provider, mock_home):
        """Test cleanup does nothing when clean_provider_files is False."""
        config = CleanupConfig(enabled=True, clean_provider_files=False)
        backup = mock_home / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=config)

        # File should still exist
        assert backup.exists()

    def test_cleanup_backup_files(self, provider, mock_home, cleanup_config):
        """Test cleanup removes .claude.json.backup.* files."""
        # Create backup files
        backup1 = mock_home / ".claude.json.backup.123"
        backup2 = mock_home / ".claude.json.backup.456"
        other_file = mock_home / "other.txt"

        backup1.write_text("backup1")
        backup2.write_text("backup2")
        other_file.write_text("other")

        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Backup files should be removed
        assert not backup1.exists()
        assert not backup2.exists()
        # Other files should remain
        assert other_file.exists()

    def test_cleanup_old_debug_logs(self, provider, mock_home, cleanup_config):
        """Test cleanup removes old debug logs."""
        debug_dir = mock_home / ".claude" / "debug"
        debug_dir.mkdir(parents=True)

        # Create old log (10 days old)
        old_log = debug_dir / "old.txt"
        old_log.write_text("old log")
        old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
        old_log.touch()
        # Set mtime to 10 days ago
        os.utime(old_log, (old_time, old_time))

        # Create recent log (1 day old)
        recent_log = debug_dir / "recent.txt"
        recent_log.write_text("recent log")

        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Old log should be removed (> 7 days)
        assert not old_log.exists()
        # Recent log should remain
        assert recent_log.exists()

    def test_cleanup_old_versions(self, provider, mock_home, cleanup_config):
        """Test cleanup removes old CLI versions."""
        versions_dir = mock_home / ".local" / "share" / "claude" / "versions"
        versions_dir.mkdir(parents=True)

        # Create version files
        current = versions_dir / "2.1.37"
        old1 = versions_dir / "2.1.36"
        old2 = versions_dir / "2.1.35"
        other = versions_dir / "other.txt"

        current.write_text("current")
        old1.write_text("old1")
        old2.write_text("old2")
        other.write_text("other")

        # Mock claude --version to return current version
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="2.1.37 (Claude Code)"
                )

                provider.cleanup_environment(
                    verbose=False, cleanup_config=cleanup_config
                )

        # Old versions should be removed
        assert not old1.exists()
        assert not old2.exists()
        # Current version and non-version files should remain
        assert current.exists()
        assert other.exists()

    def test_cleanup_verbose_output(self, provider, mock_home, cleanup_config, capsys):
        """Test cleanup prints messages when verbose=True."""
        # Create a backup file
        backup = mock_home / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)

        captured = capsys.readouterr()
        assert "Claude Code cleanup" in captured.out
        assert "Removing old .claude.json.backup.* files" in captured.out
        assert "cleanup complete" in captured.out

    def test_cleanup_handles_permission_errors(
        self, provider, mock_home, cleanup_config
    ):
        """Test cleanup continues gracefully on permission errors."""
        # This test verifies error handling doesn't crash
        # Even if files don't exist or can't be accessed
        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Should complete without raising exceptions
        # (no assertions needed - test passes if no exception raised)

    def test_cleanup_no_crash_when_claude_not_installed(
        self, provider, mock_home, cleanup_config
    ):
        """Test cleanup handles missing claude CLI gracefully."""
        with patch("shutil.which", return_value=None):
            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Should complete without raising exceptions


class TestClaudeLaunchScope:
    """launch() tells Claude which project it is in, and guards the others."""

    @pytest.fixture
    def provider(self):
        return ClaudeProvider()

    @pytest.fixture
    def dirs(self, tmp_path):
        # Spaces in every path: the hook command must survive shell quoting.
        root = tmp_path / "my projects"
        project = root / "cable modem"
        other = root / "angel captain"
        for repo in (project, other):
            repo.mkdir(parents=True)
        return root, project, other

    def _launch_cmd(self, provider, project, **kwargs):
        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(project, **kwargs)
        return mock_run.call_args[0][0]

    @staticmethod
    def _option(cmd, flag):
        return cmd[cmd.index(flag) + 1]

    def test_scope_statement_names_project(self, provider, dirs):
        _, project, _ = dirs
        cmd = self._launch_cmd(provider, project)
        assert cmd[0] == "claude"
        statement = self._option(cmd, "--append-system-prompt")
        assert "cable modem" in statement
        assert "different project" in statement

    def test_no_scan_roots_means_no_guard(self, provider, dirs):
        _, project, _ = dirs
        assert "--settings" not in self._launch_cmd(provider, project)

    def test_guard_hook_is_passed_as_settings(self, provider, dirs):
        root, project, _ = dirs
        cmd = self._launch_cmd(provider, project, scope_roots=[root])
        settings = json.loads(self._option(cmd, "--settings"))
        (entry,) = settings["hooks"]["PreToolUse"]
        assert set(entry["matcher"].split("|")) == {
            "Write",
            "Edit",
            "MultiEdit",
            "NotebookEdit",
            "Bash",
        }
        (hook,) = entry["hooks"]
        assert hook["type"] == "command"
        assert "ai_launcher.core.scope_guard" in hook["command"]

    @pytest.mark.parametrize(
        ("os_name", "expected"),
        [("posix", "'my projects'"), ("nt", '"my projects"')],
        ids=["posix", "windows"],
    )
    def test_shell_quote(self, monkeypatch, os_name, expected):
        monkeypatch.setattr("ai_launcher.providers.claude.os.name", os_name)
        assert _shell_quote("my projects") == expected

    @pytest.mark.skipif(
        sys.platform == "win32", reason="runs the hook through a POSIX shell"
    )
    def test_guard_hook_command_runs(self, provider, dirs):
        """The exact command Claude will run asks before a sibling write."""
        root, project, other = dirs
        cmd = self._launch_cmd(provider, project, scope_roots=[root])
        settings = json.loads(self._option(cmd, "--settings"))
        command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(other / "README.md")},
            "cwd": str(project),
        }
        result = subprocess.run(
            ["sh", "-c", command],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            check=True,
        )
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "ask"


class TestClaudeProviderBasics:
    """Tests for basic Claude provider functionality."""

    @pytest.fixture
    def provider(self):
        return ClaudeProvider()

    def test_metadata(self, provider):
        """Test provider metadata."""
        metadata = provider.metadata

        assert metadata.name == "claude-code"
        assert metadata.display_name == "Claude Code"
        assert metadata.command == "claude"
        assert "CLAUDE.md" in metadata.config_files
        assert metadata.guards_other_projects is True

    def test_is_installed(self, provider):
        """Test is_installed check."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/claude"
            assert provider.is_installed() is True

            mock_which.return_value = None
            assert provider.is_installed() is False

    def test_get_global_context_paths(self, provider):
        """Test getting global context paths."""
        paths = provider.get_global_context_paths()

        assert len(paths) == 2
        assert any(".claude" in str(p) for p in paths)
        assert any(".claude.json" in str(p) for p in paths)

    def test_get_context_categories(self, provider):
        """Test getting context categories."""
        categories = provider.get_context_categories()

        assert "config" in categories
        assert "logs" in categories
        assert "memory" in categories
        assert "cache" in categories
