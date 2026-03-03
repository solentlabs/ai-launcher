#!/usr/bin/env python3
"""Release automation for ai-launcher.

Phases: Validation -> Quality -> Changelog -> Update -> Git

Usage:
    python3 scripts/release.py 0.2.0
    python3 scripts/release.py 0.2.0 --no-push
    python3 scripts/release.py 0.2.0 --skip-tests --skip-quality
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
INIT_FILE = PROJECT_ROOT / "src" / "ai_launcher" / "__init__.py"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{CYAN}  {msg}{NC}")


def success(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{NC}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠ {msg}{NC}")


def error(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{NC}")


def fatal(msg: str) -> None:
    error(msg)
    sys.exit(1)


def header(phase: str) -> None:
    print(f"\n{BOLD}{CYAN}━━━ {phase} ━━━{NC}\n")


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


def detect_venv() -> str:
    """Detect virtual environment binary prefix."""
    for venv_dir in ["venv", ".venv"]:
        venv_path = PROJECT_ROOT / venv_dir / "bin"
        if venv_path.is_dir():
            return str(venv_path) + "/"
    return ""


def validate_version(version: str) -> None:
    """Validate version format (X.Y.Z)."""
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        fatal(f"Invalid version format: {version} (expected X.Y.Z)")


def check_git_clean() -> None:
    """Ensure working directory is clean."""
    result = run(["git", "status", "--porcelain"], capture=True)
    if result.stdout.strip():
        fatal("Working directory is not clean. Commit or stash changes first.")
    success("Working directory is clean")


def check_on_main() -> None:
    """Ensure we're on the main branch."""
    result = run(["git", "branch", "--show-current"], capture=True)
    branch = result.stdout.strip()
    if branch not in ("main", "master"):
        warn(f"On branch '{branch}' — release branches are typically created from main")


def check_tag_not_exists(version: str) -> None:
    """Ensure the tag doesn't already exist."""
    result = run(["git", "tag", "-l", f"v{version}"], capture=True)
    if result.stdout.strip():
        fatal(f"Tag v{version} already exists")
    success(f"Tag v{version} is available")


def run_quality_checks(venv: str, skip_tests: bool, skip_quality: bool) -> None:
    """Run ruff and pytest."""
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
    """Verify CHANGELOG.md has an entry for this version."""
    if not CHANGELOG.exists():
        fatal("CHANGELOG.md not found")

    content = CHANGELOG.read_text()
    # Look for version header like ## [0.2.0] or ## 0.2.0
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
    """Update version in pyproject.toml."""
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
    """Update version in __init__.py."""
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


def create_release_branch(version: str, no_push: bool) -> None:
    """Create release branch, commit, and optionally create PR."""
    branch = f"release/v{version}"

    info(f"Creating branch {branch}...")
    run(["git", "checkout", "-b", branch])
    success(f"Created branch {branch}")

    info("Staging version changes...")
    run(["git", "add", str(PYPROJECT), str(INIT_FILE)])

    info("Creating commit...")
    run(["git", "commit", "-m", f"chore: bump version to {version}"])
    success("Created version bump commit")

    if no_push:
        warn("--no-push specified, skipping push and PR creation")
        info(f"To push manually: git push -u origin {branch}")
        return

    info("Pushing branch...")
    run(["git", "push", "-u", "origin", branch])
    success(f"Pushed {branch}")

    # Create PR via gh CLI
    result = run(["which", "gh"], capture=True, check=False)
    if result.returncode != 0:
        warn("gh CLI not found — create PR manually")
        return

    info("Creating pull request...")
    run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            f"Release v{version}",
            "--body",
            f"## Release v{version}\n\nVersion bump to {version}.\n\nAfter merge, tag with:\n```bash\ngit tag v{version}\ngit push origin v{version}\n```",
            "--base",
            "main",
        ]
    )
    success("Pull request created")


def main() -> None:
    parser = argparse.ArgumentParser(description="Release automation for ai-launcher")
    parser.add_argument("version", help="Version to release (X.Y.Z)")
    parser.add_argument(
        "--no-push", action="store_true", help="Don't push or create PR"
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite")
    parser.add_argument("--skip-quality", action="store_true", help="Skip ruff checks")
    args = parser.parse_args()

    version = args.version
    venv = detect_venv()

    print(f"\n{BOLD}AI Launcher Release — v{version}{NC}\n")

    # Phase 1: Validation
    header("Phase 1: Validation")
    validate_version(version)
    success(f"Version format OK: {version}")
    check_git_clean()
    check_on_main()
    check_tag_not_exists(version)

    # Phase 2: Quality
    header("Phase 2: Quality Checks")
    run_quality_checks(venv, args.skip_tests, args.skip_quality)

    # Phase 3: Changelog
    header("Phase 3: Changelog")
    check_changelog(version)

    # Phase 4: Update versions
    header("Phase 4: Update Versions")
    update_pyproject_version(version)
    update_init_version(version)

    # Phase 5: Git
    header("Phase 5: Git")
    create_release_branch(version, args.no_push)

    # Done
    print(f"\n{GREEN}{BOLD}━━━ Release v{version} prepared ━━━{NC}\n")


if __name__ == "__main__":
    main()
