"""Session detection utilities for AI providers.

Detects and analyzes local session data from AI coding assistants like Claude Code.

Author: Solent Labs™
Created: 2026-02-10
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_launcher.utils.humanize import (
    format_time_ago as _humanize_format_time_ago,
)
from ai_launcher.utils.humanize import (
    humanize_size,
)


def encode_project_path(project_path: Path) -> str:
    """Encode project path into Claude's session directory naming format.

    Claude Code stores session data in directories named by encoding the project path:
    - Replace directory separators with hyphens
    - Remove leading separator
    - Example: /home/user/projects/foo -> -home-user-projects-foo

    Args:
        project_path: Absolute path to the project

    Returns:
        Encoded directory name

    Examples:
        >>> encode_project_path(Path("/home/user/projects/my-app"))
        '-home-user-projects-my-app'
        >>> encode_project_path(Path("/home/user/work"))
        '-home-user-work'
    """
    # Convert to absolute path without resolving symlinks
    abs_path = Path(os.path.abspath(project_path))  # noqa: PTH100 - resolve() follows symlinks
    path_str = str(abs_path)

    # Replace path separator with hyphens
    encoded = path_str.replace(os.sep, "-")

    return encoded


def get_claude_session_dir(project_path: Path) -> Optional[Path]:
    """Get the Claude Code session directory for a project.

    Args:
        project_path: Absolute path to the project

    Returns:
        Path to session directory if it exists, None otherwise

    Examples:
        >>> session_dir = get_claude_session_dir(Path("/home/user/projects/foo"))
        >>> session_dir
        Path('/home/user/.claude/projects/-home-user-projects-foo')
    """
    encoded_name = encode_project_path(project_path)
    session_dir = Path.home() / ".claude" / "projects" / encoded_name

    return session_dir if session_dir.exists() else None


def count_sessions(session_dir: Path) -> int:
    """Count the number of Claude Code session files.

    Session files are stored as UUID.jsonl files in the session directory.

    Args:
        session_dir: Path to the Claude session directory

    Returns:
        Number of .jsonl session files

    Examples:
        >>> count_sessions(Path("/home/user/.claude/projects/-home-user-projects-foo"))
        7
    """
    if not session_dir.exists():
        return 0

    try:
        # Count .jsonl files (excluding those in subdirectories)
        return len([f for f in session_dir.glob("*.jsonl") if f.is_file()])
    except (PermissionError, OSError):
        return 0


def get_session_size(session_dir: Path) -> int:
    """Calculate total size of session data in bytes.

    Includes all .jsonl files but excludes the memory/ subdirectory.

    Args:
        session_dir: Path to the Claude session directory

    Returns:
        Total size in bytes

    Examples:
        >>> get_session_size(
        ...     Path("/home/user/.claude/projects/-home-user-projects-foo")
        ... )
        1572864  # 1.5 MB
    """
    if not session_dir.exists():
        return 0

    total_size = 0
    try:
        # Sum up .jsonl files
        for jsonl_file in session_dir.glob("*.jsonl"):
            if jsonl_file.is_file():
                total_size += jsonl_file.stat().st_size
    except (PermissionError, OSError):
        pass

    return total_size


def get_last_session_time(session_dir: Path) -> Optional[datetime]:
    """Get the timestamp of the most recent session file.

    Args:
        session_dir: Path to the Claude session directory

    Returns:
        Datetime of most recent session modification, or None if no sessions

    Examples:
        >>> get_last_session_time(
        ...     Path("/home/user/.claude/projects/-home-user-projects-foo")
        ... )
        datetime(2026, 2, 10, 10, 14, 35)
    """
    if not session_dir.exists():
        return None

    try:
        jsonl_files = list(session_dir.glob("*.jsonl"))
        if not jsonl_files:
            return None

        # Get the most recently modified file
        latest_file = max(jsonl_files, key=lambda f: f.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)
    except (PermissionError, OSError):
        return None


def get_memory_files(session_dir: Path) -> List[Path]:
    """Get list of memory files in the session directory.

    Memory files are stored in the memory/ subdirectory and typically include:
    - MEMORY.md (auto-generated summary)
    - Topic-specific notes (debugging.md, patterns.md, etc.)

    Args:
        session_dir: Path to the Claude session directory

    Returns:
        List of memory file paths (relative to memory/ directory)

    Examples:
        >>> get_memory_files(
        ...     Path("/home/user/.claude/projects/-home-user-projects-foo")
        ... )
        [Path('MEMORY.md'), Path('debugging.md'), Path('patterns.md')]
    """
    memory_dir = session_dir / "memory"
    if not memory_dir.exists():
        return []

    try:
        # Get all markdown files in memory directory
        memory_files = [
            f.relative_to(memory_dir) for f in memory_dir.glob("*.md") if f.is_file()
        ]
        return sorted(memory_files)
    except (PermissionError, OSError):
        return []


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as a human-readable "time ago" string.

    .. deprecated::
        Use :func:`ai_launcher.utils.humanize.format_time_ago` instead.

    Args:
        dt: Datetime to format

    Returns:
        Human-readable time ago string
    """
    import warnings

    from ai_launcher.utils.humanize import format_time_ago as _format_time_ago

    warnings.warn(
        "ai_launcher.utils.session.format_time_ago() is deprecated. "
        "Use ai_launcher.utils.humanize.format_time_ago() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _format_time_ago(dt)


def get_session_summary(project_path: Path) -> Optional[Dict[str, Any]]:
    """Get a complete summary of AI session data for a project.

    Combines all session detection into a single convenient function.

    Args:
        project_path: Absolute path to the project

    Returns:
        Dictionary with session information, or None if no sessions found:
        - session_dir: Path to session directory
        - session_count: Number of session files
        - session_size: Total size in bytes
        - session_size_human: Human-readable size
        - last_session: Datetime of last session
        - last_session_ago: Human-readable time ago
        - memory_files: List of memory file names
        - memory_count: Number of memory files

    Examples:
        >>> get_session_summary(Path("/home/user/projects/my-app"))
        {
            'session_dir': Path('/home/user/.claude/projects/-home-user-projects-my-app'),
            'session_count': 7,
            'session_size': 1572864,
            'session_size_human': '1.5 MB',
            'last_session': datetime(2026, 2, 10, 10, 14, 35),
            'last_session_ago': '2 hours ago',
            'memory_files': ['MEMORY.md', 'debugging.md'],
            'memory_count': 2
        }
    """
    session_dir = get_claude_session_dir(project_path)
    if not session_dir:
        return None

    session_count = count_sessions(session_dir)
    if session_count == 0:
        return None

    session_size = get_session_size(session_dir)
    last_session = get_last_session_time(session_dir)
    memory_files = get_memory_files(session_dir)

    return {
        "session_dir": session_dir,
        "session_count": session_count,
        "session_size": session_size,
        "session_size_human": humanize_size(session_size),
        "last_session": last_session,
        "last_session_ago": _humanize_format_time_ago(last_session)
        if last_session
        else None,
        "memory_files": [f.name for f in memory_files],
        "memory_count": len(memory_files),
    }
