"""Directory browser for ai-launcher."""

import subprocess  # nosec B404
from pathlib import Path
from typing import Optional


def browse_directory(start_path: Optional[Path] = None) -> Optional[Path]:
    """Interactive directory browser for selecting a path.

    Args:
        start_path: Starting directory (default: ~/projects or ~)

    Returns:
        Selected directory Path or None if cancelled
    """
    # Start at ~/projects if it exists, otherwise ~
    if start_path is None:
        projects_dir = Path.home() / "projects"
        start_path = projects_dir if projects_dir.exists() else Path.home()

    current_path = start_path.resolve()

    while True:
        # Get directory contents
        try:
            items = []

            # Add special navigation options
            items.append(".")
            items.append("..")

            # Add subdirectories
            dirs = []
            for item in sorted(current_path.iterdir()):
                if item.is_dir():
                    # Show symlink indicator
                    if item.is_symlink():
                        dirs.append(item.name + "@")
                    else:
                        dirs.append(item.name)

            items.extend(dirs)

        except PermissionError:
            print(f"Permission denied: {current_path}")
            return None

        # Build header
        header = f"""╭─────────────────────────────────────────╮
│         Directory Browser               │
│          by Solent Labs™                │
╰─────────────────────────────────────────╯

Current: {current_path}
Select '.' to add current directory

. = Select this directory
.. = Go up one level
@ suffix = symlink"""

        # Build preview command
        preview_cmd = f"""
if [[ {{}} == '.' ]]; then
    echo 'Select: {current_path}'
elif [[ {{}} == '..' ]]; then
    echo 'Go to: {current_path.parent}'
else
    target='{current_path}/{{}}'
    target=${{target%@}}
    if [[ -L "$target" ]]; then
        echo "Symlink to: $(readlink -f "$target")"
        echo ''
    fi
    ls -la "$target" 2>/dev/null | head -20
fi
"""

        # Run fzf
        try:
            process = subprocess.Popen(  # nosec B603, B607
                [
                    "fzf",
                    "--height=80%",
                    "--layout=reverse",
                    "--border=rounded",
                    f"--header={header}",
                    "--header-first",
                    "--prompt=> ",
                    f"--preview={preview_cmd}",
                    "--preview-window=right:60%:wrap",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )

            stdout, _ = process.communicate(input="\n".join(items))

            if process.returncode != 0:
                return None

            selected = stdout.strip()
            if not selected:
                return None

        except FileNotFoundError:
            print("Error: fzf not found")
            return None

        # Handle selection
        if selected == ".":
            # Select current directory
            return current_path
        if selected == "..":
            # Navigate up
            current_path = current_path.parent
        else:
            # Navigate into subdirectory (strip @ if symlink)
            dir_name = selected.rstrip("@")
            current_path = current_path / dir_name
