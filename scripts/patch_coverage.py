#!/usr/bin/env python3
"""Report coverage of the lines this branch changed, the way Codecov does.

The suite enforces a *project* floor (``--cov-fail-under``), which a patch can
satisfy while still adding untested lines -- the floor barely moves. Codecov
checks the diff instead, so its verdict could only ever appear after a push.

That gap cost a round trip on v0.4.2: changing one character in an ``except``
branch pulled a line that had never been covered into the diff, and Codecov
failed the PR at 91.67% patch coverage. Nothing locally could have said so.

Reads ``coverage.json`` (``pytest --cov-report=json``) and the diff against a
base ref, and reports added or modified executable lines that no test reached.

Author: Solent Labs™
Created: 2026-08-06
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(base: str, paths: Sequence[str] = ()) -> Dict[str, Set[int]]:
    """Map each changed file to the set of line numbers added or modified.

    Uses ``--unified=0`` so hunks carry no context lines, keeping the result to
    lines the branch actually touched.
    """
    cmd = ["git", "diff", "--unified=0", "--no-color", f"{base}...HEAD", "--"]
    cmd.extend(paths if paths else ["*.py"])
    out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout

    result: Dict[str, Set[int]] = {}
    current: Optional[str] = None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            result.setdefault(current, set())
            continue
        if current is None:
            continue
        match = HUNK.match(line)
        if match:
            start = int(match.group(1))
            count = int(match.group(2) or 1)
            result[current].update(range(start, start + count))
    return {f: lines for f, lines in result.items() if lines}


def uncovered_in_patch(
    coverage_path: Path, changed: Dict[str, Set[int]]
) -> Dict[str, List[int]]:
    """Intersect changed lines with the executable lines no test reached."""
    data = json.loads(coverage_path.read_text(encoding="utf-8"))
    files = data.get("files", {})

    # coverage.py keys may be absolute or relative; index by suffix for matching.
    by_suffix = {}
    for name, payload in files.items():
        by_suffix[Path(name).as_posix()] = payload

    def lookup(path: str):
        posix = Path(path).as_posix()
        if posix in by_suffix:
            return by_suffix[posix]
        for name, payload in by_suffix.items():
            if name.endswith(posix) or posix.endswith(name):
                return payload
        return None

    result: Dict[str, List[int]] = {}
    for path, lines in changed.items():
        payload = lookup(path)
        if payload is None:
            continue  # not measured (a test file, or outside --cov scope)
        missing = set(payload.get("missing_lines", []))
        hit = sorted(lines & missing)
        if hit:
            result[path] = hit
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="origin/main", help="Base ref to diff against"
    )
    parser.add_argument(
        "--coverage-json",
        default="coverage.json",
        help="pytest --cov-report=json output",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Report but exit 0 (for informational runs)",
    )
    args = parser.parse_args(argv)

    coverage_path = Path(args.coverage_json)
    if not coverage_path.exists():
        print(
            f"patch-coverage: {coverage_path} not found — "
            "run pytest with --cov-report=json",
            file=sys.stderr,
        )
        return 0 if args.warn_only else 1

    changed = changed_lines(args.base)
    if not changed:
        print("patch-coverage: no changed Python lines")
        return 0

    uncovered = uncovered_in_patch(coverage_path, changed)
    total = sum(len(v) for v in changed.values())
    missed = sum(len(v) for v in uncovered.values())
    covered_pct = 100.0 if total == 0 else (total - missed) * 100.0 / total

    if not uncovered:
        print(f"patch-coverage: 100% of {total} changed line(s) covered")
        return 0

    print(f"patch-coverage: {covered_pct:.1f}% — {missed} changed line(s) uncovered")
    for path, lines in sorted(uncovered.items()):
        pretty = ", ".join(str(n) for n in lines)
        print(f"  {path}: {pretty}")
    print("\nCodecov reports these as patch coverage. Add tests or justify each line.")
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
