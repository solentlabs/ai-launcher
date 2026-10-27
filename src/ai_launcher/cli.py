"""CLI interface for ai-launcher.

This module provides the main command-line interface using Typer, handling
project selection, provider launching, and various commands like discovery
and context viewing.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added cleanup config to provider calls)
"""

import logging
import os
import shutil
import signal
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence

import typer

from ai_launcher import __version__
from ai_launcher.core.discovery import get_all_projects
from ai_launcher.core.models import ConfigData, UIConfig
from ai_launcher.ui.selector import select_project, show_project_list
from ai_launcher.ui.startup_report import display_launch_info
from ai_launcher.utils.logging import setup_logging
from ai_launcher.utils.terminal import format_terminal_title, set_terminal_title

if TYPE_CHECKING:
    from ai_launcher.core.update_check import UpdateNotice
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
    clean_npm: bool = False,
    global_files: Optional[str] = None,
    manual_paths: Optional[str] = None,
    check_permissions: bool = False,
    allow_writes: Optional[str] = None,
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
    cleanup_enabled = cleanup or clean_provider or clean_npm
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

    # Handle --check-permissions (no fzf needed — reads settings files only)
    if check_permissions:
        from ai_launcher.ui.permissions_report import check_project_permissions

        check_project_permissions(all_projects, provider_name)
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

    # Refresh stale cache sizes while the picker is open, so the launch notice
    # has numbers without ever walking a tree itself
    start_size_refresh()
    start_update_check()

    # Interactive selection
    selection = select_project(
        all_projects, config.ui.show_git_status, config, scan_paths, manual_paths_list
    )

    if selection is None:
        print("AI Launcher: No project selected")
        sys.exit(0)

    # The Shell row of the Open With list: no provider, so no cleanup or guard
    if selection.use_shell:
        launch_shell(selection.project.path, config)
        return

    # A provider picked from the Open With list replaces the default
    provider = None
    if selection.provider:
        from ai_launcher.providers.registry import get_provider

        provider = get_provider(selection.provider)

    # Launch AI provider. Every scanned folder and manual project is guarded:
    # writes there, outside the selected project, ask first, except into the
    # --allow-writes folders.
    scope_roots = [*scan_paths, *(p.path for p in manual_project_list)]
    scope_exempt = [
        Path(aw.strip()).expanduser()
        for aw in (allow_writes or "").split(",")
        if aw.strip()
    ]
    launch_ai(
        selection.project.path,
        provider=provider,
        config=config,
        scope_roots=scope_roots,
        scope_exempt=scope_exempt,
    )


def find_shell() -> Optional[str]:
    """Find the user's shell.

    Linux, macOS and WSL set SHELL; Windows sets COMSPEC. A value naming a
    program that cannot be found is skipped.

    Returns:
        The first of $SHELL, %COMSPEC% and /bin/sh that can be run, or None
    """
    for candidate in (os.environ.get("SHELL"), os.environ.get("COMSPEC"), "/bin/sh"):
        if candidate and shutil.which(candidate):
            return candidate
    return None


def launch_shell(project_path: Path, config: Optional[ConfigData] = None) -> None:
    """Open the user's shell in the specified project directory.

    Args:
        project_path: Path to the project
        config: Optional ConfigData, for the terminal title settings
    """
    # Verify directory exists
    if not project_path.exists():
        print(f"Error: Directory not found: {project_path}")
        sys.exit(1)

    shell = find_shell()
    if shell is None:
        print("Error: No shell found. Set SHELL, or COMSPEC on Windows.")
        sys.exit(1)

    ui = config.ui if config else UIConfig()
    if ui.set_terminal_title:
        set_terminal_title(
            format_terminal_title(ui.terminal_title_format, project_path, "Shell")
        )

    # The path as listed, made absolute without resolving symlinks
    listed_path = str(Path.cwd() / project_path)
    print(f"AI Launcher: shell in {listed_path} (type 'exit' to leave)")
    os.chdir(project_path)

    # PWD keeps a symlinked manual project's own path in the prompt. Shells
    # trust it only when it is absolute and names the current directory.
    env = {**os.environ, "PWD": listed_path}

    # Ctrl-C belongs to the shell while it runs. A handler, not SIG_IGN: an
    # ignored signal would stay ignored in everything the shell starts.
    previous = signal.signal(signal.SIGINT, lambda *_: None)
    try:
        completed = subprocess.run([shell], env=env, check=False)  # nosec B603
    finally:
        signal.signal(signal.SIGINT, previous)

    # Pass the shell's exit status on, as the prototype's exec does
    if completed.returncode:
        sys.exit(completed.returncode)


def start_size_refresh() -> None:
    """Start the background size refresh. Never raises: a launch comes first."""
    try:
        from ai_launcher.core.cache_notice import load_entries
        from ai_launcher.core.cache_registry import load_registry
        from ai_launcher.core.cache_scan import start_background_refresh

        registry = load_registry()
        if registry.notice.enabled:
            start_background_refresh(load_entries(registry, {"sizes": {}}))
    except Exception as error:
        logging.getLogger("ai_launcher").debug(f"Size refresh not started: {error}")


def start_update_check() -> None:
    """Start the opt-in background update check. Never raises: a launch comes first."""
    try:
        from ai_launcher.core.cache_registry import load_registry
        from ai_launcher.core.update_check import start_check

        start_check(load_registry().update_check)
    except Exception as error:
        logging.getLogger("ai_launcher").debug(f"Update check not started: {error}")


def current_update_notice() -> Optional["UpdateNotice"]:
    """The saved update notice for this launch, or None. Never raises."""
    try:
        from ai_launcher.core.cache_registry import load_registry
        from ai_launcher.core.update_check import update_notice

        return update_notice(load_registry().update_check, __version__)
    except Exception as error:
        logging.getLogger("ai_launcher").debug(f"Update notice failed: {error}")
        return None


def prepare_scratch(project_path: Path) -> Optional[Path]:
    """Make this session's scratch folder and name it in AI_SCRATCH_DIR.

    Returns None, and sets nothing, if the folder cannot be made: a session
    without scratch is better than no session.
    """
    from ai_launcher.core.scratch import ENV_VAR, create_session_dir

    try:
        path = create_session_dir(project_path.name)
    except OSError:
        return None
    os.environ[ENV_VAR] = str(path)
    return path


def launch_ai(
    project_path: Path,
    provider: Optional["AIProvider"] = None,
    config: Optional[ConfigData] = None,
    scope_roots: Sequence[Path] = (),
    scope_exempt: Sequence[Path] = (),
) -> None:
    """Launch AI provider in the specified project directory.

    Args:
        project_path: Path to the project
        provider: Optional AIProvider instance. If None, determined from config.
        config: Optional ConfigData. If None, default config is created.
        scope_roots: Directories holding other projects; writes there ask first
            (for providers that support it)
        scope_exempt: Directories under scope_roots writable without asking
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

    # The launch notice reads the size cache only; it never walks a tree
    from ai_launcher.core.cache_notice import launch_notice

    notice = launch_notice()
    update_notice = current_update_notice()

    # A scratch folder for the session. The scope guard must not ask about it.
    scratch_dir = prepare_scratch(project_path)
    if scratch_dir is not None:
        scope_exempt = [*scope_exempt, scratch_dir]

    # Display launch information and launch provider
    display_launch_info(
        project_path,
        provider,
        verbose=True,
        scope_roots=scope_roots,
        scope_exempt=scope_exempt,
        notice=notice,
        scratch_dir=scratch_dir,
        update_notice=update_notice,
    )
    try:
        provider.launch_with_title(
            project_path,
            set_title=config.ui.set_terminal_title,
            title_format=config.ui.terminal_title_format,
            scope_roots=scope_roots,
            scope_exempt=scope_exempt,
        )
    finally:
        if scratch_dir is not None:
            from ai_launcher.core.scratch import finish_session_dir

            finish_session_dir(scratch_dir)


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
    check_permissions: bool = typer.Option(
        False,
        "--check-permissions",
        help="Check permission health for all discovered projects",
    ),
    # Configuration options
    cleanup: bool = typer.Option(
        False, "--cleanup/--no-cleanup", help="Clean AI assistant cache/logs"
    ),
    clean_provider: bool = typer.Option(
        False,
        "--clean-provider/--no-clean-provider",
        help="Clean AI assistant cache/logs",
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
    allow_writes: Optional[str] = typer.Option(
        None,
        "--allow-writes",
        help="Comma-separated folders the session may write to without asking, "
        "even inside other projects (e.g. a shared journal)",
    ),
) -> None:
    """Launch Claude Code with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher claude ~/projects/solentlabs
        ai-launcher claude ~/projects --global-files ~/.claude/RULES.md
        ai-launcher claude ~/projects --cleanup
        ai-launcher claude ~/projects --check-permissions
        ai-launcher claude ~/projects --allow-writes ~/projects/journal
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
        clean_npm,
        global_files,
        manual_paths,
        check_permissions,
        allow_writes=allow_writes,
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
    clean_npm: bool = typer.Option(
        False, "--clean-npm/--no-clean-npm", help="Clean npm cache"
    ),
    global_files: Optional[str] = typer.Option(
        None, "--global-files", help="Comma-separated list of global context files"
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated list of manual project paths"
    ),
    allow_writes: Optional[str] = typer.Option(
        None,
        "--allow-writes",
        help="Comma-separated folders the session may write to, "
        "added to Gemini's workspace (e.g. a shared journal)",
    ),
) -> None:
    """Launch Gemini CLI with project selection.

    Configuration is passed via CLI flags.

    Examples:
        ai-launcher gemini ~/projects/external
        ai-launcher gemini ~/projects --global-files ~/.claude/RULES.md
        ai-launcher gemini ~/projects --cleanup
        ai-launcher gemini ~/projects --allow-writes ~/projects/journal
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
        clean_npm,
        global_files,
        manual_paths,
        allow_writes=allow_writes,
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
        clean_npm,
        global_files,
        manual_paths,
    )


def _project_paths(
    paths: Optional[List[Path]], manual_paths: Optional[str]
) -> List[Path]:
    """Every project under the scan paths and manual paths: the folders never deleted."""
    from ai_launcher.core.models import Project

    manual = []
    for mp in (manual_paths or "").split(","):
        mp_path = Path(mp.strip()).expanduser()
        if mp.strip() and mp_path.exists():
            manual.append(Project.from_path(mp_path, is_manual=True))
    scan = [p.resolve() for p in (paths or [])]
    projects = get_all_projects(
        scan, 5, ["node_modules", ".cache", "venv", ".git"], manual
    )
    return [p.path for p in projects]


@app.command()
def cache(
    paths: Optional[List[Path]] = typer.Argument(
        None,
        help="Scan folders, so projects are never offered for deletion",
        exists=True,
    ),
    manual_paths: Optional[str] = typer.Option(
        None, "--manual-paths", help="Comma-separated non-git projects to protect"
    ),
    list_only: bool = typer.Option(
        False, "--list", help="Print the table as plain text; nothing can be deleted"
    ),
) -> None:
    """See and clear the disk space AI sessions leave behind.

    Lists known cache and scratch locations with size, age and a safety class.
    Only locations in the registry can be deleted, after a confirm step.

    Example:
        ai-launcher cache ~/projects
    """
    from ai_launcher.ui.cache_page import list_command, run_cache_page
    from ai_launcher.utils.terminal import ensure_utf8_output

    ensure_utf8_output()
    projects = _project_paths(paths, manual_paths)
    if list_only:
        list_command(projects)
        return

    from ai_launcher.utils.fzf import ensure_fzf

    if not ensure_fzf():
        sys.exit(1)
    run_cache_page(projects)


@app.command()
def update(
    check: bool = typer.Option(
        False, "--check", help="Say whether a newer release exists; change nothing"
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Do not ask (needed without a terminal)"
    ),
) -> None:
    """Update AI Launcher to the latest release on PyPI.

    Contacts PyPI only when you run this. Shows the command first and asks.

    Example:
        ai-launcher update --check
    """
    from ai_launcher.ui.update import update_command
    from ai_launcher.utils.terminal import ensure_utf8_output

    ensure_utf8_output()
    raise typer.Exit(update_command(check=check, yes=yes))


scratch_app = typer.Typer(help="Per-session scratch folders", add_completion=False)
app.add_typer(scratch_app, name="scratch")


@scratch_app.command("prune")
def scratch_prune(
    older_than: str = typer.Option(
        ...,
        "--older-than",
        help="Remove session folders last written longer ago: 14d, 36h, 2w",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="List them, remove nothing"),
    yes: bool = typer.Option(
        False, "--yes", help="Do not ask (needed without a terminal)"
    ),
) -> None:
    """Remove old session scratch folders made by AI Launcher.

    Only the launcher's own scratch folder is touched. Sessions still running
    are never removed.

    Example:
        ai-launcher scratch prune --older-than 14d --dry-run
    """
    from ai_launcher.ui.cache_page import prune_command
    from ai_launcher.utils.terminal import ensure_utf8_output

    ensure_utf8_output()
    raise typer.Exit(prune_command(older_than, dry_run=dry_run, yes=yes))


if __name__ == "__main__":
    app()
