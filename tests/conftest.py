"""Pytest configuration and fixtures."""

import pytest


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
