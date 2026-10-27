"""scripts/verify-tag-ci.sh: the pre-push check on a tag, driven with a stub `gh`.

The decision is scripts/gate_checks.py ci-status, the same one the CI gate uses;
these tests check the script feeds it and acts on the answer.

Author: Solent Labs™
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "verify-tag-ci.sh"
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs bash")


def run_check(tmp_path, runs=None, gh="ok", tag=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
    }
    for cmd in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(["git", *cmd], cwd=repo, env=git_env, check=True)
    if tag:
        subprocess.run(["git", "tag", "v9.9.9"], cwd=repo, env=git_env, check=True)
    subprocess.run(
        ["git", "checkout", "-q", "--detach"], cwd=repo, env=git_env, check=True
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if gh != "missing":
        stub = bin_dir / "gh"
        payload = json.dumps({"check_runs": runs or []})
        stub.write_text(
            "#!/bin/sh\n"
            + ('[ "$1" = auth ] && exit 1\n' if gh == "unauthenticated" else "")
            + '[ "$1" = auth ] && exit 0\n'
            + f"echo '{payload}'\n"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env = {**git_env, "PATH": f"{bin_dir}:/usr/bin:/bin"}
    # python3 must be found for gate_checks; keep the venv's interpreter reachable
    env["PATH"] += os.pathsep + str(Path(sys.executable).parent)
    return subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def check(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


def test_passing_ci_allows_the_push(tmp_path):
    runs = [check("Lint"), check("test (ubuntu-latest, 3.12)")]

    result = run_check(tmp_path, runs)

    assert result.returncode == 0, result.stdout
    assert "CI passed" in result.stdout


def test_a_skipped_matrix_is_not_a_pass(tmp_path):
    runs = [check("Lint", "failure"), check("test (ubuntu-latest, 3.12)", "skipped")]

    result = run_check(tmp_path, runs)

    assert result.returncode == 1
    assert "CI failed" in result.stdout


def test_ci_still_running_blocks_the_push(tmp_path):
    runs = [check("test (ubuntu-latest, 3.12)", conclusion=None, status="in_progress")]

    result = run_check(tmp_path, runs)

    assert result.returncode == 1
    assert "still running" in result.stdout


def test_no_check_runs_yet_counts_as_still_running(tmp_path):
    assert run_check(tmp_path, []).returncode == 1


def test_a_failed_matrix_job_blocks_the_push(tmp_path):
    runs = [
        check("test (ubuntu-latest, 3.12)"),
        check("test (macos-latest, 3.8)", "failure"),
    ]

    assert run_check(tmp_path, runs).returncode == 1


@pytest.mark.parametrize("gh", ["missing", "unauthenticated"])
def test_without_a_usable_gh_it_warns_and_lets_the_push_through(tmp_path, gh):
    result = run_check(tmp_path, gh=gh)

    assert result.returncode == 0
    assert "skipping CI verification" in result.stdout


def test_a_branch_push_is_not_checked(tmp_path):
    result = run_check(tmp_path, tag=False)

    assert result.returncode == 0
