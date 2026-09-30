"""Project selector UI for ai-launcher.

This module provides the interactive fuzzy-search project selector using fzf,
with preview pane, action menu, and support for rescanning, adding/removing
paths, and accessing settings.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added settings menu item)
"""

import os
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

# ConfigManager removed - using runtime config from CLI flags
from ai_launcher.core.models import Project, ProviderConfig, Selection
from ai_launcher.providers.registry import get_registry
from ai_launcher.ui.preview import build_tree_view
from ai_launcher.utils.paths import fzf_preview_cmd, is_relative_to

if TYPE_CHECKING:
    from ai_launcher.core.models import ConfigData

# Key that opens the Open With list for the highlighted project
OPEN_WITH_KEY = "ctrl-o"
DEFAULT_MARK = "   (default)"
SHELL_ROW = "Shell"

# The Open With list is a box of this width, drawn over the picker
DIALOG_WIDTH = 50
# Border (2), header and prompt lines around the rows
DIALOG_CHROME_LINES = 4


def clear_screen() -> None:
    """Clear the terminal screen using ANSI escape codes.

    Leaves the alternate screen first: the picker runs with --no-clear, so
    fzf stays on that screen when it exits.
    """
    print("\033[?1049l\033[H\033[2J", end="", flush=True)


def _grey_out_screen(size: os.terminal_size) -> None:
    """Give everything already on screen a grey foreground.

    DECCARA changes the attributes of a rectangle of cells that are already
    drawn. A terminal without it ignores the sequence.
    """
    print(f"\033[1;1;{size.lines};{size.columns};38;5;240$r", end="", flush=True)


def _dialog_geometry(
    rows: int, label_width: int, size: os.terminal_size
) -> Tuple[int, str]:
    """Work out fzf's --height and --margin for a box centred on the screen.

    The area is every line but the last, which keeps fzf in height mode. It
    draws only inside the margins, so the picker's frame shows around the box.

    Args:
        rows: Number of rows the list shows
        label_width: Width of the border label
        size: Terminal size

    Returns:
        The height, and the margin as "top,right,bottom,left"
    """
    height = size.lines - 1
    box_height = rows + DIALOG_CHROME_LINES
    box_width = max(DIALOG_WIDTH, label_width + 4)

    top = max(0, (height - box_height) // 2)
    bottom = max(0, height - box_height - top)
    left = max(0, (size.columns - box_width) // 2)
    right = max(0, size.columns - box_width - left)
    return height, f"{top},{right},{bottom},{left}"


def _parse_picker_output(output: bytes) -> Tuple[str, str]:
    """Split the picker's output into the key pressed and the selected row.

    fzf --expect prints the key on the first line, empty for Enter, and the
    selected row on the second.
    """
    # Split on newlines only: splitlines() also breaks on characters that a
    # path may contain. strip() takes the \r that Windows leaves behind.
    lines = output.decode("utf-8", errors="replace").split("\n")
    key = lines[0].strip()
    selected = lines[1].strip() if len(lines) > 1 else ""
    return key, selected


def select_open_with(project: Project, default_provider: str) -> Optional[Selection]:
    """Show the Open With list for a project.

    Rows are the installed providers, the default first, then a shell.

    Args:
        project: Project to open
        default_provider: Name of the provider Enter launches in the picker

    Returns:
        What to open the project with, or None to go back to the picker
    """
    providers = sorted(
        get_registry().list_installed(),
        key=lambda provider: provider.metadata.name != default_provider,
    )
    rows: Dict[str, Selection] = {}
    for provider in providers:
        if provider.metadata.name == default_provider:
            row = f"{provider.metadata.display_name}{DEFAULT_MARK}"
            rows[row] = Selection(project)
        else:
            row = provider.metadata.display_name
            rows[row] = Selection(project, provider=provider.metadata.name)
    rows[SHELL_ROW] = Selection(project, use_shell=True)

    # A dialog over the picker, whose last frame is still on screen. Height
    # mode starts at the cursor's row, so start from the top of the screen.
    label = f" Open {project.name} with "
    size = shutil.get_terminal_size()
    height, margin = _dialog_geometry(len(rows), len(label), size)
    _grey_out_screen(size)
    print("\033[H", end="", flush=True)
    process = subprocess.Popen(  # nosec B603, B607
        [
            "fzf",
            "--prompt=Open with: ",
            f"--height={height}",
            f"--margin={margin}",
            "--no-clear",  # Leave the picker's frame around the box
            "--layout=reverse",
            "--border=rounded",
            f"--border-label={label}",
            "--header=Enter to open • Esc to go back",
            "--header-first",
            "--info=hidden",
            "--no-separator",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    stdout_bytes, _ = process.communicate(input="\n".join(rows).encode("utf-8"))
    if process.returncode != 0:
        return None

    return rows.get(stdout_bytes.decode("utf-8", errors="replace").strip())


def select_project(
    projects: List[Project],
    show_git_status: bool = True,
    config: Optional["ConfigData"] = None,
    scan_paths: Optional[List[Path]] = None,
    manual_paths: Optional[List[str]] = None,
) -> Optional[Selection]:
    """Show interactive project selector with action support.

    Args:
        projects: List of projects to choose from (already sorted)
        show_git_status: Whether to show git status in preview
        config: Configuration data from CLI flags (optional)
        scan_paths: Original scan paths for rescan action (optional)
        manual_paths: Manual project paths from CLI flags (optional)

    Returns:
        The selected project and what to open it with, or None if cancelled
    """
    # Enter launches this provider; the Open With list marks it
    default_provider = (config.provider if config else ProviderConfig()).default

    # Action loop - allows rescanning, adding, removing
    current_projects = projects
    while True:
        if not current_projects:
            print("No projects found. Pass a scan directory or use --manual-paths")
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
        choices.append("__ACTION__\t\t🔧 Configuration")

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
Ctrl-O for other tools
─────────────────────────────────────────
"""

        # Build preview command using helper script
        helper_script = Path(__file__).parent / "_preview_helper.py"
        preview_cmd = fzf_preview_cmd(helper_script, "{}")

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
                "--delimiter=\\t\\t",  # Double-tab delimiter (fzf interprets \t)
                "--with-nth=2..",  # Show only the tree display (field 2 onwards)
                "--preview-window=right:70%:wrap:border-left:nohidden",  # Preview 70%, list 30%
                f"--preview={preview_cmd}",
                f"--header={header}",
                "--header-first",  # Display header before prompt
                "--info=hidden",  # Hide match counter
                "--ansi",  # Enable ANSI color codes
                f"--expect={OPEN_WITH_KEY}",  # Report Ctrl-O instead of Enter
                "--no-clear",  # Keep the frame for the Open With list to cover
                "--margin=1,0,0,0",  # fzf clears row 1 when that list starts
            ]

            # Pass choices via stdin as raw UTF-8 bytes to avoid
            # Windows codepage mangling (cp1252 vs UTF-8).
            input_data = "\n".join(choices)
            input_bytes = input_data.encode("utf-8")

            process = subprocess.Popen(  # nosec B603
                fzf_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                env=env,
            )

            stdout_bytes, _ = process.communicate(input=input_bytes)
            result_code = process.returncode

            # Check if user cancelled (exit code 130 = Ctrl+C, 1 = no match/cancelled)
            if result_code in (1, 130):
                clear_screen()
                return None

            if result_code != 0:
                clear_screen()
                print(f"Error running fzf: exit code {result_code}")
                return None

            # Get the key and selected line (decode from raw bytes)
            key, selected = _parse_picker_output(stdout_bytes)
            if not selected:
                clear_screen()
                return None

            # Handle action menu items
            if selected == "__ACTION__\t\t🔧 Configuration":
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
                selection: Optional[Selection] = Selection(project)
                if key == OPEN_WITH_KEY:
                    selection = select_open_with(project, default_provider)
                    if selection is None:
                        # Esc in the list - back to the picker
                        continue

                # Clear screen before launching
                clear_screen()
                return selection

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
            clear_screen()
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
