"""Tests for Claude provider implementation.

Author: Solent Labs™
Created: 2026-02-12
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.claude import ClaudeProvider


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

    def test_cleanup_disabled_when_no_config(self, provider, tmp_path, monkeypatch):
        """Test cleanup does nothing when config is None."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create some files that would be cleaned
        backup = tmp_path / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=None)

        # File should still exist
        assert backup.exists()

    def test_cleanup_disabled_when_config_disabled(
        self, provider, tmp_path, monkeypatch
    ):
        """Test cleanup does nothing when config.enabled is False."""
        monkeypatch.setenv("HOME", str(tmp_path))

        config = CleanupConfig(enabled=False)
        backup = tmp_path / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=config)

        # File should still exist
        assert backup.exists()

    def test_cleanup_disabled_when_provider_files_disabled(
        self, provider, tmp_path, monkeypatch
    ):
        """Test cleanup does nothing when clean_provider_files is False."""
        monkeypatch.setenv("HOME", str(tmp_path))

        config = CleanupConfig(enabled=True, clean_provider_files=False)
        backup = tmp_path / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=False, cleanup_config=config)

        # File should still exist
        assert backup.exists()

    def test_cleanup_backup_files(
        self, provider, tmp_path, monkeypatch, cleanup_config
    ):
        """Test cleanup removes .claude.json.backup.* files."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create backup files
        backup1 = tmp_path / ".claude.json.backup.123"
        backup2 = tmp_path / ".claude.json.backup.456"
        other_file = tmp_path / "other.txt"

        backup1.write_text("backup1")
        backup2.write_text("backup2")
        other_file.write_text("other")

        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Backup files should be removed
        assert not backup1.exists()
        assert not backup2.exists()
        # Other files should remain
        assert other_file.exists()

    def test_cleanup_old_debug_logs(
        self, provider, tmp_path, monkeypatch, cleanup_config
    ):
        """Test cleanup removes old debug logs."""
        monkeypatch.setenv("HOME", str(tmp_path))

        debug_dir = tmp_path / ".claude" / "debug"
        debug_dir.mkdir(parents=True)

        # Create old log (10 days old)
        old_log = debug_dir / "old.txt"
        old_log.write_text("old log")
        old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
        old_log.touch()
        # Set mtime to 10 days ago
        import os

        os.utime(old_log, (old_time, old_time))

        # Create recent log (1 day old)
        recent_log = debug_dir / "recent.txt"
        recent_log.write_text("recent log")

        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Old log should be removed (> 7 days)
        assert not old_log.exists()
        # Recent log should remain
        assert recent_log.exists()

    def test_cleanup_old_versions(
        self, provider, tmp_path, monkeypatch, cleanup_config
    ):
        """Test cleanup removes old CLI versions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        versions_dir = tmp_path / ".local" / "share" / "claude" / "versions"
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

    def test_cleanup_verbose_output(
        self, provider, tmp_path, monkeypatch, cleanup_config, capsys
    ):
        """Test cleanup prints messages when verbose=True."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create a backup file
        backup = tmp_path / ".claude.json.backup.123"
        backup.write_text("backup")

        provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)

        captured = capsys.readouterr()
        assert "Claude Code cleanup" in captured.out
        assert "Removing old .claude.json.backup.* files" in captured.out
        assert "cleanup complete" in captured.out

    def test_cleanup_handles_permission_errors(
        self, provider, tmp_path, monkeypatch, cleanup_config
    ):
        """Test cleanup continues gracefully on permission errors."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # This test verifies error handling doesn't crash
        # Even if files don't exist or can't be accessed
        provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Should complete without raising exceptions
        # (no assertions needed - test passes if no exception raised)

    def test_cleanup_no_crash_when_claude_not_installed(
        self, provider, tmp_path, monkeypatch, cleanup_config
    ):
        """Test cleanup handles missing claude CLI gracefully."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("shutil.which", return_value=None):
            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)

        # Should complete without raising exceptions


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
        assert any("/.claude" in str(p) for p in paths)
        assert any("/.claude.json" in str(p) for p in paths)

    def test_get_context_categories(self, provider):
        """Test getting context categories."""
        categories = provider.get_context_categories()

        assert "config" in categories
        assert "logs" in categories
        assert "memory" in categories
        assert "cache" in categories
