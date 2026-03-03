"""Claude Code provider implementation.

This module implements the AIProvider interface for Claude Code, Anthropic's
AI pair programmer.

Author: Solent Labs™
Created: 2026-02-09
Updated: 2026-02-12 (Consolidated claude_data.py into this module)
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ai_launcher.core.provider_data import (
    ContextFile,
    GlobalContextSummary,
    GlobalFiles,
    MarketplaceInfo,
    MarketplacePlugin,
    MemoryFile,
    MemoryInfo,
    ProviderPreviewData,
    SessionConfig,
    SessionStats,
    SkillInfo,
)
from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class ClaudeProvider(AIProvider):
    """Claude Code provider implementation.

    Provides integration with Anthropic's Claude Code CLI tool.
    Delegates cleanup to the existing utils/cleanup.py module which handles:
    - Clearing ~/.cache directory
    - Cleaning npm cache
    - Removing .claude.json.backup.* files
    - Cleaning old debug logs
    - Removing old CLI versions
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Claude Code metadata.

        Returns:
            ProviderMetadata with Claude-specific configuration
        """
        return ProviderMetadata(
            name="claude-code",
            display_name="Claude Code",
            command="claude",
            description="Anthropic's AI pair programmer",
            config_files=["CLAUDE.md", ".clauderc"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if Claude CLI is installed.

        Returns:
            True if 'claude' command is available in PATH
        """
        return shutil.which("claude") is not None

    def launch(self, project_path: Path) -> None:
        """Launch Claude Code in the specified project directory.

        Args:
            project_path: Path to the project directory

        Raises:
            FileNotFoundError: If Claude CLI is not found
            subprocess.CalledProcessError: If Claude fails to launch
        """
        # Change to project directory
        os.chdir(project_path)

        # Launch Claude
        try:
            subprocess.run(["claude"], check=True)  # nosec B603, B607
        except FileNotFoundError:
            print("Error: 'claude' command not found.")
            print("Make sure Claude Code CLI is installed.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Claude: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Claude-specific environment.

        Handles Claude-specific cleanup operations:
        1. Old timestamped .claude.json.backup.* files (bug workaround)
        2. Claude debug logs older than configured age
        3. Old Claude CLI versions (keeps only current)

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        # Only clean if config is provided and cleanup is enabled
        if cleanup_config is None or not cleanup_config.enabled:
            return

        # Only clean Claude files if provider-specific cleanup is enabled
        if not cleanup_config.clean_provider_files:
            return

        home = Path.home()

        if verbose:
            print("  Claude Code cleanup:")

        # 1. Remove old timestamped .claude.json.backup.* files (bug workaround)
        # Addresses Claude Code bug: https://github.com/anthropics/claude-code/issues/21429
        # Claude creates multiple backup files on startup but never cleans them up.
        # Files are created in ~/ instead of ~/.claude/ directory.
        # TODO: Remove this cleanup when GitHub issue #21429 is resolved.
        if verbose:
            print("    → Removing old .claude.json.backup.* files")
        try:
            for backup_file in home.glob(".claude.json.backup.*"):
                if backup_file.is_file():
                    backup_file.unlink(missing_ok=True)
        except (OSError, PermissionError):
            pass  # Non-fatal, continue with other cleanup

        # 2. Remove old Claude debug logs
        # Debug logs in ~/.claude/debug/ accumulate indefinitely and can reach 500MB+.
        # Keep last N days (from config) for troubleshooting, remove older logs.
        max_age_days = cleanup_config.debug_logs_max_age_days
        if verbose:
            print(f"    → Removing debug logs older than {max_age_days} days")

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

                if removed_count > 0 and verbose:
                    print(f"    → Removed {removed_count} old debug log(s)")
            except (OSError, PermissionError):
                pass  # Non-fatal, continue with other cleanup

        # 3. Remove old Claude CLI versions
        # Claude auto-updates leave old versions in ~/.local/share/claude/versions/
        # Each version is ~212MB. Keep only the currently running version.
        if shutil.which("claude"):
            if verbose:
                print("    → Removing old CLI versions (keeping current)")

            versions_dir = home / ".local" / "share" / "claude" / "versions"
            if versions_dir.exists() and versions_dir.is_dir():
                try:
                    import re

                    # Get current version
                    result = subprocess.run(
                        ["claude", "--version"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )  # nosec B603, B607

                    if result.returncode == 0:
                        # Extract version number (e.g., "2.1.37" from output)
                        match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
                        if match:
                            current_version = match.group(1)

                            # Remove all version files except current
                            removed_count = 0
                            for version_file in versions_dir.iterdir():
                                if (
                                    version_file.is_file()
                                    and version_file.name != current_version
                                    and re.match(r"^\d+\.\d+\.\d+$", version_file.name)
                                ):
                                    version_file.unlink(missing_ok=True)
                                    removed_count += 1

                            if removed_count > 0 and verbose:
                                print(f"    → Removed {removed_count} old version(s)")
                except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass  # Non-fatal, continue

        if verbose:
            print("    ✓ Claude cleanup complete")

    # === NEW: Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Claude-specific preview data.

        Returns structured data only - no formatting.
        This follows separation of concerns:
        - This method collects DATA
        - Preview layer handles PRESENTATION

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Claude-specific information
        """
        context_files = []

        # Personal CLAUDE.md
        personal = _get_personal_context_file()
        if personal:
            context_files.append(personal)

        # Project CLAUDE.md (always include, even if doesn't exist)
        project = _get_project_context_file(project_path)
        context_files.append(project)

        # Session stats
        session_stats = _get_session_stats(project_path)

        # Global files (user-configured via CLI flags)
        global_files = _collect_global_files()

        # Provider context (auto-discovered from ~/.claude/)
        provider_context = _discover_claude_context_files()

        # Global config paths
        global_paths = self.get_global_context_paths()

        # Session configuration (permissions, MCP, hooks, model)
        session_config = _get_claude_session_config(project_path)

        # Memory info (personal + project memory)
        memory_info = _get_memory_info(project_path)

        # Skills
        skills = _get_skills()

        # Global context summary
        global_context_summary = _get_global_context_summary()

        # Marketplace plugins
        marketplace_plugins = _discover_marketplace_plugins()

        return ProviderPreviewData(
            provider_name=self.metadata.display_name,
            context_files=context_files,
            session_stats=session_stats,
            global_files=global_files,
            provider_context=provider_context,
            global_config_paths=global_paths,
            session_config=session_config,
            memory_info=memory_info,
            skills=skills,
            global_context_summary=global_context_summary,
            marketplace_plugins=marketplace_plugins,
        )

    def get_documentation_urls(self) -> dict:
        """Get Claude Code documentation URLs."""
        return {
            "CLAUDE.md guide": "https://code.claude.com/docs/en/claude-md",
            "Auto memory": "https://code.claude.com/docs/en/memory",
            "Settings": "https://code.claude.com/docs/en/settings",
            "MCP servers": "https://code.claude.com/docs/en/mcp",
            "Hooks": "https://code.claude.com/docs/en/hooks",
        }

    # === Discovery Methods ===

    def get_global_context_paths(self) -> List[Path]:
        """Get paths to Claude's global configuration."""
        return [
            Path.home() / ".claude",
            Path.home() / ".claude.json",
        ]

    def get_project_data_pattern(self) -> str:
        """Get Claude's project data pattern."""
        return "~/.claude/projects/-{encoded_path}/*.jsonl"

    def get_context_categories(self) -> dict:
        """Get Claude-specific file categorization patterns."""
        return {
            "config": [".claude.json", ".clauderc"],
            "credentials": ["oauth"],
            "logs": ["debug"],
            "cache": ["cache"],
            "memory": ["memory"],
            "projects": ["projects"],
            "executables": ["versions"],
        }


# ===== Module-level Helper Functions =====
# These functions support ClaudeProvider.collect_preview_data()
# They collect Claude-specific data and return structured objects.


def _get_personal_context_file() -> Optional[ContextFile]:
    """Get personal CLAUDE.md file information.

    Returns:
        ContextFile instance or None if not found
    """
    home = Path.home()
    candidates = [
        home / "CLAUDE.md",
        home / ".claude" / "CLAUDE.md",
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            try:
                stat = path.stat()
                size = stat.st_size

                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    # Preview: first 10 lines
                    content_preview = "".join(lines[:10])

                return ContextFile(
                    path=path,
                    label="CLAUDE.md",
                    exists=True,
                    size_bytes=size,
                    line_count=line_count,
                    file_type="personal",
                    content_preview=content_preview,
                )
            except (OSError, UnicodeDecodeError):
                pass

    return None


def _get_project_context_file(project_path: Path) -> ContextFile:
    """Get project CLAUDE.md file information.

    Always returns a ContextFile, even if file doesn't exist.

    Args:
        project_path: Path to the project

    Returns:
        ContextFile instance
    """
    claude_md = project_path / "CLAUDE.md"

    if not claude_md.exists():
        # Return non-existent file info
        return ContextFile(
            path=claude_md,
            label="CLAUDE.md",
            exists=False,
            file_type="project",
        )

    try:
        stat = claude_md.stat()
        size = stat.st_size

        with open(claude_md, encoding="utf-8") as f:
            lines = f.readlines()
            line_count = len(lines)
            content_preview = "".join(lines[:10])

        return ContextFile(
            path=claude_md,
            label="CLAUDE.md",
            exists=True,
            size_bytes=size,
            line_count=line_count,
            file_type="project",
            content_preview=content_preview,
        )
    except (OSError, UnicodeDecodeError):
        return ContextFile(
            path=claude_md,
            label="CLAUDE.md",
            exists=False,
            file_type="project",
        )


def _encode_project_path(project_path: Path) -> str:
    """Encode project path into Claude's session directory naming format.

    Claude Code stores session data in directories named by encoding the project path:
    - Replace directory separators with hyphens
    - Example: /home/user/projects/foo -> -home-user-projects-foo

    Args:
        project_path: Absolute path to the project

    Returns:
        Encoded directory name
    """
    abs_path = project_path.resolve()
    path_str = str(abs_path)
    encoded = path_str.replace(os.sep, "-")
    return encoded


def _get_session_dir(project_path: Path) -> Optional[Path]:
    """Get the Claude Code session directory for a project.

    Args:
        project_path: Absolute path to the project

    Returns:
        Path to session directory if it exists, None otherwise
    """
    encoded_name = _encode_project_path(project_path)
    session_dir = Path.home() / ".claude" / "projects" / encoded_name
    return session_dir if session_dir.exists() else None


def _get_memory_files(session_dir: Path) -> List[MemoryFile]:
    """Get list of memory files in session directory.

    Args:
        session_dir: Path to the Claude session directory

    Returns:
        List of MemoryFile instances
    """
    memory_dir = session_dir / "memory"
    if not memory_dir.exists():
        return []

    memory_files = []
    try:
        for file_path in memory_dir.glob("*.md"):
            if file_path.is_file():
                stat = file_path.stat()
                memory_files.append(
                    MemoryFile(
                        path=file_path,
                        name=file_path.name,
                        size_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
    except (PermissionError, OSError):
        pass

    return memory_files


def _get_session_stats(project_path: Path) -> Optional[SessionStats]:
    """Get Claude session statistics.

    Args:
        project_path: Path to the project

    Returns:
        SessionStats instance or None if no sessions exist
    """
    session_dir = _get_session_dir(project_path)
    if not session_dir:
        return None

    try:
        # Count .jsonl files
        session_files = list(session_dir.glob("*.jsonl"))
        session_count = len(session_files)

        if session_count == 0:
            return None

        # Calculate total size
        total_size = sum(f.stat().st_size for f in session_files if f.is_file())

        # Get last session time
        last_mtime = max(f.stat().st_mtime for f in session_files)
        last_session_time = datetime.fromtimestamp(last_mtime)

        # Get memory files
        memory_files = _get_memory_files(session_dir)

        return SessionStats(
            session_count=session_count,
            total_size_bytes=total_size,
            last_session_time=last_session_time,
            memory_files=memory_files,
            session_dir=session_dir,
        )

    except (PermissionError, OSError):
        return None


def _categorize_global_file(file_path: Path) -> str:
    """Categorize a global file by its name and location (Claude-specific).

    Args:
        file_path: Path to the global file

    Returns:
        Category description (e.g., "📋 Rule: Project instructions")
    """
    name = file_path.stem.upper()
    name_lower = file_path.stem.lower()
    parent = file_path.parent.name.lower()

    # Check parent directory for specific categories
    if parent in ["cache", "history", "logs"]:
        return "📦 Cache: Cached data or history"

    if parent in ["plans", "notes", "journal"]:
        return "📝 Notes: Plans and working notes"

    # Provider-specific instructions (check filename first)
    providers = ["CLAUDE", "CURSOR", "GEMINI", "COPILOT", "AIDER", "WINDSURF"]
    for provider in providers:
        if provider in name:
            return f"📋 Rule: {provider.title()} provider instructions"

    # Skills and capabilities
    if any(word in name for word in ["SKILL", "CAPABILITY", "TOOL", "FUNCTION"]):
        return "🔧 Skill: Custom capabilities and tools"

    # Documentation
    if any(
        word in name_lower for word in ["changelog", "readme", "doc", "guide", "manual"]
    ):
        return "📚 Docs: Documentation and guides"

    # Standards and conventions
    if any(
        word in name
        for word in ["STANDARD", "CONVENTION", "STYLE", "GUIDELINE", "POLICY"]
    ):
        return "📋 Rule: Coding standards and conventions"

    # Patterns and examples
    if any(word in name for word in ["PATTERN", "EXAMPLE", "TEMPLATE", "BOILERPLATE"]):
        return "💡 Hint: Patterns and examples to follow"

    # Agent configuration
    if any(word in name for word in ["AGENT", "SYSTEM", "PERSONA", "ROLE"]):
        return "🤖 Agent: AI agent configuration"

    # Security and operations
    if any(word in name for word in ["SECURITY", "OPS", "DEPLOY", "INFRA"]):
        return "🔒 Ops: Security and operations guidelines"

    # Testing
    if any(word in name for word in ["TEST", "QA", "QUALITY"]):
        return "🧪 Test: Testing standards and practices"

    # Architecture
    if any(word in name for word in ["ARCH", "DESIGN", "STRUCTURE"]):
        return "🏗️  Arch: Architecture and design decisions"

    # Project root instructions
    if name in ["CLAUDE", "INSTRUCTIONS", "CONTEXT", "PROMPT"]:
        return "📋 Rule: Project instructions for AI"

    # Configuration files
    if "config" in name_lower or "settings" in name_lower:
        return "⚙️  Config: CLI configuration file"

    # Configuration directories
    if ".config" in str(file_path) or ".claude" in str(file_path):
        return "📋 Rule: CLI context file"

    # DevKit or shared context
    if "devkit" in parent or "shared" in parent or "common" in parent:
        return "🔗 Shared: Organization-wide shared context"

    return "📄 General: General context or instructions"


def _collect_global_files() -> Optional["GlobalFiles"]:
    """Collect global context files from environment variable (CLI flags).

    Returns:
        GlobalFiles instance with categorized files, or None if no global files configured
    """
    import os
    from collections import defaultdict

    from ai_launcher.core.provider_data import GlobalFiles

    try:
        # Read from environment variable (set by selector from CLI flags)
        global_files_env = os.environ.get("AI_LAUNCHER_GLOBAL_FILES", "")
        if not global_files_env:
            return None

        # Parse comma-separated list and expand paths
        files = []
        for gf in global_files_env.split(","):
            gf = gf.strip()
            if gf:
                gf_path = Path(gf).expanduser()
                files.append(gf_path)

        if not files:
            return None

        # Detect common root (first directory after home)
        common_root = None
        try:
            roots = set()
            for p in files:
                rel = p.relative_to(Path.home())
                if rel.parts:
                    roots.add(rel.parts[0])

            if len(roots) == 1:
                common_root = f"~/{roots.pop()}"
        except ValueError:
            pass

        # Categorize files
        by_category = defaultdict(list)
        for file_path in files:
            category = _categorize_global_file(file_path)
            by_category[category].append(file_path)

        return GlobalFiles(
            files=files,
            common_root=common_root,
            by_category=dict(by_category),
        )

    except Exception:
        return None


def _discover_claude_context_files() -> Optional["GlobalFiles"]:
    """Auto-discover context files in ~/.claude/ directory.

    Scans ~/.claude/ for markdown files in subdirectories like:
    - skills/
    - plugins/
    - plans/
    - memory/
    - cache/

    Returns:
        GlobalFiles instance with auto-discovered files, or None if ~/.claude/ doesn't exist
    """
    from collections import defaultdict

    from ai_launcher.core.provider_data import GlobalFiles

    claude_dir = Path.home() / ".claude"
    if not claude_dir.exists():
        return None

    # Scan for markdown files in ~/.claude/ subdirectories
    files = []
    try:
        for subdir in claude_dir.iterdir():
            if subdir.is_dir() and subdir.name not in [
                "projects",
                "versions",
                "marketplaces",
                "plugins",
                "skills",
            ]:
                # Skip projects and versions dirs (they're not context files)
                try:
                    for md_file in subdir.glob("**/*.md"):
                        if md_file.is_file():
                            files.append(md_file)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        return None

    if not files:
        return None

    # Common root is always ~/.claude for these files
    common_root = "~/.claude"

    # Categorize files
    by_category = defaultdict(list)
    for file_path in files:
        category = _categorize_global_file(file_path)
        by_category[category].append(file_path)

    return GlobalFiles(
        files=files,
        common_root=common_root,
        by_category=dict(by_category),
    )


def _get_claude_session_config(project_path: Path) -> Optional[SessionConfig]:
    """Get Claude Code session configuration.

    Reads project-level and global settings to determine permissions,
    MCP servers, hooks, and model configuration.

    Args:
        project_path: Path to the project

    Returns:
        SessionConfig instance or None if no config exists
    """
    import json

    config = SessionConfig()

    # Check project permissions
    project_settings = project_path / ".claude" / "settings.local.json"
    if project_settings.exists():
        config.config_file_path = str(project_settings)
        try:
            settings = json.loads(project_settings.read_text())

            # Permissions
            if "permissions" in settings and "allow" in settings["permissions"]:
                config.permissions = settings["permissions"]["allow"]
                config.permissions_count = len(config.permissions)

            # MCP servers (project-level)
            if "mcpServers" in settings:
                config.mcp_servers = list(settings["mcpServers"].keys())

            # Hooks (project-level)
            if "hooks" in settings:
                config.hooks_configured = any(
                    hook_config for hook_config in settings["hooks"].values()
                )
        except (json.JSONDecodeError, KeyError):
            pass

    # Check global settings for model
    global_settings = Path.home() / ".claude" / "settings.json"
    if global_settings.exists():
        try:
            settings = json.loads(global_settings.read_text())
            config.model = settings.get("model")
        except json.JSONDecodeError:
            pass

    # Check global MCP servers
    mcp_config = Path.home() / ".claude" / "mcp.json"
    if mcp_config.exists():
        try:
            mcp_data = json.loads(mcp_config.read_text())
            if "mcpServers" in mcp_data:
                # Merge with project-level MCP servers (avoid duplicates)
                global_servers = list(mcp_data["mcpServers"].keys())
                for server in global_servers:
                    if server not in config.mcp_servers:
                        config.mcp_servers.append(server)
        except (json.JSONDecodeError, KeyError):
            pass

    # Check global hooks
    hooks_config = Path.home() / ".claude" / "hooks.json"
    if hooks_config.exists() and not config.hooks_configured:
        config.hooks_configured = True

    # Only return if we found some config
    if (
        config.permissions_count > 0
        or config.mcp_servers
        or config.hooks_configured
        or config.model
    ):
        return config

    return None


def _get_memory_info(project_path: Path) -> Optional[MemoryInfo]:
    """Get Claude memory information for personal and project memory.

    Uses _encode_project_path() to dynamically find the correct memory
    directories (no hardcoded paths).

    Args:
        project_path: Path to the project

    Returns:
        MemoryInfo instance or None if no memory exists
    """
    info = MemoryInfo()
    has_memory = False

    # Personal memory - encode home directory path
    home = Path.home()
    personal_encoded = _encode_project_path(home)
    personal_mem = (
        home / ".claude" / "projects" / personal_encoded / "memory" / "MEMORY.md"
    )
    if personal_mem.exists():
        info.personal_memory = personal_mem
        try:
            info.personal_lines = len(personal_mem.read_text().splitlines())
            has_memory = True
        except Exception:
            pass

    # Project memory - encode project path
    project_encoded = _encode_project_path(project_path)
    project_mem = (
        home / ".claude" / "projects" / project_encoded / "memory" / "MEMORY.md"
    )
    if project_mem.exists():
        info.project_memory = project_mem
        try:
            info.project_lines = len(project_mem.read_text().splitlines())
            has_memory = True
        except Exception:
            pass

    return info if has_memory else None


def _get_skills() -> List[SkillInfo]:
    """Get installed Claude skills.

    Scans ~/.claude/skills/ for directories containing SKILL.md.

    Returns:
        List of SkillInfo instances
    """
    skills: List[SkillInfo] = []
    skills_dir = Path.home() / ".claude" / "skills"

    if not skills_dir.exists():
        return skills

    try:
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skills.append(SkillInfo(name=skill_dir.name, path=skill_file))
    except (PermissionError, OSError):
        pass

    return skills


def _get_global_context_summary() -> Optional[GlobalContextSummary]:
    """Get summary of global context files loaded by Claude.

    Scans ~/.claude/ subdirectories for context files.

    Returns:
        GlobalContextSummary instance or None if no files found
    """
    claude_dir = Path.home() / ".claude"
    if not claude_dir.exists():
        return None

    categories = {
        "Plans": claude_dir / "plans",
        "Cache": claude_dir / "cache",
        "Plugins": claude_dir / "plugins",
        "Memories (all projects)": claude_dir / "projects",
    }

    summary = GlobalContextSummary()

    for cat_name, cat_path in categories.items():
        if not cat_path.exists():
            continue

        files = []
        try:
            if cat_name == "Memories (all projects)":
                for proj_dir in cat_path.iterdir():
                    if proj_dir.is_dir():
                        memory_dir = proj_dir / "memory"
                        if memory_dir.exists():
                            for mem_file in memory_dir.glob("*.md"):
                                files.append(mem_file)
                        journal_dir = proj_dir / "journal"
                        if journal_dir.exists():
                            for journal_file in journal_dir.glob("*.md"):
                                files.append(journal_file)
            elif cat_name == "Plugins":
                marketplaces_dir = cat_path / "marketplaces"
                if marketplaces_dir.exists():
                    for marketplace in marketplaces_dir.glob("*/"):
                        readme = marketplace / "README.md"
                        if readme.exists():
                            files.append(readme)
            else:
                files = list(cat_path.glob("*.md"))
        except (PermissionError, OSError):
            continue

        if files:
            summary.categories[cat_name] = len(files)
            summary.file_list.extend(files)

    summary.total_files = len(summary.file_list)

    return summary if summary.total_files > 0 else None


def _discover_marketplace_plugins() -> Optional[MarketplaceInfo]:
    """Discover installed marketplace plugins from ~/.claude/plugins/marketplaces/.

    Scans each marketplace directory for plugins (internal and external),
    reads plugin.json metadata, and detects capabilities (commands, agents,
    skills, hooks, MCP servers).

    Returns:
        MarketplaceInfo instance or None if no marketplace plugins found
    """

    marketplaces_dir = Path.home() / ".claude" / "plugins" / "marketplaces"
    if not marketplaces_dir.exists():
        return None

    try:
        # Find marketplace directories (e.g., claude-plugins-official)
        marketplace_dirs = [
            d
            for d in marketplaces_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
    except (PermissionError, OSError):
        return None

    if not marketplace_dirs:
        return None

    # Use the first marketplace found (typically claude-plugins-official)
    marketplace_dir = marketplace_dirs[0]
    marketplace_name = marketplace_dir.name

    plugins = []

    # Scan both plugins/ (internal) and external_plugins/ (external)
    for source_dir_name, source_type in [
        ("plugins", "internal"),
        ("external_plugins", "external"),
    ]:
        source_dir = marketplace_dir / source_dir_name
        if not source_dir.exists():
            continue

        try:
            for plugin_dir in source_dir.iterdir():
                if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
                    continue

                plugin = _read_plugin_metadata(plugin_dir, source_type)
                if plugin:
                    plugins.append(plugin)
        except (PermissionError, OSError):
            continue

    if not plugins:
        return None

    return MarketplaceInfo(name=marketplace_name, plugins=plugins)


def _read_plugin_metadata(
    plugin_dir: Path, source_type: str
) -> Optional[MarketplacePlugin]:
    """Read plugin metadata and detect capabilities from a plugin directory.

    Args:
        plugin_dir: Path to the plugin directory
        source_type: "internal" or "external"

    Returns:
        MarketplacePlugin instance or None if plugin.json is missing/invalid
    """
    import json

    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return None

    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        name = data.get("name", plugin_dir.name)
        description = data.get("description", "")
    except (json.JSONDecodeError, OSError):
        return None

    # Detect capabilities
    commands = _list_capability_names(plugin_dir / "commands", "*.md")
    agents = _list_capability_names(plugin_dir / "agents", "*.md")
    skills = _list_subdirectory_names(plugin_dir / "skills")
    has_hooks = (plugin_dir / "hooks" / "hooks.json").exists()
    has_mcp = (plugin_dir / ".mcp.json").exists()

    return MarketplacePlugin(
        name=name,
        description=description,
        source_type=source_type,
        commands=commands,
        agents=agents,
        skills=skills,
        has_hooks=has_hooks,
        has_mcp=has_mcp,
    )


def _list_capability_names(directory: Path, pattern: str) -> List[str]:
    """List capability names from files matching a pattern in a directory.

    Args:
        directory: Directory to scan
        pattern: Glob pattern (e.g., "*.md")

    Returns:
        Sorted list of file stems (names without extensions)
    """
    if not directory.exists():
        return []

    try:
        return sorted(f.stem for f in directory.glob(pattern) if f.is_file())
    except (PermissionError, OSError):
        return []


def _list_subdirectory_names(directory: Path) -> List[str]:
    """List names of subdirectories in a directory.

    Args:
        directory: Directory to scan

    Returns:
        Sorted list of subdirectory names
    """
    if not directory.exists():
        return []

    try:
        return sorted(
            d.name
            for d in directory.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
    except (PermissionError, OSError):
        return []
