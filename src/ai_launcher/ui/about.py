"""The About row of the project picker: version, install method, update status.

The preview reads saved data only; the one network call is the update flow
that Enter on the row starts.

Author: Solent Labs™
"""

import contextlib
import time
from pathlib import Path
from typing import Callable, Optional

from ai_launcher.core.self_update import (
    EDITABLE,
    PIP,
    PIPX,
    SOURCE,
    UpdatePlan,
    detect_plan,
    is_newer,
)
from ai_launcher.core.update_check import load_state, update_notice
from ai_launcher.ui.formatter import PreviewFormatter

# The picker row that shows the version and starts a manual update
ABOUT_ROW = "📦 About"

fmt = PreviewFormatter()

_METHODS = {
    PIPX: "pipx",
    PIP: "pip",
    EDITABLE: "editable (development) checkout",
    SOURCE: "source checkout",
}


def about_row_label(
    enabled: bool, installed: str, state_file: Optional[Path] = None
) -> str:
    """The row's text, with a 🆕 when the saved check found a newer release."""
    if update_notice(enabled, installed, state_file) is not None:
        return f"{ABOUT_ROW}  🆕"
    return ABOUT_ROW


def _status(
    enabled: bool, installed: str, state_file: Optional[Path], config_path: str
) -> str:
    """The update status line, from the saved check only."""
    if not enabled:
        return (
            "off · to turn on, add to "
            f"{config_path}:\n             [update]\n             check = true"
        )
    data = load_state(state_file)
    latest = data.get("latest")
    if not isinstance(latest, str):
        return "not checked yet"
    checked = data.get("checked_at")
    when = (
        f" (checked {time.strftime('%Y-%m-%d', time.localtime(checked))})"
        if isinstance(checked, (int, float))
        else ""
    )
    if is_newer(latest, installed):
        return f"{latest} is available{when}"
    return f"up to date{when}"


def render_about(
    plan: UpdatePlan,
    enabled: bool,
    installed: str,
    state_file: Optional[Path],
    config_path: str,
) -> str:
    """The preview pane text. Every input is given, so it is easy to test."""
    status = _status(enabled, installed, state_file, config_path)
    lines = [
        fmt.paint("About AI Launcher", fmt.CYAN),
        "",
        f"Version:     {installed}",
        f"Installed:   {_METHODS.get(plan.method, plan.method)}",
        f"Update:      {status}",
        "",
        fmt.paint("Enter checks PyPI and offers to update.", fmt.DIM),
    ]
    return "\n".join(lines)


def render_about_preview() -> str:
    """The picker row's preview. Reads saved data and the registry; no network."""
    from ai_launcher import __version__
    from ai_launcher.core.cache_registry import load_registry, user_registry_path

    registry = load_registry()
    return render_about(
        detect_plan(),
        registry.update_check,
        __version__,
        None,
        str(user_registry_path()),
    )


def run_about(input_fn: Callable[[str], str] = input) -> None:
    """Run the update flow in place, then hold the screen until Enter."""
    from ai_launcher.ui.selector import clear_screen
    from ai_launcher.ui.update import update_command

    # fzf runs with --no-clear, so its frame is still on screen
    clear_screen()
    update_command(check=False, yes=False)
    with contextlib.suppress(EOFError, KeyboardInterrupt):
        input_fn("\nPress Enter to go back. ")
