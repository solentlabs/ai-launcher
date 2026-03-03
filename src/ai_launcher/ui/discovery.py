"""Discovery report UI for displaying provider and project discovery results.

Author: Solent Labs™
Created: 2026-02-09
"""

from pathlib import Path
from typing import List

from ai_launcher.core.models import Project, ProviderInfo
from ai_launcher.utils.humanize import humanize_count, humanize_size
from ai_launcher.utils.paths import is_relative_to


def generate_discovery_report(
    projects: List[Project],
    providers: List[ProviderInfo],
    scan_paths: List[Path],
) -> str:
    """Generate discovery report text.

    Args:
        projects: List of discovered projects
        providers: List of detected providers
        scan_paths: Paths that were scanned

    Returns:
        Formatted discovery report string
    """
    lines = []

    # Header with branding
    lines.append("╭─────────────────────────────────────────────╮")
    lines.append("│         AI Launcher - Discovery Report      │")
    lines.append("│              by Solent Labs™                │")
    lines.append("╰─────────────────────────────────────────────╯")
    lines.append("")

    # Projects section
    lines.append("PROJECTS DISCOVERED")
    lines.append("━" * 48)
    if scan_paths:
        # Format paths with ~ shorthand
        home = Path.home()
        display_paths = [
            f"~/{p.relative_to(home)}" if is_relative_to(p, home) else str(p)
            for p in scan_paths
        ]
        lines.append(f"Scan paths: {', '.join(display_paths)}")
    lines.append(f"Found {humanize_count(len(projects), 'project')}:")
    lines.append("")

    # Show first 10 projects
    for project in projects[:10]:
        marker = "[git]" if project.is_git_repo else "[manual]"
        lines.append(f"  📁 {project.name} {marker}")

    if len(projects) > 10:
        remaining = len(projects) - 10
        lines.append(f"  ... ({humanize_count(remaining, 'more project')})")

    lines.append("")

    # Providers section
    lines.append("AI PROVIDERS")
    lines.append("━" * 48)

    installed_count = sum(1 for p in providers if p.context is not None)
    lines.append(f"Found {installed_count}/{len(providers)} installed providers:")
    lines.append("")

    for provider in providers:
        if provider.context:
            # Installed provider
            status = f"✓ {provider.name}"
            if provider.context.version:
                status += f" v{provider.context.version}"
            lines.append(status)
            lines.append(f"  Command: {provider.command}")
            lines.append("  Status: Ready to use")

            # Show context stats if available
            if provider.context.file_count > 0:
                lines.append(
                    f"  Context: {humanize_count(provider.context.file_count, 'file')} "
                    f"({humanize_size(provider.context.total_size)})"
                )
        else:
            # Not installed
            lines.append(f"✗ {provider.name}")
            lines.append(f"  Command: {provider.command}")
            lines.append("  Status: Not installed")
            if provider.install_url:
                lines.append(f"  Install: {provider.install_url}")

        lines.append("")

    # Next steps
    lines.append("NEXT STEPS")
    lines.append("━" * 48)
    lines.append("Launch a project:")
    lines.append("  ai-launcher ~/projects")
    lines.append("")
    lines.append("View context info:")
    lines.append("  ai-launcher --context")
    lines.append("")
    lines.append("List all projects:")
    lines.append("  ai-launcher --list")
    lines.append("")

    return "\n".join(lines)


def show_discovery_report(
    projects: List[Project],
    providers: List[ProviderInfo],
    scan_paths: List[Path],
) -> None:
    """Display discovery report to user.

    Args:
        projects: List of discovered projects
        providers: List of detected providers
        scan_paths: Paths that were scanned
    """
    report = generate_discovery_report(projects, providers, scan_paths)
    print(report)
    print("Press Enter to continue...")
    input()
