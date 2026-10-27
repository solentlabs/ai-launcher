"""The opt-in update check: ask PyPI once a day in the background, remember the answer.

Off unless the user sets ``[update] check = true``. The launch box reads the saved
answer only, so a launch never waits on the network, and any failure means no
notice: a bug here must not stop a session starting.

Author: Solent Labs™
"""

import contextlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import platformdirs

from ai_launcher.core.self_update import UpdateError, fetch_latest, is_newer
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)

INTERVAL_SECONDS = 24 * 3600


@dataclass
class UpdateNotice:
    """A newer release than the one running."""

    latest: str
    installed: str


def state_path() -> Path:
    """Where the last answer lives, beside the size cache."""
    return Path(platformdirs.user_state_path("ai-launcher")) / "update-check.json"


def load_state(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read the saved answer; a missing or damaged file is an empty one."""
    try:
        data = json.loads((path or state_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_due(data: Dict[str, Any], now: float) -> bool:
    """Has a day passed since the last successful check."""
    last = data.get("checked_at")
    if not isinstance(last, (int, float)):
        return True
    return now - last >= INTERVAL_SECONDS


def _save(data: Dict[str, Any], path: Path) -> None:
    """Write the answer atomically, readable by the owner only. Never raises."""
    temp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=".update-")
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(data, out)
        Path(temp).chmod(0o600)
        Path(temp).replace(path)
    except OSError as error:
        logger.debug(f"Update check not saved: {error}")
        if temp:
            with contextlib.suppress(OSError):
                Path(temp).unlink()


def check_now(
    fetch: Callable[[], str] = fetch_latest,
    path: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[str]:
    """Ask PyPI and save the answer. A failure saves nothing, so the next launch retries."""
    try:
        latest = fetch()
    except UpdateError as error:
        logger.debug(f"Update check failed: {error}")
        return None
    _save(
        {"checked_at": now if now is not None else time.time(), "latest": latest},
        path or state_path(),
    )
    return latest


def start_check(
    enabled: bool,
    path: Optional[Path] = None,
    fetch: Callable[[], str] = fetch_latest,
    now: Optional[float] = None,
) -> Optional[threading.Thread]:
    """Start the background check if opted in and a day has passed; else None."""
    if not enabled:
        return None
    path = path or state_path()
    now = now if now is not None else time.time()
    if not is_due(load_state(path), now):
        return None
    thread = threading.Thread(
        target=check_now, args=(fetch, path, now), name="update-check", daemon=True
    )
    thread.start()
    return thread


def update_notice(
    enabled: bool, installed: str, path: Optional[Path] = None
) -> Optional[UpdateNotice]:
    """The notice for this launch, from the saved answer only. None on any doubt."""
    if not enabled:
        return None
    try:
        latest = load_state(path).get("latest")
        if isinstance(latest, str) and is_newer(latest, installed):
            return UpdateNotice(latest=latest, installed=installed)
    except Exception as error:
        logger.debug(f"Update notice failed: {error}")
    return None
