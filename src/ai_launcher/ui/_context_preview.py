#!/usr/bin/env python3
"""Preview helper for context viewer.

This script is called by fzf to generate preview content for the context viewer.

Author: Solent Labs™
Created: 2026-02-09
"""

import sys
from pathlib import Path

from ai_launcher.core.provider_discovery import ProviderDiscovery
from ai_launcher.utils.humanize import humanize_count, humanize_size


def show_provider_context(provider_name: str) -> None:
    """Show context information for a provider.

    Args:
        provider_name: Name of the provider to display
    """
    discovery = ProviderDiscovery()
    provider = discovery.get_provider_by_name(provider_name)

    if not provider:
        print(f"Provider not found: {provider_name}")
        return

    # Header
    print(f"\033[1m{provider.name}\033[0m")
    print("━" * 80)
    print()

    # Installation status
    if not provider.context:
        print("\033[33mStatus: Not installed\033[0m")
        print()
        print(f"Command: {provider.command}")
        print(f"Install: {provider.install_url}")
        print()
        print("This provider is not currently available on your system.")
        return

    context = provider.context

    # Version and status
    print("\033[32m✓ Installed\033[0m")
    print()
    print(f"Command: {provider.command}")
    if context.version:
        print(f"Version: {context.version}")
    if context.executable_path:
        print(f"Executable: {context.executable_path}")
    print()

    # Global configuration
    print("\033[1mGLOBAL CONFIGURATION\033[0m")
    if context.global_config:
        for path in context.global_config:
            if path.exists():
                if path.is_dir():
                    print(f"  ✓ {path}/ (directory)")
                else:
                    size = humanize_size(path.stat().st_size)
                    print(f"  ✓ {path} ({size})")
            else:
                print(f"  ✗ {path} (missing)")
    else:
        print("  No global config files detected")
    print()

    # Project data pattern
    if context.project_data_pattern:
        print("\033[1mPROJECT DATA PATTERN\033[0m")
        print(f"  {context.project_data_pattern}")
        print()

    # Context categories
    print("\033[1mCONTEXT BREAKDOWN\033[0m")
    if context.categories:
        from ai_launcher.core.context_analyzer import ContextAnalyzer

        analyzer = ContextAnalyzer()
        sizes = analyzer.calculate_sizes(context.categories)

        # Sort categories by size (largest first)
        sorted_categories = sorted(
            context.categories.items(), key=lambda x: sizes.get(x[0], 0), reverse=True
        )

        for category, files in sorted_categories:
            if files:
                size = humanize_size(sizes[category])
                count = humanize_count(len(files), "file")
                print(f"  {category.capitalize()}: {count} ({size})")

        print()

    # Total summary
    print("\033[1mTOTAL CONTEXT\033[0m")
    print(f"  Files: {humanize_count(context.file_count, 'file')}")
    print(f"  Size: {humanize_size(context.total_size)}")


def show_project_context(project_path: Path) -> None:
    """Show context information for a project.

    Args:
        project_path: Path to the project
    """
    if not project_path.exists():
        print(f"\033[33mProject not found: {project_path}\033[0m")
        return

    # Header
    print(f"\033[1m{project_path.name}\033[0m")
    print("━" * 80)
    print()

    # Basic info
    print(f"Path: {project_path}")
    is_git = (project_path / ".git").exists()
    print(f"Type: {'Git repository' if is_git else 'Directory'}")
    print()

    # Check for context files
    print("\033[1mCONTEXT FILES\033[0m")
    context_files = ["CLAUDE.md", ".clauderc", "GEMINI.md", ".geminirc", "README.md"]
    found_any = False

    for filename in context_files:
        file_path = project_path / filename
        if file_path.exists():
            size = humanize_size(file_path.stat().st_size)
            print(f"  ✓ {filename} ({size})")
            found_any = True
        else:
            print(f"  ✗ {filename}")

    if not found_any:
        print()
        print("  No context files found in this project.")

    print()

    # Git status if applicable
    if is_git:
        print("\033[1mGIT STATUS\033[0m")
        try:
            import subprocess

            result = subprocess.run(
                ["git", "-C", str(project_path), "status", "--short"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")[:10]
                for line in lines:
                    print(f"  {line}")
                if len(result.stdout.strip().split("\n")) > 10:
                    print("  ... and more changes")
            else:
                print("  Working tree clean")
        except Exception:
            print("  Could not get git status")


def main() -> None:
    """Main entry point for preview helper."""
    if len(sys.argv) < 2:
        print("Usage: _context_preview.py <item>")
        sys.exit(1)

    line = sys.argv[1]

    # Handle different item types
    if line.startswith("PROVIDER:"):
        provider_name = line.split(":", 1)[1]
        show_provider_context(provider_name)
    elif line.startswith("PROJECT:"):
        project_path = Path(line.split(":", 1)[1])
        show_project_context(project_path)
    elif line.startswith("__HEADER__"):
        # Header items - show nothing
        pass
    elif line.startswith("__SPACER__"):
        # Spacer items - show nothing
        pass
    elif line.startswith("__INFO__"):
        # Info items - show nothing
        pass
    else:
        print("Unknown item type")


if __name__ == "__main__":
    main()
