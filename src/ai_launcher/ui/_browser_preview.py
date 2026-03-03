#!/usr/bin/env python3
"""Browser preview helper for fzf (cross-platform).

Called by browse_directory() as fzf --preview command.
Replaces bash preview script for Windows compatibility.

Usage: python _browser_preview.py <current_path> <selection>
"""

import sys
from pathlib import Path


def main() -> None:
    """Generate preview for directory browser selection."""
    if len(sys.argv) < 3:
        return

    current_path = Path(sys.argv[1])
    selection = sys.argv[2]

    if selection == ".":
        print(f"Select: {current_path}")
    elif selection == "..":
        print(f"Go to: {current_path.parent}")
    else:
        # Strip @ symlink indicator
        dir_name = selection.rstrip("@")
        target = current_path / dir_name

        if target.is_symlink():
            print(f"Symlink to: {target.resolve()}")
            print()

        if target.is_dir():
            try:
                items = sorted(target.iterdir())
                for item in items[:20]:
                    if item.is_dir():
                        print(f"  📁 {item.name}/")
                    else:
                        print(f"  📄 {item.name}")
                if len(items) > 20:
                    print(f"  ... and {len(items) - 20} more")
            except PermissionError:
                print("  (permission denied)")
        elif target.exists():
            print(f"  {target.name}")


if __name__ == "__main__":
    main()
