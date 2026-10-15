"""Tests for the cache page: rows, ranking, confirm step, deletion flow."""

import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_launcher.core import cache_registry as registry_mod
from ai_launcher.core.cache_data import (
    CLASS_CLEAN,
    CLASS_REVIEW,
    CLASS_UNREGISTERED,
    ROW_DISK,
    ROW_SCRATCH,
    ROW_UNREGISTERED,
    SEVERITY_ATTENTION,
    SEVERITY_CRITICAL,
    CacheEntry,
    DiskStatus,
    ItemResult,
    NoticeConfig,
    Plan,
    PlanItem,
    SizeInfo,
    SummaryRow,
)
from ai_launcher.ui import cache_page as page

GB = 1024**3
DAY = 86400
X = Path("/x")


def make_dir(
    path: Path, size: int = 4096, age_days: float = 30, files: int = 2
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    when = time.time() - age_days * DAY
    for n in range(files):
        f = path / f"f{n}.bak"
        f.write_bytes(b"x" * size)
        os.utime(f, (when, when))
    return path


def ent(
    name, cls=CLASS_REVIEW, gb=1.0, age=20.0, blocked=None, path=None
) -> CacheEntry:
    return CacheEntry(
        location_id="t",
        name=name,
        path=path or X / name,
        cls=cls,
        remove=True,
        size=SizeInfo(
            size_bytes=int(gb * GB),
            newest_mtime=time.time() - age * DAY,
            scanned_at=time.time(),
        ),
        blocked=blocked,
    )


def plain(text: str) -> str:
    return page.strip_ansi(text)


# ------------------------------------------------------------- formatting


@pytest.mark.parametrize(
    ("days", "text"),
    [(None, "?"), (0.2, "today"), (1, "1 day"), (12.7, "12 days"), (250, "8 mo")],
)
def test_format_age(days, text):
    assert page.format_age(days) == text


@pytest.mark.parametrize(
    ("severity", "symbol"), [(3, "🔴"), (2, "🟡"), (1, "🟢"), (0, "⚪"), (9, "")]
)
def test_severity_symbol(severity, symbol):
    assert page.severity_symbol(severity) == symbol


def row(key, severity, members=None, **detail) -> SummaryRow:
    members = members or []
    return SummaryRow(
        key=key,
        severity=severity,
        members=members,
        total_bytes=sum(m.size_bytes for m in members),
        cleanup_bytes=sum(m.size_bytes for m in members if m.blocked is None),
        count=len(members),
        detail=detail,
    )


def test_critical_scratch_row_is_red_with_symbol_and_cleanup_total():
    members = [ent("a", gb=14), ent("b", gb=12), ent("c", gb=15, blocked="in use")]

    text = page.format_summary_row(
        row(ROW_SCRATCH, SEVERITY_CRITICAL, members, over_critical=3)
    )

    assert "\033[31m" in text  # red, as well as the symbol
    assert plain(text).startswith("🔴 SCRATCH")
    assert "41 GB in 3 folders, 3 over 10 GB" in plain(text)
    assert "clean up: 26 GB" in plain(text)


def test_disk_row_names_each_disk():
    disks = [
        DiskStatus("/", "/", 1000 * GB, 880 * GB),
        DiskStatus("C:", "/mnt/c", 238 * GB, 7 * GB),
    ]
    disk_row = SummaryRow(key=ROW_DISK, severity=SEVERITY_CRITICAL, disks=disks)

    text = plain(page.format_summary_row(disk_row))

    assert "C: 97% full, 7 GB free" in text
    assert "/ 12% full" in text


def test_empty_and_report_rows_are_dim():
    unreg = row(ROW_UNREGISTERED, 0, [ent("u", CLASS_UNREGISTERED, 38)])

    text = page.format_summary_row(unreg)

    assert "\033[2m" in text
    assert "(report only)" in plain(text)
    assert "nothing here" in plain(page.format_summary_row(row(ROW_SCRATCH, 0)))


def test_entry_row_shows_class_and_tool_command_or_reason(monkeypatch):
    monkeypatch.setattr(page.shutil, "which", lambda name: "/bin/x")
    with_command = ent("pre-commit", CLASS_CLEAN, 1.8)
    with_command.clean = ["pre-commit", "clean"]
    blocked = ent("busy", CLASS_REVIEW, 8, age=0, blocked="in use")

    assert "pre-commit clean" in plain(page.format_entry_row(with_command, time.time()))
    busy = page.format_entry_row(blocked, time.time())
    assert "in use" in plain(busy)
    assert "\033[2m" in busy  # a row that cannot be deleted is dimmed


def test_unsized_entry_shows_ellipsis_and_partial_shows_lower_bound():
    pending = ent("a")
    pending.size = None
    partial = ent("b", gb=3)
    partial.size.partial = True

    assert "…" in plain(page.format_entry_row(pending, time.time()))
    assert "≥ 3 GB" in plain(page.format_entry_row(partial, time.time()))


def test_rank_puts_big_deletable_rows_first_each_group_by_size():
    small = ent("small", gb=0.2)
    big = ent("big", gb=3)
    bigger_blocked = ent("blocked", gb=9, blocked="in use")
    biggest = ent("biggest", gb=5)

    ranked = [
        e.name for e in page.rank_entries([small, big, bigger_blocked, biggest], 1.0)
    ]

    assert ranked == ["biggest", "big", "blocked", "small"]


# ---------------------------------------------------------------- choices


def registry_with_notice():
    return SimpleNamespace(
        notice=NoticeConfig(), warnings=[], user_file=Path("/u/caches.toml")
    )


def test_choices_have_summary_rows_then_separator_then_locations():
    rows = [row(ROW_SCRATCH, SEVERITY_ATTENTION, [ent("a", gb=2)])]
    entries = [ent("a", gb=2), ent("pw", CLASS_CLEAN, 5)]

    choices, row_map, entry_map = page.build_choices(
        rows, entries, registry_with_notice(), time.time()
    )

    assert choices[0].startswith("S:SCRATCH\t\t")
    assert choices[1].startswith("__SEP__")
    assert [c.split("\t\t")[0] for c in choices[2:]] == [
        f"E:{X / 'pw'}",
        f"E:{X / 'a'}",
    ]
    assert set(row_map) == {"S:SCRATCH"}
    assert set(entry_map) == {f"E:{X / 'pw'}", f"E:{X / 'a'}"}


def test_unregistered_rows_are_capped_and_the_rest_counted():
    entries = [ent(f"u{n}", CLASS_UNREGISTERED, 1 + n / 100) for n in range(14)]
    entries.append(ent("tiny", CLASS_UNREGISTERED, 0.01))  # under 100 MiB: not listed

    choices, _, entry_map = page.build_choices(
        [], entries, registry_with_notice(), time.time()
    )

    assert len(entry_map) == page.UNREGISTERED_ROWS_SHOWN
    assert "…and 4 more not in the registry" in plain(choices[-1])


def test_a_path_that_would_break_the_row_format_is_not_offered():
    bad = ent("bad", path=X / "has\ttab")

    _, _, entry_map = page.build_choices(
        [], [bad, ent("ok")], registry_with_notice(), time.time()
    )

    assert list(entry_map) == [f"E:{X / 'ok'}"]


def test_header_has_keys_registry_path_and_warnings(monkeypatch):
    monkeypatch.setattr(page, "current_platform", lambda: "wsl")
    reg = registry_with_notice()
    reg.warnings = ["user registry: x is odd"]
    disk_row = SummaryRow(
        key=ROW_DISK, severity=3, disks=[DiskStatus("C:", "/mnt/c", 100 * GB, 2 * GB)]
    )

    header = plain(page.build_header([disk_row], reg))

    assert "C: 98% full, 2 GB free" in header
    assert "Tab marks" in header
    assert "compacted" in header  # the WSL note
    assert "! user registry: x is odd" in header
    assert str(Path("/u/caches.toml")) in header


# --------------------------------------------------------------- selection


def test_summary_row_expands_to_members_and_entries_pass_through():
    members = [ent("a"), ent("b")]
    row_map = {
        "S:SCRATCH": row(ROW_SCRATCH, 2, members),
        "S:DISK": SummaryRow(key=ROW_DISK, severity=3),
        "S:UNREGISTERED": row(ROW_UNREGISTERED, 2, [ent("u", CLASS_UNREGISTERED)]),
    }
    other = ent("pw", CLASS_CLEAN)

    entries, notes = page.expand_selection(
        ["S:SCRATCH", f"E:{X / 'pw'}", "S:DISK", "S:UNREGISTERED", "__SEP__"],
        row_map,
        {f"E:{X / 'pw'}": other},
    )

    assert [e.name for e in entries] == ["a", "b", "pw"]
    assert notes == [
        "DISK: nothing to clean from here",
        "UNREGISTERED: nothing to clean from here",
    ]


# ------------------------------------------------------------ confirm step


def plan_of(*entries, skipped=()):
    plan = Plan(items=[PlanItem(e, "remove") for e in entries])
    plan.skipped = list(skipped)
    return plan


def test_render_plan_lists_every_path_total_and_skips():
    review = ent("my-agent-1", CLASS_REVIEW, 14, path=Path("/h/.cache/my-agent-1"))
    cmd = ent("pre-commit", CLASS_CLEAN, 1.8)
    plan = Plan(
        items=[
            PlanItem(review, "remove"),
            PlanItem(cmd, "command", ["pre-commit", "clean"]),
        ]
    )
    plan.skipped = [(ent("busy"), "in use")]

    text = plain(page.render_plan(plan))

    assert "About to remove 2 locations (15.8 GB)" in text
    assert str(Path("/h/.cache/my-agent-1")) in text
    assert "pre-commit clean" in text
    assert "Skipped (1): busy (in use)" in text


@pytest.mark.parametrize(
    ("cls", "answer", "expected"),
    [
        (CLASS_CLEAN, "y", True),
        (CLASS_CLEAN, "YES", True),
        (CLASS_CLEAN, "", False),  # the default is no
        (CLASS_CLEAN, "n", False),
        (CLASS_CLEAN, "delete", False),
        (CLASS_REVIEW, "delete", True),
        (CLASS_REVIEW, "y", False),  # a review row needs the typed word
        (CLASS_REVIEW, "Delete", False),
        (CLASS_REVIEW, "", False),
    ],
)
def test_confirm_answers(cls, answer, expected):
    out = []

    ok = page.confirm_plan(
        plan_of(ent("a", cls)), lambda prompt: answer, True, out.append
    )

    assert ok is expected


def test_confirm_asks_the_right_question():
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return ""

    page.confirm_plan(plan_of(ent("a", CLASS_CLEAN)), ask, True, lambda s: None)
    page.confirm_plan(plan_of(ent("a", CLASS_REVIEW)), ask, True, lambda s: None)

    assert "[y/N]" in prompts[0]
    assert 'Type "delete"' in prompts[1]


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_confirm_with_nobody_there_is_no(error):
    def ask(prompt):
        raise error

    assert page.confirm_plan(plan_of(ent("a")), ask, True, lambda s: None) is False


def test_confirm_without_a_terminal_removes_nothing():
    out = []

    def ask(prompt):
        pytest.fail("must not ask without a terminal")

    assert page.confirm_plan(plan_of(ent("a")), ask, False, out.append) is False
    assert "Not a terminal" in "\n".join(out)


def test_confirm_with_an_empty_plan_says_so():
    out = []

    assert page.confirm_plan(Plan(), lambda p: "y", True, out.append) is False
    assert "Nothing to remove." in out[-1]


def test_render_results_marks_failures_and_totals():
    results = [
        ItemResult(ent("ok"), True, freed_bytes=2 * GB),
        ItemResult(ent("bad"), False, error="denied"),
    ]

    text = plain(page.render_results(results))

    assert "✓ ok: freed 2 GB" in text
    assert "✗ bad: denied" in text
    assert "Freed 2 GB" in text


# ------------------------------------------------------------ the full page


@pytest.fixture
def world(cache_home):
    """Two review folders, one pip cache, a user entry for the agents, no projects."""
    cache = cache_home / ".cache"
    old = make_dir(cache / "my-agent-old", age_days=40)
    busy = make_dir(cache / "my-agent-busy", age_days=0)
    pw = make_dir(cache / "ms-playwright", age_days=40)
    user = cache_home / "user.toml"
    user.write_text(
        '[[location]]\nid = "agents"\nname = "Agents"\nclass = "review"\n'
        'remove = true\npaths.linux = ["{cache}/my-agent-*"]\n'
        "[notice]\nscratch_min_gb = 0.000001\n"
    )
    registry = registry_mod.load_registry(platform="linux", user_file=user)
    return SimpleNamespace(
        old=old, busy=busy, pw=pw, registry=registry, home=cache_home
    )


def keys_for(names, choices):
    """Pick the fzf lines whose text mentions one of the names."""
    return [c for c in choices if any(n in c for n in names)]


def run(world, pick, answers):
    """Run the page once. pick(choices) -> lines to mark (or None to leave)."""
    seen = {}

    calls = []

    def fzf(choices, header, preview):
        seen["choices"], seen["header"], seen["preview"] = choices, header, preview
        calls.append(1)
        # the page loops until the user leaves, so leave on the second round
        return pick(choices) if len(calls) == 1 else None

    replies = iter(answers)
    page.run_cache_page(
        [],
        world.registry,
        fzf_runner=fzf,
        input_fn=lambda p: next(replies, ""),
        is_tty=True,
    )
    return seen


def test_leaving_the_page_deletes_nothing(world):
    seen = run(world, lambda choices: None, [])

    assert world.old.exists() and world.busy.exists() and world.pw.exists()
    assert "preview" in seen and "_cache_preview_helper.py" in seen["preview"]


def test_marking_a_scratch_folder_and_typing_delete_removes_it(world):
    run(
        world,
        lambda c: keys_for(["my-agent-old"], c) if True else None,
        ["delete", ""],
    )

    assert not world.old.exists()
    assert world.busy.exists()  # untouched
    assert world.pw.exists()


def test_declining_removes_nothing(world):
    run(world, lambda c: keys_for(["my-agent-old"], c), ["no", ""])

    assert world.old.exists()


def test_a_summary_row_cleans_its_whole_group_but_skips_in_use(world):
    run(
        world,
        lambda c: [line for line in c if line.startswith("S:SCRATCH")],
        ["delete", ""],
    )

    assert not world.old.exists()
    assert world.busy.exists()  # a recent write means a session may be using it


def test_a_clean_class_cache_needs_only_yes(world):
    run(world, lambda c: keys_for(["Playwright"], c), ["y", ""])

    assert not world.pw.exists()


def test_a_marked_report_row_is_skipped_not_deleted(world):
    claude = make_dir(world.home / ".claude")

    run(world, lambda c: keys_for(["Claude Code data"], c), [""])

    assert claude.exists()


def test_marking_only_a_row_with_nothing_to_clean_goes_back(world):
    marked = iter([["S:DISK\t\tx"], None])
    prompts = []

    page.run_cache_page(
        [],
        world.registry,
        fzf_runner=lambda *a: next(marked),
        input_fn=lambda p: prompts.append(p) or "",
        is_tty=True,
    )

    assert any("Press Enter to go back" in p for p in prompts)


def test_a_session_that_started_after_the_page_drew_is_still_protected(world):
    def pick(choices):
        # a session writes to the folder after the page was drawn
        (world.old / "fresh.log").write_text("just now")
        return keys_for(["my-agent-old"], choices)

    run(world, pick, ["delete", ""])

    assert world.old.exists()


def test_a_project_is_never_offered_even_if_a_registry_entry_names_it(world):
    project = make_dir(world.home / ".cache" / "my-agent-project")
    (project / ".git").mkdir()

    calls = []

    def fzf(choices, header, preview):
        calls.append(1)
        return keys_for(["my-agent-project"], choices) if len(calls) == 1 else None

    page.run_cache_page(
        [project],
        world.registry,
        fzf_runner=fzf,
        input_fn=lambda p: "delete",
        is_tty=True,
    )

    assert project.exists()


def test_eof_at_the_pause_leaves_the_page(world):
    def ask(prompt):
        raise EOFError

    page.run_cache_page(
        [],
        world.registry,
        fzf_runner=lambda c, h, p: keys_for(["Playwright"], c),
        input_fn=ask,
        is_tty=True,
    )

    assert world.pw.exists()


# ---------------------------------------------------------------- fzf + peek


def test_run_fzf_returns_marked_lines_or_none(monkeypatch):
    process = MagicMock()
    process.communicate.return_value = (b"E:/x\t\tone\nS:SCRATCH\t\ttwo\n", b"")
    process.returncode = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(page.subprocess, "Popen", popen)

    lines = page._run_fzf(["a", "b"], "header", "preview-cmd")

    assert lines == ["E:/x\t\tone", "S:SCRATCH\t\ttwo"]
    argv = popen.call_args[0][0]
    assert "--multi" in argv and "--ansi" in argv
    process.returncode = 130
    assert page._run_fzf(["a"], "h", "p") is None


def test_peek_shows_names_sizes_and_counts_but_never_contents(cache_home):
    folder = cache_home / ".cache" / "my-agent-1"
    make_dir(folder / "logs", size=9000, files=3)
    (folder / "brief.md").write_text("TOP SECRET CONTENT")

    text = plain(page.render_peek(folder))

    assert "logs/" in text
    assert "brief.md" not in text or "TOP SECRET" not in text
    assert "TOP SECRET" not in text
    assert ".bak 3" in text
    assert "contents are never shown" in text


def test_group_preview_lists_members_from_the_cache(world):
    from ai_launcher.core.cache_scan import record_size

    record_size(
        Path(os.environ["XDG_STATE_HOME"]) / "ai-launcher" / "cache-sizes.json",
        world.old,
        SizeInfo(
            size_bytes=5 * GB,
            newest_mtime=time.time() - 40 * DAY,
            scanned_at=time.time(),
        ),
    )

    text = plain(page.render_group("SCRATCH", world.registry))

    assert "my-agent-old" in text
    assert "Enter cleans every row above" in text
    assert page.render_group("NOPE", world.registry) == ""


def test_summary_preview_for_the_picker_row(world):
    text = plain(page.render_summary_preview(world.registry))

    assert "Cache and scratch" in text
    assert "SCRATCH" in text and "DISK" in text
    assert "Sizes appear after the first scan." in text


def test_list_prints_plain_text_and_deletes_nothing(world, capsys):
    page.list_command([], world.registry)

    out = capsys.readouterr().out
    assert "\033[" not in out
    assert "SCRATCH" in out and "my-agent-old" in out
    assert world.old.exists()


# -------------------------------------------------------------------- prune


def prune_world(cache_home):
    root = registry_mod.scratch_root()
    old = make_dir(root / "proj" / "old", age_days=30)
    fresh = make_dir(root / "proj" / "fresh", age_days=1)
    return old, fresh


@pytest.mark.parametrize("text", ["", "14", "0d", "fourteen"])
def test_prune_rejects_a_bad_duration(cache_home, capsys, text):
    assert page.prune_command(text) == 2
    assert "bad duration" in capsys.readouterr().out


def test_prune_dry_run_removes_nothing(cache_home, capsys):
    old, _ = prune_world(cache_home)

    assert page.prune_command("14d", dry_run=True) == 0

    assert old.exists()
    assert "Dry run" in capsys.readouterr().out


def test_prune_without_a_terminal_or_yes_removes_nothing_and_fails(cache_home, capsys):
    old, _ = prune_world(cache_home)

    assert page.prune_command("14d", is_tty=False) == 1

    assert old.exists()
    assert "--yes" in capsys.readouterr().out


def test_prune_yes_removes_old_keeps_fresh_and_tidies(cache_home):
    old, fresh = prune_world(cache_home)

    assert page.prune_command("14d", yes=True, is_tty=False) == 0

    assert not old.exists()
    assert fresh.exists()


@pytest.mark.parametrize(
    ("answer", "removed"), [("y", True), ("n", False), ("", False)]
)
def test_prune_asks_and_defaults_to_no(cache_home, answer, removed):
    old, _ = prune_world(cache_home)

    page.prune_command("14d", input_fn=lambda p: answer, is_tty=True)

    assert (not old.exists()) is removed


def test_prune_with_nothing_old_is_a_success(cache_home, capsys):
    make_dir(registry_mod.scratch_root() / "p" / "new", age_days=1)

    assert page.prune_command("14d", yes=True) == 0
    assert "Nothing to remove" in capsys.readouterr().out


def test_prune_eof_at_the_question_is_a_failure(cache_home):
    old, _ = prune_world(cache_home)

    def ask(prompt):
        raise EOFError

    assert page.prune_command("14d", input_fn=ask, is_tty=True) == 1
    assert old.exists()


def test_prune_exit_code_reports_a_failed_removal(cache_home, monkeypatch):
    old, _ = prune_world(cache_home)
    monkeypatch.setattr(
        page,
        "execute_plan",
        lambda plan, ctx: [ItemResult(plan.items[0].entry, False, error="x")],
    )

    assert page.prune_command("14d", yes=True) == 1
