"""Startup context transparency report for AI Launcher.

Shows users exactly what context Claude loads at startup, with links to
documentation and hints for optimization.
"""

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ai_launcher.providers.base import AIProvider

from ai_launcher.utils.humanize import humanize_count


@dataclass
class ContextSource:
    """Represents a single context source loaded at startup."""

    name: str
    file_path: Optional[Path]
    status: str  # "loaded", "missing", "not applicable"
    size_bytes: Optional[int]
    line_count: Optional[int]
    purpose: str
    doc_url: str
    hints: List[str]


class StartupReport:
    """Generates a comprehensive startup context report."""

    def __init__(self, project_path: Path, provider: Optional["AIProvider"] = None):
        self.project_path = project_path
        self.provider = provider
        self.sources: List[ContextSource] = []

    def analyze(self) -> None:
        """Analyze all context sources for the given project.

        If a provider is set, uses provider.collect_preview_data() for
        provider-specific context information instead of hardcoded Claude paths.
        """
        if self.provider:
            self._analyze_with_provider()
        else:
            # Legacy behavior for backward compatibility
            self._check_claude_md()
            self._check_auto_memory()
            self._check_global_settings()
            self._check_project_settings()
            self._check_git_context()

    def _analyze_with_provider(self) -> None:
        """Analyze context sources using provider abstraction."""
        data = self.provider.collect_preview_data(self.project_path)
        doc_urls = self.provider.get_documentation_urls()

        # Context files from provider
        for ctx_file in data.context_files:
            if ctx_file.exists:
                hints = []
                if ctx_file.line_count and ctx_file.line_count > 500:
                    hints.append(
                        "⚠️  File is large - consider splitting into multiple context files"
                    )
                if ctx_file.size_bytes and ctx_file.size_bytes > 50000:
                    hints.append(
                        "💡 Consider moving detailed docs to separate files and linking them"
                    )

                self.sources.append(
                    ContextSource(
                        name=f"Project Instructions ({ctx_file.label})",
                        file_path=ctx_file.path,
                        status="loaded",
                        size_bytes=ctx_file.size_bytes,
                        line_count=ctx_file.line_count,
                        purpose="Project-specific rules, architecture, and conventions",
                        doc_url=doc_urls.get("CLAUDE.md guide", ""),
                        hints=hints,
                    )
                )
            else:
                self.sources.append(
                    ContextSource(
                        name=f"Project Instructions ({ctx_file.label})",
                        file_path=None,
                        status="missing",
                        size_bytes=None,
                        line_count=None,
                        purpose="Project-specific rules, architecture, and conventions",
                        doc_url=doc_urls.get("CLAUDE.md guide", ""),
                        hints=[
                            f"💡 Create {ctx_file.label} to add project-specific instructions"
                        ],
                    )
                )

        # Memory from provider data
        if data.memory_info:
            mem = data.memory_info
            if mem.project_memory:
                hints = []
                if mem.project_lines > 200:
                    hints.append(
                        "⚠️  Only first 200 lines are loaded - move details to topic files"
                    )
                elif mem.project_lines > 150:
                    hints.append(
                        "💡 Approaching 200-line limit - consider organizing by topics"
                    )
                elif mem.project_lines < 20 and mem.project_lines > 0:
                    hints.append("✅ Good - concise and focused")

                self.sources.append(
                    ContextSource(
                        name="Auto Memory (MEMORY.md)",
                        file_path=mem.project_memory,
                        status="loaded",
                        size_bytes=mem.project_memory.stat().st_size
                        if mem.project_memory.exists()
                        else None,
                        line_count=mem.project_lines,
                        purpose="Persistent learnings across sessions (first 200 lines only)",
                        doc_url=doc_urls.get("Auto memory", ""),
                        hints=hints,
                    )
                )
            else:
                self.sources.append(
                    ContextSource(
                        name="Auto Memory (MEMORY.md)",
                        file_path=None,
                        status="not created yet",
                        size_bytes=None,
                        line_count=None,
                        purpose="Persistent learnings across sessions (first 200 lines only)",
                        doc_url=doc_urls.get("Auto memory", ""),
                        hints=[
                            "💡 Auto memory will be created as the AI learns about your project"
                        ],
                    )
                )
        else:
            self.sources.append(
                ContextSource(
                    name="Auto Memory (MEMORY.md)",
                    file_path=None,
                    status="not created yet",
                    size_bytes=None,
                    line_count=None,
                    purpose="Persistent learnings across sessions (first 200 lines only)",
                    doc_url=doc_urls.get("Auto memory", ""),
                    hints=[
                        "💡 Auto memory will be created as the AI learns about your project"
                    ],
                )
            )

        # Session config from provider data
        if data.session_config and data.session_config.model:
            status = f"loaded (model: {data.session_config.model})"
        else:
            status = "missing"

        self.sources.append(
            ContextSource(
                name="Global Settings",
                file_path=None,
                status=status,
                size_bytes=None,
                line_count=None,
                purpose="Global preferences (model selection, features)",
                doc_url=doc_urls.get("Settings", ""),
                hints=["✅ Global preferences loaded"]
                if "loaded" in status
                else ["💡 Using default settings"],
            )
        )

        # Project settings
        self._check_project_settings()

        # Git context (generic, not provider-specific)
        self._check_git_context()

    def _check_claude_md(self) -> None:
        """Check for CLAUDE.md in project root."""
        claude_md = self.project_path / "CLAUDE.md"

        if claude_md.exists():
            size = claude_md.stat().st_size
            lines = len(claude_md.read_text().splitlines())
            status = "loaded"
            hints = []

            if lines > 500:
                hints.append(
                    "⚠️  File is large - consider splitting into multiple context files"
                )
            if size > 50000:
                hints.append(
                    "💡 Consider moving detailed docs to separate files and linking them"
                )

        else:
            size = None
            lines = None
            status = "missing"
            hints = [
                "💡 Create CLAUDE.md to add project-specific instructions",
                "📚 See examples: https://github.com/anthropics/claude-code/examples",
            ]

        self.sources.append(
            ContextSource(
                name="Project Instructions (CLAUDE.md)",
                file_path=claude_md if claude_md.exists() else None,
                status=status,
                size_bytes=size,
                line_count=lines,
                purpose="Project-specific rules, architecture, and conventions",
                doc_url="https://code.claude.com/docs/en/claude-md",
                hints=hints,
            )
        )

    def _check_auto_memory(self) -> None:
        """Check for auto memory files."""
        # Encode project path to match Claude's memory directory structure
        # Convert absolute path to encoded format: /foo/bar_baz -> -foo-bar-baz
        # Claude converts BOTH slashes (/) AND underscores (_) to dashes (-)
        abs_path = self.project_path.resolve()
        encoded_path = str(abs_path).replace("/", "-").replace("_", "-")
        memory_dir = Path.home() / ".claude" / "projects" / encoded_path / "memory"
        memory_file = memory_dir / "MEMORY.md"

        if memory_file.exists():
            size = memory_file.stat().st_size
            lines = len(memory_file.read_text().splitlines())
            status = "loaded"
            hints = []

            if lines > 200:
                hints.append(
                    "⚠️  Only first 200 lines are loaded - move details to topic files"
                )
            if lines > 150:
                hints.append(
                    "💡 Approaching 200-line limit - consider organizing by topics"
                )
            if lines < 20:
                hints.append("✅ Good - concise and focused")

        else:
            size = None
            lines = None
            status = "not created yet"
            hints = [
                "💡 Auto memory will be created as Claude learns about your project",
                "💬 Tell Claude to remember things: 'Remember we use pytest for testing'",
            ]

        self.sources.append(
            ContextSource(
                name="Auto Memory (MEMORY.md)",
                file_path=memory_file if memory_file.exists() else None,
                status=status,
                size_bytes=size,
                line_count=lines,
                purpose="Claude's persistent learnings across sessions (first 200 lines only)",
                doc_url="https://code.claude.com/docs/en/memory",
                hints=hints,
            )
        )

    def _check_global_settings(self) -> None:
        """Check for global Claude settings."""
        settings_file = Path.home() / ".claude" / "settings.json"

        if settings_file.exists():
            size = settings_file.stat().st_size
            try:
                settings = json.loads(settings_file.read_text())
                model = settings.get("model", "not specified")
                status = f"loaded (model: {model})"
            except json.JSONDecodeError:
                status = "loaded (parse error)"

            hints = ["✅ Global preferences loaded"]
        else:
            size = None
            status = "missing"
            hints = ["💡 Claude will use default settings"]

        self.sources.append(
            ContextSource(
                name="Global Settings",
                file_path=settings_file if settings_file.exists() else None,
                status=status,
                size_bytes=size,
                line_count=None,
                purpose="Global Claude preferences (model selection, features)",
                doc_url="https://code.claude.com/docs/en/settings",
                hints=hints,
            )
        )

    def _check_project_settings(self) -> None:
        """Check for project-level settings override."""
        settings_file = self.project_path / ".claude" / "settings.local.json"

        if settings_file.exists():
            size = settings_file.stat().st_size
            status = "loaded (overrides global)"
            hints = ["✅ Project-specific settings will override global settings"]
        else:
            size = None
            status = "not present"
            hints = [
                "💡 Create .claude/settings.local.json to override global settings"
            ]

        self.sources.append(
            ContextSource(
                name="Project Settings Override",
                file_path=settings_file if settings_file.exists() else None,
                status=status,
                size_bytes=size,
                line_count=None,
                purpose="Project-specific overrides for global settings",
                doc_url="https://code.claude.com/docs/en/settings",
                hints=hints,
            )
        )

    def _check_git_context(self) -> None:
        """Check for git repository context."""
        git_dir = self.project_path / ".git"

        if git_dir.exists():
            status = "loaded"
            hints = ["✅ Git branch, status, and recent commits available"]
        else:
            status = "not a git repo"
            hints = ["💡 Initialize git to enable version context: git init"]

        self.sources.append(
            ContextSource(
                name="Git Context",
                file_path=git_dir if git_dir.exists() else None,
                status=status,
                size_bytes=None,
                line_count=None,
                purpose="Branch name, git status, recent commits",
                doc_url="https://git-scm.com/doc",
                hints=hints,
            )
        )

    def format_report(self, show_hints: bool = True) -> str:
        """Format the report for terminal display."""
        provider_name = (
            self.provider.metadata.display_name if self.provider else "Claude Code"
        )

        lines = []
        lines.append("")
        lines.append(
            "┌─────────────────────────────────────────────────────────────────┐"
        )
        title_line = f"│  {provider_name} Startup Context Report"
        title_line = title_line + " " * (66 - len(title_line)) + "│"
        lines.append(title_line)
        subtitle = f"│  Transparency: What Context is {provider_name} Loading?"
        subtitle = subtitle + " " * (66 - len(subtitle)) + "│"
        lines.append(subtitle)
        lines.append(
            "└─────────────────────────────────────────────────────────────────┘"
        )
        lines.append("")
        lines.append(f"📁 Project: {self.project_path}")
        lines.append("")

        for i, source in enumerate(self.sources, 1):
            # Header
            lines.append(f"{i}. {source.name}")
            lines.append(f"   Status: {source.status}")

            # File info
            if source.file_path:
                lines.append(f"   Path: {source.file_path}")
            if source.size_bytes is not None:
                size_kb = source.size_bytes / 1024
                lines.append(f"   Size: {size_kb:.1f} KB")
            if source.line_count is not None:
                lines.append(f"   Lines: {source.line_count}")

            # Purpose
            lines.append(f"   Purpose: {source.purpose}")

            # Documentation link
            lines.append(f"   📚 Docs: {source.doc_url}")

            # Hints
            if show_hints and source.hints:
                lines.append("")
                for hint in source.hints:
                    lines.append(f"      {hint}")

            lines.append("")

        # Footer
        lines.append(
            "─────────────────────────────────────────────────────────────────"
        )
        lines.append("")
        lines.append("💡 Tips for Maximizing Your Experience:")
        lines.append("")
        lines.append("   1. Keep CLAUDE.md concise - move detailed docs elsewhere")
        lines.append("   2. Let auto memory grow naturally - Claude learns as you work")
        lines.append(
            "   3. Use project settings to override model/preferences per-project"
        )
        lines.append("   4. Tell Claude to remember things: 'Remember we use pytest'")
        lines.append("")
        lines.append("📖 Learn more:")
        lines.append("   • CLAUDE.md guide: https://code.claude.com/docs/en/claude-md")
        lines.append("   • Auto memory: https://code.claude.com/docs/en/memory")
        lines.append("   • Settings: https://code.claude.com/docs/en/settings")
        lines.append("")

        return "\n".join(lines)

    def format_summary(self) -> str:
        """Format a brief summary (for insertion at session start)."""
        lines = []
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("  CONTEXT LOADED FOR THIS SESSION")
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("")

        for source in self.sources:
            icon = (
                "✅"
                if "loaded" in source.status
                else "❌"
                if "missing" in source.status
                else "⚪"
            )
            lines.append(f"{icon} {source.name}: {source.status}")

        lines.append("")
        lines.append(
            "💡 Run 'ai-launcher --startup-report' for detailed context breakdown"
        )
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("")

        return "\n".join(lines)


def generate_startup_report(
    project_path,
    summary_only: bool = False,
    provider: Optional["AIProvider"] = None,
) -> str:
    """Generate a startup context report for a project.

    Args:
        project_path: Path to the project directory (str or Path)
        summary_only: If True, return brief summary instead of full report
        provider: Optional AI provider instance for provider-aware analysis

    Returns:
        Formatted report as a string
    """
    if not isinstance(project_path, Path):
        project_path = Path(project_path)

    report = StartupReport(project_path, provider=provider)
    report.analyze()

    if summary_only:
        return report.format_summary()
    return report.format_report()


def _visual_length(text: str) -> int:
    """Calculate visual length of text accounting for emoji width.

    Emojis typically take 2 character widths in terminal display.

    Args:
        text: String to measure

    Returns:
        Visual width in terminal characters
    """
    import unicodedata

    length = 0
    for char in text:
        # East Asian Wide and Fullwidth characters take 2 spaces
        if unicodedata.east_asian_width(char) in ("F", "W") or ord(char) > 0x1F000:
            length += 2
        else:
            length += 1
    return length


def _pad_line(text: str, width: int) -> str:
    """Pad line to exact width accounting for emoji characters.

    Args:
        text: Text to pad (should start with │)
        width: Target width including borders

    Returns:
        Padded string
    """
    visual_len = _visual_length(text)
    padding_needed = width - visual_len - 1  # -1 for closing │
    if padding_needed > 0:
        return text + " " * padding_needed + "│"
    return text + "│"


def _check_sibling_projects(project_path: Path) -> dict:
    """Check for sibling projects in the same parent directory.

    Returns dict with:
    - sibling_count: Number of sibling projects
    - selected_project: Name of the selected project
    - sibling_names: List of sibling project names
    """
    info = {
        "sibling_count": 0,
        "selected_project": project_path.name,
        "sibling_names": [],
    }

    # Check for sibling directories
    parent = project_path.parent
    if parent.exists():
        siblings = [
            d
            for d in parent.iterdir()
            if d.is_dir() and d != project_path and not d.name.startswith(".")
        ]
        info["sibling_count"] = len(siblings)
        info["sibling_names"] = [s.name for s in siblings[:6]]  # Limit to 6

    return info


def display_launch_info(
    project_path: Path,
    provider: "AIProvider",
    verbose: bool = True,
) -> None:
    """Display launch information before starting the AI provider.

    Uses provider.collect_preview_data() for all provider-specific data,
    keeping this function provider-agnostic.

    Args:
        project_path: Path to the project being launched
        provider: AI provider instance
        verbose: Whether to show full details (default: True)
    """
    if not verbose:
        # Minimal output - just launching message
        print(f"🚀 Launching {provider.metadata.display_name}...")
        return

    # Collect all provider data through the abstraction
    try:
        data = provider.collect_preview_data(project_path)
    except Exception:
        # Fallback to minimal display if data collection fails
        print(f"🚀 Launching {provider.metadata.display_name}...")
        return

    # Box width - wider to accommodate long paths
    width = 85
    metadata = provider.metadata

    # Header
    print()
    print("╭" + "─" * (width - 2) + "╮")
    title = f"AI Launcher → {project_path.name}"
    print(_pad_line(f"│ {title}", width))
    print("├" + "─" * (width - 2) + "┤")

    # Provider info
    version = None
    if hasattr(provider, "get_version"):
        with contextlib.suppress(Exception):
            version = provider.get_version()

    if version:
        provider_label = f"{metadata.display_name} v{version}"
    else:
        provider_label = metadata.display_name

    print(_pad_line(f"│ 🤖 Provider: {provider_label}", width))

    # Project path - use tilde notation for brevity
    try:
        rel_path = project_path.relative_to(Path.home())
        project_str = f"~/{rel_path}"
    except ValueError:
        project_str = str(project_path)

    print(_pad_line(f"│ 📁 Project:  {project_str}", width))
    print(_pad_line("│", width))

    # Context sources summary (from provider data)
    print(_pad_line("│ 📋 Context Sources:", width))

    loaded_files = [f for f in data.context_files if f.exists]
    if loaded_files:
        for ctx_file in loaded_files:
            type_label = "personal" if ctx_file.file_type == "personal" else "project"
            if ctx_file.line_count:
                status_text = f"{ctx_file.line_count} lines ({type_label})"
            else:
                status_text = type_label
            line = f"│   ✅ {ctx_file.label}: {status_text}"
            print(_pad_line(line, width))
    else:
        print(_pad_line("│   (no context loaded)", width))

    print(_pad_line("│", width))

    # Session configuration section (from provider data)
    session_config = data.session_config
    print(_pad_line("│ 🔧 Session Configuration:", width))

    if session_config:
        # Permissions
        if session_config.permissions_count > 0:
            perm_text = f"✓ {session_config.permissions_count} auto-approved commands"
            print(_pad_line(f"│   {perm_text}", width))
        else:
            print(_pad_line("│   ○ No pre-approved permissions", width))

        # MCP Servers
        if session_config.mcp_servers:
            server_list = ", ".join(session_config.mcp_servers[:3])
            if len(session_config.mcp_servers) > 3:
                server_list += f", +{len(session_config.mcp_servers) - 3} more"
            print(_pad_line(f"│   ✓ MCP servers: {server_list}", width))
        else:
            print(_pad_line("│   ○ No MCP servers configured", width))

        # Hooks
        if session_config.hooks_configured:
            print(_pad_line("│   ✓ Hooks configured", width))
        else:
            print(_pad_line("│   ○ No hooks configured", width))

        # Model selection
        if session_config.model:
            print(_pad_line(f"│   ✓ Model: {session_config.model}", width))
        else:
            print(_pad_line("│   ○ Model: default (sonnet)", width))
    else:
        print(_pad_line("│   ○ No pre-approved permissions", width))
        print(_pad_line("│   ○ No MCP servers configured", width))
        print(_pad_line("│   ○ No hooks configured", width))
        print(_pad_line("│   ○ Model: default (sonnet)", width))

    print(_pad_line("│", width))

    # Memory section (from provider data)
    memory_info = data.memory_info
    print(_pad_line(f"│ 🧠 {data.provider_name} Memory:", width))

    has_memory = False
    if memory_info:
        if memory_info.personal_memory and memory_info.personal_lines > 0:
            print(
                _pad_line(f"│   ✓ Personal: {memory_info.personal_lines} lines", width)
            )
            has_memory = True
        elif memory_info.personal_memory:
            print(_pad_line("│   ○ Personal: empty", width))

        if memory_info.project_memory and memory_info.project_lines > 0:
            print(_pad_line(f"│   ✓ Project: {memory_info.project_lines} lines", width))
            has_memory = True
        elif memory_info.project_memory:
            print(_pad_line("│   ○ Project: empty", width))

    if not has_memory:
        print(_pad_line("│   ○ No memory files yet", width))

    print(_pad_line("│", width))

    # Skills section (from provider data)
    skills = data.skills
    print(_pad_line(f"│ 🔨 {data.provider_name} Skills:", width))

    if skills:
        skill_names = [s.name for s in skills]
        skill_list = ", ".join(skill_names[:3])
        if len(skill_names) > 3:
            skill_list += f", +{len(skill_names) - 3} more"
        print(_pad_line(f"│   ✓ {len(skill_names)} available: {skill_list}", width))
    else:
        print(_pad_line("│   ○ No skills installed", width))

    print(_pad_line("│", width))

    # Marketplace Plugins section (from provider data)
    marketplace = data.marketplace_plugins
    if marketplace and marketplace.plugins:
        total = len(marketplace.plugins)
        max_named = 3
        names = [p.name for p in marketplace.plugins[:max_named]]
        names_str = ", ".join(names)
        if total > max_named:
            names_str += f" + {total - max_named} more"

        print(_pad_line(f"│ 🔌 Plugins: {names_str}", width))
        print(
            _pad_line(
                "│    /plugin to browse · https://code.claude.com/docs/en/discover-plugins",
                width,
            )
        )
        print(_pad_line("│", width))

    # Global Context section (from provider data)
    global_ctx = data.global_context_summary
    print(_pad_line("│ 🌐 Global Context:", width))

    if global_ctx and global_ctx.total_files > 0:
        print(_pad_line(f"│   ✓ {global_ctx.total_files} files loaded", width))

        # Show breakdown by category
        for cat_name, count in sorted(global_ctx.categories.items()):
            print(_pad_line(f"│     • {cat_name}: {count}", width))
    else:
        print(_pad_line("│   ○ No global context files", width))

    print(_pad_line("│", width))

    # Sibling Projects section (generic, not provider-specific)
    siblings = _check_sibling_projects(project_path)
    if siblings["sibling_count"] > 0:
        print(_pad_line("│ 📂 Sibling Projects:", width))
        print(
            _pad_line(
                f"│   ✓ {siblings['sibling_count']} nearby projects detected", width
            )
        )

        other_list = ", ".join(siblings["sibling_names"][:3])
        if siblings["sibling_count"] > 3:
            other_list += f", ... +{siblings['sibling_count'] - 3} more"
        print(_pad_line(f"│   ○ Other: {other_list}", width))
        print(_pad_line(f"│   ✓ Selected: {siblings['selected_project']}", width))
        print(_pad_line("│", width))

    # Provider-specific context loading section
    print(_pad_line("│ 📦 Provider Context:", width))

    context_items = []
    for config_file in metadata.config_files:
        config_path = project_path / config_file
        if config_path.exists():
            context_items.append((f"✓ {config_file}", "local project instructions"))

    if context_items:
        for item, desc in context_items:
            if desc:
                line = f"│   {item} ({desc})"
            else:
                line = f"│   {item}"
            visual_len = _visual_length(line)
            if visual_len > width - 2:
                excess = visual_len - (width - 5)
                line = line[: len(line) - excess] + "..."
            print(_pad_line(line, width))
    else:
        print(_pad_line("│   (no context files detected)", width))

    print(_pad_line("│", width))

    # Session activity section (from provider data)
    if data.session_stats:
        from ai_launcher.utils.humanize import format_time_ago, humanize_size

        stats = data.session_stats
        print(_pad_line("│ 📊 Session Activity:", width))

        # Last session time
        if stats.last_session_time:
            last_session = format_time_ago(stats.last_session_time)
            print(_pad_line(f"│   Last used:  {last_session}", width))

        session_size = humanize_size(stats.total_size_bytes)
        print(
            _pad_line(
                f"│   History:    {humanize_count(stats.session_count, 'session')} ({session_size})",
                width,
            )
        )

        # Memory notes
        if stats.memory_files:
            memory_names = [mf.name for mf in stats.memory_files[:3]]
            memory_files_str = ", ".join(memory_names)
            if len(stats.memory_files) > 3:
                memory_files_str += f", +{len(stats.memory_files) - 3} more"
            print(_pad_line(f"│   Memory:     {memory_files_str}", width))

        print(_pad_line("│", width))

    # Footer with launch message
    print(_pad_line(f"│ 🚀 Launching {metadata.display_name}...", width))
    print("╰" + "─" * (width - 2) + "╯")
    print()


def _get_file_description(filename: str) -> str:
    """Get a human-readable description for common context files.

    Args:
        filename: Name of the file

    Returns:
        Description string
    """
    descriptions = {
        "STANDARDS.md": "coding standards",
        "TESTING.md": "testing guidelines",
        "SECURITY.md": "security best practices",
        "OPERATIONS.md": "operational procedures",
        "DEVKIT-PATTERNS.md": "common patterns",
        "DEPLOYMENT.md": "deployment guide",
        "ARCHITECTURE.md": "architecture docs",
        "CONTRIBUTING.md": "contribution guide",
    }

    return descriptions.get(filename, "documentation")


if __name__ == "__main__":
    # Demo: Generate report for current directory
    import sys

    project = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(generate_startup_report(project))
