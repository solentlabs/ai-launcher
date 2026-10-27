"""Planning and deleting cache and scratch locations.

This is the only module that deletes. The safety rules live here, not in the
registry, so a wrong registry entry cannot weaken them:

- report-only locations, ``~/.claude`` and every project are never deleted;
- a path must sit under the home folder (or the temp folder), never be the
  home folder, a direct child of the home folder, or inside a credentials or documents
  folder, never be or sit under a symlink, and never be (or be inside) a git
  repository;
- the protected set and the in-use check are rerun at delete time;
- commands run as an argv list with no shell, under a timeout.

Author: Solent Labs™
"""

import contextlib
import os
import shutil
import stat as stat_module
import subprocess  # nosec B404
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Set

from ai_launcher.core.cache_data import (
    CLASS_CLEAN,
    CLASS_REPORT,
    CLASS_REVIEW,
    CacheEntry,
    ItemResult,
    Plan,
    PlanItem,
)
from ai_launcher.core.cache_scan import is_in_use, scan_tree
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)

COMMAND_TIMEOUT_SECONDS = 300

# Folders under the home folder that are never deletable at any depth, even if
# a registry entry names something inside them: credentials and user documents.
# (A direct child of the home folder is refused for any name.)
NEVER_DELETE_UNDER = frozenset(
    {
        ".ssh",
        ".gnupg",
        ".aws",
        ".kube",
        "Documents",
        "Desktop",
        "Downloads",
        "Pictures",
    }
)


@dataclass
class CleanContext:
    """What the deletion rules need to know about this machine and this run."""

    home: Path
    project_paths: List[Path] = field(default_factory=list)
    claude_dirs: List[Path] = field(default_factory=list)
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()))
    in_use_minutes: float = 120.0


def build_context(
    project_paths: Iterable[Path] = (), in_use_minutes: float = 120.0
) -> CleanContext:
    """Build the context for this machine; Claude's folder is always protected."""
    home = Path.home()
    claude = [home / ".claude"]
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        claude.append(Path(override).expanduser())
    return CleanContext(
        home=home,
        project_paths=[Path(p) for p in project_paths],
        claude_dirs=claude,
        in_use_minutes=in_use_minutes,
    )


def _norm(path: Path) -> str:
    """A path made absolute and case-normalised, without resolving symlinks."""
    return os.path.normcase(os.path.abspath(path))  # noqa: PTH100


def _forms(path: Path) -> Set[str]:
    """A path as written and as resolved, normalised for comparison."""
    forms = {_norm(path)}
    with contextlib.suppress(OSError, RuntimeError):
        forms.add(os.path.normcase(os.path.realpath(path)))
    return forms


def _inside(child: str, parent: str) -> bool:
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def _related(a: Path, b: Path) -> bool:
    """Is one path the same as, inside, or holding the other."""
    return any(_inside(x, y) or _inside(y, x) for x in _forms(a) for y in _forms(b))


def protection_reason(path: Path, ctx: CleanContext) -> Optional[str]:
    """Why a path is protected: it is, holds or sits inside a protected folder."""
    for claude in ctx.claude_dirs:
        if _related(path, claude):
            return "Claude's own folder"
    for project in ctx.project_paths:
        if _related(path, project):
            return "a project"
    return None


def _git_reason(path: Path, base: Path) -> Optional[str]:
    """A repository root, or anything inside one below `base`, is never deleted.

    The search stops at `base` (the home or temp folder): a dotfiles repository
    in the home folder must not make every cache under it undeletable.
    """
    current = path
    while current != base and current != current.parent:
        if (current / ".git").exists():
            return "a git repository"
        current = current.parent
    return None


def guard_reason(path: Path, ctx: CleanContext) -> Optional[str]:
    """Why a path fails the deletion guards, or None if it passes."""
    here = _norm(path)
    home = _norm(ctx.home)
    temp = _norm(ctx.temp_dir)
    if here in (home, temp) or Path(here).parent == Path(here):
        return "the home or temp folder itself"
    if _inside(here, home):
        base, is_home = Path(home), True
    elif _inside(here, temp):
        base, is_home = Path(temp), False
    else:
        return "outside the home folder"

    parts = Path(here[len(str(base)) :].lstrip("\\/")).parts
    # Every folder from the base down to the path, the path itself included:
    # a link anywhere in between would send the delete somewhere else.
    current = base
    for part in parts:
        current = current / part
        if current.is_symlink():
            return "a symlink" if current == Path(here) else "under a symlink"
    if is_home and len(parts) == 1:
        return "a folder directly in the home folder"
    if is_home and parts[0].lower() in {n.lower() for n in NEVER_DELETE_UNDER}:
        return "a folder that holds credentials or documents"
    return _git_reason(Path(here), base)


def action_for(entry: CacheEntry) -> Optional[PlanItem]:
    """How an entry would be cleaned: its tool's command, else removal, else not at all."""
    found = shutil.which(entry.clean[0]) if entry.clean else None
    if entry.clean and found:
        # The resolved path, not the bare name: on Windows npm is npm.cmd, which
        # subprocess will not find from the name alone
        return PlanItem(entry, "command", [found, *entry.clean[1:]])
    if entry.remove:
        return PlanItem(entry, "remove")
    return None


def blocked_reason(
    entry: CacheEntry,
    ctx: CleanContext,
    deep: bool = False,
    now: Optional[float] = None,
) -> Optional[str]:
    """Why an entry cannot be deleted, or None if it can.

    ``deep`` walks the folder for the in-use check. Without it, the newest
    write time already in the size cache is used, so drawing the page stays
    cheap; the plan and the delete always go deep.
    """
    if entry.cls == CLASS_REPORT:
        return "report only"
    if entry.cls not in (CLASS_CLEAN, CLASS_REVIEW):
        return "not in the registry"
    reason = protection_reason(entry.path, ctx)
    if reason:
        return f"never deleted ({reason})"
    reason = guard_reason(entry.path, ctx)
    if reason:
        return f"refused ({reason})"
    if action_for(entry) is None:
        return "tool not installed" if entry.clean else "no way to remove it"
    if not entry.path.exists():
        return "already gone"
    if entry.cls == CLASS_REVIEW:
        if deep:
            if is_in_use(entry.path, ctx.in_use_minutes, now):
                return "in use"
        else:
            newest = entry.newest_mtime
            moment = now if now is not None else time.time()
            if newest is not None and newest >= moment - ctx.in_use_minutes * 60:
                return "in use"
    return None


def annotate(entries: Iterable[CacheEntry], ctx: CleanContext) -> None:
    """Set each entry's ``blocked`` reason (cheap form, for drawing the page)."""
    for entry in entries:
        entry.blocked = blocked_reason(entry, ctx)


def make_plan(
    entries: Iterable[CacheEntry], ctx: CleanContext, now: Optional[float] = None
) -> Plan:
    """Turn marked entries into a plan; whatever cannot be deleted is skipped with why."""
    plan = Plan()
    seen: Set[str] = set()
    for entry in entries:
        key = _norm(entry.path)
        if key in seen:
            continue
        seen.add(key)
        reason = blocked_reason(entry, ctx, deep=True, now=now)
        item = action_for(entry) if reason is None else None
        if reason is None and item is not None:
            plan.items.append(item)
        else:
            plan.skipped.append((entry, reason or "no way to remove it"))
    return plan


def _make_writable_and_retry(
    func: Callable[[str], object], target: str, _exc: object
) -> None:
    """rmtree error hook: clear a read-only bit (Windows) and try once more.

    Changes the entry itself, never a link's target, and keeps a directory
    enterable: a bare 0600 would leave it unusable.
    """
    entry = Path(target)
    if not entry.is_symlink():
        mode = entry.lstat().st_mode
        extra = stat_module.S_IWRITE | stat_module.S_IREAD
        if stat_module.S_ISDIR(mode):
            extra |= stat_module.S_IEXEC
        entry.chmod(stat_module.S_IMODE(mode) | extra)
    func(target)


def remove_path(path: Path) -> None:
    """Remove a folder or file; a symlink is unlinked, never followed."""
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def _run(
    item: PlanItem, runner: Callable[..., "subprocess.CompletedProcess[bytes]"]
) -> Optional[str]:
    """Do one item; return an error message or None."""
    if item.action == "command":
        try:
            done = runner(
                item.argv,
                shell=False,
                capture_output=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"timed out after {COMMAND_TIMEOUT_SECONDS}s"
        except (OSError, subprocess.SubprocessError) as error:
            return str(error)
        if done.returncode != 0:
            tail = (done.stderr or b"").decode("utf-8", errors="replace").strip()
            return f"exit {done.returncode}" + (f": {tail[-200:]}" if tail else "")
        return None
    try:
        remove_path(item.entry.path)
    except OSError as error:
        return str(error)
    return None


def execute_plan(
    plan: Plan,
    ctx: CleanContext,
    runner: Optional[Callable[..., "subprocess.CompletedProcess[bytes]"]] = None,
    progress: Optional[Callable[[PlanItem], None]] = None,
    now: Optional[float] = None,
) -> List[ItemResult]:
    """Carry out a plan. Every item is checked again first; one failing does not stop the rest."""
    runner = runner or subprocess.run  # nosec B603
    results: List[ItemResult] = []
    for item in plan.items:
        entry = item.entry
        reason = blocked_reason(entry, ctx, deep=True, now=now)
        if reason:
            results.append(ItemResult(entry, False, error=f"skipped: {reason}"))
            continue
        if progress:
            progress(item)
        before = scan_tree(entry.path).size_bytes
        error = _run(item, runner)
        after = scan_tree(entry.path).size_bytes if entry.path.exists() else 0
        freed = max(0, before - after)
        if error:
            logger.debug(f"Cleaning {entry.path} failed: {error}")
        results.append(ItemResult(entry, error is None, freed_bytes=freed, error=error))
    return results


def summarize_results(results: Sequence[ItemResult]) -> int:
    """Total bytes freed by the items that worked."""
    return sum(r.freed_bytes for r in results if r.ok)
