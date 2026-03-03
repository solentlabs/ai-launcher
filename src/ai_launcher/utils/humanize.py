"""Utility functions for humanizing data for display.

Author: Solent Labs™
Created: 2026-02-09
"""

from datetime import datetime


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as a human-readable "time ago" string.

    Args:
        dt: Datetime to format

    Returns:
        Human-readable time ago string

    Examples:
        >>> from datetime import timedelta
        >>> format_time_ago(datetime.now() - timedelta(minutes=5))
        '5 minutes ago'
        >>> format_time_ago(datetime.now() - timedelta(hours=2))
        '2 hours ago'
        >>> format_time_ago(datetime.now() - timedelta(days=3))
        '3 days ago'
    """
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = int(seconds / 604800)
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def humanize_size(size_bytes: int) -> str:
    """Convert file size in bytes to human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5 MB", "342 KB")

    Examples:
        >>> humanize_size(0)
        '0 B'
        >>> humanize_size(1024)
        '1.0 KB'
        >>> humanize_size(1536)
        '1.5 KB'
        >>> humanize_size(1048576)
        '1.0 MB'
        >>> humanize_size(1073741824)
        '1.0 GB'
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    # Format with 1 decimal place, but strip trailing .0
    formatted = f"{size:.1f}"
    if formatted.endswith(".0"):
        formatted = formatted[:-2]

    return f"{formatted} {units[unit_index]}"


def humanize_count(count: int, singular: str, plural: str = "") -> str:
    """Format a count with appropriate singular/plural form.

    Args:
        count: The count value
        singular: Singular form (e.g., "file")
        plural: Optional plural form (e.g., "files"). If not provided,
                adds 's' to singular.

    Returns:
        Formatted count string (e.g., "1 file", "5 files")

    Examples:
        >>> humanize_count(0, "file")
        '0 files'
        >>> humanize_count(1, "file")
        '1 file'
        >>> humanize_count(5, "file")
        '5 files'
        >>> humanize_count(1, "directory", "directories")
        '1 directory'
        >>> humanize_count(3, "directory", "directories")
        '3 directories'
    """
    if plural == "":
        plural = singular + "s"

    word = singular if count == 1 else plural
    return f"{count} {word}"
