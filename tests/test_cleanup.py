"""Tests for environment cleanup utilities.

Author: Solent Labs™
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.utils.cleanup import cleanup_environment


@pytest.fixture
def cleanup_config():
    """Create cleanup config with all options enabled."""
    return CleanupConfig(
        enabled=True,
        clean_provider_files=True,
        clean_npm_cache=True,
        debug_logs_max_age_days=7,
    )


class TestCleanupGuards:
    """Tests for cleanup config guard conditions."""

    def test_no_config_does_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            backup = tmp_path / ".claude.json.backup.123"
            backup.write_text("data")
            cleanup_environment(verbose=False, cleanup_config=None)
            assert backup.exists()

    def test_disabled_config_does_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            config = CleanupConfig(enabled=False)
            backup = tmp_path / ".claude.json.backup.123"
            backup.write_text("data")
            cleanup_environment(verbose=False, cleanup_config=config)
            assert backup.exists()


class TestCacheFolderIsNeverSwept:
    """--clean-cache was removed: nothing under ~/.cache is deleted by cleanup."""

    def test_cleanup_leaves_the_cache_folder_alone(
        self, tmp_path, monkeypatch, cleanup_config
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        cleanup_config.clean_npm_cache = False
        with patch("pathlib.Path.home", return_value=tmp_path):
            cache_dir = tmp_path / ".cache"
            (cache_dir / "subdir").mkdir(parents=True)
            (cache_dir / "file.txt").write_text("cache")

            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert (cache_dir / "subdir").exists()
            assert (cache_dir / "file.txt").exists()

    def test_the_config_has_no_system_cache_switch(self):
        assert not hasattr(CleanupConfig(), "clean_system_cache")


class TestNpmCleanup:
    """Tests for npm cache cleanup."""

    def test_npm_cache_clean_called(self, tmp_path, monkeypatch, cleanup_config):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value="/usr/bin/npm"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    cleanup_environment(verbose=False, cleanup_config=cleanup_config)
                    # npm cache clean should be called
                    mock_run.assert_any_call(
                        ["npm", "cache", "clean", "--force"],
                        capture_output=True,
                        check=False,
                        timeout=10,
                    )

    def test_npm_not_installed_skips(self, tmp_path, monkeypatch, cleanup_config):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            # npm not found, claude not found either
            with patch("shutil.which", return_value=None):
                # Should not raise
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)


class TestProviderFileCleanup:
    """Tests for provider-specific file cleanup."""

    def test_removes_backup_files(self, tmp_path, monkeypatch, cleanup_config):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            b1 = tmp_path / ".claude.json.backup.111"
            b2 = tmp_path / ".claude.json.backup.222"
            b1.write_text("b1")
            b2.write_text("b2")

            # Disable npm to avoid mock complexity, no claude binary
            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert not b1.exists()
            assert not b2.exists()

    def test_debug_log_age_filtering(self, tmp_path, monkeypatch, cleanup_config):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            debug_dir = tmp_path / ".claude" / "debug"
            debug_dir.mkdir(parents=True)

            old_log = debug_dir / "old.txt"
            old_log.write_text("old")
            old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
            os.utime(old_log, (old_time, old_time))

            recent_log = debug_dir / "recent.txt"
            recent_log.write_text("recent")

            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert not old_log.exists()
            assert recent_log.exists()

    def test_version_cleanup(self, tmp_path, monkeypatch, cleanup_config):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            versions_dir = tmp_path / ".local" / "share" / "claude" / "versions"
            versions_dir.mkdir(parents=True)

            (versions_dir / "2.1.37").write_text("current")
            (versions_dir / "2.1.36").write_text("old")
            (versions_dir / "2.1.35").write_text("older")

            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value="/usr/bin/claude"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="2.1.37 (Claude Code)"
                    )
                    cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert (versions_dir / "2.1.37").exists()
            assert not (versions_dir / "2.1.36").exists()
            assert not (versions_dir / "2.1.35").exists()


class TestVerboseOutput:
    """Tests for verbose cleanup output."""

    def test_verbose_prints_messages(
        self, tmp_path, monkeypatch, cleanup_config, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=True, cleanup_config=cleanup_config)

        captured = capsys.readouterr()
        assert "Pre-launch cleanup:" in captured.out
        assert "Cleanup complete" in captured.out

    def test_verbose_no_longer_mentions_the_cache_folder(
        self, tmp_path, monkeypatch, cleanup_config, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=True, cleanup_config=cleanup_config)

        captured = capsys.readouterr()
        assert "~/.cache" not in captured.out
