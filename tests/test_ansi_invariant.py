"""Project invariant: all ANSI formatting goes through PreviewFormatter.

Raw escape codes in a provider or UI helper drift apart (one forgets the reset)
and cannot be changed in one place. Styling lives in ui/formatter.py; terminal
control sequences (clearing the screen, the window title) live in
utils/terminal.py. Nothing else may spell an escape code.

Author: Solent Labs™
"""

import re
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "ai_launcher"
ALLOWED = {SRC / "ui" / "formatter.py", SRC / "utils" / "terminal.py"}
ESCAPE = re.compile(r"\\033|\\x1b|\\u001b|\\e\[", re.IGNORECASE)
FILES = sorted(p for p in SRC.rglob("*.py") if p not in ALLOWED)


def test_the_scan_found_the_sources():
    assert len(FILES) > 30


@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_no_raw_escape_codes_outside_the_formatter_and_terminal_utils(path):
    hits = [
        f"{path.name}:{number}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ESCAPE.search(line)
    ]

    assert hits == []
