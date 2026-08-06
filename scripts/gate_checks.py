#!/usr/bin/env python3
"""Decision logic for the CI gates, as pure functions plus a thin CLI.

The gates used to live as inline bash and jq inside workflow YAML, where nothing
could exercise them. Both then failed on their first contact with a release:

  * changelog-check flagged the release PR's version bump as undocumented code,
    though its changelog entry had landed with the feature PR as designed.
  * tag-protection read an in-progress check run -- conclusion ``None`` -- as a
    hard failure, so tagging a freshly merged commit raced its own CI.

Keeping the decisions here means the workflows and the tests call the same code,
so a test cannot pass while the gate does something else.

Author: Solent Labs™
Created: 2026-08-06
"""

import argparse
import json
import re
import sys
from typing import Iterable, List, Optional, Sequence, Tuple

# Paths whose modification implies a user-visible change needing a changelog note.
CODE_PATTERN = re.compile(r"^(src/ai_launcher|scripts)/.*\.py$")

CHANGELOG = "CHANGELOG.md"

# Branch prefixes exempt from the changelog requirement. scripts/release.py bumps
# the version constants on a release/* branch, and docs/releasing.md requires the
# entry to already be on main by then.
EXEMPT_BRANCH_PREFIXES = ("release/",)

# Check-run names the tag gate considers. The matrix jobs are named "test (os, ver)".
CI_CHECK_PREFIX = "test ("

PENDING = "pending"
SUCCESS = "success"
FAILURE = "failure"


def is_exempt_branch(head_ref: Optional[str]) -> bool:
    """True when a branch is allowed to change code without a changelog entry."""
    if not head_ref:
        return False
    return head_ref.startswith(EXEMPT_BRANCH_PREFIXES)


def changelog_gate(
    changed_files: Iterable[str], head_ref: Optional[str] = None
) -> Tuple[bool, str]:
    """Decide whether a PR satisfies the changelog requirement.

    Args:
        changed_files: Paths changed relative to the base branch.
        head_ref: Source branch of the PR, used for the release exemption.

    Returns:
        (ok, reason). ok is False only when code changed, the changelog did not,
        and the branch is not exempt.
    """
    files = list(changed_files)
    code_changed = [f for f in files if CODE_PATTERN.match(f)]
    changelog_changed = CHANGELOG in files

    if not code_changed:
        return True, "no code changes require a changelog entry"
    if changelog_changed:
        return True, "code changed and CHANGELOG.md was updated"
    if is_exempt_branch(head_ref):
        return True, "release branch is exempt -- entry landed with the feature PR"
    return False, (
        "code changed without a CHANGELOG.md entry: " + ", ".join(sorted(code_changed))
    )


def ci_status(check_runs: Sequence[dict]) -> str:
    """Collapse a commit's check runs into pending / success / failure.

    A run that has not finished carries conclusion ``None``. Treating that as
    anything other than pending is what let a tag race its own CI: the caller
    must wait, not fail.

    Args:
        check_runs: Objects with "name", "status" and "conclusion" keys.

    Returns:
        One of PENDING, SUCCESS, FAILURE.
    """
    relevant = [
        c for c in check_runs if str(c.get("name", "")).startswith(CI_CHECK_PREFIX)
    ]
    if not relevant:
        return PENDING

    # Anything still queued or running means the answer is not yet knowable.
    for check in relevant:
        if check.get("status") != "completed" or check.get("conclusion") is None:
            return PENDING

    for check in relevant:
        # "neutral" and "skipped" are not failures; anything else is.
        if check.get("conclusion") not in (SUCCESS, "neutral", "skipped"):
            return FAILURE

    return SUCCESS


def _read_lines(source: str) -> List[str]:
    if source == "-":
        text = sys.stdin.read()
    else:
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
    return [line.strip() for line in text.splitlines() if line.strip()]


def _read_json(source: str):
    if source == "-":
        text = sys.stdin.read()
    else:
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
    return json.loads(text) if text.strip() else []


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    cl = sub.add_parser("changelog", help="Check the changelog requirement")
    cl.add_argument(
        "--files", default="-", help="File with changed paths, or - for stdin"
    )
    cl.add_argument("--head-ref", default=None, help="PR source branch")

    ci = sub.add_parser("ci-status", help="Collapse check runs to a single status")
    ci.add_argument("--check-runs", default="-", help="JSON file, or - for stdin")

    args = parser.parse_args(argv)

    if args.command == "changelog":
        ok, reason = changelog_gate(_read_lines(args.files), args.head_ref)
        if ok:
            print("OK: " + reason)
            return 0
        print("FAIL: " + reason, file=sys.stderr)
        return 1

    payload = _read_json(args.check_runs)
    runs = payload.get("check_runs", []) if isinstance(payload, dict) else payload
    print(ci_status(runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
