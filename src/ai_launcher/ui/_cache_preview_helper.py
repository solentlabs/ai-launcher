#!/usr/bin/env python3
"""Preview helper for the cache page's fzf list."""

import sys
from pathlib import Path

# Force UTF-8 output on Windows (default is system codepage e.g. cp1252)
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):  # pragma: no cover
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ai_launcher.ui.cache_page import render_group, render_peek


def main() -> None:
    """Show the peek for a path row, or the member list for a summary row."""
    if len(sys.argv) < 2:
        return
    key = sys.argv[1].split("\t\t", 1)[0]
    if key.startswith("E:"):
        print(render_peek(Path(key[2:])))
    elif key.startswith("S:"):
        print(render_group(key[2:]))


if __name__ == "__main__":
    main()
