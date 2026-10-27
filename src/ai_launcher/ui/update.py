"""The ``ai-launcher update`` command: check PyPI, show the command, ask, run it.

Author: Solent Labs™
"""

import subprocess  # nosec B404
import sys
from typing import Callable, Optional, Tuple

from ai_launcher import __version__
from ai_launcher.core.self_update import (
    UpdateError,
    UpdatePlan,
    detect_plan,
    fetch_latest,
    is_newer,
)


def run_update(
    check: bool = False,
    yes: bool = False,
    installed: str = __version__,
    fetch: Optional[Callable[[], str]] = None,
    plan: Optional[UpdatePlan] = None,
    runner: Callable[..., "subprocess.CompletedProcess[bytes]"] = subprocess.run,
    input_fn: Callable[[str], str] = input,
    is_tty: Optional[bool] = None,
) -> Tuple[int, bool]:
    """Run the update flow. Returns (exit code, whether an update was installed).

    The exit codes are in docs/updating.md.
    """
    print(f"ai-launcher {installed}")
    try:
        latest = (fetch or fetch_latest)()
    except UpdateError as error:
        print(f"Error: {error}")
        return 2, False
    if not is_newer(latest, installed):
        print(f"You are up to date (latest release: {latest}).")
        return 0, False
    print(f"A newer release is available: {latest}")

    plan = plan or detect_plan()
    if plan.argv is None and not plan.display:
        print(plan.note)
        return 0, False
    command = " ".join(plan.display or plan.argv or [])
    if check:
        print(f"Update with: {command}")
        return 0, False
    if plan.manual:
        print(plan.note)
        print(f"Run: {command}")
        return 0, False

    print(f"This will run: {command}")
    tty = sys.stdin.isatty() if is_tty is None else is_tty
    if not yes:
        if not tty:
            print("Not a terminal: nothing was run. Use --yes to update.")
            return 1, False
        try:
            answer = input_fn("Update now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1, False
        if answer not in ("y", "yes"):
            return 0, False
    try:
        done = runner(plan.argv, shell=False, check=False)  # nosec B603
    except OSError as error:
        print(f"Error: could not run the update: {error}")
        return 1, False
    if done.returncode != 0:
        print(f"The update command failed (exit {done.returncode}).")
        return 1, False
    print(f"Updated to {latest}. Start ai-launcher again to use it.")
    return 0, True


def update_command(
    check: bool = False,
    yes: bool = False,
    installed: str = __version__,
    fetch: Optional[Callable[[], str]] = None,
    plan: Optional[UpdatePlan] = None,
    runner: Callable[..., "subprocess.CompletedProcess[bytes]"] = subprocess.run,
    input_fn: Callable[[str], str] = input,
    is_tty: Optional[bool] = None,
) -> int:
    """The `ai-launcher update` command. Returns the process exit code."""
    return run_update(check, yes, installed, fetch, plan, runner, input_fn, is_tty)[0]
