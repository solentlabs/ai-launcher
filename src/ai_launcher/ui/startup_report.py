"""The launch box AI Launcher draws before it starts a tool.

Shows what the session will load (context files, permissions, memory, skills)
and the guards in place (scope, cache notice, scratch folder, update notice).
"""

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence

if TYPE_CHECKING:
    from ai_launcher.core.cache_data import CacheNotice
    from ai_launcher.core.update_check import UpdateNotice
    from ai_launcher.providers.base import AIProvider

from ai_launcher.utils.humanize import humanize_count


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


def _cut_to_width(text: str, limit: int) -> str:
    """Shorten text to at most `limit` visual columns, ending in an ellipsis."""
    if _visual_length(text) <= limit:
        return text
    kept = text
    while _visual_length(kept) > limit - 1:  # leave a column for the ellipsis
        kept = kept[:-1]
    return kept + "…"


def _pad_line(text: str, width: int) -> str:
    """Pad line to exact width accounting for emoji characters.

    A line too long for the box is cut with an ellipsis: letting it run on
    would push the right border out and wrap the row.

    Args:
        text: Text to pad (should start with │)
        width: Target width including borders

    Returns:
        Padded string
    """
    text = _cut_to_width(text, width - 1)  # -1 for the closing │
    padding_needed = width - _visual_length(text) - 1
    return text + " " * padding_needed + "│"


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
    try:
        siblings = [
            d
            for d in parent.iterdir()
            if d.is_dir() and d != project_path and not d.name.startswith(".")
        ]
    except OSError:  # missing or unreadable parent: just no sibling lines
        return info
    info["sibling_count"] = len(siblings)
    info["sibling_names"] = [s.name for s in siblings[:6]]  # Limit to 6

    return info


def _tilde(path: Path) -> str:
    """Show a path with ~ for the home directory, for brevity."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


def _fit(text: str, room: int, keep_end: bool = False) -> str:
    """Shorten text to a visual width, with an ellipsis."""
    if _visual_length(text) <= room:
        return text
    return "…" + text[-(room - 1) :] if keep_end else text[: room - 1] + "…"


def _cache_notice_line(notice: "CacheNotice", width: int) -> str:
    """The one-line cache notice, red when critical. Padded on its plain text."""
    from ai_launcher.core.cache_data import SEVERITY_CRITICAL
    from ai_launcher.ui.cache_page import fmt, notice_text, severity_symbol

    prefix = "│ 💾 Cache:    "
    text = _fit(notice_text(notice), width - 2 - _visual_length(prefix))
    plain = _pad_line(prefix + text, width)
    if notice.severity < SEVERITY_CRITICAL:
        return plain
    return plain.replace(text, fmt.paint(text, fmt.RED), 1).replace(
        "💾", severity_symbol(notice.severity), 1
    )


def _update_line(notice: "UpdateNotice", width: int) -> str:
    """The one-line update notice."""
    prefix = "│ 🆕 Update:   "
    text = _fit(
        f"{notice.latest} is available (you have {notice.installed}) · ai-launcher update",
        width - 2 - _visual_length(prefix),
    )
    return _pad_line(prefix + text, width)


def _scratch_line(scratch_dir: Path, width: int) -> str:
    """Where the session was asked to put its scratch files."""
    prefix = "│ 📂 Scratch:  $AI_SCRATCH_DIR → "
    text = _fit(_tilde(scratch_dir), width - 2 - _visual_length(prefix), True)
    return _pad_line(prefix + text, width)


def display_launch_info(
    project_path: Path,
    provider: "AIProvider",
    verbose: bool = True,
    scope_roots: Sequence[Path] = (),
    scope_exempt: Sequence[Path] = (),
    notice: Optional["CacheNotice"] = None,
    scratch_dir: Optional[Path] = None,
    update_notice: Optional["UpdateNotice"] = None,
) -> None:
    """Display launch information before starting the AI provider.

    Uses provider.collect_preview_data() for all provider-specific data,
    keeping this function provider-agnostic.

    Args:
        project_path: Path to the project being launched
        provider: AI provider instance
        verbose: Whether to show full details (default: True)
        scope_roots: Directories holding other projects that the launch guards
        scope_exempt: Directories the guard lets the session write to freely
        notice: A cache and scratch notice to show, if one is due
        scratch_dir: The session's scratch folder, if one was made
        update_notice: A newer release to mention, if the user opted in to checks
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

    print(_pad_line(f"│ 📁 Project:  {_tilde(project_path)}", width))
    if metadata.guards_other_projects and scope_roots:
        print(_pad_line("│ 🔒 Scope:    writes to other projects ask first", width))
        prefix = "│             except "
        room = width - 2 - _visual_length(prefix)
        for exempt in scope_exempt:
            shown = _tilde(exempt)
            if len(shown) > room:
                # Keep the end: the folder name says what is allowed.
                shown = "..." + shown[len(shown) - room + 3 :]
            print(_pad_line(prefix + shown, width))
    if notice is not None:
        print(_cache_notice_line(notice, width))
    if update_notice is not None:
        print(_update_line(update_notice, width))
    if scratch_dir is not None:
        print(_scratch_line(scratch_dir, width))
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
            line = f"│   ✓ {ctx_file.label}: {status_text}"
            print(_pad_line(line, width))
    else:
        print(_pad_line("│   (no context loaded)", width))

    print(_pad_line("│", width))

    # Session configuration section (from provider data)
    session_config = data.session_config
    print(_pad_line("│ 🔧 Session Configuration:", width))

    if session_config:
        # Permission warnings (show first — most actionable)
        if session_config.permission_warnings:
            for warning in session_config.permission_warnings:
                print(_pad_line(f"│   ⚠ {warning}", width))
            if session_config.permission_recommendations:
                for rec in session_config.permission_recommendations:
                    print(_pad_line(f"│     💡 {rec}", width))

        # Project-level permissions
        if session_config.permissions_count > 0:
            if (
                session_config.has_broad_bash
                and "Bash(*)" in session_config.permissions
            ):
                print(_pad_line("│   ✓ Bash(*) (project)", width))
            else:
                perm_text = f"✓ {session_config.permissions_count} auto-approved commands (project)"
                print(_pad_line(f"│   {perm_text}", width))
        else:
            print(_pad_line("│   ○ No project permissions (inherits global)", width))

        # Global-level permissions
        if session_config.global_permissions_count > 0:
            if (
                session_config.has_broad_bash
                and "Bash(*)" in session_config.global_permissions
            ):
                print(
                    _pad_line(
                        f"│   ✓ Bash(*) + {session_config.global_permissions_count - 1} more (global)",
                        width,
                    )
                )
            else:
                print(
                    _pad_line(
                        f"│   ✓ {session_config.global_permissions_count} auto-approved commands (global)",
                        width,
                    )
                )

        # Ask rules
        if session_config.global_ask:
            ask_labels = []
            for pattern in session_config.global_ask:
                if pattern.startswith("Bash(") and pattern.endswith(")"):
                    inner = pattern[5:-1]
                    ask_labels.append(inner.split(":")[0])
                else:
                    ask_labels.append(pattern)
            print(_pad_line("│   🚫 Ask before:", width))
            for label in ask_labels:
                print(_pad_line(f"│     • {label}", width))

        # Permission health summary (always shown)
        if not session_config.permission_warnings and session_config.has_broad_bash:
            print(_pad_line("│   ✓ Permission health: clean", width))

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
        # No settings files at all — every command will prompt
        print(
            _pad_line(
                "│   ⚠ No permissions configured — all commands will prompt", width
            )
        )
        print(_pad_line("│     💡 Set Bash(*) in .claude/settings.local.json", width))
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
        print(_pad_line(f"│   ✓ {len(skill_names)} available", width))
        for name in skill_names[:3]:
            print(_pad_line(f"│     • {name}", width))
        if len(skill_names) > 3:
            print(_pad_line(f"│     • +{len(skill_names) - 3} more", width))
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
                "│   ○ /plugin to browse · https://code.claude.com/docs/en/discover-plugins",
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

        for name in siblings["sibling_names"][:3]:
            print(_pad_line(f"│     • {name}", width))
        if siblings["sibling_count"] > 3:
            print(
                _pad_line(f"│     • ... +{siblings['sibling_count'] - 3} more", width)
            )
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

        # Memory notes — list each file when small; otherwise summarize with
        # a count + the directory so the user can browse on their own. The
        # encoded memory directory can be very long, so it gets its own line(s).
        if stats.memory_files:
            MEMORY_LIST_THRESHOLD = 5
            if len(stats.memory_files) <= MEMORY_LIST_THRESHOLD:
                print(
                    _pad_line(f"│   Memory:     {len(stats.memory_files)} files", width)
                )
                for mf in stats.memory_files:
                    print(_pad_line(f"│     • {mf.name}", width))
            else:
                memory_dir = stats.memory_files[0].path.parent
                # Render with forward slashes regardless of OS — this is a
                # display string, not a filesystem path, and the wrap logic
                # below splits on "/". Native separators (e.g. "\" on Windows)
                # would skip wrapping entirely and overflow the box.
                try:
                    rel = memory_dir.relative_to(Path.home())
                    dir_str = f"~/{rel.as_posix()}"
                except ValueError:
                    dir_str = memory_dir.as_posix()
                print(
                    _pad_line(f"│   Memory:     {len(stats.memory_files)} files", width)
                )
                # Wrap path across lines, breaking at "/" boundaries when
                # possible so directory segments stay intact.
                path_prefix = "│     "
                cont_prefix = "│       "
                segments = dir_str.split("/")
                lines_to_print: List[str] = []
                current = ""
                first = True
                for seg in segments:
                    sep = "" if (current == "" or current.endswith("/")) else "/"
                    candidate = current + sep + seg if current else seg
                    prefix = (
                        path_prefix if first and not lines_to_print else cont_prefix
                    )
                    budget = width - _visual_length(prefix) - 1
                    if len(candidate) <= budget:
                        current = candidate
                    else:
                        if current:
                            lines_to_print.append(current + "/")
                            current = seg
                        else:
                            # Single segment longer than the budget — hard split.
                            lines_to_print.append(seg[:budget])
                            current = seg[budget:]
                if current:
                    lines_to_print.append(current)
                for i, line_text in enumerate(lines_to_print):
                    prefix = path_prefix if i == 0 else cont_prefix
                    print(_pad_line(f"{prefix}{line_text}", width))

        print(_pad_line("│", width))

    # Footer with launch message
    print(_pad_line(f"│ 🚀 Launching {metadata.display_name}...", width))
    print("╰" + "─" * (width - 2) + "╯")
    print()
