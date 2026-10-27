"""Data types for the cache and scratch feature.

Plain dataclasses only: no display text and no ANSI codes. The core modules
fill them in; ``ui/`` formats them.

Author: Solent Labs™
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Safety classes
CLASS_CLEAN = "clean"
CLASS_REVIEW = "review"
CLASS_REPORT = "report"
CLASSES = (CLASS_CLEAN, CLASS_REVIEW, CLASS_REPORT)

# Shown for folders in the cache dir that the registry does not name
CLASS_UNREGISTERED = "unregistered"

# Severity of a summary row, least to most severe
SEVERITY_REPORT = 0
SEVERITY_FINE = 1
SEVERITY_ATTENTION = 2
SEVERITY_CRITICAL = 3

# Summary rows
ROW_DISK = "DISK"
ROW_SCRATCH = "SCRATCH"
ROW_STALE = "STALE"
ROW_CACHES = "CACHES"
ROW_UNREGISTERED = "UNREGISTERED"

# Written in a managed scratch folder while its session runs
SESSION_FILE = ".ai-launcher-session"


@dataclass
class CacheLocation:
    """One registry entry: a known place that may hold cache or scratch.

    Attributes:
        id: Unique id; a user entry with the same id replaces the default
        name: Display name
        group: Display grouping only
        cls: clean, review or report
        clean: The tool's own clean command, as an argv list
        remove: May the folder itself be removed
        note: One line about what is in it
        paths: Path patterns for this platform, tokens already expanded
        source: "default" or "user"
    """

    id: str
    name: str
    cls: str
    group: str = ""
    clean: Optional[List[str]] = None
    remove: bool = False
    note: str = ""
    paths: List[str] = field(default_factory=list)
    source: str = "default"


@dataclass
class SizeInfo:
    """What one walk of a tree found."""

    size_bytes: int = 0
    file_count: int = 0
    newest_mtime: Optional[float] = None
    oldest_mtime: Optional[float] = None
    partial: bool = False
    scanned_at: Optional[float] = None


@dataclass
class CacheEntry:
    """One concrete path, with what is known about it.

    Attributes:
        location_id: Id of the registry entry it came from ("" if unregistered)
        name: Display name
        path: The path, as registered; symlinks are not resolved
        cls: clean, review, report or unregistered
        clean: The tool's own clean command, as an argv list
        remove: May the folder itself be removed
        note: One line about what is in it
        group: Display grouping
        size: Size, if it has been walked
        blocked: Why it cannot be deleted, if it cannot
    """

    location_id: str
    name: str
    path: Path
    cls: str
    clean: Optional[List[str]] = None
    remove: bool = False
    note: str = ""
    group: str = ""
    size: Optional[SizeInfo] = None
    blocked: Optional[str] = None

    @property
    def size_bytes(self) -> int:
        """Size in bytes, 0 if not walked yet."""
        return self.size.size_bytes if self.size else 0

    @property
    def newest_mtime(self) -> Optional[float]:
        """Time of the newest file, if known."""
        return self.size.newest_mtime if self.size else None

    def age_days(self, now: float) -> Optional[float]:
        """Days since the newest file changed, None if unknown."""
        newest = self.newest_mtime
        if newest is None:
            return None
        return max(0.0, (now - newest) / 86400.0)


@dataclass
class NoticeConfig:
    """Thresholds for the launch notice and the page's summary rows."""

    enabled: bool = True
    interval_hours: float = 24.0
    min_free_percent: float = 5.0
    min_free_gb: float = 10.0
    scratch_min_gb: float = 1.0
    scratch_min_count: int = 2
    stale_days: float = 7.0
    unregistered_min_gb: float = 5.0
    critical_scratch_gb: float = 10.0
    critical_stale_days: float = 30.0
    critical_free_percent: float = 2.0
    critical_free_gb: float = 3.0
    extra_disk_paths: List[str] = field(default_factory=list)
    in_use_minutes: float = 120.0


@dataclass
class Registry:
    """The loaded registry."""

    locations: List[CacheLocation] = field(default_factory=list)
    notice: NoticeConfig = field(default_factory=NoticeConfig)
    update_check: bool = False
    warnings: List[str] = field(default_factory=list)
    user_file: Optional[Path] = None


@dataclass
class DiskStatus:
    """Free space on one disk."""

    label: str
    path: str
    total: int
    free: int

    @property
    def percent_free(self) -> float:
        """Free space as a percentage of the total."""
        return 100.0 * self.free / self.total if self.total else 100.0

    @property
    def percent_used(self) -> float:
        """Used space as a percentage of the total."""
        return 100.0 - self.percent_free


@dataclass
class SummaryRow:
    """One summary row on the page: a group of entries and how bad it is.

    Attributes:
        key: ROW_DISK, ROW_SCRATCH, ...
        severity: One of the SEVERITY_ values
        members: The entries a clean-up of this row would act on
        total_bytes: Sum of the members' sizes
        cleanup_bytes: Sum of the members' sizes that a clean-up could remove
        count: Number of members
        detail: Numbers the text needs, by name
        disk: For the disk row, the worst disk
    """

    key: str
    severity: int
    members: List[CacheEntry] = field(default_factory=list)
    total_bytes: int = 0
    cleanup_bytes: int = 0
    count: int = 0
    detail: Dict[str, float] = field(default_factory=dict)
    disk: Optional[DiskStatus] = None
    disks: List[DiskStatus] = field(default_factory=list)

    @property
    def cleanable(self) -> bool:
        """Can a clean-up of this row act on anything."""
        return self.key in (ROW_SCRATCH, ROW_STALE, ROW_CACHES) and bool(self.members)


@dataclass
class CacheNotice:
    """The launch notice: which row fired and the numbers behind it."""

    key: str
    severity: int
    total_bytes: int = 0
    count: int = 0
    detail: Dict[str, float] = field(default_factory=dict)
    disk: Optional[DiskStatus] = None


@dataclass
class PlanItem:
    """One thing the confirm step will do."""

    entry: CacheEntry
    action: str  # "command" or "remove"
    argv: Optional[List[str]] = None


@dataclass
class Plan:
    """What a deletion will do, and what was left out and why."""

    items: List[PlanItem] = field(default_factory=list)
    skipped: List[Tuple[CacheEntry, str]] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        """Sum of the sizes of the planned entries."""
        return sum(item.entry.size_bytes for item in self.items)

    @property
    def needs_typed_confirm(self) -> bool:
        """Does the plan include review-class entries."""
        return any(item.entry.cls == CLASS_REVIEW for item in self.items)


@dataclass
class ItemResult:
    """What happened to one planned item."""

    entry: CacheEntry
    ok: bool
    freed_bytes: int = 0
    error: Optional[str] = None
