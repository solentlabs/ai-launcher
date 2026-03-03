#!/usr/bin/env python3
"""Preview helper script for fzf."""

import os
import sys
from pathlib import Path

from ai_launcher.ui.preview import generate_provider_preview


def show_configuration_preview() -> None:
    """Show configuration in preview pane (read from environment variables)."""
    print("╭─────────────────────────────────────────╮")
    print("│            Configuration                │")
    print("╰─────────────────────────────────────────╯")
    print()
    print("\033[2mConfiguration is passed via CLI flags.\033[0m")
    print("\033[2mRun 'ai-launcher --help' to see all options.\033[0m")
    print()

    # Provider
    provider_name = os.environ.get("AI_LAUNCHER_PROVIDER", "claude-code")
    print(f"\033[1m🤖 Provider:\033[0m {provider_name}")
    print()

    # Project Paths
    print("\033[1m📁 Project Paths\033[0m")
    scan_paths_env = os.environ.get("AI_LAUNCHER_SCAN_PATHS", "")
    if scan_paths_env:
        scan_paths = scan_paths_env.split(os.pathsep)
        print(f"   Scan paths: {len(scan_paths)}")
        for sp in scan_paths:
            try:
                sp_path = Path(sp)
                rel = f"~/{sp_path.relative_to(Path.home())}"
            except ValueError:
                rel = sp
            print(f"     • {rel}")
    else:
        print("   \033[2mNo scan paths specified\033[0m")

    # Manual Paths
    manual_paths_env = os.environ.get("AI_LAUNCHER_MANUAL_PATHS", "")
    if manual_paths_env:
        manual_paths = [mp.strip() for mp in manual_paths_env.split(",") if mp.strip()]
        if manual_paths:
            print(f"   Manual paths: {len(manual_paths)}")
            for mp in manual_paths:
                mp_path = Path(mp).expanduser()
                try:
                    rel = f"~/{mp_path.relative_to(Path.home())}"
                except ValueError:
                    rel = mp
                print(f"     • {rel}")
    print()

    # Global Files
    print("\033[1m🌐 Global Files\033[0m")
    global_files_env = os.environ.get("AI_LAUNCHER_GLOBAL_FILES", "")
    if global_files_env:
        global_files = [gf.strip() for gf in global_files_env.split(",") if gf.strip()]
        print(f"   Configured: {len(global_files)}")
        for gf in global_files[:10]:
            # Convert to ~ shorthand if under home directory
            gf_path = Path(gf).expanduser()
            try:
                rel = f"~/{gf_path.relative_to(Path.home())}"
            except ValueError:
                rel = gf
            print(f"     • {rel}")
        if len(global_files) > 10:
            remaining = len(global_files) - 10
            print(f"     \033[2m...and {remaining} more\033[0m")
    else:
        print("   \033[2mNo global files configured\033[0m")
    print()

    # Build actual command from environment variables (multi-line format)
    print("\033[2mCurrent command:\033[0m")

    # Get provider name and map to command name
    provider_env = os.environ.get("AI_LAUNCHER_PROVIDER", "claude-code")
    provider_cmd = "claude" if provider_env == "claude-code" else provider_env

    # Build base command with path
    base_cmd = f"  ai-launcher {provider_cmd}"
    if scan_paths_env:
        scan_paths = scan_paths_env.split(os.pathsep)
        if scan_paths:
            # Use first scan path
            sp_path = Path(scan_paths[0])
            try:
                rel = f"~/{sp_path.relative_to(Path.home())}"
            except ValueError:
                rel = scan_paths[0]
            base_cmd += f" {rel}"

    print(f"\033[2m{base_cmd}\033[0m")

    # Add global files - each on separate line
    if global_files_env:
        global_files = [gf.strip() for gf in global_files_env.split(",") if gf.strip()]
        if global_files:
            print("\033[2m    --global-files\033[0m")
            for gf in global_files:
                gf_path = Path(gf).expanduser()
                try:
                    rel = f"~/{gf_path.relative_to(Path.home())}"
                except ValueError:
                    rel = gf
                print(f"\033[2m      {rel}\033[0m")

    # Add manual paths - each on separate line
    if manual_paths_env:
        manual_paths = [mp.strip() for mp in manual_paths_env.split(",") if mp.strip()]
        if manual_paths:
            print("\033[2m    --manual-paths\033[0m")
            for mp in manual_paths:
                mp_path = Path(mp).expanduser()
                try:
                    rel = f"~/{mp_path.relative_to(Path.home())}"
                except ValueError:
                    rel = mp
                print(f"\033[2m      {rel}\033[0m")
    print()

    # Available Options
    print(
        "\033[1m⚙️ Available Options\033[0m \033[2m(All options work independently)\033[0m"
    )
    print()
    print("   \033[1mContext:\033[0m")
    print("     --global-files FILE1,FILE2    Load files for all projects")
    print("     --manual-paths PATH1,PATH2    Add projects manually")
    print()
    print("   \033[1mCleanup (opt-in):\033[0m")
    print("     --cleanup                     Clean AI assistant cache/logs")
    print("     --clean-cache                 Clean ~/.cache")
    print("     --clean-npm                   Clean npm cache")
    print()
    print("   \033[1mInformation:\033[0m")
    print("     --list                        List all projects")
    print("     --discover, -d                Show discovery report")
    print("     --context, -c                 Show context viewer")
    print()
    print("   \033[1mDebug:\033[0m")
    print("     --verbose                     Enable verbose logging")
    print("     --debug                       Enable debug mode")
    print()

    # Version
    from ai_launcher import __version__

    print(f"\033[2mai-launcher v{__version__}\033[0m")


def build_tree_structure(file_paths):
    """Build a nested tree structure from file paths.

    Args:
        file_paths: List of path strings

    Returns:
        Nested dict representing the tree
    """
    tree = {}
    for path in file_paths:
        parts = path.split("/")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    return tree


def print_tree(tree, indent="", is_last_list=None):
    """Print tree structure with proper connectors.

    Args:
        tree: Nested dict tree structure
        indent: Current indentation prefix
        is_last_list: List of booleans indicating if each level is last
    """
    if is_last_list is None:
        is_last_list = []

    items = sorted(tree.items())
    for idx, (name, subtree) in enumerate(items):
        is_last = idx == len(items) - 1

        # Build connector
        if indent == "":
            # Root level - no connector
            prefix = "  "
        else:
            # Build prefix based on parent levels
            prefix_parts = []
            for is_parent_last in is_last_list:
                if is_parent_last:
                    prefix_parts.append("  ")
                else:
                    prefix_parts.append("│ ")
            prefix = "".join(prefix_parts)

        # Add current level connector
        if indent != "":
            connector = "└─" if is_last else "├─"
            line = f"{indent}{prefix}{connector} {name}"
        else:
            line = f"{indent}{prefix}{name}"

        # Check if this is a file (no children) or directory
        if subtree:
            # Directory - show with /
            if not line.endswith("/"):
                line += "/"
            print(line)
            # Recurse into subdirectory
            new_is_last_list = is_last_list + [is_last]
            print_tree(subtree, indent + "  ", new_is_last_list)
        else:
            # File - show without /
            print(line)


def main() -> None:
    """Generate preview from fzf selection line."""
    if len(sys.argv) < 2:
        print("No selection provided")
        return

    line = sys.argv[1]

    # Extract path from formatted line
    # Format is: "absolute_path\t\ttree_display" or special markers
    # Special markers: __SPACE__ (spacing line), __ACTION__ (action menu items)
    parts = line.split("\t\t", 1)

    if len(parts) == 2:
        if parts[0] == "__ACTION__" and "Configuration" in parts[1]:
            # Configuration action - show configuration preview
            show_configuration_preview()
            return
        if parts[0] in ("__SPACE__", "__ACTION__"):
            # Other action items or spacing - show nothing
            return
        # Normal line - first field is absolute path (project or directory)
        path_str = parts[0]
    else:
        # Malformed line - show nothing
        return

    try:
        path = Path(path_str).expanduser().resolve()

        # Show full path at top with divider
        print(f"{path}")
        print("━" * 80)
        print()

        # Check if it's a directory (folder header) or project
        if path.is_dir() and not (path / ".git").exists():
            # Directory header - show directory contents first
            print("Contents:")
            print("─" * 80)
            try:
                # Separate directories and files
                dirs = []
                files = []
                for item in path.iterdir():
                    if item.is_dir():
                        dirs.append(f"  📁 {item.name}/")
                    else:
                        files.append(f"  📄 {item.name}")

                # Sort each group and combine (folders first)
                items = sorted(dirs) + sorted(files)

                # Show all items (no limit)
                if items:
                    print("\n".join(items))
                else:
                    print("  (empty directory)")
            except PermissionError:
                print("  (permission denied)")
            except Exception as e:
                print(f"  (error reading directory: {e})")

            # Check if this is a scan root directory
            scan_paths_env = os.environ.get("AI_LAUNCHER_SCAN_PATHS", "")
            is_scan_root = False
            if scan_paths_env:
                scan_paths = [Path(p) for p in scan_paths_env.split(os.pathsep) if p]
                is_scan_root = any(path.resolve() == sp.resolve() for sp in scan_paths)

            # Show manual paths and global files if this is a scan root
            if is_scan_root:
                print()
                try:
                    # Show manual paths from environment variable
                    manual_paths_env = os.environ.get("AI_LAUNCHER_MANUAL_PATHS", "")
                    if manual_paths_env:
                        manual_paths = [
                            mp.strip()
                            for mp in manual_paths_env.split(",")
                            if mp.strip()
                        ]
                        if manual_paths:
                            print("─" * 80)
                            print("📌 Manual Paths:")
                            for mp in manual_paths:
                                mp_path = Path(mp).expanduser()
                                # Show relative to home if possible
                                try:
                                    rel_path = f"~/{mp_path.relative_to(Path.home())}"
                                except ValueError:
                                    rel_path = str(mp_path)
                                print(f"  {rel_path}")
                            print("─" * 80)
                            print()

                    # Show global files via provider abstraction (separation of concerns)
                    provider_name = os.environ.get(
                        "AI_LAUNCHER_PROVIDER", "claude-code"
                    )
                    try:
                        from ai_launcher.providers.registry import ProviderRegistry
                        from ai_launcher.ui.formatter import PreviewFormatter

                        # Get provider instance using abstraction
                        registry = ProviderRegistry()
                        provider = registry.get(provider_name)

                        if provider:
                            # Collect preview data (includes global_files and provider_context)
                            preview_data = provider.collect_preview_data(path)
                            formatter = PreviewFormatter()

                            # User-configured global files
                            if preview_data.global_files:
                                print(
                                    formatter._format_global_files_section(
                                        preview_data.global_files
                                    )
                                )
                                print("─" * 80)
                                print()

                            # Auto-discovered provider context files
                            if preview_data.provider_context:
                                print(
                                    formatter._format_provider_context_section(
                                        preview_data.provider_context,
                                        preview_data.provider_name,
                                    )
                                )
                                print("─" * 80)
                                print()

                            # Marketplace plugins
                            if preview_data.marketplace_plugins:
                                print(
                                    formatter._format_plugins_section(
                                        preview_data.marketplace_plugins
                                    )
                                )
                                print("─" * 80)
                                print()
                    except Exception as e:
                        print(f"\n⚠️  Error loading provider context: {e}")
                        import traceback

                        traceback.print_exc()

                except Exception:
                    pass  # Silently skip if error displaying preview info
        else:
            # Project directory - show full preview using new architecture
            provider_name = os.environ.get("AI_LAUNCHER_PROVIDER", "claude-code")
            preview_output = generate_provider_preview(
                path, provider_name=provider_name
            )
            print(preview_output)
    except Exception as e:
        print(f"Error generating preview: {e}")


if __name__ == "__main__":
    main()
