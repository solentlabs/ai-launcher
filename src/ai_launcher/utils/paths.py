"""Path utilities for ai-launcher."""

import os
import sys
from pathlib import Path


def expand_path(path_str: str) -> Path:
    """Expand path with ~ and environment variables.

    Args:
        path_str: Path string to expand

    Returns:
        Expanded Path object

    Examples:
        >>> expand_path("~/projects")
        Path('/home/user/projects')

        >>> expand_path("$HOME/work")
        Path('/home/user/work')
    """
    # Expand environment variables
    expanded = os.path.expandvars(path_str)
    # Expand ~ to home directory
    return Path(expanded).expanduser().resolve()


def validate_directory(path: Path) -> bool:
    """Check if a path exists and is a directory.

    Args:
        path: Path to validate

    Returns:
        True if path exists and is a directory, False otherwise
    """
    return path.exists() and path.is_dir()


def is_relative_to(path: Path, base: Path) -> bool:
    """Check if path is relative to base (Python 3.8 compatible).

    Equivalent to Path.is_relative_to() which requires Python 3.9+.

    Args:
        path: Path to check
        base: Base path

    Returns:
        True if path is relative to base
    """
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def quote_for_fzf(path) -> str:
    """Quote a path for use in fzf --preview commands.

    fzf preview commands are executed via shell, so paths with spaces
    need quoting. Uses double quotes which work on both Unix and Windows.
    """
    return f'"{path}"'


def fzf_preview_cmd(helper_script: Path, *extra_args: str) -> str:
    """Build a quoted fzf --preview command string.

    Quotes sys.executable and helper_script automatically. Extra args
    are included as-is — use quote_for_fzf() for paths that may contain
    spaces, and pass fzf placeholders like {} or {1} as plain strings.
    """
    parts = [quote_for_fzf(sys.executable), quote_for_fzf(helper_script)]
    parts.extend(extra_args)
    return " ".join(parts)


def get_relative_path(path: Path, base: Path) -> Path:
    """Get relative path from base, or return path if not relative.

    Args:
        path: Path to make relative
        base: Base path

    Returns:
        Relative path if possible, otherwise original path

    Examples:
        >>> get_relative_path(Path("/home/user/projects/foo"), Path("/home/user"))
        Path('projects/foo')

        >>> get_relative_path(Path("/other/path"), Path("/home/user"))
        Path('/other/path')
    """
    try:
        return path.relative_to(base)
    except ValueError:
        return path
