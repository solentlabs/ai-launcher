"""Checks on .github/workflows that keep the release path safe.

Plain text checks: PyYAML is not a dependency of this project. The rules and
their reasons are in docs/releasing.md ("Workflow Safety").

Author: Solent Labs™
"""

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted(
    (Path(__file__).parent.parent / ".github" / "workflows").glob("*.yml")
)
IDS = [w.name for w in WORKFLOWS]
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
# A value an attacker names: branch names, titles, bodies.
UNTRUSTED = re.compile(
    r"\$\{\{\s*github\.(head_ref|base_ref)\s*\}\}"
    r"|\$\{\{\s*github\.event\.(pull_request\.(title|body|head\.ref)|head_commit\.message)\s*\}\}"
)
ENV_LINE = re.compile(r"^\s+[A-Z_][A-Z0-9_]*:\s*\$\{\{")


def read(name: str) -> str:
    return (WORKFLOWS[0].parent / name).read_text(encoding="utf-8")


def test_the_workflows_were_found():
    assert len(WORKFLOWS) >= 5


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=IDS)
def test_every_action_is_pinned_to_a_commit_sha(workflow):
    unpinned = []
    for line in workflow.read_text(encoding="utf-8").splitlines():
        match = USES.match(line)
        if (
            match
            and not match.group(1).startswith("./")
            and not PINNED.match(match.group(1))
        ):
            unpinned.append(match.group(1))

    assert unpinned == []


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=IDS)
def test_every_workflow_declares_permissions_at_the_top(workflow):
    assert re.search(
        r"^permissions:", workflow.read_text(encoding="utf-8"), re.MULTILINE
    )


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=IDS)
def test_untrusted_values_reach_a_shell_only_through_env(workflow):
    inline = [
        line.strip()
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if UNTRUSTED.search(line) and not ENV_LINE.match(line)
    ]

    assert inline == []


def test_real_pypi_publishing_needs_a_version_tag():
    text = read("publish.yml")
    publish_job = text[text.index("  publish:\n") :]

    assert "github.ref_type == 'tag'" in publish_job
    assert "startsWith(github.ref_name, 'v')" in publish_job


def test_test_pypi_may_still_start_from_any_ref():
    text = read("publish.yml")
    test_job = text[text.index("  publish-test:") : text.index("  publish:\n")]

    assert "ref_type" not in test_job


def test_the_tag_check_is_an_ancestor_test_not_a_substring_match():
    text = read("tag-protection.yml")

    assert "merge-base --is-ancestor" in text
    assert "grep -q 'origin/main'" not in text


def test_the_changelog_workflow_has_no_dead_step_output():
    assert "steps.code_check" not in read("changelog-check.yml")
