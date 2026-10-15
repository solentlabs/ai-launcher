"""Tests for the summary rows and the launch notice rules."""

import time
from pathlib import Path

import pytest

from ai_launcher.core import cache_notice as notice
from ai_launcher.core import cache_summary as summary
from ai_launcher.core.cache_data import (
    CLASS_CLEAN,
    CLASS_REPORT,
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
    SizeInfo,
)

GB = 1024**3
DAY = 86400
NOW = 2_000_000_000.0


def ent(name, cls, gb, age_days=1.0, blocked=None) -> CacheEntry:
    return CacheEntry(
        location_id="t",
        name=name,
        path=Path("/x") / name,
        cls=cls,
        size=SizeInfo(size_bytes=int(gb * GB), newest_mtime=NOW - age_days * DAY),
        blocked=blocked,
    )


def disk(free_percent, total_gb=1000) -> DiskStatus:
    total = total_gb * GB
    return DiskStatus("C:", "/mnt/c", total, int(total * free_percent / 100))


def rows(entries, disks=None, config=None):
    built = summary.build_summary(
        entries, config or NoticeConfig(), disks if disks is not None else [], NOW
    )
    return {r.key: r for r in built}


# ------------------------------------------------------------------- disk


@pytest.mark.parametrize(
    ("free_percent", "total_gb", "expected"),
    [
        (50, 1000, SEVERITY_FINE),
        (4, 1000, SEVERITY_ATTENTION),  # under 5%
        (1.5, 1000, SEVERITY_CRITICAL),  # under 2%
        (50, 15, SEVERITY_ATTENTION),  # 7.5 GB free: under 10 GB
        (10, 20, SEVERITY_CRITICAL),  # 2 GB free: under 3 GB
        (2.0, 1000, SEVERITY_ATTENTION),  # exactly at the critical line is not past it
    ],
)
def test_disk_severity(free_percent, total_gb, expected):
    assert rows([], [disk(free_percent, total_gb)])[ROW_DISK].severity == expected


def test_disk_row_takes_the_worst_disk():
    healthy = DiskStatus("/", "/", 1000 * GB, 880 * GB)
    full = disk(2)

    row = rows([], [healthy, full])[ROW_DISK]

    assert row.disk.label == "C:"
    assert row.severity == SEVERITY_ATTENTION or row.severity == SEVERITY_CRITICAL


def test_disk_row_without_disks_is_report_only():
    assert rows([])[ROW_DISK].severity == SEVERITY_REPORT


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/mnt/c", "C:"),
        ("/mnt/d/", "D:"),
        ("C:\\", "C:"),
        ("/", "/"),
        ("/home", "/home"),
    ],
)
def test_disk_label(path, label):
    assert summary._disk_label(path) == label


def test_read_disks_includes_extra_paths_and_skips_missing(tmp_path):
    config = NoticeConfig(extra_disk_paths=[str(tmp_path), "/definitely/not/here"])

    labels = [d.path for d in summary.read_disks(config)]

    assert str(tmp_path) in labels
    assert "/definitely/not/here" not in labels


# ---------------------------------------------------------------- scratch


@pytest.mark.parametrize(
    ("sizes", "expected"),
    [
        ([], SEVERITY_REPORT),
        ([0.2, 0.3], SEVERITY_FINE),
        ([2], SEVERITY_FINE),  # one big folder is not "many"
        ([2, 3], SEVERITY_ATTENTION),  # two of 1 GB+
        ([0.5, 8, 0.9], SEVERITY_FINE),  # only one over 1 GB
        ([12], SEVERITY_CRITICAL),  # one folder over 10 GB
        ([4, 4, 3], SEVERITY_CRITICAL),  # 11 GB in total
    ],
)
def test_scratch_severity(sizes, expected):
    entries = [ent(f"s{i}", CLASS_REVIEW, gb) for i, gb in enumerate(sizes)]

    assert rows(entries)[ROW_SCRATCH].severity == expected


def test_scratch_counts_only_review_class():
    entries = [ent("a", CLASS_CLEAN, 50), ent("b", CLASS_REPORT, 50)]

    assert rows(entries)[ROW_SCRATCH].count == 0


def test_cleanup_bytes_leave_out_blocked_members():
    entries = [
        ent("a", CLASS_REVIEW, 5),
        ent("b", CLASS_REVIEW, 8, blocked="in use"),
    ]

    row = rows(entries)[ROW_SCRATCH]

    assert row.total_bytes == 13 * GB
    assert row.cleanup_bytes == 5 * GB
    assert row.cleanable is True


# ------------------------------------------------------------------ stale


@pytest.mark.parametrize(
    ("gb", "age", "expected"),
    [
        (2, 3, SEVERITY_REPORT),  # not stale yet
        (2, 12, SEVERITY_ATTENTION),  # 1 GB+ and 7+ days
        (0.4, 12, SEVERITY_FINE),  # stale but small
        (2, 45, SEVERITY_CRITICAL),  # 30+ days
    ],
)
def test_stale_severity(gb, age, expected):
    assert rows([ent("a", CLASS_REVIEW, gb, age)])[ROW_STALE].severity == expected


def test_stale_ignores_old_caches():
    assert rows([ent("pw", CLASS_CLEAN, 5, age_days=400)])[ROW_STALE].count == 0


# ---------------------------------------------------- caches, unregistered


def test_caches_are_never_above_fine():
    row = rows([ent("pw", CLASS_CLEAN, 500, age_days=999)])[ROW_CACHES]

    assert row.severity == SEVERITY_FINE


@pytest.mark.parametrize(
    ("gb", "expected"), [(2, SEVERITY_REPORT), (38, SEVERITY_ATTENTION)]
)
def test_unregistered_severity(gb, expected):
    row = rows([ent("u", CLASS_UNREGISTERED, gb)])[ROW_UNREGISTERED]

    assert row.severity == expected
    assert row.cleanable is False


def test_rows_are_ordered_most_severe_first_then_fixed_order():
    entries = [ent("s", CLASS_REVIEW, 12, age_days=45), ent("pw", CLASS_CLEAN, 5)]

    keys = [
        r.key for r in summary.build_summary(entries, NoticeConfig(), [disk(1)], NOW)
    ]

    assert keys[:3] == [ROW_DISK, ROW_SCRATCH, ROW_STALE]
    assert keys[-1] == ROW_UNREGISTERED


def test_unknown_age_counts_as_fresh():
    undated = ent("a", CLASS_REVIEW, 3)
    undated.size.newest_mtime = None

    assert rows([undated])[ROW_STALE].count == 0


# ------------------------------------------------------------ the notice


def pick(entries, disks=None, config=None):
    built = summary.build_summary(
        entries, config or NoticeConfig(), disks if disks is not None else [], NOW
    )
    return notice.pick_notice(built)


@pytest.mark.parametrize(
    ("entries", "disks", "key"),
    [
        ([], [], None),
        ([ent("pw", CLASS_CLEAN, 200)], [disk(50)], None),  # caches never notify
        ([], [disk(1)], ROW_DISK),
        (
            [ent("a", CLASS_REVIEW, 2), ent("b", CLASS_REVIEW, 2)],
            [disk(50)],
            ROW_SCRATCH,
        ),
        ([ent("a", CLASS_REVIEW, 2, 20)], [disk(50)], ROW_STALE),
        ([ent("u", CLASS_UNREGISTERED, 40)], [disk(50)], ROW_UNREGISTERED),
        # the most severe wins: critical scratch beats an attention-level disk
        ([ent("a", CLASS_REVIEW, 12)], [disk(4)], ROW_SCRATCH),
        # equal severity: the fixed order decides
        (
            [ent("a", CLASS_REVIEW, 2, 20), ent("b", CLASS_REVIEW, 2)],
            [disk(50)],
            ROW_SCRATCH,
        ),
    ],
    ids=[
        "nothing",
        "caches-quiet",
        "disk",
        "scratch",
        "stale",
        "unregistered",
        "severity-wins",
        "order-breaks-ties",
    ],
)
def test_pick_notice(entries, disks, key):
    picked = pick(entries, disks)

    assert (picked.key if picked else None) == key


@pytest.mark.parametrize(
    ("hours_ago", "interval", "due"),
    [(None, 24, True), (30, 24, True), (2, 24, False), (2, 0, True)],
    ids=["never", "old", "recent", "always"],
)
def test_is_due(hours_ago, interval, due):
    data = {
        "notice_times": {} if hours_ago is None else {ROW_DISK: NOW - hours_ago * 3600}
    }
    candidate = notice.CacheNotice(key=ROW_DISK, severity=SEVERITY_CRITICAL)

    assert (
        notice.is_due(candidate, data, NoticeConfig(interval_hours=interval), NOW)
        is due
    )


@pytest.fixture
def fake_disk(monkeypatch):
    state = {"free": 1.0}
    monkeypatch.setattr(notice, "read_disks", lambda config: [disk(state["free"])])
    return state


def make_registry(cache_home, **kwargs):
    from ai_launcher.core.cache_registry import load_registry

    registry = load_registry(platform="linux", user_file=cache_home / "none.toml")
    for key, value in kwargs.items():
        setattr(registry.notice, key, value)
    return registry


def test_launch_notice_fires_records_and_then_goes_quiet(cache_home, fake_disk):
    registry = make_registry(cache_home)
    cache = cache_home / "sizes.json"

    first = notice.launch_notice(registry, cache, now=NOW)
    second = notice.launch_notice(registry, cache, now=NOW + 60)
    next_day = notice.launch_notice(registry, cache, now=NOW + 25 * 3600)

    assert first.key == ROW_DISK
    assert second is None
    assert next_day is not None


def test_launch_notice_disabled(cache_home, fake_disk):
    registry = make_registry(cache_home, enabled=False)

    assert notice.launch_notice(registry, cache_home / "s.json", now=NOW) is None


def test_launch_notice_quiet_when_all_is_well(cache_home, fake_disk):
    fake_disk["free"] = 60
    registry = make_registry(cache_home)

    assert notice.launch_notice(registry, cache_home / "s.json", now=NOW) is None


def test_launch_notice_never_walks_a_tree(cache_home, fake_disk, monkeypatch):
    import os

    from ai_launcher.core import cache_scan

    (cache_home / ".cache" / "pip").mkdir()
    registry = make_registry(cache_home)
    monkeypatch.setattr(cache_scan, "scan_tree", lambda *a, **k: pytest.fail("walked"))
    real_scandir = os.scandir
    depth = []

    def counting(path):
        depth.append(str(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", counting)

    notice.launch_notice(registry, cache_home / "s.json", now=NOW)

    # only the cache folder's own listing (and glob parents), never a recursive walk
    assert all(
        Path(p).parent == cache_home / ".cache"
        or Path(p) == cache_home / ".cache"
        or "scratch" in p
        for p in depth
    )


def test_launch_notice_swallows_every_error(cache_home, monkeypatch):
    monkeypatch.setattr(
        notice, "summary_rows", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )

    assert (
        notice.launch_notice(make_registry(cache_home), cache_home / "s.json") is None
    )


def test_notice_uses_cached_sizes(cache_home, fake_disk):
    from ai_launcher.core.cache_scan import record_size

    fake_disk["free"] = 60
    folders = []
    for name in ("agent-1", "agent-2"):
        folder = cache_home / ".cache" / name
        folder.mkdir()
        folders.append(folder)
    cache = cache_home / "sizes.json"
    for folder in folders:
        record_size(
            cache,
            folder,
            SizeInfo(
                size_bytes=3 * GB, newest_mtime=time.time(), scanned_at=time.time()
            ),
        )
    user = cache_home / "user.toml"
    user.write_text(
        '[[location]]\nid = "agents"\nclass = "review"\nremove = true\n'
        'paths.linux = ["{cache}/agent-*"]\n'
    )
    from ai_launcher.core.cache_registry import load_registry

    registry = load_registry(platform="linux", user_file=user)

    picked = notice.launch_notice(registry, cache, now=time.time())

    assert picked.key == ROW_SCRATCH
    assert picked.count == 2


@pytest.mark.parametrize(
    ("free", "expected"),
    [(60, SEVERITY_FINE), (4, SEVERITY_ATTENTION), (1, SEVERITY_CRITICAL)],
)
def test_worst_severity_for_the_picker_symbol(cache_home, fake_disk, free, expected):
    fake_disk["free"] = free

    assert notice.worst_severity(make_registry(cache_home)) == expected


def test_worst_severity_is_minus_one_on_error(cache_home, monkeypatch):
    monkeypatch.setattr(
        notice, "summary_rows", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )

    assert notice.worst_severity(make_registry(cache_home)) == -1
