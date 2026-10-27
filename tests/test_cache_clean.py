"""Tests for planning and deleting. The safety rules are the point of this file."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ai_launcher.core import cache_clean as clean
from ai_launcher.core.cache_data import (
    CLASS_CLEAN,
    CLASS_REPORT,
    CLASS_REVIEW,
    CLASS_UNREGISTERED,
    CacheEntry,
    SizeInfo,
)


def make_dir(path: Path, files: int = 2, age_days: float = 30) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    when = time.time() - age_days * 86400
    for n in range(files):
        f = path / f"f{n}.bak"
        f.write_bytes(b"x" * 4096)
        os.utime(f, (when, when))
    return path


def entry(path, cls=CLASS_REVIEW, **kwargs) -> CacheEntry:
    kwargs.setdefault("remove", True)
    return CacheEntry(
        location_id="t", name=Path(path).name, path=Path(path), cls=cls, **kwargs
    )


@pytest.fixture
def ctx(cache_home):
    project = make_dir(cache_home / "projects" / "app")
    return clean.build_context([project])


# ------------------------------------------------------------- safety rules


def test_review_folder_is_planned(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1")

    plan = clean.make_plan([entry(folder)], ctx)

    assert [i.entry.path for i in plan.items] == [folder]
    assert plan.skipped == []
    assert plan.needs_typed_confirm is True


@pytest.mark.parametrize(
    ("cls", "reason"),
    [
        (CLASS_REPORT, "report only"),
        (CLASS_UNREGISTERED, "not in the registry"),
    ],
)
def test_report_and_unregistered_are_never_planned(cache_home, ctx, cls, reason):
    folder = make_dir(cache_home / ".cache" / "thing")

    plan = clean.make_plan([entry(folder, cls=cls)], ctx)

    assert plan.items == []
    assert plan.skipped[0][1] == reason


@pytest.mark.parametrize(
    "where",
    [
        ".",  # the home folder itself
        ".cache",  # the cache folder itself
        ".ssh",
        "Documents",
        "..",  # above home
        ".claude",
        ".claude/projects",
        "projects/app",  # the launched project
        "projects/app/sub",  # inside a project
        "projects",  # holds a project
        ".cache/../.ssh",  # a path that walks out
    ],
)
def test_hostile_entries_never_reach_a_plan(cache_home, ctx, where):
    target = cache_home / where
    target.mkdir(parents=True, exist_ok=True)

    plan = clean.make_plan([entry(target)], ctx)

    assert plan.items == []
    assert len(plan.skipped) == 1


@pytest.mark.parametrize(
    "where",
    [
        ".password-store",  # a direct child of home that no blocklist names
        ".mozilla",
        "scratch-stuff",
        ".ssh/keys",  # under a credentials folder, at any depth
        ".aws/cli/cache",
        ".gnupg/private-keys-v1.d",
        "Documents/notes/2026",
        "Downloads/a/b/c",
    ],
)
def test_direct_children_of_home_and_credential_trees_are_refused(
    cache_home, ctx, where
):
    target = make_dir(cache_home / where)

    plan = clean.make_plan([entry(target)], ctx)

    assert plan.items == []
    assert plan.skipped[0][1].startswith("refused")
    assert target.exists()


def test_a_path_under_a_symlinked_folder_is_refused(cache_home, ctx, make_symlink):
    real = make_dir(cache_home / "real-data" / "x")
    (cache_home / ".cache").mkdir(exist_ok=True)
    make_symlink(cache_home / ".cache" / "data", real.parent, target_is_directory=True)

    plan = clean.make_plan([entry(cache_home / ".cache" / "data" / "x")], ctx)

    assert plan.items == []
    assert "symlink" in plan.skipped[0][1]
    assert (real / "f0.bak").exists()


def test_a_git_repository_is_never_deleted_even_with_no_known_projects(cache_home):
    nothing_known = clean.build_context([])
    repo = make_dir(cache_home / "work" / "repo")
    (repo / ".git").mkdir()
    inside = make_dir(repo / "build" / "out")

    plan = clean.make_plan([entry(repo), entry(inside)], nothing_known)

    assert plan.items == []
    assert [reason for _, reason in plan.skipped] == ["refused (a git repository)"] * 2
    assert (repo / ".git").exists()


def test_a_cache_that_merely_contains_repositories_can_still_be_cleaned(
    cache_home, ctx
):
    """pre-commit keeps clones under its cache folder: the folder is not a repo."""
    cache = make_dir(cache_home / ".cache" / "pre-commit")
    (make_dir(cache / "repo1") / ".git").mkdir()

    plan = clean.make_plan([entry(cache, cls=CLASS_CLEAN)], ctx)

    assert [i.entry.path for i in plan.items] == [cache]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_making_writable_never_follows_a_link_and_keeps_directories_usable(
    cache_home, make_symlink
):
    outside = make_dir(cache_home / "important")
    outside.chmod(0o755)
    link = cache_home / "link"
    make_symlink(link, outside, target_is_directory=True)
    seen = []

    clean._make_writable_and_retry(lambda target: seen.append(target), str(link), None)

    assert seen == [str(link)]
    assert (outside.stat().st_mode & 0o777) == 0o755  # the target was not touched

    locked = make_dir(cache_home / "locked")
    locked.chmod(0o500)
    clean._make_writable_and_retry(lambda target: None, str(locked), None)

    assert (locked.stat().st_mode & 0o700) == 0o700  # still enterable and writable


def test_removing_a_readonly_tree_raises_no_deprecation_warning(cache_home):
    import warnings

    tree = make_dir(cache_home / "tree")
    (tree / "f0.bak").chmod(0o400)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        clean.remove_path(tree)

    assert not tree.exists()


def test_root_is_refused(ctx):
    root = Path(Path.cwd().anchor)

    assert clean.make_plan([entry(root)], ctx).items == []


def test_outside_home_is_refused(cache_home, ctx, tmp_path_factory):
    other = make_dir(tmp_path_factory.mktemp("elsewhere") / "x")
    ctx.temp_dir = cache_home / "no-such-temp"
    ctx.home = cache_home / "nowhere-home"

    plan = clean.make_plan([entry(other)], ctx)

    assert "outside" in plan.skipped[0][1]


def test_claude_config_dir_override_is_protected(cache_home, monkeypatch):
    custom = make_dir(cache_home / "elsewhere" / "claude-config")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
    context = clean.build_context([])

    assert clean.make_plan([entry(custom)], context).items == []


def test_symlinked_location_is_refused_and_target_untouched(
    cache_home, ctx, make_symlink
):
    real = make_dir(cache_home / "real-data")
    link = cache_home / ".cache" / "agent-link"
    make_symlink(link, real, target_is_directory=True)

    plan = clean.make_plan([entry(link)], ctx)

    assert plan.items == []
    assert "symlink" in plan.skipped[0][1]
    assert real.exists()


def test_symlink_inside_a_tree_is_unlinked_not_followed(cache_home, ctx, make_symlink):
    outside = make_dir(cache_home / "important")
    folder = make_dir(cache_home / ".cache" / "agent-1")
    make_symlink(folder / "link", outside, target_is_directory=True)
    old = time.time() - 30 * 86400
    try:
        os.utime(folder / "link", (old, old), follow_symlinks=False)
    except NotImplementedError:
        pytest.skip("this platform cannot set a symlink's own times")

    clean.execute_plan(clean.make_plan([entry(folder)], ctx), ctx)

    assert not folder.exists()
    assert (outside / "f0.bak").exists()


def test_projects_are_protected_even_when_a_registry_entry_names_one(cache_home, ctx):
    plan = clean.make_plan(
        [entry(cache_home / "projects" / "app", cls=CLASS_CLEAN)], ctx
    )

    assert plan.items == []


# ------------------------------------------------------------------ in use


def test_recently_written_review_folder_is_not_offered(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "busy", age_days=0)

    plan = clean.make_plan([entry(folder)], ctx)

    assert plan.items == []
    assert plan.skipped[0][1] == "in use"


def test_in_use_is_rechecked_at_delete_time(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1")
    plan = clean.make_plan([entry(folder)], ctx)
    assert len(plan.items) == 1

    (folder / "fresh.log").write_text("a session just wrote this")
    results = clean.execute_plan(plan, ctx)

    assert results[0].ok is False
    assert "in use" in results[0].error
    assert folder.exists()


def test_cached_newest_time_marks_in_use_without_walking(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1")
    candidate = entry(folder)
    candidate.size = SizeInfo(size_bytes=1, newest_mtime=time.time() - 60)

    clean.annotate([candidate], ctx)

    assert candidate.blocked == "in use"


def test_clean_class_is_not_subject_to_the_in_use_check(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "ms-playwright", age_days=0)

    plan = clean.make_plan([entry(folder, cls=CLASS_CLEAN)], ctx)

    assert len(plan.items) == 1
    assert plan.needs_typed_confirm is False


# -------------------------------------------------------- commands and rmtree


def test_tool_command_is_preferred_and_run_without_a_shell(
    cache_home, ctx, monkeypatch
):
    folder = make_dir(cache_home / ".cache" / "pip")
    monkeypatch.setattr(clean.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    candidate = entry(folder, cls=CLASS_CLEAN, clean=["pip", "cache", "purge"])
    results = clean.execute_plan(clean.make_plan([candidate], ctx), ctx, runner=runner)

    assert calls[0][0] == ["/usr/bin/pip", "cache", "purge"]  # the resolved path
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == clean.COMMAND_TIMEOUT_SECONDS
    assert results[0].ok is True
    assert folder.exists()  # the tool's command ran; the folder was not rmtree'd


def test_missing_tool_falls_back_to_remove_only_when_allowed(
    cache_home, ctx, monkeypatch
):
    monkeypatch.setattr(clean.shutil, "which", lambda name: None)
    allowed = make_dir(cache_home / ".cache" / "pip")
    denied = make_dir(cache_home / ".cache" / "uv")

    a = entry(allowed, cls=CLASS_CLEAN, clean=["pip", "cache", "purge"], remove=True)
    d = entry(denied, cls=CLASS_CLEAN, clean=["uv", "cache", "clean"], remove=False)
    plan = clean.make_plan([a, d], ctx)

    assert [i.action for i in plan.items] == ["remove"]
    assert plan.skipped[0][1] == "tool not installed"


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (subprocess.CompletedProcess([], 3, b"", b"boom"), "exit 3: boom"),
        (subprocess.TimeoutExpired("pip", 1), "timed out"),
        (FileNotFoundError("no pip"), "no pip"),
    ],
    ids=["exit-code", "timeout", "not-found"],
)
def test_failing_command_is_reported_not_raised(
    cache_home, ctx, monkeypatch, outcome, message
):
    folder = make_dir(cache_home / ".cache" / "pip")
    monkeypatch.setattr(clean.shutil, "which", lambda name: "/bin/pip")

    def runner(argv, **kwargs):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    candidate = entry(folder, cls=CLASS_CLEAN, clean=["pip", "cache", "purge"])
    results = clean.execute_plan(clean.make_plan([candidate], ctx), ctx, runner=runner)

    assert results[0].ok is False
    assert message in results[0].error
    assert folder.exists()


def test_one_failure_does_not_stop_the_rest(cache_home, ctx, monkeypatch):
    first = make_dir(cache_home / ".cache" / "agent-1")
    second = make_dir(cache_home / ".cache" / "agent-2")
    real = clean.remove_path

    def flaky(path):
        if path.name == "agent-1":
            raise PermissionError("denied")
        real(path)

    monkeypatch.setattr(clean, "remove_path", flaky)

    results = clean.execute_plan(
        clean.make_plan([entry(first), entry(second)], ctx), ctx
    )

    assert [r.ok for r in results] == [False, True]
    assert "denied" in results[0].error
    assert first.exists()
    assert not second.exists()


def test_freed_bytes_are_measured(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1", files=3)

    results = clean.execute_plan(clean.make_plan([entry(folder)], ctx), ctx)

    assert results[0].freed_bytes >= 3 * 4096
    assert clean.summarize_results(results) == results[0].freed_bytes


def test_duplicates_are_planned_once(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1")

    plan = clean.make_plan([entry(folder), entry(folder)], ctx)

    assert len(plan.items) == 1


def test_vanished_folder_is_skipped(cache_home, ctx):
    plan = clean.make_plan([entry(cache_home / ".cache" / "gone")], ctx)

    assert plan.skipped[0][1] == "already gone"


def test_remove_path_handles_files_and_readonly_trees(cache_home):
    lone = cache_home / "lone.txt"
    lone.write_text("x")
    clean.remove_path(lone)
    tree = make_dir(cache_home / "tree")
    (tree / "f0.bak").chmod(0o400)

    clean.remove_path(tree)

    assert not lone.exists()
    assert not tree.exists()


def test_annotate_sets_blocked(cache_home, ctx):
    folder = make_dir(cache_home / ".cache" / "agent-1")
    ok, reported = entry(folder), entry(folder, cls=CLASS_REPORT)

    clean.annotate([ok, reported], ctx)

    assert ok.blocked is None
    assert reported.blocked == "report only"
