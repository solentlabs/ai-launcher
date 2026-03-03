"""Path utilities for ai-launcher."""

import os
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
