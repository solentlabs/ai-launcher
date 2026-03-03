"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


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
