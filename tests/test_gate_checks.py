"""Tests for the CI gate decision logic.

Both gates failed on their first contact with a release, because neither had ever
been run against a release-shaped input. Every scenario that actually broke has a
named regression test here.

Author: Solent Labs™
Created: 2026-08-06
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
GATE_SCRIPT = SCRIPTS / "gate_checks.py"

_spec = importlib.util.spec_from_file_location("gate_checks", GATE_SCRIPT)
gate_checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_checks)


# The exact file list scripts/release.py produces for a release PR.
RELEASE_PR_FILES = ["pyproject.toml", "src/ai_launcher/__init__.py"]


class TestChangelogGate:
    """The changelog requirement."""

    def test_release_pr_is_exempt(self):
        """Regression: this deadlocked the v0.4.2 release at phase 6.

        A release PR bumps the version constants -- which match the code pattern
        -- while its changelog entry landed with the feature PR, exactly as
        docs/releasing.md requires. Failing it blocks every release.
        """
        ok, reason = gate_checks.changelog_gate(
            RELEASE_PR_FILES, head_ref="release/v0.4.2"
        )
        assert ok, reason
        assert "exempt" in reason

    def test_release_pr_without_exemption_would_fail(self):
        """Guards the test above: absent the exemption this input really does fail."""
        ok, _ = gate_checks.changelog_gate(RELEASE_PR_FILES, head_ref="fix/something")
        assert not ok

    def test_feature_pr_touching_code_without_changelog_fails(self):
        ok, reason = gate_checks.changelog_gate(
            ["src/ai_launcher/ui/formatter.py"], head_ref="fix/thing"
        )
        assert not ok
        assert "formatter.py" in reason

    def test_feature_pr_with_changelog_passes(self):
        ok, _ = gate_checks.changelog_gate(
            ["src/ai_launcher/ui/formatter.py", "CHANGELOG.md"], head_ref="fix/thing"
        )
        assert ok

    @pytest.mark.parametrize(
        "path",
        [
            "docs/configuration.md",
            "README.md",
            "tests/test_formatter.py",
            ".github/workflows/ci.yml",
            "src/ai_launcher/ui/template.html",
        ],
    )
    def test_non_code_paths_never_require_an_entry(self, path):
        ok, _ = gate_checks.changelog_gate([path], head_ref="fix/thing")
        assert ok

    @pytest.mark.parametrize("path", ["src/ai_launcher/cli.py", "scripts/release.py"])
    def test_code_paths_do_require_an_entry(self, path):
        ok, _ = gate_checks.changelog_gate([path], head_ref="fix/thing")
        assert not ok

    def test_empty_diff_passes(self):
        ok, _ = gate_checks.changelog_gate([], head_ref="fix/thing")
        assert ok

    def test_missing_head_ref_is_not_exempt(self):
        """A absent branch name must not accidentally grant the exemption."""
        ok, _ = gate_checks.changelog_gate(RELEASE_PR_FILES, head_ref=None)
        assert not ok

    def test_branch_merely_containing_release_is_not_exempt(self):
        """Exemption is a prefix match, not a substring match."""
        ok, _ = gate_checks.changelog_gate(
            RELEASE_PR_FILES, head_ref="fix/pre-release-notes"
        )
        assert not ok


def _check(name, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion}


class TestCiStatus:
    """Collapsing check runs into one status."""

    def test_in_progress_run_is_pending_not_failure(self):
        """Regression: this failed tag-protection on the v0.4.2 release.

        release.py pushed the tag seconds after the merge, while CI on main was
        still running. An unfinished check run carries conclusion None; reading
        that as failure turns a race into a hard stop.
        """
        runs = [
            _check("test (ubuntu-latest, 3.12)", status="in_progress", conclusion=None),
            _check("test (ubuntu-latest, 3.11)"),
        ]
        assert gate_checks.ci_status(runs) == gate_checks.PENDING

    def test_queued_run_is_pending(self):
        runs = [_check("test (macos-latest, 3.8)", status="queued", conclusion=None)]
        assert gate_checks.ci_status(runs) == gate_checks.PENDING

    def test_all_success_is_success(self):
        runs = [_check(f"test (ubuntu-latest, 3.{v})") for v in (8, 9, 10, 11, 12)]
        assert gate_checks.ci_status(runs) == gate_checks.SUCCESS

    def test_any_completed_failure_is_failure(self):
        runs = [
            _check("test (ubuntu-latest, 3.12)"),
            _check("test (windows-latest, 3.8)", conclusion="failure"),
        ]
        assert gate_checks.ci_status(runs) == gate_checks.FAILURE

    def test_no_matching_runs_is_pending(self):
        """Checks may not have registered yet -- that is 'wait', not 'go'."""
        assert gate_checks.ci_status([]) == gate_checks.PENDING
        assert gate_checks.ci_status([_check("coverage")]) == gate_checks.PENDING

    def test_unrelated_checks_are_ignored(self):
        """Only the matrix jobs are consulted; other checks have their own gates."""
        runs = [
            _check("test (ubuntu-latest, 3.12)"),
            _check("Verify CHANGELOG.md Updated", conclusion="failure"),
        ]
        assert gate_checks.ci_status(runs) == gate_checks.SUCCESS

    @pytest.mark.parametrize("conclusion", ["neutral", "skipped"])
    def test_neutral_and_skipped_are_not_failures(self, conclusion):
        runs = [
            _check("test (ubuntu-latest, 3.12)"),
            _check("test (macos-latest, 3.8)", conclusion=conclusion),
        ]
        assert gate_checks.ci_status(runs) == gate_checks.SUCCESS

    @pytest.mark.parametrize(
        "conclusion", ["cancelled", "timed_out", "action_required"]
    )
    def test_other_terminal_conclusions_are_failures(self, conclusion):
        runs = [_check("test (ubuntu-latest, 3.12)", conclusion=conclusion)]
        assert gate_checks.ci_status(runs) == gate_checks.FAILURE


class TestCli:
    """The CLI the workflows actually invoke."""

    def _run(self, args, stdin):
        return subprocess.run(
            [sys.executable, str(GATE_SCRIPT)] + args,
            input=stdin,
            capture_output=True,
            text=True,
        )

    def test_changelog_cli_exit_codes(self):
        ok = self._run(
            ["changelog", "--head-ref", "release/v0.4.2"], "\n".join(RELEASE_PR_FILES)
        )
        assert ok.returncode == 0

        bad = self._run(["changelog", "--head-ref", "fix/x"], "src/ai_launcher/cli.py")
        assert bad.returncode == 1
        assert "FAIL" in bad.stderr

    def test_ci_status_cli_accepts_github_api_shape(self):
        """gh api returns {"check_runs": [...]}; the CLI must unwrap that."""
        payload = json.dumps(
            {"check_runs": [_check("test (ubuntu-latest, 3.12)", "in_progress", None)]}
        )
        result = self._run(["ci-status"], payload)
        assert result.returncode == 0
        assert result.stdout.strip() == gate_checks.PENDING

    def test_ci_status_cli_accepts_bare_list(self):
        payload = json.dumps([_check("test (ubuntu-latest, 3.12)")])
        result = self._run(["ci-status"], payload)
        assert result.stdout.strip() == gate_checks.SUCCESS

    def test_ci_status_cli_handles_empty_input(self):
        result = self._run(["ci-status"], "")
        assert result.stdout.strip() == gate_checks.PENDING
