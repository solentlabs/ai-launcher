"""Tests for the cleanup helpers: npm cache, old Claude versions and backups.

Author: Solent Labs™
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.utils.cleanup import (
    clean_npm_cache,
    prune_claude_backups,
    prune_claude_versions,
)


def test_the_config_has_no_system_cache_switch():
    """--clean-cache was removed: nothing sweeps ~/.cache any more."""
    assert not hasattr(CleanupConfig(), "clean_system_cache")


class TestCleanNpmCache:
    """--clean-npm runs the tool's own command, and only when it can."""

    def test_runs_npm_cache_clean_with_a_timeout(self):
        runner = MagicMock(return_value=MagicMock(returncode=0))

        assert clean_npm_cache(runner=runner, which=lambda name: "/usr/bin/npm") is True

        runner.assert_called_once_with(
            ["npm", "cache", "clean", "--force"],
            capture_output=True,
            check=False,
            timeout=10,
        )

    def test_npm_not_installed_is_skipped_quietly(self):
        runner = MagicMock()

        assert clean_npm_cache(runner=runner, which=lambda name: None) is False

        runner.assert_not_called()

    @pytest.mark.parametrize(
        "outcome",
        [
            MagicMock(returncode=1),
            subprocess.TimeoutExpired("npm", 10),
            OSError("gone"),
            subprocess.SubprocessError("odd"),
        ],
        ids=["nonzero-exit", "timeout", "os-error", "subprocess-error"],
    )
    def test_a_failure_is_swallowed_and_reported_false(self, outcome):
        def runner(*args, **kwargs):
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        assert (
            clean_npm_cache(runner=runner, which=lambda name: "/usr/bin/npm") is False
        )

    def test_verbose_says_what_it_does(self, capsys):
        clean_npm_cache(
            verbose=True,
            runner=lambda *a, **k: MagicMock(returncode=0),
            which=lambda name: "/usr/bin/npm",
        )

        assert "npm cache" in capsys.readouterr().out.lower()


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


class TestPruneFailuresAreContained:
    """Listing problems end the prune quietly; they never reach a launch."""

    def test_backups_unlistable(self, tmp_path, monkeypatch):
        def refuse(self, pattern):
            raise PermissionError("no")

        monkeypatch.setattr(Path, "glob", refuse)

        assert prune_claude_backups(tmp_path) == 0

    def test_versions_unlistable(self, tmp_path):
        versions = tmp_path / ".local" / "share" / "claude" / "versions"
        versions.mkdir(parents=True)

        def broken(name):
            raise OSError("which failed")

        assert prune_claude_versions(tmp_path, which=broken) == 0
