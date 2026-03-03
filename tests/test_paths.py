"""Tests for path utilities."""

import os
from pathlib import Path

from ai_launcher.utils.paths import (
    expand_path,
    get_relative_path,
    validate_directory,
)


def test_expand_path_with_tilde():
    """Test expanding path with ~ to home directory."""
    result = expand_path("~/projects")
    assert result == Path.home() / "projects"


def test_expand_path_with_env_var(tmp_path):
    """Test expanding path with environment variable."""
    # Use real tmp_path for cross-platform compatibility
    os.environ["TEST_PATH"] = str(tmp_path)
    result = expand_path("$TEST_PATH/subdir")
    assert result == (tmp_path / "subdir").resolve()


def test_expand_path_with_both():
    """Test expanding path with both ~ and env vars."""
    os.environ["TEST_SUBDIR"] = "projects"
    result = expand_path("~/$TEST_SUBDIR/foo")
    expected = Path.home() / "projects" / "foo"
    assert result == expected


def test_expand_path_absolute(tmp_path):
    """Test expanding absolute path returns resolved absolute path."""
    result = expand_path(str(tmp_path))
    assert result == tmp_path.resolve()


def test_validate_directory_exists(tmp_path):
    """Test validating existing directory."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    assert validate_directory(test_dir) is True


def test_validate_directory_not_exists(tmp_path):
    """Test validating non-existent directory."""
    test_dir = tmp_path / "nonexistent"

    assert validate_directory(test_dir) is False


def test_validate_directory_is_file(tmp_path):
    """Test validating path that is a file, not directory."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test")

    assert validate_directory(test_file) is False


def test_get_relative_path_success(tmp_path):
    """Test getting relative path when path is under base."""
    base = tmp_path
    sub_path = tmp_path / "projects" / "foo"
    sub_path.mkdir(parents=True)

    result = get_relative_path(sub_path, base)
    assert result == Path("projects/foo")


def test_get_relative_path_not_relative(tmp_path):
    """Test getting relative path when path is not under base."""
    base = tmp_path / "base"
    other_path = tmp_path / "other" / "path"

    # Path is not relative to base, should return original
    result = get_relative_path(other_path, base)
    assert result == other_path


def test_get_relative_path_same_path(tmp_path):
    """Test getting relative path when path equals base."""
    result = get_relative_path(tmp_path, tmp_path)
    assert result == Path()
