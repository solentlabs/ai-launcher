"""Data structures for provider preview data.

These classes define the contract between providers and the preview layer.
Providers return instances of these classes (NOT dicts or formatted strings).
The preview layer formats these into display-ready content.

Separation of concerns:
- Providers collect DATA (return these dataclasses)
- Preview layer handles PRESENTATION (formats these for display)

Author: Solent Labs™
Created: 2026-02-12
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ContextFile:
    """Information about a context file (e.g., CLAUDE.md, GEMINI.md).

    Attributes:
        path: Absolute path to the file
        label: Display label (e.g., "CLAUDE.md", ".cursorrules")
        exists: Whether the file exists
        size_bytes: File size in bytes (0 if doesn't exist)
        line_count: Number of lines (0 if doesn't exist)
        file_type: Type of context file ("personal", "project", "shared")
        content_preview: First N lines of content (optional)
    """

    path: Path
    label: str
    exists: bool
    size_bytes: int = 0
    line_count: int = 0
    file_type: str = "unknown"  # "personal", "project", "shared"
    content_preview: Optional[str] = None


@dataclass
class MemoryFile:
    """Information about a memory file (provider's learning/notes).

    Attributes:
        path: Path to memory file
        name: Filename (e.g., "MEMORY.md", "notes.md")
        size_bytes: File size in bytes
        last_modified: When file was last modified
    """

    path: Path
    name: str
    size_bytes: int
    last_modified: datetime


@dataclass
class SessionStats:
    """Statistics about provider sessions.

    Attributes:
        session_count: Number of sessions
        total_size_bytes: Total size of all session data
        last_session_time: Timestamp of most recent session
        memory_files: List of memory files from sessions
        session_dir: Path to session directory (optional)
    """

    session_count: int
    total_size_bytes: int
    last_session_time: Optional[datetime] = None
    memory_files: List[MemoryFile] = field(default_factory=list)
    session_dir: Optional[Path] = None


@dataclass
class MemoryInfo:
    """Information about provider memory files.

    Attributes:
        personal_memory: Path to personal memory file (if exists)
        personal_lines: Line count for personal memory
        project_memory: Path to project memory file (if exists)
        project_lines: Line count for project memory
    """

    personal_memory: Optional[Path] = None
    personal_lines: int = 0
    project_memory: Optional[Path] = None
    project_lines: int = 0


@dataclass
class SkillInfo:
    """Information about a provider skill/plugin.

    Attributes:
        name: Skill name (directory name)
        path: Path to the skill definition file (e.g., SKILL.md)
    """

    name: str
    path: Optional[Path] = None


@dataclass
class GlobalContextSummary:
    """Summary of global context files loaded by a provider.

    Attributes:
        total_files: Total count of global context files
        categories: Display name -> count mapping
        file_list: List of file paths
    """

    total_files: int = 0
    categories: Dict[str, int] = field(default_factory=dict)
    file_list: List[Path] = field(default_factory=list)


@dataclass
class GlobalFiles:
    """Information about global context files configured for all projects.

    Attributes:
        files: List of global file paths
        common_root: Common root directory if all files share one (e.g., "~/.claude")
        by_category: Files grouped by category (key=category like "📋 Rule", value=list of paths)
    """

    files: List[Path] = field(default_factory=list)
    common_root: Optional[str] = None
    by_category: dict = field(default_factory=dict)


@dataclass
class MarketplacePlugin:
    """A single installed marketplace plugin.

    Attributes:
        name: Plugin name from plugin.json
        description: Plugin description from plugin.json
        source_type: "internal" (plugins/) or "external" (external_plugins/)
        commands: List of command names (from commands/ directory)
        agents: List of agent names (from agents/ directory)
        skills: List of skill names (from skills/ directory)
        has_hooks: Whether the plugin has hooks configured
        has_mcp: Whether the plugin provides an MCP server
    """

    name: str
    description: str
    source_type: str = "internal"
    commands: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    has_hooks: bool = False
    has_mcp: bool = False


@dataclass
class MarketplaceInfo:
    """Summary of an installed marketplace.

    Attributes:
        name: Marketplace directory name (e.g., "claude-plugins-official")
        plugins: List of discovered plugins
    """

    name: str
    plugins: List[MarketplacePlugin] = field(default_factory=list)


@dataclass
class ProviderPreviewData:
    """All data a provider can provide for preview display.

    This is the main contract between providers and the preview layer.
    Providers return this (NO formatting, just data).
    Preview layer formats this into display content.

    Attributes:
        provider_name: Display name of the provider (e.g., "Claude Code")
        context_files: List of context files (CLAUDE.md, etc.)
        session_stats: Session statistics (if provider tracks sessions)
        global_files: Global context files configured for all projects
        provider_context: Auto-discovered provider-specific files (e.g., ~/.claude/)
        global_config_paths: Paths to global provider config
        custom_data: Provider-specific data (key-value pairs)
    """

    provider_name: str
    context_files: List[ContextFile] = field(default_factory=list)
    session_stats: Optional[SessionStats] = None
    global_files: Optional[GlobalFiles] = None
    provider_context: Optional[GlobalFiles] = None
    global_config_paths: List[Path] = field(default_factory=list)
    custom_data: dict = field(default_factory=dict)
    session_config: Optional["SessionConfig"] = None
    memory_info: Optional[MemoryInfo] = None
    skills: List[SkillInfo] = field(default_factory=list)
    global_context_summary: Optional[GlobalContextSummary] = None
    marketplace_plugins: Optional[MarketplaceInfo] = None


@dataclass
class GitStatus:
    """Git repository status information.

    Attributes:
        is_repo: Whether directory is a git repo
        is_clean: Whether working tree is clean
        changed_files: List of changed file paths
        branch: Current branch name
        has_changes: Whether there are uncommitted changes
    """

    is_repo: bool
    is_clean: bool = True
    changed_files: List[str] = field(default_factory=list)
    branch: Optional[str] = None
    has_changes: bool = False


@dataclass
class DirectoryListing:
    """Directory contents listing.

    Attributes:
        directories: List of subdirectory names
        files: List[file names
        total_items: Total number of items
    """

    directories: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    total_items: int = 0


@dataclass
class SessionConfig:
    """Session configuration data.

    Attributes:
        permissions: List of auto-approved command patterns
        permissions_count: Number of auto-approved permissions
        mcp_servers: List of configured MCP server names
        hooks_configured: Whether hooks are configured
        model: Model selection from settings
        config_file_path: Path to the config file (for transparency)
    """

    permissions: List[str] = field(default_factory=list)
    permissions_count: int = 0
    mcp_servers: List[str] = field(default_factory=list)
    hooks_configured: bool = False
    model: Optional[str] = None
    config_file_path: Optional[str] = None
