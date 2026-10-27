"""Environment cleanup utilities.

.. deprecated:: 0.1.0
    Provider-specific cleanup has been moved to individual provider classes.
    This module is kept for backward compatibility with system-wide cleanup
    (npm) but provider-specific logic should use provider.cleanup_environment().

The ~/.cache sweep that used to live here (--clean-cache) was removed: it deleted every
child of ~/.cache with no list and no confirmation. Use `ai-launcher cache` instead
(see docs/cache-and-scratch.md).

This module provides cleanup functions to maintain a clean development environment
before launching AI assistants.

IMPORTANT: This cleanup is COMPLEMENTARY to Claude's built-in cleanup.
Claude Code has a built-in cleanup process controlled by the cleanupPeriodDays
setting (default: 30 days) that ONLY cleans session transcripts in
~/.claude/projects/. This module addresses the gaps that Claude doesn't clean.

NOTE: As of February 2026, provider-specific cleanup (Claude backup files, debug logs,
old versions) has been moved to ClaudeProvider.cleanup_environment(). This module now
only handles system-wide cleanup (npm) which is unrelated to specific providers.

What Claude cleans automatically:
  - Session transcripts older than cleanupPeriodDays (default: 30 days)
  - Reference: https://code.claude.com/docs/en/settings
  - GitHub Issues: #2543, #18881 (documentation ambiguity)
    https://github.com/anthropics/claude-code/issues/2543
    https://github.com/anthropics/claude-code/issues/18881

What this module cleans (Claude does NOT clean these):
  - Debug logs (~/.claude/debug/)
  - Old CLI versions (~/.local/share/claude/versions/)
  - Backup files (~/.claude.json.backup.*) - bug workaround
  - npm cache (~/.npm/)

This module addresses known issues and common pain points:

1. NPM Cache Accumulation (General Issue)
   - npm stores packages in ~/.npm which can reach 800MB+
   - Cleaned via official `npm cache clean --force` command
   - Safe to clear as npm re-downloads packages when needed

2. Claude Code Backup File Bug (Known Issue)
   - GitHub Issue: https://github.com/anthropics/claude-code/issues/21429
   - Bug: Claude creates multiple .claude.json.backup.* files on startup
   - Files created within milliseconds but never cleaned up
   - Causes clutter in home directory (~/ instead of ~/.claude/)
   - **TODO: Remove this cleanup when issue is fixed**

3. Claude Debug Logs Accumulation (General Issue)
   - Debug logs in ~/.claude/debug/ accumulate indefinitely
   - Can reach 500MB+ with 600+ files over time
   - Keeps last 7 days for troubleshooting, removes older logs
   - Safe to clean as logs are for debugging, not critical data

4. Old Claude CLI Versions Accumulation (General Issue)
   - Claude auto-updates and leaves old versions behind
   - Stored in ~/.local/share/claude/versions/
   - Each version is ~212MB, can accumulate to 600MB+
   - Only current version is needed, old versions are unused binaries
   - Best practice: Regular cleanup of accumulated files
   - Reference: https://ctok.ai/en/claude-code-cleanup
   - Reference: https://claudelog.com/faqs/revert-claude-code-version/

Author: Solent Labs™
Created: 2026-02-09
Last Modified: 2026-02-10 (Added cleanup config support)
"""

import re
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from ai_launcher.utils.logging import get_logger

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig

logger = get_logger(__name__)

_VERSION_FILE = re.compile(r"^\d+\.\d+\.\d+$")


def prune_claude_backups(home: Path) -> int:
    """Remove old ``~/.claude.json.backup.*`` files, keeping the newest.

    Claude Code writes one at every start and never removes them. The newest can
    be the only recovery copy of a damaged ``~/.claude.json``, so it stays. A
    file that cannot be removed is skipped. Returns how many were removed.
    """
    try:
        backups = [f for f in home.glob(".claude.json.backup.*") if f.is_file()]
        backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError as error:
        logger.debug(f"Could not list backup files: {error}")
        return 0
    removed = 0
    for backup in backups[1:]:
        try:
            backup.unlink(missing_ok=True)
            removed += 1
        except OSError as error:
            logger.debug(f"Could not remove {backup}: {error}")
    return removed


def prune_claude_versions(
    home: Path, which: Optional[Callable[[str], Optional[str]]] = None
) -> int:
    """Remove native Claude Code versions other than the one `claude` runs.

    Only when the ``claude`` on PATH resolves into the native versions folder:
    the file it resolves to is the version in use, and is kept. If ``claude``
    comes from elsewhere (an npm install, say) nothing is removed, because the
    native version in use cannot be told. Reading ``claude --version`` for it
    once deleted the binary that ``~/.local/bin/claude`` points to. A file that
    cannot be removed is skipped. Returns how many were removed.
    """
    versions = home / ".local" / "share" / "claude" / "versions"
    try:
        found = (which or shutil.which)("claude")
        if not found or not versions.is_dir():
            return 0
        in_use = Path(found).resolve()
        if in_use.parent != versions.resolve():
            return 0
        candidates = [
            f
            for f in versions.iterdir()
            if f.is_file() and f.name != in_use.name and _VERSION_FILE.match(f.name)
        ]
    except OSError as error:
        logger.debug(f"Could not look at Claude versions: {error}")
        return 0
    removed = 0
    for version in candidates:
        try:
            version.unlink(missing_ok=True)
            removed += 1
        except OSError as error:
            logger.debug(f"Could not remove {version}: {error}")
    return removed


def cleanup_environment(
    verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
) -> None:
    """Clean up environment before launching AI assistant.

    This function is COMPLEMENTARY to Claude's built-in cleanupPeriodDays setting,
    which only cleans session transcripts. This function cleans what Claude doesn't.

    Cleanup operations (controlled by cleanup_config):
    1. Provider-specific files (if clean_provider_files=True):
       - Old timestamped .claude.json.backup.* files (bug workaround)
       - Claude debug logs older than debug_logs_max_age_days
       - Old Claude CLI versions, keeps only current
    2. npm cache (if clean_npm_cache=True):
       - Cleans npm cache (WARNING: affects npm installs)

    Args:
        verbose: Whether to print cleanup messages to stdout
        cleanup_config: Configuration object controlling what gets cleaned.
                       If None, no cleanup is performed (safe default).

    Note:
        All cleanup operations are non-fatal - errors are logged but don't stop execution.
        Monitor GitHub issue #21429 and remove backup cleanup when the bug is fixed.

        Claude's cleanupPeriodDays setting (default: 30) automatically cleans session
        transcripts, so we don't need to handle that here. See:
        - https://code.claude.com/docs/en/settings
        - https://github.com/anthropics/claude-code/issues/2543
    """
    # If no config provided or cleanup disabled, do nothing
    if cleanup_config is None or not cleanup_config.enabled:
        return

    home = Path.home()

    if verbose:
        print("Pre-launch cleanup:")

    # Clean npm cache (OPTIONAL - unrelated to AI providers)
    # WARNING: Can slow down future npm install operations
    if cleanup_config.clean_npm_cache and shutil.which("npm"):
        if verbose:
            print("  → Clearing npm cache")
        try:
            subprocess.run(
                ["npm", "cache", "clean", "--force"],
                capture_output=True,
                check=False,
                timeout=10,
            )  # nosec B603, B607
            logger.debug("Cleaned npm cache")
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug(f"Could not clean npm cache: {e}")

    # Provider-specific cleanup (safe, only affects AI providers)
    if cleanup_config.clean_provider_files:
        # Remove old timestamped .claude.json.backup.* files (bug workaround)
        # Addresses Claude Code bug: https://github.com/anthropics/claude-code/issues/21429
        # Claude creates multiple backup files on startup but never cleans them up.
        # Files are created in ~/ instead of ~/.claude/ directory.
        # TODO: Remove this cleanup when GitHub issue #21429 is resolved.
        if verbose:
            print("  → Removing old .claude.json.backup.* files (keeping the newest)")
        prune_claude_backups(home)

        # Remove old Claude debug logs (provider-specific maintenance)
        # Debug logs in ~/.claude/debug/ accumulate indefinitely and can reach 500MB+.
        # Keep last N days (from config) for troubleshooting, remove older logs.
        # Safe to clean as logs are for debugging, not critical data.
        max_age_days = cleanup_config.debug_logs_max_age_days
        if verbose:
            print(f"  → Removing Claude debug logs older than {max_age_days} days")
        claude_debug_dir = home / ".claude" / "debug"
        if claude_debug_dir.exists() and claude_debug_dir.is_dir():
            try:
                import time

                current_time = time.time()
                cutoff_time = current_time - (max_age_days * 24 * 60 * 60)

                removed_count = 0
                for debug_file in claude_debug_dir.glob("*.txt"):
                    if (
                        debug_file.is_file()
                        and debug_file.stat().st_mtime < cutoff_time
                    ):
                        debug_file.unlink(missing_ok=True)
                        removed_count += 1

                if removed_count > 0:
                    logger.debug(f"Removed {removed_count} old Claude debug log(s)")
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not clean Claude debug logs: {e}")

        # Remove old Claude CLI versions (provider-specific maintenance)
        # Claude auto-updates leave old versions in ~/.local/share/claude/versions/
        # Each version is ~212MB. Keep only the currently running version.
        # Best practice: Regular cleanup of accumulated files
        # References: https://ctok.ai/en/claude-code-cleanup
        #            https://claudelog.com/faqs/revert-claude-code-version/
        if verbose:
            print("  → Removing old Claude CLI versions (keeping the one in use)")
        prune_claude_versions(home)

    if verbose:
        print("  ✓ Cleanup complete")
