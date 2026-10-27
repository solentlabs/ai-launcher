"""The About row of the project picker: version, install method, update status.

The preview reads saved data only; the one network call is the update flow
that Enter on the row starts.

Author: Solent Labs™
"""

import contextlib
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from ai_launcher.core.self_update import (
    EDITABLE,
    PIP,
    PIPX,
    SOURCE,
    UpdatePlan,
    detect_plan,
    is_newer,
)
from ai_launcher.core.update_check import load_setting, load_state, update_notice
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


def _when(checked: object) -> str:
    """` (checked 2026-10-27)`, or nothing when the saved time makes no sense."""
    if isinstance(checked, bool) or not isinstance(checked, (int, float)):
        return ""
    try:
        return f" (checked {time.strftime('%Y-%m-%d', time.localtime(checked))})"
    except (OverflowError, OSError, ValueError):  # a corrupt state file
        return ""


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
    when = _when(data.get("checked_at"))
    if is_newer(latest, installed):
        return f"{latest} is available{when}"
    return f"up to date{when}"


def render_about(
    plan: UpdatePlan,
    enabled: bool,
    installed: str,
    state_file: Optional[Path],
    config_path: str,
    warnings: Sequence[str] = (),
) -> str:
    """The preview pane text. Every input is given, so it is easy to test."""
    status = _status(enabled, installed, state_file, config_path)
    lines = [
        fmt.paint("About AI Launcher", fmt.CYAN),
        "",
        f"Version:     {installed}",
        f"Installed:   {_METHODS.get(plan.method, plan.method)}",
        f"Update:      {status}",
        *(fmt.paint(f"Problem:     {warning}", fmt.YELLOW) for warning in warnings),
        "",
        fmt.paint("Enter checks PyPI and offers to update.", fmt.DIM),
    ]
    return "\n".join(lines)


def render_about_preview() -> str:
    """The picker row's preview. Reads saved data and the registry; no network."""
    from ai_launcher import __version__
    from ai_launcher.core.cache_registry import user_registry_path

    setting = load_setting()
    return render_about(
        detect_plan(),
        setting.enabled,
        __version__,
        None,
        str(user_registry_path()),
        setting.warnings,
    )


def run_about(input_fn: Callable[[str], str] = input) -> bool:
    """Run the update flow in place. True if it installed an update.

    After an install the caller must stop: the running picker would load the
    new version's files next to the old ones. Otherwise hold the screen until
    Enter.
    """
    from ai_launcher.ui.selector import clear_screen
    from ai_launcher.ui.update import run_update

    # fzf runs with --no-clear, so its frame is still on screen
    clear_screen()
    _, updated = run_update(check=False, yes=False)
    if not updated:
        with contextlib.suppress(EOFError, KeyboardInterrupt):
            input_fn("\nPress Enter to go back. ")
    return updated
