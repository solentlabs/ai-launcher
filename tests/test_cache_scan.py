"""Tests for sizing, the size cache and the in-use check."""

import json
import os
import threading
import time
from pathlib import Path

import pytest

from ai_launcher.core import cache_scan as scan
from ai_launcher.core.cache_data import SESSION_FILE, CacheEntry, SizeInfo


def make_file(path: Path, size: int = 100, age_days: float = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    when = time.time() - age_days * 86400
    os.utime(path, (when, when))
    return path


def entry(path: Path) -> CacheEntry:
    return CacheEntry(location_id="t", name=path.name, path=path, cls="clean")


def test_scan_tree_totals_and_times(tmp_path):
    make_file(tmp_path / "a" / "one", 5000, age_days=10)
    make_file(tmp_path / "a" / "b" / "two", 5000, age_days=2)

    info = scan.scan_tree(tmp_path)

    assert info.file_count == 2
    assert info.size_bytes >= 10000
    assert info.partial is False
    assert info.newest_mtime > info.oldest_mtime
    assert (time.time() - info.newest_mtime) / 86400 == pytest.approx(2, abs=0.1)


@pytest.mark.skipif(
    os.name == "nt", reason="Windows directory entries carry no link count or inode"
)
def test_scan_tree_counts_hard_links_once(tmp_path):
    first = make_file(tmp_path / "one", 8192)
    os.link(first, tmp_path / "two")

    info = scan.scan_tree(tmp_path)

    assert info.file_count == 1


def test_scan_tree_does_not_follow_symlinks(tmp_path, make_symlink):
    big = tmp_path / "big"
    make_file(big / "huge", 100000)
    tree = tmp_path / "tree"
    tree.mkdir()
    make_symlink(tree / "link", big, target_is_directory=True)

    info = scan.scan_tree(tree)

    assert info.size_bytes < 100000


def test_scan_tree_stops_at_the_budget(tmp_path):
    for n in range(20):
        make_file(tmp_path / f"d{n}" / "f")

    info = scan.scan_tree(tmp_path, budget_seconds=-1)

    assert info.partial is True


def test_scan_tree_skips_what_it_cannot_read(tmp_path):
    assert scan.scan_tree(tmp_path / "missing").file_count == 0


def test_size_cache_round_trip_and_atomic_write(tmp_path):
    path = tmp_path / "state" / "sizes.json"
    info = SizeInfo(size_bytes=7, file_count=1, newest_mtime=5.0, scanned_at=10.0)

    scan.record_size(path, Path("/x"), info)
    data = scan.load_size_cache(path)
    entries = [entry(Path("/x")), entry(Path("/y"))]
    scan.attach_sizes(entries, data)

    assert entries[0].size.size_bytes == 7
    assert entries[1].size is None
    assert not [p for p in path.parent.iterdir() if p.name.startswith(".sizes-")]
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "content",
    ["", "not json", "[]", '{"version": 99}'],
    ids=["empty", "garbage", "wrong-type", "wrong-version"],
)
def test_damaged_size_cache_is_empty(tmp_path, content):
    path = tmp_path / "sizes.json"
    path.write_text(content)

    assert scan.load_size_cache(path)["sizes"] == {}


def test_bad_record_is_ignored(tmp_path):
    path = tmp_path / "sizes.json"
    path.write_text(json.dumps({"version": 1, "sizes": {"/x": {"size": "nope"}}}))
    entries = [entry(Path("/x"))]

    scan.attach_sizes(entries, scan.load_size_cache(path))

    assert entries[0].size is None


def test_newer_scan_wins(tmp_path):
    path = tmp_path / "sizes.json"
    scan.record_size(path, Path("/x"), SizeInfo(size_bytes=2, scanned_at=20.0))
    scan.record_size(path, Path("/x"), SizeInfo(size_bytes=1, scanned_at=10.0))

    assert scan.load_size_cache(path)["sizes"][str(Path("/x"))]["size"] == 2


def test_refresh_walks_only_stale_entries(tmp_path):
    fresh_dir = make_file(tmp_path / "fresh" / "f", 4096).parent
    stale_dir = make_file(tmp_path / "stale" / "f", 4096).parent
    cache = tmp_path / "sizes.json"
    now = time.time()
    scan.record_size(cache, fresh_dir, SizeInfo(size_bytes=1, scanned_at=now - 60))
    scan.record_size(
        cache, stale_dir, SizeInfo(size_bytes=1, scanned_at=now - 99 * 3600)
    )
    entries = [entry(fresh_dir), entry(stale_dir)]
    walked = []

    scan.refresh_sizes(
        entries, cache, now=now, progress=lambda e: walked.append(e.name)
    )

    assert walked == ["stale"]
    assert entries[0].size.size_bytes == 1  # taken from the cache
    assert entries[1].size.size_bytes >= 4096


def test_refresh_force_walks_everything_and_stop_halts_it(tmp_path):
    first = make_file(tmp_path / "a" / "f").parent
    second = make_file(tmp_path / "b" / "f").parent
    cache = tmp_path / "sizes.json"
    stop = threading.Event()
    walked = []

    def progress(e):
        walked.append(e.name)
        stop.set()

    scan.refresh_sizes(
        [entry(first), entry(second)], cache, force=True, progress=progress, stop=stop
    )

    assert walked == ["a"]


def test_refresh_survives_an_unwritable_cache(tmp_path, monkeypatch):
    directory = make_file(tmp_path / "a" / "f").parent
    monkeypatch.setattr(
        scan, "record_size", lambda *a, **k: (_ for _ in ()).throw(OSError("full"))
    )

    scan.refresh_sizes([entry(directory)], tmp_path / "s.json")


def test_background_refresh_fills_the_cache(tmp_path):
    directory = make_file(tmp_path / "a" / "f", 4096).parent
    cache = tmp_path / "sizes.json"
    scan.start_background_refresh([entry(directory)], cache)

    deadline = time.time() + 5
    while time.time() < deadline and not cache.exists():
        time.sleep(0.02)

    assert str(directory) in scan.load_size_cache(cache)["sizes"]


def test_background_refresh_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        scan, "refresh_sizes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    done = threading.Event()
    stop = scan.start_background_refresh([], tmp_path / "s.json")
    done.wait(0.1)

    assert isinstance(stop, threading.Event)


@pytest.mark.parametrize(
    ("age_minutes", "window", "expected"),
    [(5, 120, True), (200, 120, False)],
    ids=["recent", "old"],
)
def test_recently_modified(tmp_path, age_minutes, window, expected):
    make_file(tmp_path / "d" / "f", age_days=age_minutes / 1440)

    assert scan.recently_modified(tmp_path, window * 60) is expected


def test_session_file_does_not_count_as_a_write(tmp_path):
    make_file(tmp_path / "old", age_days=3)
    (tmp_path / SESSION_FILE).write_text("1")

    assert scan.recently_modified(tmp_path, 3600) is False


def test_is_in_use_by_live_session(tmp_path, monkeypatch):
    make_file(tmp_path / "old", age_days=3)
    (tmp_path / SESSION_FILE).write_text(str(os.getpid()))

    assert scan.is_in_use(tmp_path, 120) == "session running"


def test_stale_session_file_is_ignored(tmp_path, monkeypatch):
    make_file(tmp_path / "old", age_days=3)
    (tmp_path / SESSION_FILE).write_text("4194999")
    monkeypatch.setattr(scan, "pid_alive", lambda pid: False)

    assert scan.is_in_use(tmp_path, 120) is None


def test_is_in_use_by_recent_write(tmp_path):
    make_file(tmp_path / "f")

    assert scan.is_in_use(tmp_path, 120) == "recently modified"


def test_session_pid_reads_garbage_as_none(tmp_path):
    (tmp_path / SESSION_FILE).write_text("not a pid")

    assert scan.session_pid(tmp_path) is None
    assert scan.session_pid(tmp_path / "nowhere") is None


# ---------------------------------------------------------------------- peek


def test_peek_lists_largest_children_and_extension_counts(tmp_path):
    make_file(tmp_path / "logs" / "a.log", 9000, age_days=5)
    make_file(tmp_path / "logs" / "b.log", 9000, age_days=9)
    make_file(tmp_path / "brief.md", 100, age_days=1)
    make_file(tmp_path / "x.bak", 100)
    (tmp_path / "x.bak").rename(tmp_path / "y.BAK")

    peek = scan.peek_tree(tmp_path)

    assert peek.children[0].name == "logs"
    assert peek.children[0].is_dir is True
    assert peek.extensions == {".log": 2, ".md": 1, ".bak": 1}
    assert peek.total.file_count == 4
    assert peek.total.oldest_mtime < peek.total.newest_mtime


def test_peek_limits_rows_and_never_reads_contents(tmp_path, monkeypatch):
    for n in range(30):
        make_file(tmp_path / f"f{n}.txt", 10 + n)
    monkeypatch.setattr(
        Path, "read_bytes", lambda self: pytest.fail("peek must not read contents")
    )
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: pytest.fail("peek must not read")
    )

    peek = scan.peek_tree(tmp_path, top=5)

    assert len(peek.children) == 5


def test_peek_marks_partial_at_the_budget(tmp_path):
    for n in range(5):
        make_file(tmp_path / f"d{n}" / "f")

    assert scan.peek_tree(tmp_path, budget_seconds=-1).total.partial is True


def test_peek_of_a_missing_folder_is_empty(tmp_path):
    assert scan.peek_tree(tmp_path / "gone").children == []
