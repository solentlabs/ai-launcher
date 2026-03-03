"""Terminal manipulation utilities.

Provides functions to set terminal window titles and detect terminal capabilities.

This module uses ANSI escape sequences to set terminal titles, which works on
most modern terminal emulators (xterm, GNOME Terminal, iTerm2, Kitty, Alacritty,
Windows Terminal, etc.).

Author: Solent Labs™
Created: 2026-02-12
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


def set_terminal_title(title: str) -> bool:
    """Set the terminal window title.

    Uses ANSI escape sequences to set terminal title.
    Works on most modern terminals (xterm, gnome-terminal, iTerm2, Windows Terminal, etc.)

    Args:
        title: Title string to set

    Returns:
        True if title was set, False if not supported

    Examples:
        >>> set_terminal_title("my-project → Claude Code")
        True
    """
    # Check if terminal supports title setting
    if not _supports_title_setting():
        logger.debug("Terminal does not support title setting")
        return False

    try:
        # Special handling for tmux
        if os.environ.get("TMUX"):
            return _set_terminal_title_tmux(title)

        # ANSI escape sequence for setting title
        # ESC]0;{title}BEL
        # \033]0; = ESC]0; (start title sequence)
        # \007 = BEL (bell character, ends sequence)
        title_sequence = f"\033]0;{title}\007"

        # Write to stdout
        sys.stdout.write(title_sequence)
        sys.stdout.flush()

        logger.debug(f"Set terminal title to: {title}")
        return True
    except Exception as e:
        logger.debug(f"Failed to set terminal title: {e}")
        return False


def restore_terminal_title() -> bool:
    """Restore terminal title to default.

    Most terminals will restore automatically when process exits.

    Returns:
        True if title was restored, False otherwise
    """
    # Most terminals restore automatically, but we can try to clear it
    return set_terminal_title("")


def format_terminal_title(
    format_string: str,
    project_path: Path,
    provider_name: str,
) -> str:
    """Format terminal title string with variables.

    Args:
        format_string: Format string with variables like "{project}"
        project_path: Path to the project
        provider_name: Display name of provider (e.g., "Claude Code")

    Returns:
        Formatted title string

    Raises:
        ValueError: If format_string contains invalid/unknown variables

    Available variables:
        {project}  - Project folder name
        {provider} - Provider display name
        {path}     - Full project path
        {parent}   - Parent directory name

    Examples:
        >>> format_terminal_title(
        ...     "{project} → {provider}",
        ...     Path("/home/user/projects/my-app"),
        ...     "Claude Code",
        ... )
        'my-app → Claude Code'
    """
    # Get project name (last component of path)
    # Handle edge case: empty name for root directory or current directory
    project_name = project_path.name or str(project_path)

    # Get parent directory name
    parent_name = project_path.parent.name

    # Get full path as string
    full_path = str(project_path)

    # Sanitize inputs to prevent ANSI injection attacks
    project_name = _sanitize_title_component(project_name)
    provider_name = _sanitize_title_component(provider_name)
    parent_name = _sanitize_title_component(parent_name)
    full_path = _sanitize_title_component(full_path)

    # Replace variables
    try:
        title = format_string.format(
            project=project_name,
            provider=provider_name,
            path=full_path,
            parent=parent_name,
        )
    except KeyError as e:
        raise ValueError(
            f"Invalid format string variable: {e}. "
            f"Valid variables: project, provider, path, parent"
        ) from e

    # Sanitize final output (in case format_string contains ANSI codes)
    title = _sanitize_title_component(title)

    return title


def get_terminal_info() -> Dict[str, Any]:
    """Get information about the current terminal.

    Returns:
        Dictionary with terminal information

    Example:
        >>> get_terminal_info()
        {
            'term': 'xterm-256color',
            'term_program': 'iTerm.app',
            'supports_title': True,
            'is_tty': True,
        }
    """
    return {
        "term": os.environ.get("TERM", "unknown"),
        "term_program": os.environ.get("TERM_PROGRAM", "unknown"),
        "supports_title": _supports_title_setting(),
        "is_tty": sys.stdout.isatty(),
        "wt_session": os.environ.get("WT_SESSION"),  # Windows Terminal
        "tmux": bool(os.environ.get("TMUX")),
    }


def _supports_title_setting() -> bool:
    """Check if terminal supports title setting.

    Returns:
        True if title setting is supported
    """
    # Check if we're in a terminal
    if not sys.stdout.isatty():
        return False

    # Check TERM environment variable
    term = os.environ.get("TERM", "")

    # List of terminals that support title setting
    supported_terms = [
        "xterm",
        "xterm-256color",
        "xterm-color",
        "screen",
        "screen-256color",
        "tmux",
        "tmux-256color",
        "rxvt",
        "rxvt-unicode",
        "alacritty",
        "kitty",
        "vte",  # GNOME Terminal, Tilix, etc.
    ]

    # Check if current TERM matches any supported terminal
    for supported in supported_terms:
        if term.startswith(supported):
            return True

    # Check for specific terminal emulators via environment
    if os.environ.get("TERM_PROGRAM") in ["iTerm.app", "vscode", "Apple_Terminal"]:
        return True

    # Windows Terminal (WT_SESSION)
    return bool(os.environ.get("WT_SESSION"))


def _set_terminal_title_tmux(title: str) -> bool:
    """Set terminal title when running in tmux.

    tmux uses a different escape sequence than regular terminals.

    Args:
        title: Title to set

    Returns:
        True if successful
    """
    try:
        # tmux uses different escape sequence
        # \033k{title}\033\\
        sys.stdout.write(f"\033k{title}\033\\")
        sys.stdout.flush()
        logger.debug(f"Set tmux title to: {title}")
        return True
    except Exception as e:
        logger.debug(f"Failed to set tmux title: {e}")
        return False


def _sanitize_title_component(text: str) -> str:
    """Remove ANSI escape codes from text.

    This prevents ANSI injection attacks where malicious escape codes
    could be injected via config files or project names to manipulate
    the terminal (e.g., clear screen, move cursor, etc.).

    Args:
        text: Text to sanitize

    Returns:
        Text with all ANSI escape sequences removed

    Examples:
        >>> _sanitize_title_component("\x1b[31mRed\x1b[0m")
        'Red'
        >>> _sanitize_title_component("\x1b[H\x1b[2JClear")
        'Clear'
    """
    # Remove ANSI escape sequences:
    # - CSI sequences: ESC[...letter (e.g., \x1b[31m for colors)
    # - OSC with BEL: ESC]...BEL (e.g., \x1b]0;title\x07)
    # - OSC with ST: ESC]...ESC\ (e.g., \x1b]0;title\x1b\)
    ansi_pattern = re.compile(
        r"\x1b\[[0-9;]*[a-zA-Z]|"  # CSI sequences (colors, cursor movement, etc.)
        r"\x1b\][^\x07\x1b]*[\x07]|"  # OSC with BEL terminator
        r"\x1b\][^\x1b]*\x1b\\"  # OSC with ST terminator
    )
    return ansi_pattern.sub("", text)
