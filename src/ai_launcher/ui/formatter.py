"""Preview content formatter.

This module handles all presentation logic for preview data.
It receives structured data from providers and formats it for display.

Separation of concerns:
- Providers collect DATA (return dataclasses)
- This formatter handles PRESENTATION (formatting, ANSI codes)

Author: Solent Labs™
Created: 2026-02-12
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from ai_launcher.core.provider_data import (
    ContextFile,
    DirectoryListing,
    GitStatus,
    MarketplaceInfo,
    ProviderPreviewData,
    SessionStats,
)
from ai_launcher.utils.paths import is_relative_to

if TYPE_CHECKING:
    from ai_launcher.core.provider_data import GlobalFiles, SessionConfig


class PreviewFormatter:
    """Formats preview data for display in fzf preview pane.

    This class centralizes all formatting logic, keeping it separate from
    data collection. It takes structured data objects and produces
    display-ready strings with ANSI color codes.
    """

    # ANSI color codes
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"

    def __init__(self, max_preview_lines: int = 20):
        """Initialize formatter.

        Args:
            max_preview_lines: Maximum lines to show in file previews
        """
        self.max_preview_lines = max_preview_lines

    # ===== Top-level Formatters =====

    def format_complete_preview(
        self,
        project_path: Path,
        provider_data: ProviderPreviewData,
        git_status: Optional[GitStatus] = None,
        directory: Optional[DirectoryListing] = None,
        session_config: Optional["SessionConfig"] = None,
    ) -> str:
        """Format complete preview with generic and provider-specific data.

        This is the main entry point that combines:
        - Generic project data (git, directory) - same for all providers
        - Provider-specific data (Claude/Gemini context, sessions, etc.)
        - Session configuration (permissions, MCP servers, hooks)

        Args:
            project_path: Path to the project
            provider_data: Provider-specific preview data
            git_status: Git status (generic, optional)
            directory: Directory listing (generic, optional)
            session_config: Session configuration (optional)

        Returns:
            Formatted preview string with rich formatting
        """
        sections = []

        # Provider header
        if provider_data.provider_name:
            sections.append(self._format_header(provider_data.provider_name))

        # PROVIDER-SPECIFIC sections
        if provider_data.context_files:
            sections.append(self._format_context_section(provider_data.context_files))

        if provider_data.session_stats:
            sections.append(self._format_session_section(provider_data.session_stats))

        # SESSION CONFIGURATION (transparency!)
        if session_config:
            sections.append(self._format_session_config_section(session_config))

        # GENERIC sections (same for all providers)
        if git_status:
            sections.append(self._format_git_section(git_status))

        if directory and directory.total_items > 0:
            sections.append(self._format_directory_section(directory))

        # NOTE: Global files, provider context, and marketplace plugins are
        # shown on the scan root preview panel (not per-project).
        # See _preview_helper.py for where those are rendered.

        # Footer with helpful tip
        sections.append(self._format_footer())

        return "\n\n".join(s.rstrip("\n") for s in sections)

    def format_context_files(self, files: List[ContextFile]) -> str:
        """Format context files section.

        Args:
            files: List of context files

        Returns:
            Formatted string
        """
        lines = [f"{self.BOLD}Context Files{self.RESET}"]

        for ctx_file in files:
            if ctx_file.exists:
                size_kb = ctx_file.size_bytes / 1024
                label = f"{self.CYAN}{ctx_file.label}{self.RESET}"
                info = f"{self.DIM}({ctx_file.line_count} lines, {size_kb:.1f}KB){self.RESET}"
                lines.append(f"  {label} {info}")

                # Show preview if available
                if ctx_file.content_preview:
                    preview_lines = ctx_file.content_preview.split("\n")[
                        : self.max_preview_lines
                    ]
                    for line in preview_lines:
                        if line.strip():  # Skip empty lines
                            lines.append(f"    {self.DIM}{line[:80]}{self.RESET}")
            else:
                label = f"{self.DIM}{ctx_file.label}{self.RESET}"
                lines.append(f"  {label} {self.DIM}(not found){self.RESET}")

        return "\n".join(lines)

    def format_session_stats(self, stats: SessionStats) -> str:
        """Format session statistics.

        Args:
            stats: Session statistics

        Returns:
            Formatted string
        """
        lines = [f"{self.BOLD}Session History{self.RESET}"]

        # Session count and size
        size_mb = stats.total_size_bytes / (1024 * 1024)
        lines.append(
            f"  {self.GREEN}{stats.session_count} sessions{self.RESET} "
            f"{self.DIM}({size_mb:.2f}MB total){self.RESET}"
        )

        # Last session time
        if stats.last_session_time:
            time_str = self._format_relative_time(stats.last_session_time)
            lines.append(f"  Last used: {self.DIM}{time_str}{self.RESET}")

        # Memory files
        if stats.memory_files:
            lines.append(f"\n  {self.BOLD}Memory Files:{self.RESET}")
            for mem_file in stats.memory_files[:5]:  # Show up to 5
                size_kb = mem_file.size_bytes / 1024
                lines.append(
                    f"    {self.CYAN}{mem_file.name}{self.RESET} "
                    f"{self.DIM}({size_kb:.1f}KB){self.RESET}"
                )

            if len(stats.memory_files) > 5:
                remaining = len(stats.memory_files) - 5
                lines.append(f"    {self.DIM}...and {remaining} more{self.RESET}")

        return "\n".join(lines)

    def format_global_config_paths(self, paths: List[Path]) -> str:
        """Format global configuration paths.

        Args:
            paths: List of config paths

        Returns:
            Formatted string
        """
        lines = [f"{self.BOLD}Global Configuration{self.RESET}"]

        for path in paths:
            if path.exists():
                # Show size if it's a file
                if path.is_file():
                    size_kb = path.stat().st_size / 1024
                    lines.append(
                        f"  {self.CYAN}{path}{self.RESET} "
                        f"{self.DIM}({size_kb:.1f}KB){self.RESET}"
                    )
                else:
                    lines.append(
                        f"  {self.CYAN}{path}{self.RESET} {self.DIM}(directory){self.RESET}"
                    )
            else:
                lines.append(f"  {self.DIM}{path} (not found){self.RESET}")

        return "\n".join(lines)

    def format_custom_data(self, data: dict) -> str:
        """Format custom provider-specific data.

        Args:
            data: Custom data dictionary

        Returns:
            Formatted string
        """
        if not data:
            return ""

        lines = [f"{self.BOLD}Additional Information{self.RESET}"]

        for key, value in data.items():
            # Format key as title case
            key_display = key.replace("_", " ").title()
            lines.append(f"  {key_display}: {self.CYAN}{value}{self.RESET}")

        return "\n".join(lines)

    # ===== Git Status Formatting =====

    def format_git_status(self, status: GitStatus) -> str:
        """Format git status information.

        Args:
            status: Git status data

        Returns:
            Formatted string
        """
        if not status.is_repo:
            return f"{self.DIM}Not a git repository{self.RESET}"

        lines = [f"{self.BOLD}Git Status{self.RESET}"]

        # Branch
        if status.branch:
            lines.append(f"  Branch: {self.CYAN}{status.branch}{self.RESET}")

        # Status
        if status.is_clean:
            lines.append(f"  Status: {self.GREEN}Clean{self.RESET}")
        else:
            lines.append(
                f"  Status: {self.YELLOW}{len(status.changed_files)} files changed{self.RESET}"
            )

            # Show all changed files
            for file_path in status.changed_files:
                lines.append(f"    {self.DIM}{file_path}{self.RESET}")

        return "\n".join(lines)

    # ===== Directory Listing Formatting =====

    def format_directory_listing(self, listing: DirectoryListing) -> str:
        """Format directory contents listing.

        Args:
            listing: Directory listing data

        Returns:
            Formatted string
        """
        if listing.total_items == 0:
            return f"{self.DIM}Empty directory{self.RESET}"

        lines = [f"{self.BOLD}Contents{self.RESET}"]

        # Show all directories first
        for directory in listing.directories:
            lines.append(f"  {self.BLUE}{directory}/{self.RESET}")

        # Then all files
        for file in listing.files:
            lines.append(f"  {self.DIM}{file}{self.RESET}")

        return "\n".join(lines)

    # ===== Helper Methods =====

    def _format_header(self, provider_name: str) -> str:
        """Format section header.

        Args:
            provider_name: Name of the provider

        Returns:
            Formatted header string
        """
        return f"{self.BOLD}{self.CYAN}=== {provider_name} ==={self.RESET}"

    def _format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time string.

        Args:
            dt: Datetime to format

        Returns:
            Relative time string (e.g., "2 hours ago")
        """
        now = datetime.now()
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        if delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        return "just now"

    def _humanize_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"

    # ===== Rich Formatting Methods (for format_complete_preview) =====

    def _format_rich_header(self, provider_name: str) -> str:
        """Format rich header with box.

        Args:
            provider_name: Provider display name

        Returns:
            Formatted header with box
        """
        line = "━" * 50
        return (
            f"{self.CYAN}┏{line}┓\n"
            f"┃ {provider_name}{' ' * (49 - len(provider_name))}┃\n"
            f"┗{line}┛{self.RESET}"
        )

    def _format_context_section(self, files: List[ContextFile]) -> str:
        """Format context files section with emojis.

        Args:
            files: List of context files

        Returns:
            Formatted section
        """
        lines = [f"{self.BOLD}📋 Context Files{self.RESET}"]

        for ctx_file in files:
            if ctx_file.exists:
                size = self._humanize_size(ctx_file.size_bytes)
                type_emoji = "🏠" if ctx_file.file_type == "personal" else "📁"
                label = f"{self.GREEN}✓{self.RESET} {type_emoji} {self.CYAN}{ctx_file.label}{self.RESET}"
                info = f"{self.DIM}({ctx_file.line_count} lines, {size}){self.RESET}"
                lines.append(f"  {label} {info}")

                # Show content preview if available
                if ctx_file.content_preview:
                    lines.append("")  # Blank line before preview
                    preview_lines = ctx_file.content_preview.split("\n")[
                        : self.max_preview_lines
                    ]
                    for line in preview_lines:
                        if line.strip():  # Skip empty lines
                            # Truncate long lines to 80 chars
                            display_line = line[:80] if len(line) > 80 else line
                            lines.append(f"    {self.DIM}{display_line}{self.RESET}")
                    lines.append("")  # Blank line after preview
            else:
                lines.append(f"  {self.DIM}✗ {ctx_file.label} (not found){self.RESET}")

        return "\n".join(lines)

    def _format_session_section(self, stats: SessionStats) -> str:
        """Format session statistics with emojis.

        Args:
            stats: Session statistics

        Returns:
            Formatted section
        """
        lines = [f"{self.BOLD}🧠 Session History{self.RESET}"]

        # Session count and size
        size = self._humanize_size(stats.total_size_bytes)
        lines.append(
            f"  {self.GREEN}{stats.session_count} sessions{self.RESET} {self.DIM}({size} total){self.RESET}"
        )

        # Last session time
        if stats.last_session_time:
            time_str = self._format_relative_time(stats.last_session_time)
            lines.append(f"  Last used: {self.DIM}{time_str}{self.RESET}")

        # Memory files
        if stats.memory_files:
            for mem_file in stats.memory_files[:3]:  # Show up to 3
                size = self._humanize_size(mem_file.size_bytes)
                lines.append(
                    f"    {self.GREEN}✓{self.RESET} {mem_file.name} {self.DIM}({size}){self.RESET}"
                )

            if len(stats.memory_files) > 3:
                remaining = len(stats.memory_files) - 3
                lines.append(f"    {self.DIM}...and {remaining} more{self.RESET}")

        return "\n".join(lines)

    def _format_global_files_section(self, global_files: "GlobalFiles") -> str:
        """Format global files section grouped by category.

        Args:
            global_files: Global files data from provider

        Returns:
            Formatted section with files grouped by category
        """
        # Header with common root if present
        if global_files.common_root:
            lines = [
                f"{self.BOLD}🌐 Global Files{self.RESET} {self.DIM}({global_files.common_root}/){self.RESET}"
            ]
        else:
            lines = [f"{self.BOLD}🌐 Global Files{self.RESET}"]

        # Category display order (most important first)
        category_order = [
            "📋 Rule",  # Project instructions and standards
            "🔧 Skill",  # Custom capabilities
            "🤖 Agent",  # AI agent configuration
            "💡 Hint",  # Patterns and examples
            "🏗️  Arch",  # Architecture decisions
            "📚 Docs",  # Documentation
            "🔒 Ops",  # Security and operations
            "🧪 Test",  # Testing standards
            "⚙️  Config",  # Configuration files
            "🔗 Shared",  # Shared context
            "📝 Notes",  # Plans and notes
            "📦 Cache",  # Cache and history
            "📄 General",  # General files
        ]

        # Display each category
        for cat_prefix in category_order:
            matching = [
                cat for cat in global_files.by_category if cat.startswith(cat_prefix)
            ]

            for category in matching:
                files = global_files.by_category[category]
                if not files:
                    continue

                # Extract type name
                type_name = category.split(":")[0].strip()

                # Detect common subdirectory within category
                category_common_subdir = None
                if global_files.common_root:
                    subdirs = set()
                    for file_path in files:
                        try:
                            rel_path = file_path.relative_to(Path.home())
                            if len(rel_path.parts) > 2:
                                subdirs.add(rel_path.parts[1])
                        except ValueError:
                            pass
                    if len(subdirs) == 1:
                        category_common_subdir = subdirs.pop()

                # Print category header
                lines.append("")
                if category_common_subdir:
                    lines.append(
                        f"{type_name}: {self.DIM}(./{category_common_subdir}/){self.RESET}"
                    )
                else:
                    lines.append(f"{type_name}:")

                # Group files by directory
                by_root: Dict[str, Dict[str, List[str]]] = defaultdict(
                    lambda: defaultdict(list)
                )
                for file_path in files:
                    try:
                        rel_path = file_path.relative_to(Path.home())
                        parts = rel_path.parts

                        if len(parts) >= 1:
                            root = f"~/{parts[0]}"
                            rest_parts = parts[1:]

                            if len(rest_parts) == 0:
                                by_root[root][""].append(file_path.name)
                            elif len(rest_parts) == 1:
                                by_root[root][""].append(rest_parts[0])
                            else:
                                subdir = "/".join(rest_parts[:-1])
                                # Strip category common subdir if present
                                if category_common_subdir and subdir.startswith(
                                    category_common_subdir
                                ):
                                    if subdir == category_common_subdir:
                                        subdir = ""
                                    else:
                                        subdir = subdir[
                                            len(category_common_subdir) + 1 :
                                        ]
                                by_root[root][subdir].append(file_path.name)
                    except ValueError:
                        by_root[str(file_path.parent)][""].append(file_path.name)

                # Display tree
                for root in sorted(by_root.keys()):
                    show_root = (
                        root != global_files.common_root
                        if global_files.common_root
                        else True
                    )

                    if show_root:
                        lines.append(f"  {root}/")

                    dir_groups = by_root[root]
                    for subdir in sorted(dir_groups.keys()):
                        file_list = sorted(dir_groups[subdir])
                        indent = "    " if show_root else "  "
                        file_indent = "      " if show_root else "    "

                        if subdir == "":
                            for fname in file_list:
                                lines.append(f"{indent}{self.DIM}• {fname}{self.RESET}")
                        else:
                            lines.append(f"{indent}{subdir}/")
                            for fname in file_list:
                                lines.append(
                                    f"{file_indent}{self.DIM}• {fname}{self.RESET}"
                                )

        return "\n".join(lines)

    def _format_provider_context_section(
        self, provider_context: "GlobalFiles", provider_name: str = "Provider"
    ) -> str:
        """Format auto-discovered provider context files.

        This is separate from global_files - these are auto-discovered from ~/.claude/
        rather than user-configured.

        Args:
            provider_context: Auto-discovered provider files
            provider_name: Display name of the provider (e.g., "Claude Code")

        Returns:
            Formatted section
        """
        # Reuse the global files formatting logic but with different header
        result = self._format_global_files_section(provider_context)

        # Replace the header to indicate these are auto-discovered
        if provider_context.common_root:
            old_header = f"{self.BOLD}🌐 Global Files{self.RESET} {self.DIM}({provider_context.common_root}/){self.RESET}"
            new_header = f"{self.BOLD}🔧 {provider_name} Context{self.RESET} {self.DIM}({provider_context.common_root}/){self.RESET}"
        else:
            old_header = f"{self.BOLD}🌐 Global Files{self.RESET}"
            new_header = f"{self.BOLD}🔧 {provider_name} Context{self.RESET}"

        return result.replace(old_header, new_header, 1)

    def _format_session_config_section(self, config: "SessionConfig") -> str:
        """Format session configuration section.

        Args:
            config: Session configuration data

        Returns:
            Formatted section showing permissions, MCP servers, hooks, model
        """

        lines = [f"{self.BOLD}⚙️ Session Configuration{self.RESET}"]

        # Auto-approved permissions (expandable)
        if config.permissions_count > 0:
            lines.append(
                f"  {self.GREEN}✓{self.RESET} {config.permissions_count} auto-approved commands"
            )

            # Show first 5 permissions as examples
            max_show = 5
            for perm in config.permissions[:max_show]:
                # Truncate long patterns
                display_perm = perm if len(perm) < 60 else perm[:57] + "..."
                lines.append(f"    {self.DIM}• {display_perm}{self.RESET}")

            # Show count of remaining
            if config.permissions_count > max_show:
                remaining = config.permissions_count - max_show
                lines.append(f"    {self.DIM}...and {remaining} more{self.RESET}")

        # MCP Servers
        if config.mcp_servers:
            server_list = ", ".join(config.mcp_servers[:3])
            if len(config.mcp_servers) > 3:
                server_list += f", +{len(config.mcp_servers) - 3} more"
            lines.append(f"  {self.CYAN}🔌{self.RESET} MCP Servers: {server_list}")

        # Hooks
        if config.hooks_configured:
            lines.append(f"  {self.YELLOW}🪝{self.RESET} Hooks: Configured")

        # Model
        if config.model:
            lines.append(f"  {self.BLUE}🤖{self.RESET} Model: {config.model}")

        # Config file location (transparency!)
        if config.config_file_path:
            # Show relative path if possible
            try:
                from pathlib import Path

                config_path = Path(config.config_file_path)
                home = Path.home()
                if is_relative_to(config_path, home):
                    display_path = f"~/{config_path.relative_to(home)}"
                else:
                    display_path = str(config_path)
            except Exception:
                display_path = config.config_file_path

            lines.append(f"  {self.DIM}Source: {display_path}{self.RESET}")

        return "\n".join(lines)

    def _format_git_section(self, status: GitStatus) -> str:
        """Format git status section.

        Args:
            status: Git status data

        Returns:
            Formatted section
        """
        if not status.is_repo:
            return ""

        lines = [f"{self.BOLD}📊 Git Status{self.RESET}"]

        # Branch
        if status.branch:
            lines.append(f"  Branch: {self.CYAN}{status.branch}{self.RESET}")

        # Status
        if status.is_clean:
            lines.append(f"  {self.GREEN}✓{self.RESET} Working tree clean")
        else:
            lines.append(
                f"  {self.YELLOW}⚠{self.RESET}  {len(status.changed_files)} files changed"
            )

            # Show all changed files
            for file_path in status.changed_files:
                lines.append(f"    {self.DIM}{file_path}{self.RESET}")

        return "\n".join(lines)

    def _format_directory_section(self, listing: DirectoryListing) -> str:
        """Format directory contents section.

        Args:
            listing: Directory listing data

        Returns:
            Formatted section
        """
        lines = [f"{self.BOLD}📂 Contents{self.RESET}"]

        # Show all directories first
        for directory in listing.directories:
            lines.append(f"  {self.BLUE}📁 {directory}/{self.RESET}")

        # Then all files
        for file in listing.files:
            lines.append(f"  {self.DIM}📄 {file}{self.RESET}")

        return "\n".join(lines)

    def _format_plugins_section(self, marketplace: MarketplaceInfo) -> str:
        """Format marketplace plugins as a compact 2-line summary.

        Shows top plugin names with a count, plus a hint for browsing more.

        Args:
            marketplace: MarketplaceInfo with discovered plugins

        Returns:
            Formatted compact plugin summary
        """
        if not marketplace.plugins:
            return ""

        total = len(marketplace.plugins)
        max_named = 3
        names = [p.name for p in marketplace.plugins[:max_named]]
        names_str = ", ".join(names)

        if total > max_named:
            names_str += f" + {total - max_named} more"

        lines = [
            f"{self.BOLD}🔌 Plugins:{self.RESET} {names_str}",
            f"   {self.DIM}/plugin to browse · https://code.claude.com/docs/en/discover-plugins{self.RESET}",
        ]

        return "\n".join(lines)

    def _format_footer(self) -> str:
        """Format helpful footer tip.

        Returns:
            Formatted footer
        """
        separator = self.DIM + ("─" * 60) + self.RESET
        tip = f"{self.DIM}💡 Tip: Context files = you instruct | Memory = AI learns{self.RESET}"
        return f"{separator}\n{tip}"
