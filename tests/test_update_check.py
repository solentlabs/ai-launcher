"""Tests for the opt-in update check: setting, saved result, thread, launch line."""

import json
from unittest.mock import MagicMock

import pytest

from ai_launcher import cli
from ai_launcher.cli import launch_ai, start_update_check
from ai_launcher.core import cache_registry as reg
from ai_launcher.core import update_check as uc
from ai_launcher.core.models import ConfigData
from ai_launcher.core.self_update import UpdateError
from ai_launcher.ui import cache_page
from ai_launcher.ui.startup_report import _visual_length, display_launch_info
from tests.test_cache_integration import make_box_provider

DAY = 24 * 3600


def registry_with(cache_home, text):
    user = cache_home / "user.toml"
    user.write_text(text, encoding="utf-8")
    return reg.load_registry(platform="linux", user_file=user)


@pytest.fixture
def state(cache_home):
    return cache_home / "update-check.json"


# ------------------------------------------------------------------- setting


@pytest.mark.parametrize(
    ("text", "enabled", "warnings"),
    [
        (None, False, 0),
        ("[update]\ncheck = true\n", True, 0),
        ("[update]\ncheck = false\n", False, 0),
        ('[update]\ncheck = "yes"\n', False, 1),
        ("[update]\nbogus = 1\n", False, 1),
        ("update = 3\n", False, 0),
    ],
    ids=["absent", "on", "off", "wrong-type", "unknown-key", "not-a-table"],
)
def test_update_check_setting(cache_home, text, enabled, warnings):
    if text is None:
        registry = reg.load_registry(platform="linux", user_file=cache_home / "none")
    else:
        registry = registry_with(cache_home, text)

    assert registry.update_check is enabled
    assert len(registry.warnings) == warnings


# --------------------------------------------------------------- saved result


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, {}),
        ("not json", {}),
        ("[1, 2]", {}),
        ('{"checked_at": 5, "latest": "0.9.0"}', {"checked_at": 5, "latest": "0.9.0"}),
    ],
    ids=["missing", "damaged", "wrong-shape", "good"],
)
def test_load_state(state, content, expected):
    if content is not None:
        state.write_text(content, encoding="utf-8")

    assert uc.load_state(state) == expected


@pytest.mark.parametrize(
    ("saved_at", "now", "due"),
    [
        (None, 1000.0, True),
        (1000.0, 1000.0 + DAY - 1, False),
        (1000.0, 1000.0 + DAY, True),
        ("soon", 1000.0, True),
    ],
    ids=["never", "just-under", "exactly-a-day", "garbage"],
)
def test_check_is_due(saved_at, now, due):
    data = {} if saved_at is None else {"checked_at": saved_at}

    assert uc.is_due(data, now) is due


def test_check_now_saves_the_answer_and_the_time(state):
    assert uc.check_now(lambda: "0.9.0", state, now=50.0) == "0.9.0"

    assert json.loads(state.read_text()) == {"checked_at": 50.0, "latest": "0.9.0"}
    assert (state.stat().st_mode & 0o777) == 0o600


def test_a_failed_check_saves_nothing_so_the_next_launch_retries(state):
    def broken():
        raise UpdateError("offline")

    assert uc.check_now(broken, state, now=50.0) is None
    assert not state.exists()


def test_a_failed_check_keeps_the_previous_answer(state):
    state.write_text('{"checked_at": 1, "latest": "0.9.0"}', encoding="utf-8")

    uc.check_now(lambda: (_ for _ in ()).throw(UpdateError("x")), state, now=50.0)

    assert uc.load_state(state)["latest"] == "0.9.0"


# ---------------------------------------------------------------- the thread


def test_background_check_runs_when_opted_in_and_due(state):
    seen = []

    thread = uc.start_check(True, state, fetch=lambda: seen.append(1) or "0.9.0")
    thread.join(5)

    assert seen == [1]
    assert uc.load_state(state)["latest"] == "0.9.0"


@pytest.mark.parametrize(
    ("enabled", "saved"),
    [(False, None), (True, 1_000_000_000.0)],
    ids=["opted-out", "checked-recently"],
)
def test_background_check_stays_quiet(state, enabled, saved):
    if saved is not None:
        state.write_text(json.dumps({"checked_at": saved}), encoding="utf-8")

    thread = uc.start_check(
        enabled,
        state,
        fetch=lambda: pytest.fail("contacted PyPI"),
        now=saved or 0.0,
    )

    assert thread is None


def test_cli_hook_never_raises_and_respects_the_setting(cache_home, monkeypatch):
    registry = reg.load_registry(platform="linux", user_file=cache_home / "none")
    seen = []
    monkeypatch.setattr(uc, "start_check", lambda enabled: seen.append(enabled))
    monkeypatch.setattr(reg, "load_registry", lambda: registry)

    start_update_check()

    assert seen == [False]  # off by default

    monkeypatch.setattr(
        reg, "load_registry", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )

    start_update_check()  # must not raise


# --------------------------------------------------------------- the notice


@pytest.mark.parametrize(
    ("enabled", "saved", "installed", "expected"),
    [
        (True, {"latest": "0.9.0"}, "0.8.0", ("0.9.0", "0.8.0")),
        (True, {"latest": "0.8.0"}, "0.8.0", None),
        (True, {"latest": "0.7.0"}, "0.8.0", None),
        (True, {}, "0.8.0", None),
        (True, {"latest": "junk"}, "0.8.0", None),
        (False, {"latest": "0.9.0"}, "0.8.0", None),
    ],
    ids=["newer", "current", "older", "no-result", "unreadable", "opted-out"],
)
def test_update_notice(state, enabled, saved, installed, expected):
    state.write_text(json.dumps(saved), encoding="utf-8")

    notice = uc.update_notice(enabled, installed, state)

    assert (notice and (notice.latest, notice.installed)) == expected


def test_update_notice_never_raises(state, monkeypatch):
    monkeypatch.setattr(uc, "load_state", lambda *a: (_ for _ in ()).throw(OSError()))

    assert uc.update_notice(True, "0.8.0", state) is None


# ----------------------------------------------------------------- launch box


def test_box_shows_the_update_line_and_fits(tmp_path, capsys):
    notice = uc.UpdateNotice(latest="0.9.0", installed="0.8.0")

    display_launch_info(
        tmp_path, make_box_provider(), verbose=True, update_notice=notice
    )

    line = next(
        line for line in capsys.readouterr().out.splitlines() if "Update:" in line
    )
    plain = cache_page.strip_ansi(line)
    assert "0.9.0 is available (you have 0.8.0) · ai-launcher update" in plain
    assert _visual_length(plain) == 85


def test_no_update_notice_means_no_update_line(tmp_path, capsys):
    display_launch_info(tmp_path, make_box_provider(), verbose=True)

    assert "Update:" not in capsys.readouterr().out


def test_launch_passes_the_update_notice_to_the_box(cache_home, monkeypatch, tmp_path):
    notice = uc.UpdateNotice(latest="0.9.0", installed="0.8.0")
    monkeypatch.setattr(uc, "update_notice", lambda *a, **k: notice)
    display = MagicMock()
    monkeypatch.setattr(cli, "display_launch_info", display)
    provider = MagicMock()

    launch_ai(tmp_path, provider=provider, config=ConfigData())

    assert display.call_args.kwargs["update_notice"] is notice


# ------------------------------------------------------- defaults and failures


def test_state_path_is_beside_the_size_cache(cache_home):
    from ai_launcher.core.cache_scan import size_cache_path

    assert uc.state_path() == size_cache_path().parent / "update-check.json"


def test_an_unwritable_state_folder_is_swallowed(state, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(uc.tempfile, "mkstemp", refuse)

    assert uc.check_now(lambda: "0.9.0", state, now=1.0) == "0.9.0"  # no raise
    assert not state.exists()


def test_a_failed_replace_cleans_up_its_temp_file(state, monkeypatch):
    def refuse(self, target):
        raise OSError("busy")

    monkeypatch.setattr(uc.Path, "replace", refuse)

    uc.check_now(lambda: "0.9.0", state, now=1.0)

    assert not list(state.parent.glob(".update-*"))


@pytest.mark.parametrize(
    ("enabled", "saved", "expected"),
    [(True, {"latest": "0.9.0"}, "0.9.0"), (False, {"latest": "0.9.0"}, None)],
    ids=["opted-in", "opted-out"],
)
def test_current_update_notice_follows_the_setting(
    cache_home, monkeypatch, enabled, saved, expected
):
    from ai_launcher.cli import current_update_notice

    registry = reg.load_registry(platform="linux", user_file=cache_home / "none")
    registry.update_check = enabled
    monkeypatch.setattr(reg, "load_registry", lambda: registry)
    uc.state_path().parent.mkdir(parents=True, exist_ok=True)
    uc.state_path().write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr("ai_launcher.cli.__version__", "0.8.0")

    notice = current_update_notice()

    assert (notice.latest if notice else None) == expected


def test_current_update_notice_never_raises(monkeypatch):
    from ai_launcher.cli import current_update_notice

    monkeypatch.setattr(
        reg, "load_registry", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )

    assert current_update_notice() is None
