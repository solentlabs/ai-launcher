"""The opt-in update check: ask PyPI once a day in the background, remember the answer.

Off unless the user sets ``[update] check = true``. The launch box reads the saved
answer only, so a launch never waits on the network, and any failure means no
notice: a bug here must not stop a session starting.

Author: Solent Labs™
"""

import contextlib
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import platformdirs

from ai_launcher.core.cache_registry import user_registry_path
from ai_launcher.core.self_update import fetch_latest, is_newer
from ai_launcher.utils.logging import get_logger

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.8 to 3.10 only
    import tomli as tomllib

logger = get_logger(__name__)

INTERVAL_SECONDS = 24 * 3600


@dataclass
class UpdateNotice:
    """A newer release than the one running."""

    latest: str
    installed: str


@dataclass
class UpdateSetting:
    """The user's [update] table: whether the check is on, and what was wrong with it."""

    enabled: bool = False
    warnings: List[str] = field(default_factory=list)


def load_setting(path: Optional[Path] = None) -> UpdateSetting:
    """Read `[update] check` on its own, never through the cache registry.

    Only `check = true` turns anything on. Nothing here raises: a broken file or
    value becomes a warning and leaves the check off.
    """
    setting = UpdateSetting()
    try:
        with open(path or user_registry_path(), "rb") as handle:
            table = tomllib.load(handle).get("update")
    except FileNotFoundError:
        return setting
    except (OSError, ValueError) as error:
        setting.warnings.append(f"caches.toml could not be read: {error}")
        return setting
    if table is None:
        return setting
    if not isinstance(table, dict):
        setting.warnings.append("[update] must be a table")
        return setting
    for key, value in table.items():
        if key != "check":
            setting.warnings.append(f"[update] unknown key {key!r} ignored")
        elif not isinstance(value, bool):
            setting.warnings.append("[update] check has the wrong type")
        else:
            setting.enabled = value
    return setting


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
    """Has a day passed since the last attempt. A time in the future (a clock
    that was wrong once) counts as due, so it cannot switch the check off."""
    last = data.get("checked_at")
    if not isinstance(last, (int, float)) or last > now:
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
    """Ask PyPI and save the attempt. Never raises.

    The time is recorded even when the ask fails, so an offline machine is not
    asked at every launch; the last good answer is kept.
    """
    path = path or state_path()
    try:
        latest: Optional[str] = fetch()
    except Exception as error:  # a thread must not print over the picker
        logger.debug(f"Update check failed: {error}")
        latest = None
    data: Dict[str, Any] = {"checked_at": now if now is not None else time.time()}
    answer = latest or load_state(path).get("latest")
    if isinstance(answer, str):
        data["latest"] = answer
    _save(data, path)
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
