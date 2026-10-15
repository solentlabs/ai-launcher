"""Summary rows: how bad is disk, scratch, stale scratch, caches, unregistered.

One computation feeds both the launch notice and the page, so the two never
disagree about what is worth attention. No walking: it works from entries
whose sizes were read out of the size cache.

Author: Solent Labs™
"""

import re
import shutil
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ai_launcher.core import cache_registry
from ai_launcher.core.cache_data import (
    CLASS_CLEAN,
    CLASS_REVIEW,
    CLASS_UNREGISTERED,
    ROW_CACHES,
    ROW_DISK,
    ROW_SCRATCH,
    ROW_STALE,
    ROW_UNREGISTERED,
    SEVERITY_ATTENTION,
    SEVERITY_CRITICAL,
    SEVERITY_FINE,
    SEVERITY_REPORT,
    CacheEntry,
    DiskStatus,
    NoticeConfig,
    SummaryRow,
)

GB = 1024**3
WSL_DISK = "WSL disk"
ROW_ORDER = (ROW_DISK, ROW_SCRATCH, ROW_STALE, ROW_CACHES, ROW_UNREGISTERED)


def _disk_label(path: str) -> str:
    """Name a disk: /mnt/c is C:, a Windows drive anchor C:\\ is C:."""
    match = re.match(r"^/mnt/([a-zA-Z])/?$", path)
    if match:
        return match.group(1).upper() + ":"
    if re.match(r"^[a-zA-Z]:", path):
        return path[:2].upper()
    return path


def read_disks(config: NoticeConfig) -> List[DiskStatus]:
    """Free space on the home disk and any extra disks (the Windows drive on WSL).

    On WSL the home disk is a virtual disk with its own, usually much larger,
    size; it is labelled so, since its free space says nothing about the
    Windows drive it lives on.
    """
    home_path = Path.home().anchor or "/"
    paths = [home_path] + list(config.extra_disk_paths)
    on_wsl = cache_registry.current_platform() == "wsl"
    disks: List[DiskStatus] = []
    for path in paths:
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        label = WSL_DISK if on_wsl and path == home_path else _disk_label(path)
        disks.append(DiskStatus(label, path, usage.total, usage.free))
    return disks


def wsl_overcommit(disks: List[DiskStatus]) -> Optional[Tuple[DiskStatus, DiskStatus]]:
    """The WSL disk and the larger-than-its-host drive, if WSL could outgrow it.

    WSL's virtual disk can be bigger than the Windows drive that holds it, so
    WSL can fill the drive while still reporting plenty of free space.
    """
    wsl = next((d for d in disks if d.label == WSL_DISK), None)
    host = next((d for d in disks if d.label != WSL_DISK), None)
    if wsl and host and wsl.total > host.total:
        return wsl, host
    return None


def _disk_severity(disk: DiskStatus, config: NoticeConfig) -> int:
    free_gb = disk.free / GB
    if (
        disk.percent_free < config.critical_free_percent
        or free_gb < config.critical_free_gb
    ):
        return SEVERITY_CRITICAL
    if disk.percent_free < config.min_free_percent or free_gb < config.min_free_gb:
        return SEVERITY_ATTENTION
    return SEVERITY_FINE


def _row(key: str, severity: int, members: List[CacheEntry]) -> SummaryRow:
    return SummaryRow(
        key=key,
        severity=severity,
        members=members,
        total_bytes=sum(m.size_bytes for m in members),
        cleanup_bytes=sum(m.size_bytes for m in members if m.blocked is None),
        count=len(members),
    )


def build_summary(
    entries: Iterable[CacheEntry],
    config: NoticeConfig,
    disks: List[DiskStatus],
    now: Optional[float] = None,
) -> List[SummaryRow]:
    """Build the summary rows, most severe first (ties keep the fixed order)."""
    now = now if now is not None else time.time()
    items = list(entries)
    scratch_min = config.scratch_min_gb * GB
    critical_scratch = config.critical_scratch_gb * GB

    # DISK: the worst disk sets the row
    disk_row = SummaryRow(key=ROW_DISK, severity=SEVERITY_REPORT, disks=disks)
    if disks:
        worst = min(disks, key=lambda d: d.percent_free)
        disk_row.disk = worst
        disk_row.severity = max(_disk_severity(d, config) for d in disks)
        disk_row.detail = {
            "percent_used": worst.percent_used,
            "free_bytes": float(worst.free),
        }

    # SCRATCH: every review-class entry
    review = [e for e in items if e.cls == CLASS_REVIEW]
    scratch = _row(ROW_SCRATCH, SEVERITY_FINE if review else SEVERITY_REPORT, review)
    big = [e for e in review if e.size_bytes >= scratch_min]
    scratch.detail = {
        "big_count": float(len(big)),
        "over_critical": float(
            len([e for e in review if e.size_bytes >= critical_scratch])
        ),
    }
    if scratch.total_bytes >= critical_scratch or scratch.detail["over_critical"] > 0:
        scratch.severity = SEVERITY_CRITICAL
    elif len(big) >= config.scratch_min_count:
        scratch.severity = SEVERITY_ATTENTION

    # STALE: review-class entries untouched for stale_days or more
    def age(entry: CacheEntry) -> float:
        value = entry.age_days(now)
        return value if value is not None else 0.0

    stale = [e for e in review if age(e) >= config.stale_days]
    stale_row = _row(ROW_STALE, SEVERITY_FINE if stale else SEVERITY_REPORT, stale)
    big_stale = [e for e in stale if e.size_bytes >= scratch_min]
    stale_row.detail = {"oldest_days": max((age(e) for e in stale), default=0.0)}
    if any(age(e) >= config.critical_stale_days for e in big_stale):
        stale_row.severity = SEVERITY_CRITICAL
    elif big_stale:
        stale_row.severity = SEVERITY_ATTENTION

    # CACHES: regenerable, big by nature, so never above fine
    caches = [e for e in items if e.cls == CLASS_CLEAN]
    caches_row = _row(ROW_CACHES, SEVERITY_FINE if caches else SEVERITY_REPORT, caches)

    # UNREGISTERED: report only, never cleanable from here
    unreg = [e for e in items if e.cls == CLASS_UNREGISTERED]
    unreg_row = _row(ROW_UNREGISTERED, SEVERITY_REPORT, unreg)
    if unreg_row.total_bytes >= config.unregistered_min_gb * GB:
        unreg_row.severity = SEVERITY_ATTENTION

    rows = [disk_row, scratch, stale_row, caches_row, unreg_row]
    order = {key: i for i, key in enumerate(ROW_ORDER)}
    return sorted(rows, key=lambda r: (-r.severity, order[r.key]))
