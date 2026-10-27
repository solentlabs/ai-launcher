"""Tests for the About row: label, preview, and Enter running the update flow."""

import json
from unittest.mock import MagicMock

import pytest

from ai_launcher.core import self_update as su
from ai_launcher.ui import about, cache_page
from ai_launcher.ui import update as update_ui
from tests.test_cache_integration import run_picker

ABOUT_LINE = f"__ACTION__\t\t{about.ABOUT_ROW}"


@pytest.fixture
def state(cache_home):
    return cache_home / "update-check.json"


def preview(plan=None, enabled=False, installed="0.8.0", state_file=None):
    plan = plan or su.UpdatePlan(su.PIP, argv=["py"], display=["py"])
    return cache_page.strip_ansi(
        about.render_about(plan, enabled, installed, state_file, "~/c.toml")
    )


# ------------------------------------------------------------------- label


@pytest.mark.parametrize(
    ("saved", "enabled", "marked"),
    [
        ({"latest": "0.9.0"}, True, True),
        ({"latest": "0.8.0"}, True, False),
        ({}, True, False),
        ({"latest": "0.9.0"}, False, False),
    ],
    ids=["newer", "current", "unchecked", "opted-out"],
)
def test_row_label_marks_a_newer_release(state, saved, enabled, marked):
    state.write_text(json.dumps(saved), encoding="utf-8")

    label = about.about_row_label(enabled, "0.8.0", state)

    assert label == (f"{about.ABOUT_ROW}  🆕" if marked else about.ABOUT_ROW)


# ----------------------------------------------------------------- preview


@pytest.mark.parametrize(
    ("plan", "enabled", "saved", "expected"),
    [
        (None, True, {"checked_at": 0, "latest": "0.9.0"}, ["0.9.0 is available"]),
        (None, True, {"checked_at": 0, "latest": "0.8.0"}, ["up to date"]),
        (None, True, {}, ["not checked yet"]),
        (None, False, {}, ["off", "[update]", "check = true", "~/c.toml"]),
        (su.UpdatePlan(su.PIPX, argv=["pipx"]), False, {}, ["pipx"]),
        (su.UpdatePlan(su.EDITABLE, note="n"), False, {}, ["editable"]),
        (su.UpdatePlan(su.SOURCE, note="n"), False, {}, ["source"]),
        (su.UpdatePlan(su.PIP, argv=["py"]), False, {}, ["pip"]),
    ],
    ids=["newer", "current", "unchecked", "off", "pipx", "editable", "source", "pip"],
)
def test_preview_content(state, plan, enabled, saved, expected):
    state.write_text(json.dumps(saved), encoding="utf-8")

    text = preview(plan, enabled, state_file=state)

    assert "0.8.0" in text and "Enter" in text
    for fragment in expected:
        assert fragment in text


def test_preview_makes_no_network_call(state, monkeypatch):
    monkeypatch.setattr(su, "fetch_latest", lambda *a, **k: pytest.fail("network"))

    preview(enabled=True, state_file=state)


def test_helper_prints_the_preview(cache_home, monkeypatch):
    from ai_launcher.ui import _preview_helper

    monkeypatch.setattr("sys.argv", ["helper", f"__ACTION__\t\t{about.ABOUT_ROW}  🆕"])
    printed = []
    monkeypatch.setattr(
        "builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a)))
    )

    _preview_helper.main()

    assert "About" in cache_page.strip_ansi("\n".join(printed))


# ------------------------------------------------------------- Enter on it


def test_run_about_clears_the_picker_then_runs_the_update_flow_then_waits(
    monkeypatch,
):
    # fzf runs with --no-clear, so its frame is still up: clear it first
    order = []
    monkeypatch.setattr(
        "ai_launcher.ui.selector.clear_screen", lambda: order.append("clear")
    )
    monkeypatch.setattr(
        update_ui, "update_command", lambda **k: order.append(("update", k)) or 0
    )

    about.run_about(input_fn=lambda prompt: order.append("wait") or "")

    assert order == ["clear", ("update", {"check": False, "yes": False}), "wait"]


def test_run_about_survives_ctrl_c_at_the_pause(monkeypatch):
    monkeypatch.setattr(update_ui, "update_command", lambda **k: 0)

    def interrupt(prompt):
        raise KeyboardInterrupt

    about.run_about(input_fn=interrupt)  # must not raise


def test_picker_has_an_about_row_below_the_cache_row(tmp_path, cache_home):
    _, _, procs, _ = run_picker(tmp_path, [None])

    sent = procs[0].communicate.call_args.kwargs["input"].decode().splitlines()
    assert sent[-2].startswith("__ACTION__\t\t💾 Cache and scratch")
    assert sent[-1].startswith(ABOUT_LINE)


def test_enter_on_the_about_row_runs_about_then_returns_to_the_picker(
    tmp_path, cache_home, monkeypatch
):
    run = MagicMock()
    monkeypatch.setattr(about, "run_about", run)

    result, _, _, project = run_picker(tmp_path, [ABOUT_LINE + "  🆕", None])

    run.assert_called_once()
    assert result.project == project
