"""Tests for `ai-launcher update`: version checks, install detection, the flow."""

import io
import json
import subprocess
import urllib.error

import pytest
from typer.testing import CliRunner

from ai_launcher.cli import app
from ai_launcher.core import self_update as su
from ai_launcher.ui import update as ui

SITE = "/home/u/.local/lib/python3.12/site-packages"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.7.0", (0, 7, 0)),
        ("1", (1,)),
        (" 2.10.3 ", (2, 10, 3)),
        ("1.0.0rc1", None),
        ("", None),
        ("latest", None),
        ("1.2.3.4.5", None),
    ],
)
def test_parse_version(text, expected):
    assert su.parse_version(text) == expected


@pytest.mark.parametrize(
    ("latest", "installed", "newer"),
    [
        ("0.7.1", "0.7.0", True),
        ("0.7.0", "0.7.0", False),
        ("0.6.9", "0.7.0", False),
        ("0.10.0", "0.9.0", True),  # numeric, not alphabetical
        ("1.0", "0.9.9", True),
        ("0.7", "0.7.0", False),  # trailing zeros do not count
        ("0.7.0", "0.7.0+local", False),
        ("garbage", "0.7.0", False),
        ("0.8.0", "dev", False),
    ],
)
def test_is_newer(latest, installed, newer):
    assert su.is_newer(latest, installed) is newer


class Reply:
    def __init__(self, body: bytes):
        self.body = io.BytesIO(body)

    def __enter__(self):
        return self.body

    def __exit__(self, *exc):
        return False


def opener_returning(payload):
    def opener(url, timeout):
        assert url == su.PYPI_URL
        assert timeout == su.TIMEOUT_SECONDS
        return Reply(
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )

    return opener


def test_fetch_latest_reads_the_version():
    assert su.fetch_latest(opener_returning({"info": {"version": "0.9.1"}})) == "0.9.1"


@pytest.mark.parametrize(
    "payload",
    [b"not json", {"info": {}}, {"nope": 1}, {"info": {"version": "0.9.0rc1"}}, [1, 2]],
    ids=["bad-json", "no-version", "no-info", "prerelease-only", "wrong-shape"],
)
def test_fetch_latest_rejects_a_reply_it_cannot_use(payload):
    with pytest.raises(su.UpdateError):
        su.fetch_latest(opener_returning(payload))


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("offline"), TimeoutError("slow"), OSError("x")]
)
def test_fetch_latest_turns_network_errors_into_update_errors(error):
    def opener(url, timeout):
        raise error

    with pytest.raises(su.UpdateError, match="could not read"):
        su.fetch_latest(opener)


# ------------------------------------------------------- install detection


def plan(**overrides):
    args = {
        "direct_url": {},
        "prefix": "/usr",
        "base_prefix": "/usr",
        "package_file": SITE + "/ai_launcher/__init__.py",
        "platform": "linux",
        "argv0": "/usr/bin/ai-launcher",
        "which": lambda name: f"/usr/bin/{name}",
        "executable": "/usr/bin/python3",
    }
    args.update(overrides)
    return su.detect_plan(**args)


def test_editable_install_is_never_updated_from_pypi():
    result = plan(direct_url={"dir_info": {"editable": True}})

    assert result.method == su.EDITABLE
    assert result.argv is None
    assert "git pull" in result.note


def test_source_install_is_never_updated_from_pypi():
    result = plan(direct_url={"url": "file:///src/x", "dir_info": {}})

    assert result.method == su.SOURCE and result.argv is None


def test_pipx_install_uses_pipx():
    result = plan(prefix="/home/u/.local/pipx/venvs/ai-launcher")

    assert result.method == su.PIPX
    assert result.argv == ["pipx", "upgrade", "ai-launcher"]
    assert result.manual is False


def test_pipx_missing_from_path_is_shown_not_run():
    result = plan(prefix="/home/u/.local/pipx/venvs/ai-launcher", which=lambda n: None)

    assert result.manual is True and "not on PATH" in result.note


def test_venv_install_has_no_user_flag():
    result = plan(prefix="/proj/venv", base_prefix="/usr")

    assert result.argv == [
        "/usr/bin/python3",
        "-m",
        "pip",
        "install",
        "--upgrade",
        "ai-launcher",
    ]


def test_user_site_install_adds_user(monkeypatch):
    monkeypatch.setattr(su.site, "getusersitepackages", lambda: SITE)

    assert "--user" in plan().argv


def test_system_site_install_does_not_add_user(monkeypatch):
    monkeypatch.setattr(su.site, "getusersitepackages", lambda: "/elsewhere")

    assert "--user" not in plan().argv


def test_no_user_site_does_not_crash(monkeypatch):
    def broken():
        raise AttributeError("no user site")

    monkeypatch.setattr(su.site, "getusersitepackages", broken)

    assert "--user" not in plan().argv


def test_windows_exe_entry_point_leaves_the_command_to_the_user():
    result = plan(platform="win32", argv0=r"C:\Py\Scripts\ai-launcher.exe")

    assert result.manual is True
    assert result.display[0] == "/usr/bin/python3"  # the interpreter in use
    assert "running" in result.note


def test_windows_python_dash_m_may_run_it():
    result = plan(platform="win32", argv0=r"C:\Py\ai_launcher\__main__.py")

    assert result.manual is False


def test_detect_plan_reads_the_real_environment():
    result = su.detect_plan()  # this checkout is an editable install

    assert result.method in (su.EDITABLE, su.SOURCE, su.PIP, su.PIPX)


def test_direct_url_survives_a_missing_or_broken_record(monkeypatch):
    class Dist:
        def __init__(self, text):
            self.text = text

        def read_text(self, name):
            return self.text

    import importlib.metadata as md

    for text, expected in (
        ("not json", None),
        (None, None),
        ("[1]", None),
        ('{"a": 1}', {"a": 1}),
    ):
        monkeypatch.setattr(md, "distribution", lambda name, t=text: Dist(t))
        assert su._direct_url() == expected

    def missing(name):
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(md, "distribution", missing)
    assert su._direct_url() is None


# ----------------------------------------------------------- the command


def run(
    plan_,
    *,
    installed="0.7.0",
    latest="0.8.0",
    check=False,
    yes=False,
    tty=True,
    answer="y",
    runner=None,
):
    calls = []

    def fake_runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    code = ui.update_command(
        check=check,
        yes=yes,
        installed=installed,
        fetch=lambda: latest,
        plan=plan_,
        runner=runner or fake_runner,
        input_fn=lambda prompt: answer,
        is_tty=tty,
    )
    return code, calls


PIP_PLAN = su.UpdatePlan(
    su.PIP,
    argv=["py", "-m", "pip", "install", "--upgrade", "ai-launcher"],
    display=["py", "-m", "pip", "install", "--upgrade", "ai-launcher"],
)


def test_up_to_date_does_nothing(capsys):
    code, calls = run(PIP_PLAN, latest="0.7.0")

    assert code == 0 and calls == []
    assert "up to date" in capsys.readouterr().out


def test_check_reports_and_changes_nothing(capsys):
    code, calls = run(PIP_PLAN, check=True)

    out = capsys.readouterr().out
    assert code == 0 and calls == []
    assert (
        "0.8.0" in out and "Update with: py -m pip install --upgrade ai-launcher" in out
    )


def test_update_runs_the_command_without_a_shell_after_yes(capsys):
    code, calls = run(PIP_PLAN, answer="y")

    assert code == 0
    assert calls == [(PIP_PLAN.argv, {"shell": False, "check": False})]
    assert "Updated to 0.8.0" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_default_answer_is_no(answer):
    code, calls = run(PIP_PLAN, answer=answer)

    assert code == 0 and calls == []


def test_without_a_terminal_nothing_runs_unless_yes(capsys):
    code, calls = run(PIP_PLAN, tty=False)

    assert code == 1 and calls == []
    assert "--yes" in capsys.readouterr().out
    code, calls = run(PIP_PLAN, tty=False, yes=True)
    assert code == 0 and len(calls) == 1


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_eof_at_the_question_is_a_failure(error):
    def ask(prompt):
        raise error

    code = ui.update_command(
        installed="0.7.0",
        fetch=lambda: "0.8.0",
        plan=PIP_PLAN,
        input_fn=ask,
        is_tty=True,
    )

    assert code == 1


def test_a_failing_upgrade_is_reported(capsys):
    def failing(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 5)

    code, _ = run(PIP_PLAN, yes=True, runner=failing)

    assert code == 1 and "exit 5" in capsys.readouterr().out


def test_a_missing_installer_is_reported(capsys):
    def missing(argv, **kwargs):
        raise FileNotFoundError("no pipx")

    code, _ = run(PIP_PLAN, yes=True, runner=missing)

    assert code == 1 and "could not run" in capsys.readouterr().out


def test_manual_plans_print_the_command_and_run_nothing(capsys):
    manual = su.UpdatePlan(
        su.PIP,
        argv=["x"],
        display=["py", "-m", "pip"],
        manual=True,
        note="Windows says no.",
    )

    code, calls = run(manual, yes=True)

    out = capsys.readouterr().out
    assert code == 0 and calls == []
    assert "Windows says no." in out and "Run: py -m pip" in out


def test_editable_installs_get_guidance_not_a_command(capsys):
    plan_ = su.UpdatePlan(su.EDITABLE, note="Use git pull.")

    code, calls = run(plan_, yes=True)

    assert code == 0 and calls == []
    assert "Use git pull." in capsys.readouterr().out


def test_pypi_failure_exits_2_without_a_traceback(capsys):
    def offline():
        raise su.UpdateError("no network")

    code = ui.update_command(fetch=offline)

    assert code == 2 and "Error: no network" in capsys.readouterr().out


def test_cli_update_check(monkeypatch):
    monkeypatch.setattr("ai_launcher.ui.update.fetch_latest", lambda: "99.0.0")
    monkeypatch.setattr(
        "ai_launcher.ui.update.detect_plan",
        lambda: su.UpdatePlan(su.EDITABLE, note="Use git pull."),
    )

    result = CliRunner().invoke(app, ["update", "--check"])

    assert result.exit_code == 0
    assert "99.0.0" in result.output


def test_the_launcher_makes_no_request_unless_update_is_run(monkeypatch):
    """Nothing but `update` may touch the network."""
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used")
    )

    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
