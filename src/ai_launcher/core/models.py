"""Data models for ai-launcher.

This module defines the core data structures used throughout the application,
including project representation, configuration models, and context information.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added CleanupConfig)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Project:
    """Represents a project that can be launched with Claude."""

    path: Path
    name: str
    parent_path: Path
    is_git_repo: bool
    is_manual: bool

    @classmethod
    def from_path(cls, path: Path, is_manual: bool = False) -> "Project":
        """Create a Project from a filesystem path.

        Args:
            path: Path to the project directory
            is_manual: Whether this was manually added (vs auto-discovered)

        Returns:
            Project instance
        """
        # For manual projects, don't resolve symlinks so they appear under their symlink location
        # For discovered projects, resolve to avoid duplicates
        if is_manual:
            resolved_path = path
        else:
            resolved_path = path.resolve()

        is_git = (resolved_path / ".git").exists()
        return cls(
            path=resolved_path,
            name=resolved_path.name,
            parent_path=resolved_path.parent,
            is_git_repo=is_git,
            is_manual=is_manual,
        )

    def __str__(self) -> str:
        """String representation showing path."""
        return str(self.path)


@dataclass
class ScanConfig:
    """Configuration for project scanning."""

    paths: List[Path] = field(default_factory=list)
    max_depth: int = 5
    prune_dirs: List[str] = field(
        default_factory=lambda: [
            "node_modules",
            ".cache",
            "venv",
            "__pycache__",
            ".git",
            ".venv",
            "env",
            "ENV",
        ]
    )


@dataclass
class UIConfig:
    """Configuration for user interface.

    Attributes:
        preview_width: Width of the preview pane in fzf
        show_git_status: Whether to show git status in preview
        set_terminal_title: Whether to set terminal window title on launch
        terminal_title_format: Format string for terminal title
                               Available variables: {project}, {provider}, {path}, {parent}
    """

    preview_width: int = 70
    show_git_status: bool = True
    set_terminal_title: bool = True
    terminal_title_format: str = "{project} → {provider}"


@dataclass
class HistoryConfig:
    """Configuration for history tracking."""

    max_entries: int = 50


@dataclass
class ProviderConfig:
    """Configuration for AI provider selection.

    Attributes:
        default: Default provider to use (e.g., "claude-code")
        per_project: Map of project paths to provider names for overrides
    """

    default: str = "claude-code"
    per_project: dict = field(default_factory=dict)


@dataclass
class ContextConfig:
    """Configuration for global context files.

    Attributes:
        global_files: List of markdown files to load for all projects
                     e.g., ["~/projects/solentlabs/devkit/STANDARDS.md", ...]
    """

    global_files: List[str] = field(default_factory=list)


@dataclass
class CleanupConfig:
    """Configuration for pre-launch cleanup operations.

    Attributes:
        enabled: Whether to run any cleanup before launch (default: False)
        clean_provider_files: Clean provider-specific files (backups, debug logs, old versions)
        clean_system_cache: Clean entire ~/.cache directory (WARNING: affects all apps)
        clean_npm_cache: Clean npm cache using npm CLI (WARNING: affects npm installs)
        debug_logs_max_age_days: Maximum age of debug logs to keep (default: 7 days)
    """

    enabled: bool = False
    clean_provider_files: bool = True
    clean_system_cache: bool = False
    clean_npm_cache: bool = False
    debug_logs_max_age_days: int = 7


@dataclass
class ConfigData:
    """Complete configuration for ai-launcher."""

    scan: ScanConfig = field(default_factory=ScanConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)



@dataclass
class ProviderContext:
    """Context files and directories a provider accesses.

    Attributes:
        name: Provider name
        version: Provider version if available
        installed: Whether provider is installed
        executable_path: Path to provider executable
        global_config: List of global configuration files
        project_data_pattern: Pattern showing how provider stores project data
        categories: Categorized list of context files (config, logs, cache, etc.)
        total_size: Total size of all context files in bytes
        file_count: Total number of context files
    """

    name: str
    version: Optional[str] = None
    installed: bool = False
    executable_path: Optional[Path] = None
    global_config: List[Path] = field(default_factory=list)
    project_data_pattern: str = ""
    categories: dict = field(default_factory=dict)
    total_size: int = 0
    file_count: int = 0


@dataclass
class ProviderInfo:
    """Information about an AI provider for discovery.

    Attributes:
        name: Provider display name
        command: CLI command to execute
        context: Provider context information if installed
        install_url: URL with installation instructions
        detection_paths: Paths used to detect the provider
    """

    name: str
    command: str
    context: Optional[ProviderContext] = None
    install_url: str = ""
    detection_paths: List[Path] = field(default_factory=list)
