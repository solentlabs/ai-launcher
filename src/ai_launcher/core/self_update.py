"""Working out whether AI Launcher can update, and how.

Nothing here runs by itself: ``ai-launcher update`` is the only caller, so the
launcher never contacts PyPI unless asked. The package name and index URL are
fixed; nothing in PyPI's reply is ever executed.

Author: Solent Labs™
"""

import json
import re
import shutil
import site
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

PACKAGE = "ai-launcher"
PYPI_URL = "https://pypi.org/pypi/ai-launcher/json"
TIMEOUT_SECONDS = 10

_VERSION = re.compile(r"^\d+(\.\d+){0,3}$")

# How AI Launcher was installed
PIPX = "pipx"
PIP = "pip"
EDITABLE = "editable"
SOURCE = "source"


class UpdateError(Exception):
    """PyPI could not be reached or its reply could not be understood."""


@dataclass
class UpdatePlan:
    """How to update, and whether AI Launcher may run the command itself.

    Attributes:
        method: pipx, pip, editable or source
        argv: The upgrade command; None when there is nothing to run
        manual: True when the command is shown but left to the user
        note: Why, for the cases that run nothing
    """

    method: str
    argv: Optional[List[str]] = None
    manual: bool = False
    note: str = ""
    display: List[str] = field(default_factory=list)


def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    """Parse a plain release version like 0.7.0; anything else is None."""
    text = text.strip()
    if not _VERSION.match(text):
        return None
    return tuple(int(part) for part in text.split("."))


def is_newer(latest: str, installed: str) -> bool:
    """Is `latest` a higher release than `installed`. Unparseable means no."""
    a, b = parse_version(latest), parse_version(installed.split("+")[0])
    if a is None or b is None:
        return False
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def fetch_latest(
    opener: Callable[..., Any] = urllib.request.urlopen,
    url: str = PYPI_URL,
) -> str:
    """Ask PyPI for the latest release. The only network call in this feature."""
    try:
        with opener(url, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
        version = str(data["info"]["version"])
    except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError) as error:
        raise UpdateError(f"could not read the latest version from PyPI: {error}")
    if parse_version(version) is None:
        raise UpdateError(f"PyPI returned a version I do not recognise: {version!r}")
    return version


def _direct_url() -> Optional[dict]:
    """The install record pip leaves for source and editable installs, if any."""
    try:
        from importlib.metadata import distribution

        raw = distribution(PACKAGE).read_text("direct_url.json")
    except Exception:  # not installed as a distribution, or unreadable
        return None
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def detect_plan(
    direct_url: Optional[dict] = None,
    prefix: Optional[str] = None,
    base_prefix: Optional[str] = None,
    package_file: Optional[str] = None,
    platform: Optional[str] = None,
    argv0: Optional[str] = None,
    which: Callable[[str], Optional[str]] = shutil.which,
    executable: Optional[str] = None,
) -> UpdatePlan:
    """Work out how AI Launcher was installed and what upgrades it.

    Every input can be given, so each case is testable on any platform.
    """
    direct_url = _direct_url() if direct_url is None else direct_url
    prefix = prefix if prefix is not None else sys.prefix
    base_prefix = base_prefix if base_prefix is not None else sys.base_prefix
    platform = platform or sys.platform
    argv0 = argv0 if argv0 is not None else (sys.argv[0] if sys.argv else "")
    executable = executable or sys.executable
    if package_file is None:
        import ai_launcher

        package_file = ai_launcher.__file__

    if direct_url:
        if (direct_url.get("dir_info") or {}).get("editable"):
            return UpdatePlan(
                EDITABLE,
                note="This is an editable (development) install. "
                "Update it with git pull in the project folder.",
            )
        return UpdatePlan(
            SOURCE,
            note="This was installed from a folder or repository, not PyPI. "
            "Pull the new source and reinstall it.",
        )

    parts = {p.lower() for p in Path(prefix).parts}
    if "pipx" in parts and "venvs" in parts:
        argv = ["pipx", "upgrade", PACKAGE]
        if not which("pipx"):
            return UpdatePlan(
                PIPX, display=argv, manual=True, note="pipx is not on PATH."
            )
        return UpdatePlan(PIPX, argv=argv, display=argv)

    argv = [executable, "-m", "pip", "install", "--upgrade", PACKAGE]
    in_venv = prefix != base_prefix
    if not in_venv and _under_user_site(package_file):
        argv.insert(4, "--user")
    # Shown with the interpreter that is running the launcher: right on every
    # machine, including ones with no `py` launcher
    display = list(argv)

    # Windows will not replace an .exe that is running, and the launcher's own
    # entry point is one: show the command, do not run it from here
    if platform == "win32" and argv0.lower().endswith(".exe"):
        return UpdatePlan(
            PIP,
            argv=argv,
            display=display,
            manual=True,
            note="Windows cannot replace ai-launcher.exe while it is running. "
            "Run this from a normal prompt instead.",
        )
    return UpdatePlan(PIP, argv=argv, display=display)


def _under_user_site(package_file: str) -> bool:
    """Is the package inside the user's own site-packages (a --user install)."""
    try:
        user_site = site.getusersitepackages()
    except Exception:  # no user site on this interpreter
        return False
    return str(Path(package_file)).startswith(str(Path(user_site)))
