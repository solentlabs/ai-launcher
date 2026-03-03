"""Project selector UI for ai-launcher.

This module provides the interactive fuzzy-search project selector using fzf,
with preview pane, action menu, and support for rescanning, adding/removing
paths, and accessing settings.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added settings menu item)
"""

import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

# ConfigManager removed - using runtime config from CLI flags
from ai_launcher.core.models import Project
from ai_launcher.ui.preview import build_tree_view
from ai_launcher.utils.paths import is_relative_to

if TYPE_CHECKING:
    from ai_launcher.core.models import ConfigData


def clear_screen() -> None:
    """Clear the terminal screen using ANSI escape codes."""
    print("\033[H\033[2J", end="", flush=True)


def select_project(
    projects: List[Project],
    show_git_status: bool = True,
    config: Optional["ConfigData"] = None,
    scan_paths: Optional[List[Path]] = None,
    manual_paths: Optional[List[str]] = None,
) -> Optional[Project]:
    """Show interactive project selector with action support.

    Args:
        projects: List of projects to choose from (already sorted)
        show_git_status: Whether to show git status in preview
        config: Configuration data from CLI flags (optional)
        scan_paths: Original scan paths for rescan action (optional)
        manual_paths: Manual project paths from CLI flags (optional)

    Returns:
        Selected Project or None if cancelled
    """
    # Action loop - allows rescanning, adding, removing
    current_projects = projects
    while True:
        if not current_projects:
            print(
                "No projects found. Add scan paths with --setup or add manual paths with --add"
            )
            return None

        # Clear screen before launching fzf
        clear_screen()

        # Determine base path for display
        # Use the actual scan path for header and tree display
        if scan_paths:
            if len(scan_paths) == 1:
                base_path = scan_paths[0]
            else:
                # Multiple scan paths - find common base
                common = os.path.commonpath([str(p) for p in scan_paths])
                base_path = Path(common)
        else:
            base_path = Path.cwd()

        # Build tree view of projects with the base path
        # Format: "absolute_path\t\ttree_display"
        choices, choice_to_project = build_tree_view(current_projects, base_path)

        # Add action menu items at the bottom
        choices.append("__ACTION__\t\t")
        choices.append("__ACTION__\t\t⚙️ Configuration")

        # Build header with project info
        project_count = len(current_projects)

        # Format base path with ~ shorthand
        home = Path.home()
        display_base = (
            f"~/{base_path.relative_to(home)}"
            if is_relative_to(base_path, home)
            else str(base_path)
        )

        header = f"""╭─────────────────────────────────────────╮
│            AI Launcher                  │
│          by Solent Labs™                │
╰─────────────────────────────────────────╯

{project_count} project{"s" if project_count != 1 else ""} in {display_base}
Type to filter • Arrows to navigate
─────────────────────────────────────────
"""

        # Build preview command using helper script
        helper_script = Path(__file__).parent / "_preview_helper.py"
        preview_cmd = f"{sys.executable} {helper_script} {{}}"

        # Set environment variables for preview helper
        env = os.environ.copy()
        if scan_paths:
            env["AI_LAUNCHER_SCAN_PATHS"] = os.pathsep.join(str(p) for p in scan_paths)
        if config and config.context.global_files:
            env["AI_LAUNCHER_GLOBAL_FILES"] = ",".join(config.context.global_files)
        if manual_paths:
            env["AI_LAUNCHER_MANUAL_PATHS"] = ",".join(manual_paths)
        if config:
            env["AI_LAUNCHER_PROVIDER"] = config.provider.default

        # Run fzf directly via subprocess
        try:
            fzf_cmd = [
                "fzf",
                "--prompt=Filter: ",
                "--height=100%",
                "--layout=reverse",  # Nav at top
                "--border=rounded",
                "--border-label= Projects ",
                "--delimiter=\t\t",  # Use double-tab as delimiter
                "--with-nth=2..",  # Show only the tree display (field 2 onwards)
                "--preview-window=right:70%:wrap:border-left:nohidden",  # Preview 70%, list 30%
                f"--preview={preview_cmd}",
                f"--header={header}",
                "--header-first",  # Display header before prompt
                "--info=hidden",  # Hide match counter
                "--ansi",  # Enable ANSI color codes
            ]

            # Pass choices via stdin
            input_data = "\n".join(choices)

            # Run fzf with stdin, but let it use the terminal for UI
            # Do NOT capture stdout/stderr - fzf needs direct terminal access
            process = subprocess.Popen(  # nosec B603
                fzf_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                env=env,
            )

            stdout, _ = process.communicate(input=input_data)
            result_code = process.returncode

            # Check if user cancelled (exit code 130 = Ctrl+C, 1 = no match/cancelled)
            if result_code in (1, 130):
                clear_screen()
                return None

            if result_code != 0:
                clear_screen()
                print(f"Error running fzf: exit code {result_code}")
                return None

            # Get selected line
            selected = stdout.strip()
            if not selected:
                return None

            # Handle action menu items
            if selected == "__ACTION__\t\t⚙️ Configuration":
                # Configuration preview is shown in right pane, just loop back
                continue

            # Handle empty line action item (just loop back)
            if selected == "__ACTION__\t\t" or selected.startswith("__SPACE__"):
                continue

            # Regular project selection
            if not selected:
                return None

            # Look up the project from the formatted line
            project = choice_to_project.get(selected)
            if project:
                # Clear screen before launching Claude
                clear_screen()
                return project

            # Not a project - check if it's a directory header or other non-selectable item
            # Extract path from formatted line to check
            parts = selected.split("\t\t", 1)
            if len(parts) == 2:
                path_str = parts[0]
                try:
                    path = Path(path_str).expanduser().resolve()
                    # If it's a directory (folder header), just loop back
                    if path.is_dir() and not (path / ".git").exists():
                        continue
                except Exception:
                    pass

            # If we get here, it's an unknown selection - just loop back instead of closing
            continue

        except FileNotFoundError:
            print("Error: fzf not found. Please install fzf:")
            print("  Ubuntu/Debian: sudo apt install fzf")
            print("  macOS: brew install fzf")
            return None
        except Exception as e:
            print(f"Error in project selector: {e}")
            import traceback

            traceback.print_exc()
            return None


def show_project_list(projects: List[Project]) -> None:
    """Show a simple list of all projects.

    Args:
        projects: List of projects to display
    """
    if not projects:
        print("No projects found.")
        return

    print(f"\nFound {len(projects)} project(s):\n")

    for project in projects:
        markers = []
        if project.is_git_repo:
            markers.append("git")
        if project.is_manual:
            markers.append("manual")

        marker_str = f" [{','.join(markers)}]" if markers else ""
        print(f"  {project.path}{marker_str}")

    print()
