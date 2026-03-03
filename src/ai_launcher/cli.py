"""CLI interface for ai-launcher.

This module provides the main command-line interface using Typer, handling
project selection, provider launching, and various commands like discovery
and context viewing.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added cleanup config to provider calls)
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

from ai_launcher import __version__
from ai_launcher.core.discovery import get_all_projects
from ai_launcher.core.models import ConfigData
from ai_launcher.ui.selector import select_project, show_project_list
from ai_launcher.ui.startup_report import display_launch_info
from ai_launcher.utils.logging import setup_logging

if TYPE_CHECKING:
    from ai_launcher.providers.base import AIProvider

app = typer.Typer(
    help="AI coding assistant launcher with multi-provider support",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"ai-launcher {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """AI coding assistant launcher with multi-provider support."""


def _run_launcher(
    provider_name: str,
    path: Optional[Path] = None,
    verbose: bool = False,
    debug: bool = False,
    list_projects: bool = False,
    discover: bool = False,
    context: bool = False,
    cleanup: bool = False,
    clean_provider: bool = False,
    clean_cache: bool = False,
    clean_npm: bool = False,
    global_files: Optional[str] = None,
    manual_paths: Optional[str] = None,
) -> None:
    """Internal function to run the launcher with specified provider."""

    # Setup logging
    logger = setup_logging(verbose=verbose or debug)
    logger.debug("AI Launcher starting")
    logger.debug(f"Version: {__version__}")

    # Build runtime config from CLI flags (no config file needed)
    from ai_launcher.core.models import (
        CleanupConfig,
        ConfigData,
        ContextConfig,
        ProviderConfig,
        ScanConfig,
        UIConfig,
    )

    # Parse global files from comma-separated string
    global_files_list = []
    if global_files:
        global_files_list = [f.strip() for f in global_files.split(",") if f.strip()]

    # Build cleanup config - each flag works independently
    cleanup_enabled = cleanup or clean_provider or clean_cache or clean_npm
    config = ConfigData(
        scan=ScanConfig(
            paths=[],  # Will be set from CLI argument
            max_depth=5,
            prune_dirs=["node_modules", ".cache", "venv", "__pycache__", ".git"],
        ),
        ui=UIConfig(
            preview_width=70,
            show_git_status=True,
            set_terminal_title=True,
            terminal_title_format="{project} → {provider}",
        ),
        cleanup=CleanupConfig(
            enabled=cleanup_enabled,
            clean_provider_files=cleanup or clean_provider,
            clean_system_cache=clean_cache,
            clean_npm_cache=clean_npm,
        ),
        context=ContextConfig(
            global_files=global_files_list,
        ),
        provider=ProviderConfig(
            default=provider_name,
            per_project={},
        ),
    )

    # Determine scan paths: CLI argument takes precedence
    if path:
        scan_paths = [path.resolve()]
    else:
        # Only error if we need scan paths for the operation
        if not (discover or context):
            print(f"Error: No directory specified for {provider_name}")
            print(f"Usage: ai-launcher {provider_name} ~/projects")
            sys.exit(1)
        # For discover/context without paths, use empty list
        scan_paths = []

    # Get all projects (needed for several commands)
    # Parse manual paths from CLI flag
    manual_project_list = []
    if manual_paths:
        from ai_launcher.core.models import Project

        for mp in manual_paths.split(","):
            mp = mp.strip()
            if mp:
                mp_path = Path(mp).expanduser()
                if mp_path.exists():
                    manual_project_list.append(
                        Project(
                            path=mp_path,
                            name=mp_path.name,
                            parent_path=mp_path.parent,
                            is_git_repo=(mp_path / ".git").exists(),
                            is_manual=True,
                        )
                    )

    all_projects = (
        get_all_projects(
            scan_paths,
            config.scan.max_depth,
            config.scan.prune_dirs,
            manual_project_list,
        )
        if scan_paths
        else []
    )

    # Handle --discover (no fzf needed)
    if discover:
        from ai_launcher.core.provider_discovery import ProviderDiscovery
        from ai_launcher.ui.discovery import show_discovery_report

        discovery = ProviderDiscovery()
        provider_infos = discovery.detect_all()

        show_discovery_report(all_projects, provider_infos, scan_paths)
        sys.exit(0)

    # Handle --list (no fzf needed)
    if list_projects:
        show_project_list(all_projects)
        sys.exit(0)

    # All remaining code paths require fzf — ensure it's available
    from ai_launcher.utils.fzf import ensure_fzf

    if not ensure_fzf():
        sys.exit(1)

    # Handle --context
    if context:
        from ai_launcher.core.provider_discovery import ProviderDiscovery
        from ai_launcher.ui.context_viewer import show_context_viewer

        discovery = ProviderDiscovery()
        provider_infos = discovery.detect_all()

        show_context_viewer(provider_infos, all_projects)
        sys.exit(0)

    # Parse manual paths for display (convert to list of path strings)
    manual_paths_list = []
    if manual_paths:
        manual_paths_list = [mp.strip() for mp in manual_paths.split(",") if mp.strip()]

    # Interactive selection
    selected_project = select_project(
        all_projects, config.ui.show_git_status, config, scan_paths, manual_paths_list
    )

    if selected_project is None:
        print("AI Launcher: No project selected")
        sys.exit(0)

    # Launch AI provider
    launch_ai(selected_project.path, config=config)


def launch_ai(
    project_path: Path,
    provider: Optional["AIProvider"] = None,
    config: Optional[ConfigData] = None,
) -> None:
    """Launch AI provider in the specified project directory.

    Args:
        project_path: Path to the project
        provider: Optional AIProvider instance. If None, determined from config.
        config: Optional ConfigData. If None, default config is created.
    """
    from ai_launcher.providers.registry import get_provider

    # Verify directory exists
    if not project_path.exists():
        print(f"Error: Directory not found: {project_path}")
        sys.exit(1)

    # Determine provider if not explicitly provided
    if provider is None:
        # Use default config if none provided
        if config is None:
            from ai_launcher.core.models import (
                CleanupConfig,
                ConfigData,
                ContextConfig,
                ProviderConfig,
                ScanConfig,
                UIConfig,
            )

            config = ConfigData(
                scan=ScanConfig(paths=[], max_depth=5, prune_dirs=[]),
                ui=UIConfig(),
                cleanup=CleanupConfig(enabled=False),
                context=ContextConfig(global_files=[]),
                provider=ProviderConfig(default="claude-code", per_project={}),
            )

        # Check per-project override
        project_str = str(project_path)
        if project_str in config.provider.per_project:
            provider_name = config.provider.per_project[project_str]
        else:
            provider_name = config.provider.default

        provider = get_provider(provider_name)

    # Clean environment before launching (if configured)
    print()
    provider.cleanup_environment(verbose=True, cleanup_config=config.cleanup)

    # Display launch information and launch provider
    display_launch_info(project_path, provider, verbose=True)
    provider.launch_with_title(
        project_path,
        set_title=config.ui.set_terminal_title,
        title_format=config.ui.terminal_title_format,
    )


@app.command()
def claude(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for projects (optional)",
        exists=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    list_projects: bool = typer.Option(False, "--list", help="List all projects"),
    discover: bool = typer.Option(
        False, "--discover", "-d", help="Show discovery report"
    ),
    context: bool = typer.Option(False, "--context", "-c", help="Show context viewer"),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
    ),
    clean_cache: bool = typer.Option(
        False, "--clean-cache/--no-clean-cache", help="Clean system cache (~/.cache)"
    ),
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
) -> None:
    """Launch Claude Code with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher claude ~/projects/solentlabs
        ai-launcher claude ~/projects --global-files ~/.claude/RULES.md
        ai-launcher claude ~/projects --cleanup --clean-cache
    """
    # Just call main() with provider forced to claude-code
    _run_launcher(
        "claude-code",
        path,
        verbose,
        debug,
        list_projects,
        discover,
        context,
        cleanup,
        clean_provider,
        clean_cache,
        clean_npm,
        global_files,
        manual_paths,
    )


@app.command()
def gemini(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for projects (optional)",
        exists=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    list_projects: bool = typer.Option(False, "--list", help="List all projects"),
    discover: bool = typer.Option(
        False, "--discover", "-d", help="Show discovery report"
    ),
    context: bool = typer.Option(False, "--context", "-c", help="Show context viewer"),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
    ),
    clean_cache: bool = typer.Option(
        False, "--clean-cache/--no-clean-cache", help="Clean system cache (~/.cache)"
    ),
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
) -> None:
    """Launch Gemini CLI with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher gemini ~/projects/external
        ai-launcher gemini ~/projects --global-files ~/.claude/RULES.md
        ai-launcher gemini ~/projects --cleanup --clean-cache
    """
    # Just call main() with provider forced to gemini
    _run_launcher(
        "gemini",
        path,
        verbose,
        debug,
        list_projects,
        discover,
        context,
        cleanup,
        clean_provider,
        clean_cache,
        clean_npm,
        global_files,
        manual_paths,
    )


@app.command()
def cursor(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for projects (optional)",
        exists=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    list_projects: bool = typer.Option(False, "--list", help="List all projects"),
    discover: bool = typer.Option(
        False, "--discover", "-d", help="Show discovery report"
    ),
    context: bool = typer.Option(False, "--context", "-c", help="Show context viewer"),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
    ),
    clean_cache: bool = typer.Option(
        False, "--clean-cache/--no-clean-cache", help="Clean system cache (~/.cache)"
    ),
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
) -> None:
    """Launch Cursor with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher cursor ~/projects
        ai-launcher cursor ~/projects --global-files ~/.cursor/RULES.md
    """
    _run_launcher(
        "cursor",
        path,
        verbose,
        debug,
        list_projects,
        discover,
        context,
        cleanup,
        clean_provider,
        clean_cache,
        clean_npm,
        global_files,
        manual_paths,
    )


@app.command()
def aider(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for projects (optional)",
        exists=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    list_projects: bool = typer.Option(False, "--list", help="List all projects"),
    discover: bool = typer.Option(
        False, "--discover", "-d", help="Show discovery report"
    ),
    context: bool = typer.Option(False, "--context", "-c", help="Show context viewer"),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
    ),
    clean_cache: bool = typer.Option(
        False, "--clean-cache/--no-clean-cache", help="Clean system cache (~/.cache)"
    ),
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
) -> None:
    """Launch Aider with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher aider ~/projects
        ai-launcher aider ~/projects --global-files ~/.aider/RULES.md
    """
    _run_launcher(
        "aider",
        path,
        verbose,
        debug,
        list_projects,
        discover,
        context,
        cleanup,
        clean_provider,
        clean_cache,
        clean_npm,
        global_files,
        manual_paths,
    )


@app.command()
def copilot(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for projects (optional)",
        exists=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    list_projects: bool = typer.Option(False, "--list", help="List all projects"),
    discover: bool = typer.Option(
        False, "--discover", "-d", help="Show discovery report"
    ),
    context: bool = typer.Option(False, "--context", "-c", help="Show context viewer"),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
    ),
    clean_cache: bool = typer.Option(
        False, "--clean-cache/--no-clean-cache", help="Clean system cache (~/.cache)"
    ),
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
) -> None:
    """Launch GitHub Copilot CLI with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher copilot ~/projects
        ai-launcher copilot ~/projects --global-files ~/.config/github-copilot/RULES.md
    """
    _run_launcher(
        "copilot",
        path,
        verbose,
        debug,
        list_projects,
        discover,
        context,
        cleanup,
        clean_provider,
        clean_cache,
        clean_npm,
        global_files,
        manual_paths,
    )


if __name__ == "__main__":
    app()
