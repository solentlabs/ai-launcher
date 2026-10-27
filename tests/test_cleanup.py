"""Tests for environment cleanup utilities.

Author: Solent Labs™
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.utils.cleanup import (
    cleanup_environment,
    prune_claude_backups,
    prune_claude_versions,
)


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

            os.utime(b1, (100, 100))
            os.utime(b2, (200, 200))

            # Disable npm to avoid mock complexity, no claude binary
            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=None):
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert not b1.exists()
            assert b2.exists()  # the newest is kept

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

    def test_version_cleanup_keeps_the_native_install_in_use(
        self, tmp_path, monkeypatch, cleanup_config, make_symlink
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("pathlib.Path.home", return_value=tmp_path):
            versions_dir = tmp_path / ".local" / "share" / "claude" / "versions"
            versions_dir.mkdir(parents=True)
            for name in ("2.1.37", "2.1.36", "2.1.35"):
                (versions_dir / name).write_text(name)
            link = tmp_path / ".local" / "bin" / "claude"
            link.parent.mkdir(parents=True)
            make_symlink(link, versions_dir / "2.1.36")

            cleanup_config.clean_npm_cache = False
            with patch("shutil.which", return_value=str(link)):
                cleanup_environment(verbose=False, cleanup_config=cleanup_config)

            assert (versions_dir / "2.1.36").exists()  # what the link points to
            assert not (versions_dir / "2.1.37").exists()
            assert not (versions_dir / "2.1.35").exists()


class TestPruneClaudeVersions:
    """The version prune must never remove the binary the user actually runs."""

    @pytest.fixture
    def versions(self, tmp_path):
        folder = tmp_path / ".local" / "share" / "claude" / "versions"
        folder.mkdir(parents=True)
        for name in ("2.1.37", "2.1.36", "other.txt"):
            (folder / name).write_text(name)
        return folder

    def test_claude_from_somewhere_else_removes_nothing(self, tmp_path, versions):
        """An npm install first on PATH said nothing about which native binary is live."""
        npm = tmp_path / "npm-global" / "bin" / "claude"
        npm.parent.mkdir(parents=True)
        npm.write_text("#!/bin/sh")

        removed = prune_claude_versions(tmp_path, which=lambda name: str(npm))

        assert removed == 0
        assert sorted(f.name for f in versions.iterdir()) == [
            "2.1.36",
            "2.1.37",
            "other.txt",
        ]

    @pytest.mark.parametrize(
        "which",
        [lambda name: None, lambda name: "/no/such/claude"],
        ids=["not-installed", "dangling-path"],
    )
    def test_no_claude_removes_nothing(self, tmp_path, versions, which):
        assert prune_claude_versions(tmp_path, which=which) == 0
        assert (versions / "2.1.37").exists() and (versions / "2.1.36").exists()

    def test_no_versions_folder_is_fine(self, tmp_path):
        assert prune_claude_versions(tmp_path, which=lambda name: "x") == 0

    def test_native_claude_keeps_its_own_file_and_non_versions(
        self, tmp_path, versions, make_symlink
    ):
        link = tmp_path / ".local" / "bin" / "claude"
        link.parent.mkdir(parents=True)
        make_symlink(link, versions / "2.1.37")

        removed = prune_claude_versions(tmp_path, which=lambda name: str(link))

        assert removed == 1
        assert sorted(f.name for f in versions.iterdir()) == ["2.1.37", "other.txt"]

    def test_a_file_that_cannot_be_removed_does_not_stop_the_rest(
        self, tmp_path, versions, make_symlink, monkeypatch
    ):
        (versions / "2.1.35").write_text("x")
        link = tmp_path / ".local" / "bin" / "claude"
        link.parent.mkdir(parents=True)
        make_symlink(link, versions / "2.1.37")
        real_unlink = Path.unlink

        def busy(self, *args, **kwargs):
            if self.name == "2.1.36":
                raise PermissionError("in use")
            real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", busy)

        removed = prune_claude_versions(tmp_path, which=lambda name: str(link))

        assert removed == 1
        assert not (versions / "2.1.35").exists()
        assert (versions / "2.1.36").exists()


class TestPruneClaudeBackups:
    """The newest backup can be the only recovery copy of ~/.claude.json."""

    def test_keeps_the_newest_and_removes_the_rest(self, tmp_path):
        names = {"1": 100, "2": 300, "3": 200}
        for name, when in names.items():
            f = tmp_path / f".claude.json.backup.{name}"
            f.write_text(name)
            os.utime(f, (when, when))
        (tmp_path / ".claude.json").write_text("live")

        removed = prune_claude_backups(tmp_path)

        assert removed == 2
        assert sorted(f.name for f in tmp_path.iterdir()) == [
            ".claude.json",
            ".claude.json.backup.2",
        ]

    def test_a_single_backup_is_left_alone(self, tmp_path):
        only = tmp_path / ".claude.json.backup.1"
        only.write_text("x")

        assert prune_claude_backups(tmp_path) == 0
        assert only.exists()

    def test_a_file_that_cannot_be_removed_does_not_stop_the_rest(
        self, tmp_path, monkeypatch
    ):
        for name, when in {"1": 100, "2": 200, "3": 300}.items():
            f = tmp_path / f".claude.json.backup.{name}"
            f.write_text(name)
            os.utime(f, (when, when))
        real_unlink = Path.unlink

        def busy(self, *args, **kwargs):
            if self.name.endswith(".1"):
                raise PermissionError("in use")
            real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", busy)

        assert prune_claude_backups(tmp_path) == 1
        assert not (tmp_path / ".claude.json.backup.2").exists()


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
