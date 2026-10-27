"""Per-session scratch folders and pruning them.

At launch the launcher makes a folder for the session, names it in
``AI_SCRATCH_DIR`` and asks the tool to put throwaway files there. That is a
request, not a rule: a tool may ignore it. The launcher never removes a
non-empty scratch folder on its own; only ``scratch prune``, which a person
runs and confirms, does.

Author: Solent Labs™
"""

import contextlib
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from ai_launcher.core.cache_clean import CleanContext, make_plan
from ai_launcher.core.cache_data import (
    CLASS_REVIEW,
    SESSION_FILE,
    CacheEntry,
    Plan,
)
from ai_launcher.core.cache_registry import scratch_root
from ai_launcher.core.cache_scan import scan_tree

ENV_VAR = "AI_SCRATCH_DIR"

SCRATCH_STATEMENT = (
    "AI Launcher made a scratch folder for this session: {path} (also in $AI_SCRATCH_DIR). "
    "Put throwaway files there: .bak copies, patches, logs and briefs. "
    "Anything worth keeping belongs in the project, not in scratch, "
    "because the folder may be removed after the session ends."
)

_DURATION = re.compile(r"^(\d+)([hdw])$")
_UNIT_SECONDS = {"h": 3600, "d": 86400, "w": 7 * 86400}


def project_slug(name: str) -> str:
    """A project's folder name made safe for a path: letters, digits, - and _."""
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("_")
    return slug or "project"


def create_session_dir(
    project_name: str,
    now: Optional[float] = None,
    pid: Optional[int] = None,
    root: Optional[Path] = None,
) -> Path:
    """Make this session's scratch folder, with a session file naming the process."""
    root = root or scratch_root()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    path = root / project_slug(project_name) / f"{stamp}-{pid or os.getpid()}"
    path.mkdir(parents=True, exist_ok=True)
    (path / SESSION_FILE).write_text(str(pid or os.getpid()), encoding="utf-8")
    return path


def finish_session_dir(path: Path) -> None:
    """At exit: drop the session file, and the folder too if nothing was put in it."""
    with contextlib.suppress(OSError):
        (path / SESSION_FILE).unlink()
    with contextlib.suppress(OSError):
        path.rmdir()  # fails, harmlessly, if anything is inside
    with contextlib.suppress(OSError):
        path.parent.rmdir()  # the project folder, if that was the last session


def scratch_env(path: Path) -> Dict[str, str]:
    """The environment variable that names the session's scratch folder."""
    return {ENV_VAR: str(path)}


def parse_duration(text: str) -> float:
    """Parse 14d, 36h or 2w into seconds. Anything else is an error, not a default."""
    match = _DURATION.match(text.strip().lower())
    if not match or int(match.group(1)) == 0:
        raise ValueError(
            f"bad duration {text!r}: use a whole number and h, d or w (for example 14d)"
        )
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2)]


def prune_candidates(
    older_than_seconds: float,
    ctx: CleanContext,
    now: Optional[float] = None,
    root: Optional[Path] = None,
) -> Plan:
    """Plan the removal of session folders last written longer ago than the limit.

    Only folders two levels inside the managed scratch root are considered, so
    nothing else is reachable from here whatever the registry says. Folders in
    use, and any that fail the deletion guards, are left out with a reason.
    """
    root = root or scratch_root()
    now = now if now is not None else time.time()
    entries: List[CacheEntry] = []
    for project in _subdirs(root):
        for session in _subdirs(project):
            info = scan_tree(session, now=now)
            newest = info.newest_mtime
            if newest is None:
                try:
                    newest = session.stat().st_mtime
                except OSError:  # vanished since it was listed
                    continue
            if now - newest < older_than_seconds:
                continue
            entries.append(
                CacheEntry(
                    location_id="ai-launcher-scratch",
                    name=f"{project.name}/{session.name}",
                    path=session,
                    cls=CLASS_REVIEW,
                    remove=True,
                    size=info,
                )
            )
    return make_plan(entries, ctx, now)


def _subdirs(path: Path) -> List[Path]:
    """Real subfolders of a path, sorted; symlinks are not followed."""
    try:
        with os.scandir(path) as scan:
            return sorted(
                (Path(e.path) for e in scan if e.is_dir(follow_symlinks=False)),
            )
    except OSError:
        return []


def tidy_empty_projects(root: Optional[Path] = None) -> None:
    """After a prune, remove project folders left with no sessions in them."""
    for project in _subdirs(root or scratch_root()):
        with contextlib.suppress(OSError):
            project.rmdir()
