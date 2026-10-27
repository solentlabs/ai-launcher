"""Cache and scratch wired into the launcher: launch, picker, Claude, the CLI."""

import os
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from ai_launcher import cli
from ai_launcher.cli import app, launch_ai, prepare_scratch, start_size_refresh
from ai_launcher.core import scratch
from ai_launcher.core.cache_data import (
    ROW_DISK,
    ROW_SCRATCH,
    SEVERITY_ATTENTION,
    SEVERITY_CRITICAL,
    CacheNotice,
    DiskStatus,
)
from ai_launcher.core.cache_registry import scratch_root
from ai_launcher.core.models import ConfigData, Project, Selection
from ai_launcher.providers.base import ProviderMetadata
from ai_launcher.ui import cache_page
from ai_launcher.ui.startup_report import _visual_length, display_launch_info

runner = CliRunner()
GB = 1024**3


# ----------------------------------------------------------------- launch_ai


@pytest.fixture
def provider():
    mock = MagicMock()
    type(mock).metadata = PropertyMock(
        return_value=ProviderMetadata(
            name="test", display_name="Test", command="test", description="d"
        )
    )
    return mock


def test_launch_sets_scratch_dir_env_and_removes_the_empty_folder(
    cache_home, provider, monkeypatch, tmp_path
):
    project = tmp_path / "proj"
    project.mkdir()
    seen = {}

    def fake_launch(*args, **kwargs):
        seen["env"] = os.environ.get("AI_SCRATCH_DIR")
        seen["exists"] = Path(seen["env"]).is_dir()

    provider.launch_with_title.side_effect = fake_launch
    monkeypatch.setattr(cli, "display_launch_info", MagicMock())

    launch_ai(project, provider=provider, config=ConfigData())

    assert Path(seen["env"]).parent == scratch_root() / "proj"
    assert seen["exists"] is True
    assert not Path(seen["env"]).exists()  # nothing was put in it, so it is gone


def test_launch_keeps_a_scratch_folder_the_session_filled(
    cache_home, provider, monkeypatch, tmp_path
):
    project = tmp_path / "proj"
    project.mkdir()

    def fake_launch(*args, **kwargs):
        (Path(os.environ["AI_SCRATCH_DIR"]) / "patch.diff").write_text("work")

    provider.launch_with_title.side_effect = fake_launch
    monkeypatch.setattr(cli, "display_launch_info", MagicMock())

    launch_ai(project, provider=provider, config=ConfigData())

    kept = list((scratch_root() / "proj").iterdir())
    assert len(kept) == 1
    assert (kept[0] / "patch.diff").exists()


def test_scratch_folder_is_finished_even_when_the_launch_exits(
    cache_home, provider, monkeypatch, tmp_path
):
    project = tmp_path / "proj"
    project.mkdir()
    provider.launch_with_title.side_effect = SystemExit(1)
    monkeypatch.setattr(cli, "display_launch_info", MagicMock())

    with pytest.raises(SystemExit):
        launch_ai(project, provider=provider, config=ConfigData())

    assert not scratch_root().exists() or not any(scratch_root().rglob("*"))


def test_launch_passes_the_notice_to_the_box(
    cache_home, provider, monkeypatch, tmp_path
):
    notice = CacheNotice(key=ROW_SCRATCH, severity=SEVERITY_ATTENTION, count=3)
    monkeypatch.setattr("ai_launcher.core.cache_notice.launch_notice", lambda: notice)
    display = MagicMock()
    monkeypatch.setattr(cli, "display_launch_info", display)

    launch_ai(tmp_path, provider=provider, config=ConfigData())

    assert display.call_args.kwargs["notice"] is notice


def test_a_scratch_folder_that_cannot_be_made_does_not_stop_the_launch(
    cache_home, provider, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        scratch,
        "create_session_dir",
        lambda name: (_ for _ in ()).throw(OSError("full")),
    )
    display = MagicMock()
    monkeypatch.setattr(cli, "display_launch_info", display)

    launch_ai(tmp_path, provider=provider, config=ConfigData())

    assert prepare_scratch(tmp_path) is None
    assert display.call_args.kwargs["scratch_dir"] is None
    provider.launch_with_title.assert_called_once()


def test_start_size_refresh_never_raises(cache_home, monkeypatch):
    monkeypatch.setattr(
        "ai_launcher.core.cache_registry.load_registry",
        lambda: (_ for _ in ()).throw(RuntimeError("x")),
    )

    start_size_refresh()


def test_start_size_refresh_respects_the_off_switch(cache_home, monkeypatch):
    from ai_launcher.core import cache_scan
    from ai_launcher.core.cache_registry import load_registry

    registry = load_registry(platform="linux", user_file=cache_home / "none")
    registry.notice.enabled = False
    monkeypatch.setattr(
        "ai_launcher.core.cache_registry.load_registry", lambda: registry
    )
    monkeypatch.setattr(
        cache_scan, "start_background_refresh", lambda *a, **k: pytest.fail("started")
    )

    start_size_refresh()


# ----------------------------------------------------------------- launch box


def make_box_provider():
    provider = MagicMock()
    type(provider).metadata = PropertyMock(
        return_value=ProviderMetadata(
            name="t", display_name="Test", command="t", description="d"
        )
    )
    from ai_launcher.core.provider_data import ProviderPreviewData

    provider.collect_preview_data.return_value = ProviderPreviewData(
        provider_name="Test"
    )
    del provider.get_version
    return provider


@pytest.mark.parametrize(
    ("notice", "expected"),
    [
        (
            CacheNotice(
                key=ROW_DISK,
                severity=SEVERITY_CRITICAL,
                disk=DiskStatus("C:", "/mnt/c", 238 * GB, 7 * GB),
            ),
            "Disk C: 97% full (7 GB free) · ai-launcher cache",
        ),
        (
            CacheNotice(
                key=ROW_SCRATCH,
                severity=SEVERITY_ATTENTION,
                total_bytes=41 * GB,
                count=3,
            ),
            "41 GB in 3 scratch folders · ai-launcher cache",
        ),
    ],
    ids=["disk", "scratch"],
)
def test_box_shows_the_notice_line_and_fits(tmp_path, capsys, notice, expected):
    display_launch_info(tmp_path, make_box_provider(), verbose=True, notice=notice)

    lines = capsys.readouterr().out.splitlines()
    line = next(line for line in lines if "Cache:" in line or "🔴" in line)
    assert expected in cache_page.strip_ansi(line)
    assert _visual_length(cache_page.strip_ansi(line)) == 85


def test_critical_notice_is_red_and_a_mild_one_is_not(tmp_path, capsys):
    critical = CacheNotice(
        key=ROW_SCRATCH, severity=SEVERITY_CRITICAL, total_bytes=GB, count=2
    )
    mild = CacheNotice(
        key=ROW_SCRATCH, severity=SEVERITY_ATTENTION, total_bytes=GB, count=2
    )

    display_launch_info(tmp_path, make_box_provider(), verbose=True, notice=critical)
    red = capsys.readouterr().out
    display_launch_info(tmp_path, make_box_provider(), verbose=True, notice=mild)
    plain = capsys.readouterr().out

    assert "\033[31m" in red and "🔴" in red
    assert "\033[31m" not in plain


def test_no_notice_means_no_cache_line(tmp_path, capsys):
    display_launch_info(tmp_path, make_box_provider(), verbose=True)

    assert "Cache:" not in capsys.readouterr().out


def test_box_names_the_scratch_folder_and_shortens_a_long_one(tmp_path, capsys):
    deep = tmp_path.joinpath(*["a-long-folder-name"] * 8, "20261015-101010-1")

    display_launch_info(tmp_path, make_box_provider(), verbose=True, scratch_dir=deep)

    line = next(l for l in capsys.readouterr().out.splitlines() if "Scratch:" in l)
    assert "$AI_SCRATCH_DIR →" in line
    assert "…" in line and line.rstrip("│ ").endswith("20261015-101010-1")
    assert _visual_length(line) == 85


# ----------------------------------------------------------------- Claude


def claude_cmd(project, env=None):
    from ai_launcher.providers.claude import ClaudeProvider

    with patch("subprocess.run") as run, patch("os.chdir"), patch.dict(
        os.environ, env or {}, clear=False
    ):
        ClaudeProvider().launch(project)
    return run.call_args[0][0]


def test_claude_is_asked_to_use_the_scratch_folder(tmp_path):
    cmd = claude_cmd(tmp_path, {"AI_SCRATCH_DIR": "/x/scratch/p/1"})

    statement = cmd[cmd.index("--append-system-prompt") + 1]
    assert "/x/scratch/p/1" in statement
    assert "worth keeping belongs in the project" in statement
    assert "changes belong in this project" in statement  # the scope statement stays


def test_claude_gets_no_scratch_sentence_without_the_variable(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_SCRATCH_DIR", raising=False)

    cmd = claude_cmd(tmp_path)

    assert "AI_SCRATCH_DIR" not in cmd[cmd.index("--append-system-prompt") + 1]


# ----------------------------------------------------------------- the CLI


def test_clean_cache_flag_is_gone(tmp_path):
    result = runner.invoke(app, ["claude", str(tmp_path), "--clean-cache"])

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_cache_list_prints_the_table_and_deletes_nothing(cache_home):
    folder = cache_home / ".cache" / "ms-playwright"
    folder.mkdir()
    (folder / "browser").write_bytes(b"x" * 4096)

    result = runner.invoke(app, ["cache", "--list"])

    assert result.exit_code == 0
    assert "DISK" in result.output and "Playwright" in result.output
    assert (folder / "browser").exists()


def test_cache_protects_projects_found_under_the_scan_path(cache_home):
    root = cache_home / "projects"
    (root / "app" / ".git").mkdir(parents=True)

    assert cli._project_paths([root], None) == [(root / "app").resolve()]
    manual = cache_home / "notes"
    manual.mkdir()
    assert manual in cli._project_paths(None, str(manual))


def test_cache_without_fzf_exits(cache_home, monkeypatch):
    monkeypatch.setattr("ai_launcher.utils.fzf.ensure_fzf", lambda: False)

    result = runner.invoke(app, ["cache"])

    assert result.exit_code == 1


def test_cache_runs_the_page_with_the_projects(cache_home, monkeypatch):
    monkeypatch.setattr("ai_launcher.utils.fzf.ensure_fzf", lambda: True)
    page = MagicMock()
    monkeypatch.setattr(cache_page, "run_cache_page", page)

    result = runner.invoke(app, ["cache"])

    assert result.exit_code == 0
    page.assert_called_once_with([])


def test_scratch_prune_exit_codes(cache_home):
    old = scratch_root() / "p" / "old"
    old.mkdir(parents=True)
    (old / "f.bak").write_text("x")
    when = 1_000_000_000
    os.utime(old / "f.bak", (when, when))

    assert (
        runner.invoke(app, ["scratch", "prune"]).exit_code != 0
    )  # --older-than is required
    assert (
        runner.invoke(app, ["scratch", "prune", "--older-than", "soon"]).exit_code == 2
    )
    assert (
        runner.invoke(
            app, ["scratch", "prune", "--older-than", "14d", "--dry-run"]
        ).exit_code
        == 0
    )
    assert old.exists()
    # no terminal under the test runner and no --yes: nothing removed, non-zero
    assert (
        runner.invoke(app, ["scratch", "prune", "--older-than", "14d"]).exit_code == 1
    )
    assert old.exists()
    assert (
        runner.invoke(
            app, ["scratch", "prune", "--older-than", "14d", "--yes"]
        ).exit_code
        == 0
    )
    assert not old.exists()


# ----------------------------------------------------------------- the picker


def run_picker(tmp_path, rows_picked):
    from ai_launcher.ui.selector import select_project

    project_path = tmp_path / "my-proj"
    project_path.mkdir(exist_ok=True)
    project = Project.from_path(project_path, is_manual=False)
    choice = f"{project_path}\t\tmy-proj"
    procs = []
    for row in rows_picked:
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate.return_value = (f"\n{row or choice}\n".encode(), b"")
        procs.append(proc)
    with patch("subprocess.Popen", side_effect=procs) as popen, patch(
        "ai_launcher.ui.selector.build_tree_view",
        return_value=([choice], {choice: project}),
    ), patch("ai_launcher.ui.selector.clear_screen"):
        result = select_project([project])
    return result, popen, procs, project


def test_picker_has_a_cache_row_below_configuration(tmp_path, cache_home):
    result, _, procs, project = run_picker(tmp_path, [None])

    sent = procs[0].communicate.call_args.kwargs["input"].decode().splitlines()
    assert sent[-3].endswith("🔧 Configuration")
    assert sent[-2].startswith("__ACTION__\t\t💾 Cache and scratch")
    assert result == Selection(project)


def test_enter_on_the_cache_row_opens_the_page_then_returns_to_the_picker(
    tmp_path, cache_home, monkeypatch
):
    page = MagicMock()
    monkeypatch.setattr(cache_page, "run_cache_page", page)

    result, _, _, project = run_picker(
        tmp_path, ["__ACTION__\t\t💾 Cache and scratch  🔴", None]
    )

    page.assert_called_once()
    assert page.call_args[0][0] == [
        project.path
    ]  # the page knows which folders are projects
    assert result == Selection(project)


@pytest.mark.parametrize(
    ("severity", "symbol"),
    [(0, ""), (1, ""), (2, "🟡"), (3, "🔴"), (-1, "")],
    ids=["report", "fine", "attention", "critical", "error"],
)
def test_cache_row_symbol_follows_the_worst_severity(monkeypatch, severity, symbol):
    from ai_launcher.ui import selector

    monkeypatch.setattr(
        "ai_launcher.core.cache_notice.worst_severity", lambda: severity
    )

    label = selector.cache_row_label()

    assert label == (
        f"{selector.CACHE_ROW}  {symbol}" if symbol else selector.CACHE_ROW
    )


def test_picker_row_preview_is_the_summary(cache_home, monkeypatch):
    from ai_launcher.ui import _preview_helper

    monkeypatch.setattr(
        "sys.argv", ["helper", "__ACTION__\t\t💾 Cache and scratch  🔴"]
    )
    printed = []
    monkeypatch.setattr(
        "builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a)))
    )

    _preview_helper.main()

    assert "Cache and scratch" in cache_page.strip_ansi("\n".join(printed))


def test_cache_preview_helper_dispatches_by_row_kind(cache_home, monkeypatch, capsys):
    from ai_launcher.ui import _cache_preview_helper as helper

    folder = cache_home / ".cache" / "my-agent-1"
    folder.mkdir()
    (folder / "a.log").write_text("hidden contents")

    for argv, expected in (
        (f"E:{folder}\t\tshown", "a.log"),
        ("S:SCRATCH\t\tshown", "SCRATCH"),
    ):
        monkeypatch.setattr("sys.argv", ["helper", argv])
        helper.main()
        out = cache_page.strip_ansi(capsys.readouterr().out)
        assert expected in out
        assert "hidden contents" not in out

    monkeypatch.setattr("sys.argv", ["helper"])
    helper.main()
    assert capsys.readouterr().out == ""


def test_a_launch_error_before_the_session_starts_still_cleans_the_scratch_folder(
    cache_home, provider, monkeypatch, tmp_path
):
    project = tmp_path / "proj"
    project.mkdir()
    seen = {}

    def boom(*args, **kwargs):
        seen["dir"] = Path(os.environ["AI_SCRATCH_DIR"])
        raise RuntimeError("box failed")

    monkeypatch.setattr(cli, "display_launch_info", boom)

    with pytest.raises(RuntimeError, match="box failed"):
        launch_ai(project, provider=provider, config=ConfigData())

    assert not seen["dir"].exists()  # finished, and an empty folder is removed


def test_sibling_lines_survive_an_unreadable_parent_folder(tmp_path, monkeypatch):
    from ai_launcher.ui.startup_report import _check_sibling_projects

    def refuse(self):
        raise PermissionError("no")

    monkeypatch.setattr(Path, "iterdir", refuse)

    info = _check_sibling_projects(tmp_path / "proj")

    assert info["sibling_count"] == 0 and info["sibling_names"] == []


def test_a_failed_scratch_folder_does_not_leave_an_inherited_one_in_place(
    cache_home, monkeypatch, tmp_path
):
    monkeypatch.setenv("AI_SCRATCH_DIR", str(tmp_path / "an-older-session"))
    monkeypatch.setattr(
        scratch,
        "create_session_dir",
        lambda name: (_ for _ in ()).throw(OSError("full")),
    )

    assert prepare_scratch(tmp_path / "proj") is None

    assert "AI_SCRATCH_DIR" not in os.environ


def test_a_file_not_found_from_the_cache_page_is_not_reported_as_a_missing_fzf(
    tmp_path, cache_home, monkeypatch, capsys
):
    monkeypatch.setattr(
        cache_page,
        "run_cache_page",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("a scratch file")),
    )

    with pytest.raises(SystemExit) as stopped:
        run_picker(tmp_path, ["__ACTION__\t\t💾 Cache and scratch", None])

    assert stopped.value.code == 1
    out = capsys.readouterr().out
    assert "Error in project selector: a scratch file" in out
    assert "install fzf" not in out.lower()


@pytest.mark.parametrize(
    ("enabled", "npm", "expected"),
    [(True, True, 1), (True, False, 0), (False, True, 0)],
    ids=["asked-for", "flag-off", "cleanup-disabled"],
)
def test_clean_npm_runs_only_when_asked(
    cache_home, provider, monkeypatch, tmp_path, enabled, npm, expected
):
    from ai_launcher.core.models import CleanupConfig
    from ai_launcher.utils import cleanup

    calls = []
    monkeypatch.setattr(cleanup, "clean_npm_cache", lambda **kw: calls.append(kw))
    monkeypatch.setattr(cli, "display_launch_info", MagicMock())
    project = tmp_path / "proj"
    project.mkdir()
    config = ConfigData(cleanup=CleanupConfig(enabled=enabled, clean_npm_cache=npm))

    launch_ai(project, provider=provider, config=config)

    assert len(calls) == expected
