"""The launch notice: one line when disk, scratch or cache use needs attention.

Reads the size cache and makes one disk-usage call; it never walks a tree. Any
failure means no notice, because a bug here must not stop a session starting.

Author: Solent Labs™
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_launcher.core.cache_data import (
    ROW_CACHES,
    SEVERITY_ATTENTION,
    SEVERITY_REPORT,
    CacheEntry,
    CacheNotice,
    NoticeConfig,
    Registry,
    SummaryRow,
)
from ai_launcher.core.cache_registry import (
    find_unregistered,
    load_registry,
    resolve_entries,
)
from ai_launcher.core.cache_scan import (
    attach_sizes,
    load_size_cache,
    save_size_cache,
    size_cache_path,
)
from ai_launcher.core.cache_summary import build_summary, read_disks
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


def load_entries(registry: Registry, cache_data: Dict[str, Any]) -> List[CacheEntry]:
    """Registered and unregistered entries, with whatever sizes are cached."""
    entries = resolve_entries(registry)
    entries += find_unregistered(entries)
    attach_sizes(entries, cache_data)
    return entries


def summary_rows(
    registry: Registry,
    cache_path: Optional[Path] = None,
    now: Optional[float] = None,
) -> List[SummaryRow]:
    """The summary rows as the size cache last saw things. No walking."""
    data = load_size_cache(cache_path)
    entries = load_entries(registry, data)
    return build_summary(entries, registry.notice, read_disks(registry.notice), now)


def pick_notice(rows: List[SummaryRow]) -> Optional[CacheNotice]:
    """The most severe row at attention or above; the caches row never counts."""
    for row in rows:  # already most severe first
        if row.key == ROW_CACHES or row.severity < SEVERITY_ATTENTION:
            continue
        return CacheNotice(
            key=row.key,
            severity=row.severity,
            total_bytes=row.total_bytes,
            count=row.count,
            detail=dict(row.detail),
            disk=row.disk,
        )
    return None


def is_due(
    notice: CacheNotice, data: Dict[str, Any], config: NoticeConfig, now: float
) -> bool:
    """Has this rule been quiet for the configured interval."""
    last = data.get("notice_times", {}).get(notice.key)
    if not isinstance(last, (int, float)):
        return True
    return now - last >= config.interval_hours * 3600


def launch_notice(
    registry: Optional[Registry] = None,
    cache_path: Optional[Path] = None,
    now: Optional[float] = None,
) -> Optional[CacheNotice]:
    """The notice to show at this launch, or None. Records that it was shown."""
    try:
        now = now if now is not None else time.time()
        registry = registry or load_registry()
        if not registry.notice.enabled:
            return None
        notice = pick_notice(summary_rows(registry, cache_path, now))
        if notice is None:
            return None
        data = load_size_cache(cache_path)
        if not is_due(notice, data, registry.notice, now):
            return None
        data["notice_times"][notice.key] = now
        save_size_cache(data, cache_path or size_cache_path())
        return notice
    except Exception as error:
        logger.debug(f"Cache notice failed: {error}")
        return None


def worst_severity(registry: Optional[Registry] = None) -> int:
    """The worst severity across the rows, for the picker row's symbol. -1 on error."""
    try:
        rows = summary_rows(registry or load_registry())
        return max(
            (r.severity for r in rows if r.key != ROW_CACHES),
            default=SEVERITY_REPORT,
        )
    except Exception as error:
        logger.debug(f"Cache severity failed: {error}")
        return -1
