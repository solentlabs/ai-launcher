#!/usr/bin/env python3
"""Release automation for ai-launcher.

Phases:
  1. Validation   — version format, clean tree, tag not taken
  2. Quality      — ruff + pytest
  3. Changelog    — verify entry exists
  4. Update       — bump version in pyproject.toml and __init__.py
  5. Git          — create release branch, commit, push, open PR
  6. Merge        — wait for PR CI, then squash-merge
  7. Wait for CI  — wait for CI to pass on main after merge
  8. Tag+Release  — create tag, push, wait for tag-protection, create GitHub release

Usage:
    python3 scripts/release.py 0.2.0
    python3 scripts/release.py 0.2.0 --dry-run
    python3 scripts/release.py 0.2.0 --no-push
    python3 scripts/release.py 0.2.0 --skip-tests --skip-quality
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
INIT_FILE = PROJECT_ROOT / "src" / "ai_launcher" / "__init__.py"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"

# Polling config
POLL_INTERVAL = 15  # seconds between CI polls
POLL_TIMEOUT = 1200  # 20 minutes max wait

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
DIM = "\033[2m"
BOLD = "\033[1m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{CYAN}  {msg}{NC}")


def success(msg: str) -> None:
    print(f"{GREEN}  \u2713 {msg}{NC}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  \u26a0 {msg}{NC}")


def error(msg: str) -> None:
    print(f"{RED}  \u2717 {msg}{NC}")


def fatal(msg: str) -> None:
    error(msg)
    sys.exit(1)


def header(phase: str) -> None:
    print(f"\n{BOLD}{CYAN}\u2501\u2501\u2501 {phase} \u2501\u2501\u2501{NC}\n")


def dry(msg: str) -> None:
    print(f"{DIM}  [dry-run] {msg}{NC}")


def run(
    cmd: list[str], check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        fatal(f"Command failed: {' '.join(cmd)}")
    return result


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command with capture."""
    return run(["gh"] + args, check=check, capture=True)


def detect_venv() -> str:
    """Detect virtual environment binary prefix."""
    for venv_dir in ["venv", ".venv"]:
        venv_path = PROJECT_ROOT / venv_dir / "bin"
        if venv_path.is_dir():
            return str(venv_path) + "/"
    return ""


def require_gh() -> None:
    """Ensure gh CLI is installed and authenticated."""
    result = run(["which", "gh"], capture=True, check=False)
    if result.returncode != 0:
        fatal("gh CLI is required for phases 6-8. Install: https://cli.github.com/")
    result = run(["gh", "auth", "status"], capture=True, check=False)
    if result.returncode != 0:
        fatal("gh CLI is not authenticated. Run: gh auth login")


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_current_branch() -> str:
    result = run(["git", "branch", "--show-current"], capture=True)
    return str(result.stdout.strip())


def get_pr_number_for_branch(branch: str) -> int | None:
    """Find an open or merged PR for the given branch."""
    for state in ("open", "merged"):
        result = run_gh(
            ["pr", "list", "--head", branch, "--state", state, "--json", "number"],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            prs = json.loads(result.stdout)
            if prs:
                return int(prs[0]["number"])
    return None


def is_pr_merged(pr_number: int) -> bool:
    result = run_gh(
        ["pr", "view", str(pr_number), "--json", "state"],
        check=False,
    )
    if result.returncode != 0:
        return False
    data = json.loads(result.stdout)
    return bool(data.get("state") == "MERGED")


def tag_exists_remote(version: str) -> bool:
    result = run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/v{version}"],
        capture=True,
        check=False,
    )
    return bool(result.stdout.strip())


def release_exists(version: str) -> bool:
    result = run_gh(
        ["release", "view", f"v{version}", "--json", "tagName"],
        check=False,
    )
    return result.returncode == 0


def extract_changelog_section(version: str) -> str:
    """Extract the changelog section for a specific version."""
    content = CHANGELOG.read_text()
    lines = content.splitlines()

    # Find the start of the version section
    start = None
    for i, line in enumerate(lines):
        if any(
            p in line for p in [f"## [{version}]", f"## {version}", f"## v{version}"]
        ):
            start = i + 1
            break

    if start is None:
        return f"Release v{version}"

    # Find the end (next ## header or end of file)
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break

    # Join and strip leading/trailing whitespace
    section = "\n".join(lines[start:end]).strip()
    return section if section else f"Release v{version}"


def _parse_pr_checks_text(output: str) -> list[dict[str, str]]:
    """Parse tab-separated output from 'gh pr checks' (no --json support)."""
    checks = []
    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            checks.append({"name": parts[0].strip(), "state": parts[1].strip()})
    return checks


def poll_pr_checks(pr_number: int) -> bool:
    """Poll PR checks until all pass or any fails. Returns True if all passed."""
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        result = run_gh(
            ["pr", "checks", str(pr_number)],
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            info(f"Waiting for checks to appear... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        checks = _parse_pr_checks_text(result.stdout)
        if not checks:
            info(f"No checks found yet... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        failed = [c for c in checks if c["state"] == "fail"]
        pending = [c for c in checks if c["state"] not in ("pass", "fail")]

        if failed:
            error("The following checks failed:")
            for c in failed:
                error(f"  - {c['name']}")
            return False

        if not pending:
            success(f"All {len(checks)} checks passed")
            return True

        names = ", ".join(c["name"] for c in pending[:3])
        remaining = f" (+{len(pending) - 3} more)" if len(pending) > 3 else ""
        info(f"Waiting for {len(pending)} checks: {names}{remaining} ({elapsed}s)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    fatal(f"Timed out after {POLL_TIMEOUT}s waiting for PR checks")
    return False  # unreachable, fatal exits


def poll_main_ci() -> bool:
    """Poll the latest CI run on main until it completes. Returns True if passed."""
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        result = run_gh(
            [
                "run",
                "list",
                "--branch",
                "main",
                "--workflow",
                "ci.yml",
                "--limit",
                "1",
                "--json",
                "status,conclusion,databaseId",
            ],
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            info(f"Waiting for CI run to appear on main... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        runs = json.loads(result.stdout)
        if not runs:
            info(f"No CI runs found on main... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        run_data = runs[0]
        status = run_data.get("status")
        conclusion = run_data.get("conclusion")
        run_id = run_data.get("databaseId", "?")

        if status == "completed":
            if conclusion == "success":
                success(f"CI run {run_id} passed on main")
                return True
            fatal(f"CI run {run_id} on main concluded: {conclusion}")
            return False

        info(f"CI run {run_id} status: {status} ({elapsed}s)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    fatal(f"Timed out after {POLL_TIMEOUT}s waiting for CI on main")
    return False


def poll_tag_protection(version: str) -> bool:
    """Poll tag-protection workflow until it completes. Returns True if passed."""
    elapsed = 0
    tag = f"v{version}"
    while elapsed < POLL_TIMEOUT:
        result = run_gh(
            [
                "run",
                "list",
                "--workflow",
                "tag-protection.yml",
                "--limit",
                "5",
                "--json",
                "status,conclusion,headBranch",
            ],
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            info(f"Waiting for tag-protection run... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        runs = json.loads(result.stdout)
        # Find the run for our tag
        tag_run = None
        for r in runs:
            if r.get("headBranch") == tag:
                tag_run = r
                break

        if not tag_run:
            info(f"Waiting for tag-protection run for {tag}... ({elapsed}s)")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        status = tag_run.get("status")
        conclusion = tag_run.get("conclusion")

        if status == "completed":
            if conclusion == "success":
                success(f"Tag protection passed for {tag}")
                return True
            fatal(f"Tag protection for {tag} concluded: {conclusion}")
            return False

        info(f"Tag protection status: {status} ({elapsed}s)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    fatal(f"Timed out after {POLL_TIMEOUT}s waiting for tag-protection")
    return False


# ── Phase functions ───────────────────────────────────────────────────────────


def validate_version(version: str) -> None:
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        fatal(f"Invalid version format: {version} (expected X.Y.Z)")


def check_git_clean() -> None:
    result = run(["git", "status", "--porcelain"], capture=True)
    if result.stdout.strip():
        fatal("Working directory is not clean. Commit or stash changes first.")
    success("Working directory is clean")


def check_on_main() -> None:
    branch = get_current_branch()
    if branch not in ("main", "master"):
        warn(
            f"On branch '{branch}' \u2014 release branches are typically created from main"
        )


def check_tag_not_exists(version: str) -> None:
    result = run(["git", "tag", "-l", f"v{version}"], capture=True)
    if result.stdout.strip():
        fatal(f"Tag v{version} already exists locally")
    success(f"Tag v{version} is available")


def run_quality_checks(venv: str, skip_tests: bool, skip_quality: bool) -> None:
    if skip_quality and skip_tests:
        warn("Skipping all quality checks")
        return

    if not skip_quality:
        info("Running ruff check...")
        run([f"{venv}ruff", "check", "."])
        success("ruff check passed")

        info("Running ruff format check...")
        run([f"{venv}ruff", "format", "--check", "."])
        success("ruff format passed")

    if not skip_tests:
        info("Running pytest...")
        run([f"{venv}pytest", "--tb=short", "-q"])
        success("All tests passed")


def check_changelog(version: str) -> None:
    if not CHANGELOG.exists():
        fatal("CHANGELOG.md not found")

    content = CHANGELOG.read_text()
    patterns = [f"## [{version}]", f"## {version}", f"## v{version}"]
    for pattern in patterns:
        if pattern in content:
            success(f"CHANGELOG.md has entry for {version}")
            return

    fatal(
        f"CHANGELOG.md has no entry for {version}.\n"
        f"  Add a section like: ## [{version}] - YYYY-MM-DD"
    )


def update_pyproject_version(version: str) -> None:
    content = PYPROJECT.read_text()
    new_content = re.sub(
        r'^version\s*=\s*"[^"]*"',
        f'version = "{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content == content:
        fatal("Could not find version string in pyproject.toml")
    PYPROJECT.write_text(new_content)
    success(f"Updated pyproject.toml to {version}")


def update_init_version(version: str) -> None:
    content = INIT_FILE.read_text()
    new_content = re.sub(
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content == content:
        fatal("Could not find __version__ in __init__.py")
    INIT_FILE.write_text(new_content)
    success(f"Updated __init__.py to {version}")


def create_release_branch(version: str, no_push: bool, dry_run: bool) -> int | None:
    """Create release branch, commit, push, and open PR. Returns PR number or None."""
    branch = f"release/v{version}"

    # Idempotent: check if branch already exists
    result = run(["git", "branch", "--list", branch], capture=True, check=False)
    if result.stdout.strip():
        info(f"Branch {branch} already exists, switching to it")
        if not dry_run:
            run(["git", "checkout", branch])
    else:
        if dry_run:
            dry(f"Would create branch {branch}")
        else:
            info(f"Creating branch {branch}...")
            run(["git", "checkout", "-b", branch])
            success(f"Created branch {branch}")

    if dry_run:
        dry("Would stage and commit version bump")
    else:
        # Check if there are changes to commit
        result = run(["git", "status", "--porcelain"], capture=True)
        if result.stdout.strip():
            info("Staging version changes...")
            run(["git", "add", str(PYPROJECT), str(INIT_FILE)])
            info("Creating commit...")
            run(["git", "commit", "-m", f"chore: bump version to {version}"])
            success("Created version bump commit")
        else:
            info("No changes to commit (already committed)")

    if no_push:
        warn("--no-push specified, skipping push and PR creation")
        info(f"To push manually: git push -u origin {branch}")
        return None

    if dry_run:
        dry(f"Would push {branch} and create PR")
        return None

    info("Pushing branch...")
    run(["git", "push", "-u", "origin", branch])
    success(f"Pushed {branch}")

    # Idempotent: check if PR already exists
    pr_number = get_pr_number_for_branch(branch)
    if pr_number:
        info(f"PR #{pr_number} already exists for {branch}")
        return pr_number

    info("Creating pull request...")
    result = run_gh(
        [
            "pr",
            "create",
            "--title",
            f"Release v{version}",
            "--body",
            f"## Release v{version}\n\nVersion bump to {version}.\n\n"
            f"_Automated by `scripts/release.py`_",
            "--base",
            "main",
        ],
    )
    # Extract PR number from URL in output
    url = result.stdout.strip()
    match = re.search(r"/pull/(\d+)", url)
    if match:
        pr_number = int(match.group(1))
        success(f"Pull request #{pr_number} created")
        return pr_number

    success("Pull request created")
    # Fall back to lookup
    return get_pr_number_for_branch(branch)


def merge_pr(pr_number: int, dry_run: bool) -> None:
    """Wait for CI on the PR, then squash-merge it."""
    # Idempotent: already merged?
    if is_pr_merged(pr_number):
        info(f"PR #{pr_number} is already merged")
        return

    if dry_run:
        dry(f"Would wait for CI on PR #{pr_number}")
        dry(f"Would squash-merge PR #{pr_number}")
        return

    info(f"Waiting for CI checks on PR #{pr_number}...")
    if not poll_pr_checks(pr_number):
        fatal(f"CI checks failed on PR #{pr_number}")

    info(f"Squash-merging PR #{pr_number}...")
    run_gh(["pr", "merge", str(pr_number), "--squash", "--delete-branch"])
    success(f"PR #{pr_number} merged")


def wait_for_main_ci(dry_run: bool) -> None:
    """Switch to main, pull, and wait for CI to pass."""
    if dry_run:
        dry("Would checkout main, pull, and wait for CI")
        return

    info("Switching to main and pulling...")
    run(["git", "checkout", "main"])
    run(["git", "pull", "origin", "main"])
    success("On main with latest changes")

    info("Waiting for CI on main...")
    poll_main_ci()


def create_tag_and_release(version: str, dry_run: bool) -> None:
    """Create tag, push it, wait for tag-protection, and create GitHub release."""
    tag = f"v{version}"

    # Idempotent: tag already exists remotely?
    if tag_exists_remote(version):
        info(f"Tag {tag} already exists on remote")
    elif dry_run:
        dry(f"Would create and push tag {tag}")
    else:
        # Create tag locally if needed
        result = run(["git", "tag", "-l", tag], capture=True)
        if not result.stdout.strip():
            info(f"Creating tag {tag}...")
            run(["git", "tag", tag])
            success(f"Created tag {tag}")
        else:
            info(f"Tag {tag} already exists locally")

        info(f"Pushing tag {tag}...")
        run(["git", "push", "origin", tag])
        success(f"Pushed tag {tag}")

    # Wait for tag-protection workflow
    if dry_run:
        dry("Would wait for tag-protection workflow")
    else:
        info("Waiting for tag-protection workflow...")
        poll_tag_protection(version)

    # Idempotent: release already exists?
    if release_exists(version):
        info(f"GitHub release {tag} already exists")
        return

    if dry_run:
        dry(f"Would create GitHub release {tag}")
        notes = extract_changelog_section(version)
        dry(f"Release notes ({len(notes)} chars):\n{DIM}{notes[:200]}...{NC}")
        return

    notes = extract_changelog_section(version)
    info(f"Creating GitHub release {tag}...")
    result = subprocess.run(
        ["gh", "release", "create", tag, "--title", tag, "--notes-file", "-"],
        input=notes,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error(f"gh release create failed: {result.stderr.strip()}")
        fatal("Failed to create GitHub release")
    success(f"GitHub release {tag} created")
    url = result.stdout.strip()
    if url:
        info(f"Release URL: {url}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Release automation for ai-launcher")
    parser.add_argument("version", help="Version to release (X.Y.Z)")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push or create PR (stops after phase 5)",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite")
    parser.add_argument("--skip-quality", action="store_true", help="Skip ruff checks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing",
    )
    args = parser.parse_args()

    version = args.version
    venv = detect_venv()
    dry_run = args.dry_run

    label = f"v{version}"
    if dry_run:
        label += " (dry run)"
    print(f"\n{BOLD}AI Launcher Release \u2014 {label}{NC}\n")

    # Phase 1: Validation
    header("Phase 1: Validation")
    validate_version(version)
    success(f"Version format OK: {version}")
    check_git_clean()
    check_on_main()
    check_tag_not_exists(version)
    if not args.no_push:
        require_gh()
        success("gh CLI is installed and authenticated")

    # Phase 2: Quality
    header("Phase 2: Quality Checks")
    if dry_run:
        dry("Would run ruff + pytest")
    else:
        run_quality_checks(venv, args.skip_tests, args.skip_quality)

    # Phase 3: Changelog
    header("Phase 3: Changelog")
    check_changelog(version)

    # Phase 4: Update versions
    header("Phase 4: Update Versions")
    if dry_run:
        dry(f"Would update pyproject.toml version to {version}")
        dry(f"Would update __init__.py version to {version}")
    else:
        update_pyproject_version(version)
        update_init_version(version)

    # Phase 5: Git (branch + PR)
    header("Phase 5: Git (Branch + PR)")
    pr_number = create_release_branch(version, args.no_push, dry_run)

    if args.no_push:
        print(
            f"\n{GREEN}{BOLD}\u2501\u2501\u2501 Release v{version} prepared (local only) \u2501\u2501\u2501{NC}\n"
        )
        return

    # Phase 6: Merge
    header("Phase 6: Merge PR")
    if pr_number is None and not dry_run:
        branch = f"release/v{version}"
        pr_number = get_pr_number_for_branch(branch)
    if pr_number is None and not dry_run:
        fatal("Could not find PR number. Create or find the PR manually.")
    merge_pr(pr_number or 0, dry_run)

    # Phase 7: Wait for CI on main
    header("Phase 7: Wait for CI on main")
    wait_for_main_ci(dry_run)

    # Phase 8: Tag + Release
    header("Phase 8: Tag + Release")
    create_tag_and_release(version, dry_run)

    # Done
    if dry_run:
        print(
            f"\n{BOLD}{YELLOW}\u2501\u2501\u2501 Dry run complete for v{version} \u2501\u2501\u2501{NC}\n"
        )
    else:
        print(
            f"\n{GREEN}{BOLD}\u2501\u2501\u2501 Release v{version} published! \u2501\u2501\u2501{NC}\n"
        )


if __name__ == "__main__":
    main()
