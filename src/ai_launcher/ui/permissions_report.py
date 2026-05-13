"""Permission health check report for AI Launcher.

Scans all discovered projects for Claude Code permission accumulation
issues and prints a diagnostic report with fix recommendations.

This is a standalone diagnostic — it does not launch a session or
modify any files. Users run it via:

    ai-launcher claude ~/projects --check-permissions

Author: Solent Labs™
Created: 2026-03-24
"""

import sys
from pathlib import Path
from typing import List

from ai_launcher.core.models import Project


def check_project_permissions(
    projects: List[Project],
    provider_name: str,
) -> None:
    """Check permission health for all discovered projects.

    Scans each project for Claude Code settings files and reports
    accumulation issues with actionable fix commands.

    Args:
        projects: List of discovered projects
        provider_name: Provider name (currently only claude-code is supported)
    """
    # Only Claude Code has a permission system that accumulates
    if provider_name != "claude-code":
        print(
            f"Permission checking is only available for Claude Code (not {provider_name})"
        )
        sys.exit(0)

    from ai_launcher.providers.claude import (
        _get_claude_session_config,
    )

    print()
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  Claude Code Permission Health Check                           │")
    print("│  Scans projects for accumulated permission patterns            │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print()

    # Read global settings once (shared across all projects)
    _print_global_settings()
    print()

    # Scan each project
    issues_found = 0
    projects_checked = 0

    for project in projects:
        config = _get_claude_session_config(project.path)
        if config is None:
            continue

        projects_checked += 1

        if config.permission_warnings:
            issues_found += 1
            # Show project with warnings
            print(f"⚠  {project.name}")
            print(f"   {project.path}")

            for warning in config.permission_warnings:
                print(f"   ⚠ {warning}")

            for rec in config.permission_recommendations:
                print(f"   💡 {rec}")

            print()
        else:
            # Clean project — show briefly
            status_parts = []
            if config.has_broad_bash and "Bash(*)" in config.permissions:
                status_parts.append("Bash(*)")
            elif config.permissions_count > 0:
                status_parts.append(f"{config.permissions_count} rules")
            else:
                status_parts.append("inherits global")

            print(f"✓  {project.name} ({', '.join(status_parts)})")

    if projects_checked == 0:
        print("No projects with Claude Code settings found.")
        print()
        print("This is normal — projects inherit global permissions by default.")
        print(
            "Settings files are created when you click 'allow' on permission prompts."
        )
    else:
        print()
        print("─" * 65)
        print(f"Checked {projects_checked} project(s) with settings files")
        if issues_found > 0:
            print(f"⚠  {issues_found} project(s) with permission issues")
        else:
            print("✓  All projects healthy")

    print()


def _print_global_settings() -> None:
    """Print global Claude Code permission settings."""
    import json

    home = Path.home()

    print("Global Settings:")

    # settings.json
    settings_file = home / ".claude" / "settings.json"
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
            perms = settings.get("permissions", {})
            allow = perms.get("allow", [])
            deny = perms.get("deny", [])
            ask = perms.get("ask", [])

            if allow:
                print(f"  ✓ Allow: {', '.join(allow[:6])}")
                if len(allow) > 6:
                    print(f"    ...and {len(allow) - 6} more")
            if deny:
                print(f"  🚫 Deny: {', '.join(deny[:3])}")
            if ask:
                # Extract readable names
                ask_labels = []
                for pattern in ask:
                    if pattern.startswith("Bash(") and pattern.endswith(")"):
                        inner = pattern[5:-1]
                        ask_labels.append(inner.split(":")[0])
                    else:
                        ask_labels.append(pattern)
                print(f"  🚫 Ask before: {', '.join(ask_labels)}")
        except json.JSONDecodeError:
            print(f"  ⚠ {settings_file} has invalid JSON")
    else:
        print("  ○ No ~/.claude/settings.json")

    # settings.local.json
    local_file = home / ".claude" / "settings.local.json"
    if local_file.exists():
        try:
            settings = json.loads(local_file.read_text())
            allow = settings.get("permissions", {}).get("allow", [])
            if allow:
                print(f"  ✓ Local allow: {', '.join(allow[:6])}")
                if len(allow) > 6:
                    print(f"    ...and {len(allow) - 6} more")
        except json.JSONDecodeError:
            print(f"  ⚠ {local_file} has invalid JSON")
    else:
        print("  ○ No ~/.claude/settings.local.json")
