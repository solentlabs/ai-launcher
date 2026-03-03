"""Tests for session detection utilities."""

import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from ai_launcher.utils.session import (
    count_sessions,
    encode_project_path,
    format_time_ago,
    get_claude_session_dir,
    get_last_session_time,
    get_memory_files,
    get_session_size,
    get_session_summary,
)

# ============================================================================
# encode_project_path() tests
# ============================================================================


def test_encode_project_path_absolute(tmp_path):
    """Test encoding an absolute path."""
    project = tmp_path / "my-project"
    project.mkdir()
    result = encode_project_path(project)
    # Should replace / with - throughout
    assert "/" not in result
    assert "-" in result
    assert "my-project" in result


def test_encode_project_path_preserves_hyphens(tmp_path):
    """Test that existing hyphens in path are preserved."""
    project = tmp_path / "my-cool-project"
    project.mkdir()
    result = encode_project_path(project)
    assert "my-cool-project" in result


def test_encode_project_path_uses_os_sep(tmp_path):
    """Test that path separator replacement is OS-aware."""
    project = tmp_path / "project"
    project.mkdir()
    result = encode_project_path(project)
    # Result should have hyphens where separators were
    assert result.startswith("-")


# ============================================================================
# get_claude_session_dir() tests
# ============================================================================


def test_get_claude_session_dir_exists(tmp_path):
    """Test finding existing session directory."""
    project = tmp_path / "project"
    project.mkdir()

    encoded = encode_project_path(project)
    session_dir = tmp_path / ".claude" / "projects" / encoded
    session_dir.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_claude_session_dir(project)

    assert result == session_dir


def test_get_claude_session_dir_not_exists(tmp_path):
    """Test when session directory doesn't exist."""
    project = tmp_path / "project"
    project.mkdir()

    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_claude_session_dir(project)

    assert result is None


# ============================================================================
# count_sessions() tests
# ============================================================================


def test_count_sessions_with_files(tmp_path):
    """Test counting session files."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "abc123.jsonl").write_text("{}")
    (session_dir / "def456.jsonl").write_text("{}")
    (session_dir / "ghi789.jsonl").write_text("{}")

    assert count_sessions(session_dir) == 3


def test_count_sessions_empty_dir(tmp_path):
    """Test counting sessions in empty directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    assert count_sessions(session_dir) == 0


def test_count_sessions_nonexistent_dir(tmp_path):
    """Test counting sessions when directory doesn't exist."""
    assert count_sessions(tmp_path / "nonexistent") == 0


def test_count_sessions_ignores_non_jsonl(tmp_path):
    """Test that non-.jsonl files are not counted."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "abc123.jsonl").write_text("{}")
    (session_dir / "readme.md").write_text("notes")
    (session_dir / "config.json").write_text("{}")

    assert count_sessions(session_dir) == 1


def test_count_sessions_ignores_subdirectories(tmp_path):
    """Test that .jsonl files in subdirectories are not counted."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "abc123.jsonl").write_text("{}")
    sub = session_dir / "memory"
    sub.mkdir()
    (sub / "nested.jsonl").write_text("{}")

    assert count_sessions(session_dir) == 1


def test_count_sessions_permission_error(tmp_path):
    """Test handling permission errors."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    with patch.object(Path, "glob", side_effect=PermissionError):
        assert count_sessions(session_dir) == 0


# ============================================================================
# get_session_size() tests
# ============================================================================


def test_get_session_size_with_files(tmp_path):
    """Test calculating total session size."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "a.jsonl").write_text("x" * 100)
    (session_dir / "b.jsonl").write_text("y" * 200)

    result = get_session_size(session_dir)
    assert result == 300


def test_get_session_size_empty_dir(tmp_path):
    """Test session size for empty directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    assert get_session_size(session_dir) == 0


def test_get_session_size_nonexistent_dir(tmp_path):
    """Test session size when directory doesn't exist."""
    assert get_session_size(tmp_path / "nonexistent") == 0


def test_get_session_size_permission_error(tmp_path):
    """Test handling permission errors."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    with patch.object(Path, "glob", side_effect=PermissionError):
        assert get_session_size(session_dir) == 0


# ============================================================================
# get_last_session_time() tests
# ============================================================================


def test_get_last_session_time_with_files(tmp_path):
    """Test getting last session modification time."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "old.jsonl").write_text("{}")
    (session_dir / "new.jsonl").write_text("{}")

    result = get_last_session_time(session_dir)
    assert result is not None
    assert isinstance(result, datetime)


def test_get_last_session_time_empty_dir(tmp_path):
    """Test last session time for empty directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    assert get_last_session_time(session_dir) is None


def test_get_last_session_time_nonexistent_dir(tmp_path):
    """Test last session time when directory doesn't exist."""
    assert get_last_session_time(tmp_path / "nonexistent") is None


def test_get_last_session_time_permission_error(tmp_path):
    """Test handling permission errors."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    with patch.object(Path, "glob", side_effect=PermissionError):
        assert get_last_session_time(session_dir) is None


# ============================================================================
# get_memory_files() tests
# ============================================================================


def test_get_memory_files_with_files(tmp_path):
    """Test listing memory files."""
    session_dir = tmp_path / "sessions"
    memory_dir = session_dir / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory")
    (memory_dir / "debugging.md").write_text("# Debug notes")

    result = get_memory_files(session_dir)
    assert len(result) == 2
    names = [f.name for f in result]
    assert "MEMORY.md" in names
    assert "debugging.md" in names


def test_get_memory_files_sorted(tmp_path):
    """Test that memory files are returned sorted."""
    session_dir = tmp_path / "sessions"
    memory_dir = session_dir / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "z-notes.md").write_text("")
    (memory_dir / "a-patterns.md").write_text("")
    (memory_dir / "m-debug.md").write_text("")

    result = get_memory_files(session_dir)
    names = [f.name for f in result]
    assert names == sorted(names)


def test_get_memory_files_no_memory_dir(tmp_path):
    """Test when memory directory doesn't exist."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    assert get_memory_files(session_dir) == []


def test_get_memory_files_empty_memory_dir(tmp_path):
    """Test when memory directory is empty."""
    session_dir = tmp_path / "sessions"
    memory_dir = session_dir / "memory"
    memory_dir.mkdir(parents=True)

    assert get_memory_files(session_dir) == []


def test_get_memory_files_ignores_non_md(tmp_path):
    """Test that non-.md files are ignored."""
    session_dir = tmp_path / "sessions"
    memory_dir = session_dir / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory")
    (memory_dir / "data.json").write_text("{}")

    result = get_memory_files(session_dir)
    assert len(result) == 1


def test_get_memory_files_permission_error(tmp_path):
    """Test handling permission errors."""
    session_dir = tmp_path / "sessions"
    memory_dir = session_dir / "memory"
    memory_dir.mkdir(parents=True)

    with patch.object(Path, "glob", side_effect=PermissionError):
        assert get_memory_files(session_dir) == []


# ============================================================================
# format_time_ago() deprecated wrapper tests
# ============================================================================


def test_format_time_ago_deprecated():
    """Test that the deprecated wrapper emits a warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = format_time_ago(datetime.now() - timedelta(minutes=5))

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert result == "5 minutes ago"


# ============================================================================
# get_session_summary() tests
# ============================================================================


def test_get_session_summary_with_sessions(tmp_path):
    """Test complete session summary."""
    project = tmp_path / "project"
    project.mkdir()

    encoded = encode_project_path(project)
    session_dir = tmp_path / ".claude" / "projects" / encoded
    session_dir.mkdir(parents=True)
    (session_dir / "session1.jsonl").write_text("x" * 500)
    (session_dir / "session2.jsonl").write_text("y" * 300)

    memory_dir = session_dir / "memory"
    memory_dir.mkdir()
    (memory_dir / "MEMORY.md").write_text("# Memory")

    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_session_summary(project)

    assert result is not None
    assert result["session_count"] == 2
    assert result["session_size"] == 800
    assert result["session_size_human"] == "800 B"
    assert result["memory_count"] == 1
    assert "MEMORY.md" in result["memory_files"]
    assert result["last_session"] is not None
    assert result["session_dir"] == session_dir


def test_get_session_summary_no_session_dir(tmp_path):
    """Test summary when no session directory exists."""
    project = tmp_path / "project"
    project.mkdir()

    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_session_summary(project)

    assert result is None


def test_get_session_summary_empty_session_dir(tmp_path):
    """Test summary when session directory is empty (no .jsonl files)."""
    project = tmp_path / "project"
    project.mkdir()

    encoded = encode_project_path(project)
    session_dir = tmp_path / ".claude" / "projects" / encoded
    session_dir.mkdir(parents=True)

    with patch("pathlib.Path.home", return_value=tmp_path):
        result = get_session_summary(project)

    assert result is None
