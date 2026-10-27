"""Cleanup helpers run before a launch: npm's cache, and Claude Code's leftovers.

Claude Code has its own cleanup (``cleanupPeriodDays``) that only trims session
transcripts in ``~/.claude/projects/``. The helpers here cover what it leaves:
``~/.claude.json.backup.*`` files and old native CLI versions. Debug-log pruning
lives in ``ClaudeProvider.cleanup_environment``, which calls these.

Nothing here sweeps ``~/.cache``: that was removed, and ``ai-launcher cache``
(see docs/cache-and-scratch.md) lists what it would delete and asks first.

Every helper contains its own failures: a launch must never stop because a
cleanup could not run.

Author: Solent Labs™
"""

import re
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import Any, Callable, Optional

from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)

NPM_TIMEOUT_SECONDS = 10

_VERSION_FILE = re.compile(r"^\d+\.\d+\.\d+$")


def clean_npm_cache(
    verbose: bool = False,
    runner: Optional[Callable[..., Any]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> bool:
    """Run ``npm cache clean --force`` if npm is installed (``--clean-npm``).

    WARNING: the next ``npm install`` is slower. Returns True if npm ran and
    succeeded; a missing npm, a timeout or a failure return False and never raise.
    """
    if not (which or shutil.which)("npm"):
        return False
    if verbose:
        print("  → Clearing npm cache")
    try:
        done = (runner or subprocess.run)(
            ["npm", "cache", "clean", "--force"],
            capture_output=True,
            check=False,
            timeout=NPM_TIMEOUT_SECONDS,
        )  # nosec B603, B607
    except (subprocess.SubprocessError, OSError) as error:
        logger.debug(f"Could not clean npm cache: {error}")
        return False
    return bool(done.returncode == 0)


def prune_claude_backups(home: Path) -> int:
    """Remove old ``~/.claude.json.backup.*`` files, keeping the newest.

    Claude Code writes one at every start and never removes them. The newest can
    be the only recovery copy of a damaged ``~/.claude.json``, so it stays. A
    file that cannot be removed is skipped. Returns how many were removed.
    """
    try:
        backups = [f for f in home.glob(".claude.json.backup.*") if f.is_file()]
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError as error:
        logger.debug(f"Could not list backup files: {error}")
        return 0
    removed = 0
    for backup in backups[1:]:
        try:
            backup.unlink(missing_ok=True)
            removed += 1
        except OSError as error:
            logger.debug(f"Could not remove {backup}: {error}")
    return removed


def prune_claude_versions(
    home: Path, which: Optional[Callable[[str], Optional[str]]] = None
) -> int:
    """Remove native Claude Code versions other than the one `claude` runs.

    Only when the ``claude`` on PATH resolves into the native versions folder:
    the file it resolves to is the version in use, and is kept. If ``claude``
    comes from elsewhere (an npm install, say) nothing is removed, because the
    native version in use cannot be told. Reading ``claude --version`` for it
    once deleted the binary that ``~/.local/bin/claude`` points to. A file that
    cannot be removed is skipped. Returns how many were removed.
    """
    versions = home / ".local" / "share" / "claude" / "versions"
    try:
        found = (which or shutil.which)("claude")
        if not found or not versions.is_dir():
            return 0
        in_use = Path(found).resolve()
        if in_use.parent != versions.resolve():
            return 0
        candidates = [
            f
            for f in versions.iterdir()
            if f.is_file() and f.name != in_use.name and _VERSION_FILE.match(f.name)
        ]
    except OSError as error:
        logger.debug(f"Could not look at Claude versions: {error}")
        return 0
    removed = 0
    for version in candidates:
        try:
            version.unlink(missing_ok=True)
            removed += 1
        except OSError as error:
            logger.debug(f"Could not remove {version}: {error}")
    return removed
