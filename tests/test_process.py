"""Tests for process helpers."""

import os

import pytest

from ai_launcher.utils import process


def test_pid_alive_for_this_process():
    assert process.pid_alive(os.getpid()) is True


@pytest.mark.parametrize("pid", [0, -5])
def test_pid_alive_rejects_nonsense(pid):
    assert process.pid_alive(pid) is False


@pytest.mark.skipif(os.name == "nt", reason="os.kill semantics differ on Windows")
@pytest.mark.parametrize(
    ("error", "expected"),
    [(ProcessLookupError, False), (PermissionError, True), (OSError, False)],
    ids=["gone", "other-users", "other-error"],
)
def test_pid_alive_maps_errors(monkeypatch, error, expected):
    def fake_kill(pid, sig):
        raise error

    monkeypatch.setattr(process.os, "kill", fake_kill)

    assert process.pid_alive(1234) is expected


def test_windows_never_signals(monkeypatch):
    monkeypatch.setattr(process.sys, "platform", "win32")
    monkeypatch.setattr(process, "_pid_alive_windows", lambda pid: True)
    monkeypatch.setattr(
        process.os,
        "kill",
        lambda *a: pytest.fail("os.kill must not be used on Windows"),
    )

    assert process.pid_alive(1234) is True
