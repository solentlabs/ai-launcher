"""The bash prototype (bin/ai-launcher): the parts that run without a terminal.

`--list` needs no fzf, so it can be driven here. The paths it is given are
data: they may carry `$(...)` or backticks and must never be run.

Author: Solent Labs™
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROTOTYPE = Path(__file__).parent.parent / "bin" / "ai-launcher"
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs bash")


def run(home: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", str(PROTOTYPE), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
        cwd=home,
        check=False,
        timeout=30,
    )


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".config" / "ai-launcher").mkdir(parents=True)
    return tmp_path


def make_repo(path: Path) -> Path:
    (path / ".git").mkdir(parents=True)
    return path


@pytest.mark.parametrize(
    "hostile",
    ["x$(touch INJECTED)", "x`touch INJECTED`", "x;touch INJECTED"],
    ids=["substitution", "backticks", "semicolon"],
)
def test_a_path_argument_is_data_never_code(home, hostile):
    result = run(home, "--list", hostile)

    assert result.returncode == 0, result.stderr
    assert not (home / "INJECTED").exists()


@pytest.mark.parametrize(
    "hostile",
    ["x$(touch INJECTED)", "x`touch INJECTED`"],
    ids=["substitution", "backticks"],
)
def test_a_scan_path_in_the_config_is_data_never_code(home, hostile):
    (home / ".config" / "ai-launcher" / "config.toml").write_text(
        f"SCAN_PATHS='{hostile}'\n", encoding="utf-8"
    )

    result = run(home, "--list")

    assert result.returncode == 0, result.stderr
    assert not (home / "INJECTED").exists()


def test_a_tilde_in_the_config_is_expanded(home):
    make_repo(home / "work" / "repo")
    (home / ".config" / "ai-launcher" / "config.toml").write_text(
        'SCAN_PATHS="~/work"\n', encoding="utf-8"
    )

    result = run(home, "--list")

    assert f"{home}/work/repo" in result.stdout


def test_a_tilde_argument_is_expanded(home):
    make_repo(home / "work" / "repo")

    result = run(home, "--list", "~/work")

    assert f"{home}/work/repo" in result.stdout
