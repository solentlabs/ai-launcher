"""Edge cases for the cache and scratch modules: errors, odd platforms, partial results."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_launcher.core import cache_clean as clean
from ai_launcher.core import cache_registry as reg
from ai_launcher.core import cache_scan as scan
from ai_launcher.core import scratch
from ai_launcher.core.cache_data import (
    ROW_DISK,
    ROW_STALE,
    ROW_UNREGISTERED,
    SEVERITY_ATTENTION,
    CacheNotice,
    DiskStatus,
    SizeInfo,
)
from ai_launcher.core.cache_scan import PeekInfo
from ai_launcher.ui import cache_page
from ai_launcher.ui.formatter import PreviewFormatter

GB = 1024**3


# ------------------------------------------------------------ deletion guards


def test_guard_refuses_the_home_and_temp_folders_themselves(cache_home):
    ctx = clean.build_context([])

    assert "home or temp" in clean.guard_reason(cache_home, ctx)
    assert "home or temp" in clean.guard_reason(ctx.temp_dir, ctx)


def test_guard_allows_a_folder_inside_temp_but_outside_home(
    cache_home, tmp_path_factory
):
    outside = tmp_path_factory.mktemp("elsewhere")
    ctx = clean.CleanContext(home=cache_home / "other-home", temp_dir=outside.parent)

    assert clean.guard_reason(outside, ctx) is None


def test_the_rmtree_error_hook_clears_read_only_and_retries(tmp_path):
    locked = tmp_path / "locked.txt"
    locked.write_text("x")
    locked.chmod(0o400)
    seen = []

    clean._make_writable_and_retry(
        lambda target: seen.append(target), str(locked), None
    )

    assert seen == [str(locked)]


# ------------------------------------------------------------------ registry


def test_platform_without_proc_version_is_linux(monkeypatch):
    real = Path.read_text

    def fake(self, *args, **kwargs):
        if self == Path("/proc/version"):
            raise OSError("no such file")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(reg.sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", fake)

    assert reg.current_platform() == "linux"


def test_notice_values_must_match_the_default_type(cache_home):
    user = cache_home / "user.toml"
    user.write_text(
        '[notice]\nenabled = "yes"\nextra_disk_paths = "/mnt/d"\n'
        "stale_days = true\nscratch_min_count = 3\nextra_disk_paths_2 = 1\n"
    )

    registry = reg.load_registry(platform="linux", user_file=user)

    assert registry.notice.enabled is True
    assert registry.notice.extra_disk_paths == []
    assert registry.notice.stale_days == 7.0
    assert registry.notice.scratch_min_count == 3
    assert len(registry.warnings) == 4


def test_a_list_value_replaces_the_default_list(cache_home):
    user = cache_home / "user.toml"
    user.write_text('[notice]\nextra_disk_paths = ["/mnt/d"]\n')

    assert reg.load_registry("linux", user).notice.extra_disk_paths == ["/mnt/d"]


def test_two_entries_matching_one_path_make_one_row(cache_home):
    (cache_home / ".cache" / "agent-1").mkdir()
    user = cache_home / "user.toml"
    user.write_text(
        '[[location]]\nid = "a"\nclass = "review"\npaths.linux = ["{cache}/agent-*"]\n'
        '[[location]]\nid = "b"\nclass = "review"\npaths.linux = ["{cache}/agent-1"]\n'
    )
    entries = reg.resolve_entries(reg.load_registry("linux", user))

    assert [e.location_id for e in entries if e.path.name == "agent-1"] == ["a"]


# --------------------------------------------------------------------- scan


class FakeEntry:
    """A directory entry whose stat fails."""

    name = "broken"
    path = "/fake/broken"

    def stat(self, follow_symlinks=True):
        raise OSError("gone")

    def is_dir(self, follow_symlinks=True):
        raise OSError("gone")


class FakeScan:
    def __init__(self, entries):
        self.entries = entries

    def __enter__(self):
        return iter(self.entries)

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self.entries)


def test_walks_skip_entries_that_vanish_mid_walk(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "scandir", lambda path: FakeScan([FakeEntry()]))

    assert scan.scan_tree(tmp_path).file_count == 0
    assert scan.recently_modified(tmp_path, 60) is False
    assert scan.peek_tree(tmp_path).children == []


def test_a_failed_cache_write_leaves_no_temp_file_and_raises(tmp_path, monkeypatch):
    path = tmp_path / "state" / "sizes.json"

    def fail(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail)

    with pytest.raises(OSError, match="disk full"):
        scan.save_size_cache({"version": 1, "sizes": {}, "notice_times": {}}, path)

    assert list(path.parent.iterdir()) == []


def test_peek_counts_a_hard_link_once(tmp_path):
    first = tmp_path / "d" / "one.log"
    first.parent.mkdir()
    first.write_bytes(b"x" * 4096)
    os.link(first, tmp_path / "d" / "two.log")

    assert scan.peek_tree(tmp_path).total.file_count == 1


# ------------------------------------------------------------------ scratch


def test_tidy_and_candidates_survive_a_missing_scratch_folder(cache_home):
    scratch.tidy_empty_projects(cache_home / "nowhere")
    ctx = clean.build_context([])

    assert scratch.prune_candidates(1, ctx, root=cache_home / "nowhere").items == []


# --------------------------------------------------------------------- page


@pytest.mark.parametrize(
    ("notice", "expected"),
    [
        (
            CacheNotice(
                key=ROW_STALE,
                severity=SEVERITY_ATTENTION,
                total_bytes=14 * GB,
                detail={"oldest_days": 12.4},
            ),
            "Scratch untouched 12 days: 14 GB · ai-launcher cache",
        ),
        (
            CacheNotice(
                key=ROW_UNREGISTERED, severity=SEVERITY_ATTENTION, total_bytes=38 * GB
            ),
            "38 GB in unregistered cache folders · ai-launcher cache",
        ),
        (
            CacheNotice(
                key=ROW_DISK,
                severity=SEVERITY_ATTENTION,
                disk=DiskStatus("/", "/", 100 * GB, 4 * GB),
            ),
            "Disk 96% full (4 GB free) · ai-launcher cache",
        ),
    ],
    ids=["stale", "unregistered", "root-disk-has-no-label"],
)
def test_notice_text(notice, expected):
    assert cache_page.notice_text(notice) == expected


def test_peek_says_when_it_was_cut_short(tmp_path, monkeypatch):
    partial = PeekInfo(total=SizeInfo(size_bytes=1, file_count=1, partial=True))
    monkeypatch.setattr(cache_page, "peek_tree", lambda path: partial)

    assert "Cut short" in cache_page.strip_ansi(cache_page.render_peek(tmp_path))


def test_group_preview_for_the_disk_row_lists_each_disk(cache_home, monkeypatch):
    registry = reg.load_registry("linux", cache_home / "none")
    monkeypatch.setattr(
        cache_page,
        "read_disks",
        lambda config: [DiskStatus("C:", "/mnt/c", 238 * GB, 7 * GB)],
    )

    text = cache_page.strip_ansi(cache_page.render_group(ROW_DISK, registry))

    assert "C:" in text and "97% full" in text


def test_list_prints_registry_warnings(cache_home, capsys):
    user = cache_home / "user.toml"
    user.write_text('[[location]]\nid = "x"\nclass = "bogus"\n')
    registry = reg.load_registry("linux", user)

    cache_page.list_command([], registry)

    assert "! user registry: x: bad class" in capsys.readouterr().out


# ---------------------------------------------------------------- formatter


def test_paint_without_codes_or_text_is_unchanged():
    fmt = PreviewFormatter()

    assert fmt.paint("text") == "text"
    assert fmt.paint("", fmt.RED) == ""
    assert fmt.paint("x", fmt.RED) == f"{fmt.RED}x{fmt.RESET}"


def make_tree(root: Path) -> Path:
    """root/outer/inner/file, so a walk has a nested folder to descend into."""
    inner = root / "outer" / "inner"
    inner.mkdir(parents=True)
    (inner / "file.log").write_bytes(b"x" * 4096)
    return root


def scandir_failing_below(monkeypatch, root: Path, replacement=None):
    """Make os.scandir fail (or return `replacement`) for anything under root/outer."""
    real = os.scandir
    outer = str(root / "outer")

    def fake(path):
        if str(path).startswith(outer):
            if replacement is None:
                raise OSError("unreadable")
            return replacement
        return real(path)

    monkeypatch.setattr(os, "scandir", fake)


def test_an_unreadable_subfolder_is_skipped_by_every_walk(tmp_path, monkeypatch):
    root = make_tree(tmp_path)
    scandir_failing_below(monkeypatch, root)

    assert scan.recently_modified(root, 3600) is False
    peek = scan.peek_tree(root)
    assert [c.name for c in peek.children] == ["outer"]
    assert peek.total.file_count == 0


def test_a_vanishing_entry_inside_a_subfolder_is_skipped_by_peek(tmp_path, monkeypatch):
    root = make_tree(tmp_path)
    scandir_failing_below(monkeypatch, root, replacement=FakeScan([FakeEntry()]))

    assert scan.peek_tree(root).total.file_count == 0


def test_peek_descends_into_nested_folders(tmp_path):
    peek = scan.peek_tree(make_tree(tmp_path))

    assert peek.total.file_count == 1
    assert peek.extensions == {".log": 1}


# ------------------------------------------------------------- WSL disk label


def test_wsl_labels_the_home_disk_so_it_is_not_mistaken_for_the_windows_drive(
    cache_home, monkeypatch, tmp_path
):
    from ai_launcher.core.cache_data import NoticeConfig
    from ai_launcher.core.cache_summary import WSL_DISK, read_disks

    config = NoticeConfig(extra_disk_paths=[str(tmp_path)])
    monkeypatch.setattr(reg, "current_platform", lambda: "wsl")
    on_wsl = read_disks(config)
    monkeypatch.setattr(reg, "current_platform", lambda: "linux")
    on_linux = read_disks(config)

    assert on_wsl[0].label == WSL_DISK
    assert on_wsl[1].label == str(tmp_path)  # extra disks keep their own names
    assert on_linux[0].label == Path.home().anchor or "/"


@pytest.mark.parametrize(
    ("wsl_total", "host_total", "expected"),
    [(1000, 238, True), (200, 238, False), (238, 238, False)],
    ids=["wsl-bigger-than-host", "smaller", "equal"],
)
def test_wsl_overcommit(wsl_total, host_total, expected):
    from ai_launcher.core.cache_summary import WSL_DISK, wsl_overcommit

    disks = [
        DiskStatus(WSL_DISK, "/", wsl_total * GB, 880 * GB),
        DiskStatus("C:", "/mnt/c", host_total * GB, 3 * GB),
    ]

    assert (wsl_overcommit(disks) is not None) is expected
    assert wsl_overcommit(disks[:1]) is None  # no host drive known


def test_header_warns_when_wsl_can_outgrow_its_drive(monkeypatch):
    from ai_launcher.core.cache_data import SummaryRow
    from ai_launcher.core.cache_summary import WSL_DISK

    monkeypatch.setattr(cache_page, "current_platform", lambda: "wsl")
    disks = [
        DiskStatus(WSL_DISK, "/", 1000 * GB, 880 * GB),
        DiskStatus("C:", "/mnt/c", 238 * GB, 3 * GB),
    ]
    row = SummaryRow(key=ROW_DISK, severity=3, disks=disks)
    registry = SimpleNamespace(warnings=[], user_file=Path("/u"))

    header = cache_page.strip_ansi(cache_page.build_header([row], registry))

    assert "WSL disk 12% full" in header
    assert "WSL can fill C: before it reports low space" in header


def test_notice_for_the_wsl_disk_does_not_say_disk_twice():
    from ai_launcher.core.cache_summary import WSL_DISK

    notice = CacheNotice(
        key=ROW_DISK,
        severity=SEVERITY_ATTENTION,
        disk=DiskStatus(WSL_DISK, "/", 100 * GB, 4 * GB),
    )

    assert cache_page.notice_text(notice).startswith("WSL disk 96% full")


# ------------------------------------------------------- platform cache folders


def test_windows_has_no_cache_folder_to_take_stock_of(cache_home):
    (cache_home / "AppData" / "Local" / "Roaming-like").mkdir(parents=True)

    assert reg.find_unregistered([], platform="windows") == []


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("linux", ".cache"),
        ("wsl", ".cache"),
        ("macos", ".cache"),  # the fixture's stand-in for ~/Library/Caches
    ],
)
def test_cache_dir_per_platform(cache_home, platform, expected):
    assert reg.cache_dir(platform) == cache_home / expected


def test_windows_cache_token_points_at_local_app_data(cache_home, monkeypatch):
    local = cache_home / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert reg.cache_dir("windows") == local
    monkeypatch.delenv("LOCALAPPDATA")
    assert reg.cache_dir("windows") == cache_home / "AppData" / "Local"
