"""Runs install.sh against stub tools, in a throwaway HOME.

The script is documented as ``curl ... | bash``, so most tests feed it on stdin,
the way that runs it. Prompts come from a file (INSTALL_TTY), standing in for
/dev/tty. Nothing here touches the real machine: pipx, fzf, uuidgen and cmd.exe
are stubs, and HOME is a temp folder.

Author: Solent Labs™
"""

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "install.sh"
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or not Path("/bin/bash").exists(), reason="needs bash"
)

WT_RELATIVE = (
    "AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe"
    "/LocalState/settings.json"
)


@pytest.fixture
def box(tmp_path):
    """A fake machine: stub tools on PATH, a HOME, and a WSL-looking /proc/version."""
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "pipx": "exit 0",
        "fzf": "exit 0",
        "uuidgen": "echo 11111111-2222-3333-4444-555555555555",
        "cmd.exe": "printf 'tester\\r\\n'",
    }.items():
        stub = bin_dir / name
        stub.write_text(f"#!/bin/sh\n{body}\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    proc = tmp_path / "proc_version"
    proc.write_text("Linux version 6.0 microsoft-standard-WSL2")
    settings = home / WT_RELATIVE
    settings.parent.mkdir(parents=True)

    def run(answers=None, settings_text='{"profiles": {"list": []}}', via_pipe=True):
        if settings_text is not None:
            settings.write_text(settings_text, encoding="utf-8")
        answer_file = tmp_path / "answers"
        answer_file.write_text("\n".join(answers or []) + "\n", encoding="utf-8")
        env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(home),
            "INSTALL_TTY": str(answer_file) if answers is not None else "/nonexistent",
            "INSTALL_PROC_VERSION": str(proc),
        }
        if via_pipe:
            return subprocess.run(
                ["/bin/bash"],
                input=SCRIPT.read_text(encoding="utf-8"),
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp_path,
                check=False,
                timeout=60,
            )
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            cwd=tmp_path,
            check=False,
            timeout=60,
        )

    return type(
        "Box",
        (),
        {"run": staticmethod(run), "settings": settings, "home": home, "tmp": tmp_path},
    )


def profiles(box):
    return json.loads(box.settings.read_text(encoding="utf-8"))["profiles"]["list"]


def test_piped_install_reads_its_prompts_from_the_keyboard_not_the_script(box):
    result = box.run(answers=["y", "/home/tester/code", "n"])

    assert result.returncode == 0, result.stderr
    (profile,) = profiles(box)
    assert profile["name"] == "AI Launcher"
    assert "/home/tester/code" in profile["commandline"]


def test_the_profile_runs_a_provider_command_the_cli_accepts(box):
    box.run(answers=["y", "/home/tester/code", "n"])

    (profile,) = profiles(box)
    assert "ai-launcher claude " in profile["commandline"]
    assert profile["startingDirectory"] == "//wsl.localhost/Ubuntu/home/tester/code"


def test_the_closing_message_names_a_working_command(box):
    result = box.run(answers=[])

    assert "ai-launcher claude ~/projects" in result.stdout
    assert "Run: ai-launcher ~/projects" not in result.stdout


def test_a_typed_tilde_is_expanded(box):
    box.run(answers=["y", "~/code", "n"])

    (profile,) = profiles(box)
    assert f"{box.home}/code" in profile["commandline"]
    assert "~" not in profile["startingDirectory"]


def test_the_settings_file_is_backed_up_first(box):
    original = '{"profiles": {"list": []}, "theme": "dark"}'

    box.run(answers=["y", "/home/tester/code", "n"], settings_text=original)

    backup = box.settings.with_name("settings.json.ai-launcher.bak")
    assert backup.read_text(encoding="utf-8") == original
    assert json.loads(box.settings.read_text())["theme"] == "dark"  # the rest is kept


def test_the_default_profile_is_only_changed_when_asked(box):
    box.run(answers=["y", "/home/tester/code", "n"])
    assert "defaultProfile" not in json.loads(box.settings.read_text())

    box.run(
        answers=["y", "/home/tester/code", "y"],
        settings_text='{"profiles": {"list": []}}',
    )
    config = json.loads(box.settings.read_text())
    assert config["defaultProfile"] == config["profiles"]["list"][0]["guid"]


@pytest.mark.parametrize(
    "typed",
    ["/tmp/x'; touch INJECTED; '", "/tmp/$(touch INJECTED)", "/tmp/`touch INJECTED`"],
    ids=["quote", "command-substitution", "backticks"],
)
def test_what_you_type_is_data_never_code(box, typed):
    result = box.run(answers=["y", typed, "n"])

    assert result.returncode == 0, result.stderr
    assert not (box.tmp / "INJECTED").exists()
    assert not (box.home / "INJECTED").exists()
    (profile,) = profiles(box)
    assert "touch INJECTED" in profile["commandline"]  # kept as text


def test_a_path_with_a_double_quote_is_refused_without_touching_the_file(box):
    original = '{"profiles": {"list": []}}'

    result = box.run(answers=["y", '/tmp/a"b', "n"], settings_text=original)

    assert result.returncode == 0
    assert box.settings.read_text(encoding="utf-8") == original
    assert "quote" in result.stdout.lower()


def test_a_settings_file_with_comments_is_left_alone_and_the_install_finishes(box):
    commented = '// my settings\n{"profiles": {"list": []}}\n'

    result = box.run(answers=["y", "/home/tester/code", "n"], settings_text=commented)

    assert result.returncode == 0
    assert box.settings.read_text(encoding="utf-8") == commented
    assert "Installation complete" in result.stdout
    assert "by hand" in result.stdout.lower()


@pytest.mark.parametrize("existing", ["AI Launcher", "Claude Code"])
def test_an_existing_profile_is_not_added_twice(box, existing):
    text = json.dumps({"profiles": {"list": [{"name": existing, "guid": "{x}"}]}})

    result = box.run(answers=["y", "/home/tester/code", "n"], settings_text=text)

    assert result.returncode == 0
    assert len(profiles(box)) == 1
    assert "already" in result.stdout.lower()


def test_with_no_keyboard_nothing_is_configured_and_the_install_still_finishes(box):
    original = '{"profiles": {"list": []}}'

    result = box.run(answers=None, settings_text=original)

    assert result.returncode == 0
    assert box.settings.read_text(encoding="utf-8") == original
    assert "Installation complete" in result.stdout


def test_running_the_file_directly_behaves_the_same(box):
    result = box.run(answers=["y", "/home/tester/code", "n"], via_pipe=False)

    assert result.returncode == 0, result.stderr
    assert len(profiles(box)) == 1
