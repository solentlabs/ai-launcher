"""Global context file management UI for ai-launcher."""

import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import List, Optional

from ai_launcher.core.config import ConfigManager
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


def add_global_files(
    config_manager: ConfigManager, scan_paths: Optional[List[Path]] = None
) -> bool:
    """Simple interface to add global files.

    Args:
        config_manager: ConfigManager instance
        scan_paths: Optional scan paths to limit scope

    Returns:
        True if files were added, False otherwise
    """
    clear_screen()
    print("╭─────────────────────────────────────────╮")
    print("│      Add Global Files                   │")
    print("│          by Solent Labs™                │")
    print("╰─────────────────────────────────────────╯")
    print()
    print("Scanning for markdown files...")
    print()

    # Find markdown files
    md_files = _find_markdown_files(scan_paths)

    if not md_files:
        print("No markdown files found.")
        input("Press Enter to continue...")
        return False

    config = config_manager.load()
    current_global = set(config.context.global_files)

    # Build simple list of files (exclude already configured)
    items = []
    for md_file in md_files:
        try:
            display_path = f"~/{md_file.relative_to(Path.home())}"
        except ValueError:
            display_path = str(md_file)

        # Skip if already configured
        if display_path in current_global:
            continue

        items.append(f"{display_path}\t\t📄 {md_file.name}")

    if not items:
        print("All available files are already configured.")
        input("Press Enter to continue...")
        return False

    # Run fzf to select files to add
    try:
        helper_script = Path(__file__).parent / "_file_preview.py"
        preview_cmd = f"{sys.executable} {helper_script} {{1}}"

        process = subprocess.Popen(
            [
                "fzf",
                "--multi",
                "--prompt=Select files to add > ",
                "--height=100%",
                "--layout=reverse",
                "--border=rounded",
                "--border-label= Add Global Files ",
                "--delimiter=\\t\\t",
                "--with-nth=2..",
                "--preview-window=right:60%:wrap:border-left",
                f"--preview={preview_cmd}",
                "--header=Tab: Select • Enter: Add selected files",
                "--ansi",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        stdout_bytes, _ = process.communicate(input="\n".join(items).encode("utf-8"))
        stdout = stdout_bytes.decode("utf-8", errors="replace")

        if process.returncode != 0 or not stdout.strip():
            return False

        # Parse selected files
        selected_lines = stdout.strip().split("\n")
        selected_paths = [line.split("\t\t")[0] for line in selected_lines if line]

        if not selected_paths:
            return False

        # Add to config
        config.context.global_files = sorted(
            set(config.context.global_files) | set(selected_paths)
        )
        config_manager.save(config)
        return True

    except FileNotFoundError:
        print("Error: fzf not found.")
        input("Press Enter to continue...")
        return False


def remove_global_files(config_manager: ConfigManager) -> bool:
    """Simple interface to remove global files.

    Args:
        config_manager: ConfigManager instance

    Returns:
        True if files were removed, False otherwise
    """
    clear_screen()
    config = config_manager.load()

    if not config.context.global_files:
        print("No global files configured.")
        input("Press Enter to continue...")
        return False

    print("╭─────────────────────────────────────────╮")
    print("│      Remove Global Files                │")
    print("│          by Solent Labs™                │")
    print("╰─────────────────────────────────────────╯")
    print()

    # Build list of current files
    items = []
    for file_path in sorted(config.context.global_files):
        # Extract just filename for display
        path = Path(file_path.replace("~/", str(Path.home()) + "/"))
        items.append(f"{file_path}\t\t📄 {path.name}")

    # Run fzf to select files to remove
    try:
        helper_script = Path(__file__).parent / "_file_preview.py"
        preview_cmd = f"{sys.executable} {helper_script} {{1}}"

        process = subprocess.Popen(
            [
                "fzf",
                "--multi",
                "--prompt=Select files to remove > ",
                "--height=100%",
                "--layout=reverse",
                "--border=rounded",
                "--border-label= Remove Global Files ",
                "--delimiter=\\t\\t",
                "--with-nth=2..",
                "--preview-window=right:60%:wrap:border-left",
                f"--preview={preview_cmd}",
                "--header=Tab: Select • Enter: Remove selected files",
                "--ansi",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        stdout_bytes, _ = process.communicate(input="\n".join(items).encode("utf-8"))
        stdout = stdout_bytes.decode("utf-8", errors="replace")

        if process.returncode != 0 or not stdout.strip():
            return False

        # Parse selected files
        selected_lines = stdout.strip().split("\n")
        selected_paths = {line.split("\t\t")[0] for line in selected_lines if line}

        if not selected_paths:
            return False

        # Remove from config
        config.context.global_files = sorted(
            set(config.context.global_files) - selected_paths
        )
        config_manager.save(config)
        return True

    except FileNotFoundError:
        print("Error: fzf not found.")
        input("Press Enter to continue...")
        return False


def _find_markdown_files(scan_paths: Optional[List[Path]] = None) -> List[Path]:
    """Find markdown files in common locations.

    Args:
        scan_paths: Optional scan paths to limit scope

    Returns:
        List of markdown file paths
    """
    md_files = []
    home = Path.home()

    # Build search paths
    search_paths = [(home / ".claude", "~/.claude")]

    if scan_paths:
        for scan_path in scan_paths:
            search_paths.append((scan_path, str(scan_path)))
    else:
        search_paths.extend(
            [
                (home / "projects", "~/projects"),
                (home / ".config", "~/.config"),
            ]
        )

    for search_path, _ in search_paths:
        if not search_path.exists():
            continue

        try:
            for md_file in search_path.rglob("*.md"):
                # Skip hidden directories and common ignore patterns
                if any(
                    part.startswith(".") and part not in [".claude", ".config"]
                    for part in md_file.parts
                ):
                    continue
                if any(
                    ignore in str(md_file)
                    for ignore in ["node_modules", ".git", ".cache", "__pycache__"]
                ):
                    continue

                # Only include files up to reasonable depth
                try:
                    rel_path = md_file.relative_to(search_path)
                    if len(rel_path.parts) <= 5:
                        md_files.append(md_file)
                except ValueError:
                    continue
        except (OSError, PermissionError):
            continue

    return md_files
