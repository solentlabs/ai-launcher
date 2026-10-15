"""Pytest configuration and fixtures."""

from pathlib import Path
from typing import Optional

import pytest

from ai_launcher.core.models import CleanupConfig


def _redirect_platformdirs(
    monkeypatch, base: Path, cache: Optional[Path] = None
) -> None:
    """Point platformdirs' cache, config and state folders inside `base`.

    The XDG variables only steer platformdirs on Linux; macOS and Windows read
    the system's folders, which would reach the real home.
    """
    import platformdirs

    for name, folder in (
        ("user_cache_path", cache or base / "cache"),
        ("user_config_path", base / "config"),
        ("user_state_path", base / "state"),
    ):

        def patched(appname=None, *args, _folder=folder, **kwargs):
            return _folder / appname if appname else _folder

        monkeypatch.setattr(platformdirs, name, patched)


@pytest.fixture(autouse=True)
def _isolate_xdg_dirs(tmp_path_factory, monkeypatch):
    """Keep every test's cache, config and state folders out of the real home.

    The launcher now writes a scratch folder and a size cache at launch; a test
    that reaches launch_ai must not touch the developer's own ~/.cache.
    """
    base = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CACHE_HOME", str(base / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(base / "state"))
    _redirect_platformdirs(monkeypatch, base)


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Override both HOME env var and Path.home() for cross-platform tests.

    On Windows, Path.home() uses USERPROFILE, not HOME. This fixture
    ensures consistent behavior across all platforms.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return tmp_path


@pytest.fixture
def make_symlink():
    """Create a symlink, or skip the test where the account may not.

    Windows needs administrator rights or Developer Mode to create one.
    """

    def _make(link: Path, target: Path, target_is_directory: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=target_is_directory)
        except OSError:
            pytest.skip("symlinks not permitted on this platform")

    return _make


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory structure."""
    # Create some git repos
    (tmp_path / "project1" / ".git").mkdir(parents=True)
    (tmp_path / "project2" / ".git").mkdir(parents=True)
    (tmp_path / "work" / "project3" / ".git").mkdir(parents=True)

    # Create some non-git directories
    (tmp_path / "docs").mkdir()
    (tmp_path / "notes").mkdir()

    # Create directories that should be pruned
    (tmp_path / "node_modules" / "package" / ".git").mkdir(parents=True)
    (tmp_path / ".cache" / "stuff").mkdir(parents=True)

    return tmp_path


@pytest.fixture
def cleanup_config():
    """Standard cleanup config for provider tests."""
    return CleanupConfig(
        enabled=True,
        clean_provider_files=True,
        clean_npm_cache=False,
    )


@pytest.fixture
def cache_home(mock_home, monkeypatch):
    """A fake home for the cache and scratch tests.

    Points HOME, the XDG folders and LOCALAPPDATA inside tmp_path, so nothing
    reaches the developer's real ~/.cache, and fails to start if a path
    leaks outside it.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(mock_home / ".cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(mock_home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(mock_home / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(mock_home / ".local" / "share"))
    monkeypatch.setenv("LOCALAPPDATA", str(mock_home / "AppData" / "Local"))
    _redirect_platformdirs(
        monkeypatch, mock_home / ".platformdirs", cache=mock_home / ".cache"
    )
    # The cache logic is the same everywhere; tests that need another platform
    # pass it explicitly. Without this a Windows run would look in %LOCALAPPDATA%.
    from ai_launcher.core import cache_registry

    monkeypatch.setattr(cache_registry, "current_platform", lambda: "linux")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AI_SCRATCH_DIR", raising=False)
    (mock_home / ".cache").mkdir()
    return mock_home
