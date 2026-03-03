#!/usr/bin/env python3
"""File preview helper for fzf (cross-platform).

Called by shared_context.py as fzf --preview command.
Replaces bash cat/sed commands for Windows compatibility.

Usage: python _file_preview.py <path>
  Path may start with ~ which will be expanded.
"""

import sys
from pathlib import Path


def main() -> None:
    """Read and display a file for fzf preview."""
    if len(sys.argv) < 2:
        return

    path = Path(sys.argv[1]).expanduser()

    if path.is_file():
        try:
            print(path.read_text(errors="replace"))
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        print("File not found")


if __name__ == "__main__":
    main()
