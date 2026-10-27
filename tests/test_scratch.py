"""Tests for per-session scratch folders and pruning."""

import os
import time
from pathlib import Path

import pytest

from ai_launcher.core import cache_clean as clean
from ai_launcher.core import scratch
from ai_launcher.core.cache_data import SESSION_FILE
from ai_launcher.core.cache_registry import scratch_root

DAY = 86400


def fill(path: Path, age_days: float, name: str = "f.bak") -> None:
    path.mkdir(parents=True, exist_ok=True)
    f = path / name
    f.write_bytes(b"x" * 4096)
    when = time.time() - age_days * DAY
    os.utime(f, (when, when))


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("ai-launcher", "ai-launcher"),
        ("cable_modem_monitor", "cable_modem_monitor"),
        ("my project/v2", "my_project_v2"),
        ("../../etc", "etc"),
        ("", "project"),
        ("***", "project"),
    ],
)
def test_project_slug(name, slug):
    assert scratch.project_slug(name) == slug


def test_session_dir_is_created_under_the_scratch_root(cache_home):
    path = scratch.create_session_dir("ai-launcher", pid=4242)

    assert path.parent == scratch_root() / "ai-launcher"
    assert path.name.endswith("-4242")
    assert (path / SESSION_FILE).read_text() == "4242"


def test_env_names_the_folder(cache_home):
    path = scratch.create_session_dir("p")

    assert scratch.scratch_env(path) == {"AI_SCRATCH_DIR": str(path)}


def test_empty_session_dir_is_removed_at_exit(cache_home):
    path = scratch.create_session_dir("p")

    scratch.finish_session_dir(path)

    assert not path.exists()
    assert not path.parent.exists()  # the empty project folder goes too


def test_non_empty_session_dir_is_kept_at_exit(cache_home):
    path = scratch.create_session_dir("p")
    (path / "patch.diff").write_text("work")

    scratch.finish_session_dir(path)

    assert (path / "patch.diff").exists()
    assert not (path / SESSION_FILE).exists()  # a finished session leaves no lock


def test_finish_survives_a_vanished_folder(cache_home):
    scratch.finish_session_dir(cache_home / "nowhere")


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("14d", 14 * DAY), ("36h", 36 * 3600), ("2w", 14 * DAY), (" 7D ", 7 * DAY)],
)
def test_parse_duration(text, seconds):
    assert scratch.parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "14", "d", "0d", "-3d", "1.5d", "14 days", "3m"])
def test_parse_duration_rejects_the_rest(text):
    with pytest.raises(ValueError, match="bad duration"):
        scratch.parse_duration(text)


@pytest.fixture
def ctx(cache_home):
    return clean.build_context([])


def test_prune_picks_only_old_idle_sessions(cache_home, ctx):
    root = scratch_root()
    fill(root / "p" / "old", age_days=20)
    fill(root / "p" / "fresh", age_days=2)
    fill(root / "p" / "mid", age_days=13)

    plan = scratch.prune_candidates(14 * DAY, ctx)

    assert [i.entry.path.name for i in plan.items] == ["old"]


def test_prune_never_offers_a_live_session(cache_home, ctx):
    root = scratch_root()
    live = root / "p" / "live"
    fill(live, age_days=20)
    (live / SESSION_FILE).write_text(str(os.getpid()))
    old = time.time() - 20 * DAY
    os.utime(live / SESSION_FILE, (old, old))  # a session that started long ago

    plan = scratch.prune_candidates(14 * DAY, ctx)

    assert plan.items == []
    assert plan.skipped[0][1] == "in use"


def test_prune_reaches_nothing_outside_the_managed_folder(cache_home, ctx):
    fill(cache_home / ".cache" / "my-agent-1", age_days=90)
    fill(cache_home / ".cache" / "ai-launcher" / "other" / "x", age_days=90)
    fill(scratch_root() / "stray-file-level", age_days=90)  # one level only

    plan = scratch.prune_candidates(DAY, ctx)

    assert plan.items == []
    assert (cache_home / ".cache" / "my-agent-1").exists()


def test_prune_does_not_follow_symlinked_projects(cache_home, ctx, make_symlink):
    elsewhere = cache_home / "elsewhere"
    fill(elsewhere / "session", age_days=90)
    scratch_root().mkdir(parents=True)
    make_symlink(scratch_root() / "linked", elsewhere, target_is_directory=True)

    assert scratch.prune_candidates(DAY, ctx).items == []


def test_prune_counts_an_empty_old_folder(cache_home, ctx):
    session = scratch_root() / "p" / "empty"
    session.mkdir(parents=True)
    old = time.time() - 40 * DAY
    os.utime(session, (old, old))

    assert len(scratch.prune_candidates(14 * DAY, ctx).items) == 1


def test_tidy_removes_empty_project_folders_only(cache_home):
    (scratch_root() / "empty").mkdir(parents=True)
    fill(scratch_root() / "full" / "s", age_days=1)

    scratch.tidy_empty_projects()

    assert not (scratch_root() / "empty").exists()
    assert (scratch_root() / "full").exists()


def test_statement_names_the_folder_and_what_to_keep(cache_home):
    text = scratch.SCRATCH_STATEMENT.format(path="/x/y")

    assert "/x/y" in text
    assert "worth keeping belongs in the project" in text


def test_prune_skips_a_session_folder_that_vanished_mid_listing(
    cache_home, ctx, monkeypatch
):
    root = scratch_root()
    fill(root / "p" / "old", age_days=20)
    ghost = root / "p" / "vanished"
    real_subdirs = scratch._subdirs
    monkeypatch.setattr(
        scratch,
        "_subdirs",
        lambda path: (
            [*real_subdirs(path), ghost] if path.name == "p" else real_subdirs(path)
        ),
    )

    plan = scratch.prune_candidates(14 * DAY, ctx)  # must not raise

    assert [i.entry.path.name for i in plan.items] == ["old"]
