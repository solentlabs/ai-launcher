"""Tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ai_launcher.utils.git import clone_repository

# ============================================================================
# clone_repository() tests
# ============================================================================


def test_clone_repository_url_validation():
    """Test that invalid URLs are rejected."""
    with pytest.raises(ValueError, match="Invalid git URL"):
        clone_repository("invalid-url", Path("/tmp"), None)

    with pytest.raises(ValueError, match="Invalid git URL"):
        clone_repository("ftp://example.com/repo", Path("/tmp"), None)


@pytest.mark.parametrize(
    "url,expected_name",
    [
        ("https://github.com/user/repo.git", "repo"),
        ("git@github.com:user/repo.git", "repo"),
    ],
    ids=["https", "ssh"],
)
def test_clone_repository_url_accepted(tmp_path, url, expected_name):
    """Test that valid git URLs (HTTPS and SSH) are accepted."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        result = clone_repository(url, tmp_path, None)
        assert result == tmp_path / expected_name


def test_clone_repository_existing_directory(tmp_path):
    """Test that cloning to existing directory is rejected."""
    existing = tmp_path / "repo"
    existing.mkdir()

    with pytest.raises(ValueError, match="already exists"):
        clone_repository("https://github.com/user/repo.git", tmp_path, None)


def test_clone_repository_existing_directory_with_subfolder(tmp_path):
    """Test that cloning to existing directory in subfolder is rejected."""
    subfolder = tmp_path / "projects"
    subfolder.mkdir()
    existing = subfolder / "repo"
    existing.mkdir()

    with pytest.raises(ValueError, match="already exists"):
        clone_repository("https://github.com/user/repo.git", tmp_path, "projects")


@patch("subprocess.run")
def test_clone_repository_success(mock_run, tmp_path):
    """Test successful repository cloning."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    result = clone_repository(
        "https://github.com/user/my-repo.git",
        tmp_path,
        "projects",
    )

    expected_path = tmp_path / "projects" / "my-repo"
    assert result == expected_path

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert args[1] == "clone"
    assert args[2] == "https://github.com/user/my-repo.git"
    assert args[3] == str(expected_path)


@patch("subprocess.run")
def test_clone_repository_success_no_subfolder(mock_run, tmp_path):
    """Test successful repository cloning without subfolder."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    result = clone_repository(
        "https://github.com/user/my-repo.git",
        tmp_path,
        None,
    )

    expected_path = tmp_path / "my-repo"
    assert result == expected_path
    assert mock_run.call_args[0][0][3] == str(expected_path)


@patch("subprocess.run")
def test_clone_repository_git_failure(mock_run, tmp_path):
    """Test handling of git clone failure."""
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "git", stderr="Authentication failed"
    )

    with pytest.raises(RuntimeError, match="Git clone failed"):
        clone_repository("https://github.com/user/repo.git", tmp_path, None)


@pytest.mark.parametrize(
    "stderr,match_pattern",
    [
        ("fatal: repository not found", "fatal: repository not found"),
        ("", "Git clone failed"),
    ],
    ids=["with_stderr", "without_stderr"],
)
@patch("subprocess.run")
def test_clone_repository_git_failure_stderr(mock_run, tmp_path, stderr, match_pattern):
    """Test handling of git clone failure with and without stderr."""
    error = subprocess.CalledProcessError(128, "git")
    error.stderr = stderr
    mock_run.side_effect = error

    with pytest.raises(RuntimeError, match=match_pattern):
        clone_repository("https://github.com/user/repo.git", tmp_path, None)


@patch("subprocess.run")
def test_clone_repository_git_not_found(mock_run, tmp_path):
    """Test handling when git command is not found."""
    mock_run.side_effect = FileNotFoundError("git not found")

    with pytest.raises(RuntimeError, match="Git command not found"):
        clone_repository("https://github.com/user/repo.git", tmp_path, None)


@patch("subprocess.run")
def test_clone_repository_creates_parent_directory(mock_run, tmp_path):
    """Test that parent directories are created if they don't exist."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    result = clone_repository(
        "https://github.com/user/repo.git",
        tmp_path,
        "deep/nested/path",
    )

    expected_path = tmp_path / "deep" / "nested" / "path" / "repo"
    assert result == expected_path
    assert expected_path.parent.exists()


@pytest.mark.parametrize(
    "url,expected_name",
    [
        ("https://github.com/user/repo.git", "repo"),
        ("https://github.com/user/repo", "repo"),
        ("git@github.com:user/repo.git", "repo"),
        ("https://gitlab.com/user/my-project.git", "my-project"),
        ("https://github.com/user/repo/", "repo"),
        ("git@bitbucket.org:user/my-app.git", "my-app"),
    ],
    ids=[
        "https_dotgit",
        "https_bare",
        "ssh_dotgit",
        "gitlab",
        "trailing_slash",
        "bitbucket",
    ],
)
def test_clone_extracts_repo_name(url, expected_name):
    """Test that repository name is correctly extracted from URL."""
    extracted = url.rstrip("/").split("/")[-1].replace(".git", "")
    assert extracted == expected_name


@patch("subprocess.run")
def test_clone_repository_strips_dotgit(mock_run, tmp_path):
    """Test that .git suffix is properly removed from repo name."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    result = clone_repository("https://github.com/user/repo.git", tmp_path, None)
    assert result == tmp_path / "repo"
    assert ".git" not in str(result)


@patch("subprocess.run")
def test_clone_repository_handles_trailing_slash(mock_run, tmp_path):
    """Test that URLs with trailing slashes are handled correctly."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    result = clone_repository("https://github.com/user/repo.git/", tmp_path, None)
    assert result == tmp_path / "repo"
