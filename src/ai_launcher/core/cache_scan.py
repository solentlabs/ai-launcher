"""Sizing, the size cache, and the in-use check.

The launch path must never walk a tree: it reads the size cache file this
module writes. Walks happen on the cache page and in a background thread
while the picker is open.

Author: Solent Labs™
"""

import contextlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import platformdirs

from ai_launcher.core.cache_data import SESSION_FILE, CacheEntry, SizeInfo
from ai_launcher.utils.logging import get_logger
from ai_launcher.utils.process import pid_alive

logger = get_logger(__name__)

WALK_BUDGET_SECONDS = 10.0
FRESH_SECONDS = 6 * 3600
CACHE_VERSION = 1


def size_cache_path() -> Path:
    """Where the size cache file lives."""
    return Path(platformdirs.user_state_path("ai-launcher")) / "cache-sizes.json"


def _disk_bytes(stat: os.stat_result) -> int:
    """Space a file takes: allocated blocks on POSIX, st_size on Windows."""
    blocks = getattr(stat, "st_blocks", None)
    return int(blocks * 512) if blocks is not None else int(stat.st_size)


def scan_tree(
    path: Path,
    budget_seconds: float = WALK_BUDGET_SECONDS,
    now: Optional[float] = None,
) -> SizeInfo:
    """Walk a tree and total it up.

    Never follows symlinks (a link counts as the link), counts a hard-linked
    file once, skips what it cannot read, and stops at the time budget with
    ``partial`` set.
    """
    started = time.monotonic()
    info = SizeInfo(scanned_at=now if now is not None else time.time())
    seen_links = set()
    stack = [str(path)]
    while stack:
        if time.monotonic() - started > budget_seconds:
            info.partial = True
            break
        current = stack.pop()
        try:
            scan = os.scandir(current)
        except OSError:
            continue
        with scan:
            for entry in scan:
                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if is_dir:
                    stack.append(entry.path)
                    continue
                if stat.st_nlink > 1:
                    key = (stat.st_dev, stat.st_ino)
                    if key in seen_links:
                        continue
                    seen_links.add(key)
                info.size_bytes += _disk_bytes(stat)
                info.file_count += 1
                mtime = stat.st_mtime
                if info.newest_mtime is None or mtime > info.newest_mtime:
                    info.newest_mtime = mtime
                if info.oldest_mtime is None or mtime < info.oldest_mtime:
                    info.oldest_mtime = mtime
    return info


# ---------------------------------------------------------------- size cache


def _empty_cache() -> Dict[str, Any]:
    return {"version": CACHE_VERSION, "sizes": {}, "notice_times": {}}


def load_size_cache(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read the size cache; a missing or damaged file is an empty cache."""
    path = path or size_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty_cache()
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return _empty_cache()
    data.setdefault("sizes", {})
    data.setdefault("notice_times", {})
    return data


def save_size_cache(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Write the size cache atomically, readable by the owner only."""
    path = path or size_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=".sizes-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(data, out)
        Path(temp).chmod(0o600)
        Path(temp).replace(path)
    except OSError:
        with contextlib.suppress(OSError):
            Path(temp).unlink()
        raise


def _info_to_json(info: SizeInfo) -> Dict[str, Any]:
    return {
        "size": info.size_bytes,
        "files": info.file_count,
        "newest": info.newest_mtime,
        "oldest": info.oldest_mtime,
        "partial": info.partial,
        "at": info.scanned_at,
    }


def _info_from_json(raw: Any) -> Optional[SizeInfo]:
    if not isinstance(raw, dict):
        return None
    try:
        return SizeInfo(
            size_bytes=int(raw["size"]),
            file_count=int(raw.get("files", 0)),
            newest_mtime=raw.get("newest"),
            oldest_mtime=raw.get("oldest"),
            partial=bool(raw.get("partial", False)),
            scanned_at=raw.get("at"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def record_size(path: Path, entry_path: Path, info: SizeInfo) -> None:
    """Merge one location's result into the cache file; the newer scan wins."""
    data = load_size_cache(path)
    old = _info_from_json(data["sizes"].get(str(entry_path)))
    if old and old.scanned_at and info.scanned_at and old.scanned_at > info.scanned_at:
        return
    data["sizes"][str(entry_path)] = _info_to_json(info)
    save_size_cache(data, path)


def attach_sizes(entries: Iterable[CacheEntry], data: Dict[str, Any]) -> None:
    """Fill each entry's size from the cache data, if it has one."""
    for entry in entries:
        entry.size = _info_from_json(data["sizes"].get(str(entry.path)))


def is_fresh(info: Optional[SizeInfo], now: float) -> bool:
    """Is a cached size recent enough to trust without walking again."""
    return bool(info and info.scanned_at and now - info.scanned_at < FRESH_SECONDS)


def refresh_sizes(
    entries: List[CacheEntry],
    cache_path: Optional[Path] = None,
    force: bool = False,
    now: Optional[float] = None,
    budget_seconds: float = WALK_BUDGET_SECONDS,
    progress: Optional[Callable[[CacheEntry], None]] = None,
    stop: Optional[threading.Event] = None,
) -> None:
    """Walk every entry whose cached size is stale, writing each result as it ends."""
    cache_path = cache_path or size_cache_path()
    now = now if now is not None else time.time()
    data = load_size_cache(cache_path)
    for entry in entries:
        if stop is not None and stop.is_set():
            return
        cached = _info_from_json(data["sizes"].get(str(entry.path)))
        if not force and is_fresh(cached, now):
            entry.size = cached
            continue
        if progress:
            progress(entry)
        info = scan_tree(entry.path, budget_seconds, now=time.time())
        entry.size = info
        try:
            record_size(cache_path, entry.path, info)
        except OSError as error:
            logger.debug(f"Could not write the size cache: {error}")


def start_background_refresh(
    entries: List[CacheEntry], cache_path: Optional[Path] = None
) -> "threading.Event":
    """Refresh stale sizes in a daemon thread; set the returned event to stop it.

    A thread, not a detached process: it dies with the launcher, so nothing is
    left running. The file is replaced only at the end of each location, so a
    thread cut off by exit leaves nothing half-written.
    """
    stop = threading.Event()

    def work() -> None:
        try:
            refresh_sizes(entries, cache_path, stop=stop)
        except Exception as error:  # a refresh must never disturb a launch
            logger.debug(f"Background size refresh failed: {error}")

    threading.Thread(target=work, daemon=True, name="cache-size-refresh").start()
    return stop


# -------------------------------------------------------------------- in use


def recently_modified(
    path: Path, window_seconds: float, now: Optional[float] = None
) -> bool:
    """Was any file under path written within the window. Stops at the first."""
    cutoff = (now if now is not None else time.time()) - window_seconds
    stack = [str(path)]
    while stack:
        try:
            scan = os.scandir(stack.pop())
        except OSError:
            continue
        with scan:
            for entry in scan:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    elif (
                        entry.name != SESSION_FILE
                        and entry.stat(follow_symlinks=False).st_mtime >= cutoff
                    ):
                        return True
                except OSError:
                    continue
    return False


def session_pid(path: Path) -> Optional[int]:
    """The process id in a managed scratch folder's session file, if any."""
    try:
        return int((path / SESSION_FILE).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_in_use(
    path: Path, window_minutes: float, now: Optional[float] = None
) -> Optional[str]:
    """Why a folder may be in use right now, or None if it looks idle.

    Two checks: the launcher's own session file naming a live process, and any
    file written within the window. Both are heuristics.
    """
    pid = session_pid(path)
    if pid is not None and pid_alive(pid):
        return "session running"
    if recently_modified(path, window_minutes * 60.0, now):
        return "recently modified"
    return None


# ---------------------------------------------------------------------- peek


@dataclass
class PeekChild:
    """One child of a peeked folder: a name and numbers, never contents."""

    name: str
    is_dir: bool
    size_bytes: int = 0
    newest_mtime: Optional[float] = None


@dataclass
class PeekInfo:
    """What the page's peek pane shows for a folder."""

    total: SizeInfo = field(default_factory=SizeInfo)
    children: List[PeekChild] = field(default_factory=list)
    extensions: Dict[str, int] = field(default_factory=dict)


def peek_tree(path: Path, budget_seconds: float = 3.0, top: int = 15) -> PeekInfo:
    """Summarise a folder for the peek pane: largest children, counts by extension.

    Reads names, sizes and times only; file contents are never opened. Stops at
    the budget and marks the result partial.
    """
    deadline = time.monotonic() + budget_seconds
    peek = PeekInfo(total=SizeInfo(scanned_at=time.time()))
    seen_links: set = set()

    def add_file(child: PeekChild, name: str, stat: os.stat_result) -> None:
        if stat.st_nlink > 1:
            key = (stat.st_dev, stat.st_ino)
            if key in seen_links:
                return
            seen_links.add(key)
        size, mtime, total = _disk_bytes(stat), stat.st_mtime, peek.total
        child.size_bytes += size
        total.size_bytes += size
        total.file_count += 1
        if child.newest_mtime is None or mtime > child.newest_mtime:
            child.newest_mtime = mtime
        if total.newest_mtime is None or mtime > total.newest_mtime:
            total.newest_mtime = mtime
        if total.oldest_mtime is None or mtime < total.oldest_mtime:
            total.oldest_mtime = mtime
        ext = Path(name).suffix.lower()
        if ext:
            peek.extensions[ext] = peek.extensions.get(ext, 0) + 1

    try:
        with os.scandir(path) as scan:
            top_entries = sorted(scan, key=lambda e: e.name)
    except OSError:
        return peek
    for top_entry in top_entries:
        try:
            is_dir = top_entry.is_dir(follow_symlinks=False)
            top_stat = top_entry.stat(follow_symlinks=False)
        except OSError:
            continue
        child = PeekChild(top_entry.name, is_dir)
        peek.children.append(child)
        if not is_dir:
            add_file(child, top_entry.name, top_stat)
            continue
        stack = [top_entry.path]
        while stack:
            if time.monotonic() > deadline:
                peek.total.partial = True
                break
            try:
                scan = os.scandir(stack.pop())
            except OSError:
                continue
            with scan:
                for item in scan:
                    try:
                        if item.is_dir(follow_symlinks=False):
                            stack.append(item.path)
                        else:
                            add_file(child, item.name, item.stat(follow_symlinks=False))
                    except OSError:
                        continue
        if peek.total.partial:
            break
    peek.children.sort(key=lambda c: c.size_bytes, reverse=True)
    del peek.children[top:]
    return peek
