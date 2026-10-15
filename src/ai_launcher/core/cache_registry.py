"""Registry of known cache and scratch locations.

The registry is data: ``data/caches.toml`` ships the defaults and an optional
``caches.toml`` in the user's config folder adds to or replaces them. This
module loads both, picks the paths for the current platform and resolves them
to concrete entries. It never touches the contents of a location.

Author: Solent Labs™
"""

import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import platformdirs

from ai_launcher.core.cache_data import (
    CLASS_REPORT,
    CLASS_UNREGISTERED,
    CLASSES,
    CacheEntry,
    CacheLocation,
    NoticeConfig,
    Registry,
)
from ai_launcher.utils.logging import get_logger

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.8 to 3.10 only
    import tomli as tomllib

logger = get_logger(__name__)

PLATFORMS = ("linux", "macos", "windows", "wsl")
LOCATION_KEYS = {"id", "name", "group", "class", "clean", "remove", "note", "paths"}
NOTICE_KEYS = {f for f in NoticeConfig.__dataclass_fields__ if f != "in_use_minutes"}
TOKEN_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)|%(\w+)%")


def current_platform() -> str:
    """Name the platform: linux, macos, windows or wsl."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    try:
        version = Path("/proc/version").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "linux"
    return "wsl" if "microsoft" in version.lower() else "linux"


def user_registry_path() -> Path:
    """Where the user's optional caches.toml lives."""
    return Path(platformdirs.user_config_path("ai-launcher")) / "caches.toml"


def cache_dir(platform: Optional[str] = None) -> Path:
    """The folder the {cache} token stands for."""
    platform = platform or current_platform()
    if platform in ("linux", "wsl"):
        xdg = os.environ.get("XDG_CACHE_HOME")
        return Path(xdg) if xdg else Path.home() / ".cache"
    if platform == "macos":
        return Path(platformdirs.user_cache_path())  # ~/Library/Caches itself
    # Windows has no one folder for caches; LOCALAPPDATA is where the {cache}
    # token points, but it is app data, not a cache folder to list
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) if local else Path.home() / "AppData" / "Local"


def scratch_root() -> Path:
    """The launcher's own scratch folder, which the {scratch} token stands for."""
    return Path(platformdirs.user_cache_path("ai-launcher")) / "scratch"


def expand_path(pattern: str, platform: Optional[str] = None) -> Optional[str]:
    """Expand ~, {cache}, {scratch} and environment variables in a pattern.

    Returns:
        The expanded pattern, or None if it names an environment variable
        that is not set (the path does not exist on this machine)
    """
    platform = platform or current_platform()
    text = pattern.replace("{cache}", str(cache_dir(platform)))
    text = text.replace("{scratch}", str(scratch_root()))
    if text == "~" or text.startswith(("~/", "~\\")):
        text = str(Path.home()) + text[1:]

    missing = []

    def replace(match: "re.Match[str]") -> str:
        name = next(g for g in match.groups() if g)
        value = os.environ.get(name)
        if value is None:
            missing.append(name)
            return ""
        return value

    text = TOKEN_RE.sub(replace, text)
    return None if missing else text


def _paths_for(raw: Dict[str, Any], platform: str) -> List[str]:
    """Pick this platform's path patterns; wsl falls back to linux."""
    paths = raw.get(platform)
    if paths is None and platform == "wsl":
        paths = raw.get("linux")
    return [p for p in (paths or []) if isinstance(p, str)]


def _validate_pattern(pattern: str) -> Optional[str]:
    """Check where a raw pattern may use a wildcard; return the problem, if any.

    Wildcards are allowed in the last path component only. The launcher's own
    {scratch}/*/* (project, then session) is the one pattern that may use two.
    """
    parts = re.split(r"[\\/]", pattern)
    wild = [i for i, part in enumerate(parts) if any(c in part for c in "*?[")]
    if not wild:
        return None
    last = len(parts) - 1
    allowed = {last - 1, last} if parts[0] == "{scratch}" else {last}
    if set(wild) <= allowed and last in wild:
        return None
    return "wildcards are allowed in the last path component only"


def _parse_location(
    raw: Dict[str, Any], platform: str, source: str, warnings: List[str]
) -> Optional[CacheLocation]:
    """Turn one [[location]] table into a CacheLocation, or warn and skip it."""
    ident = raw.get("id")
    if not isinstance(ident, str) or not ident:
        warnings.append(f"{source} registry: an entry has no id; skipped")
        return None
    unknown = sorted(set(raw) - LOCATION_KEYS)
    if unknown:
        warnings.append(f"{source} registry: {ident}: unknown keys {unknown} ignored")
    cls = raw.get("class", CLASS_REPORT)
    if cls not in CLASSES:
        warnings.append(f"{source} registry: {ident}: bad class {cls!r}; skipped")
        return None
    clean = raw.get("clean")
    if clean is not None and not (
        isinstance(clean, list) and clean and all(isinstance(a, str) for a in clean)
    ):
        warnings.append(f"{source} registry: {ident}: clean must be a list; skipped")
        return None

    paths = []
    raw_paths = raw.get("paths", {})
    for pattern in _paths_for(
        raw_paths if isinstance(raw_paths, dict) else {}, platform
    ):
        problem = _validate_pattern(pattern)
        if problem:
            warnings.append(f"{source} registry: {ident}: {pattern}: {problem}")
            continue
        expanded = expand_path(pattern, platform)
        if expanded:
            paths.append(expanded)
    return CacheLocation(
        id=ident,
        name=str(raw.get("name", ident)),
        cls=cls,
        group=str(raw.get("group", "")),
        clean=list(clean) if clean else None,
        remove=bool(raw.get("remove", False)),
        note=str(raw.get("note", "")),
        paths=paths,
        source=source,
    )


def _read_toml(path: Path, warnings: List[str], label: str) -> Dict[str, Any]:
    """Read a TOML file; a missing file is empty, a broken one warns."""
    try:
        with open(path, "rb") as handle:
            data: Dict[str, Any] = tomllib.load(handle)
            return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        warnings.append(f"{label} registry could not be read: {error}")
        return {}


def _type_ok(current: Any, value: Any) -> bool:
    """Does a user's value have the type of the default it replaces."""
    if isinstance(current, bool):
        return isinstance(value, bool)
    if isinstance(current, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(current, list) and isinstance(value, list)


def _notice_config(
    notice: Dict[str, Any], scratch: Dict[str, Any], platform: str, warnings: List[str]
) -> NoticeConfig:
    """Build the thresholds from the user's [notice] and [scratch] tables."""
    config = NoticeConfig()
    if platform == "wsl":
        config.extra_disk_paths = ["/mnt/c"]
    for key, value in notice.items():
        if key not in NOTICE_KEYS:
            warnings.append(f"user registry: [notice] unknown key {key!r} ignored")
        elif not _type_ok(getattr(config, key), value):
            warnings.append(f"user registry: [notice] {key} has the wrong type")
        else:
            setattr(config, key, value)
    for key, value in scratch.items():
        if key == "in_use_minutes" and _type_ok(config.in_use_minutes, value):
            config.in_use_minutes = float(value)
        else:
            warnings.append(f"user registry: [scratch] {key!r} ignored")
    return config


def load_registry(
    platform: Optional[str] = None,
    user_file: Optional[Path] = None,
    defaults_file: Optional[Path] = None,
) -> Registry:
    """Load the default registry and the user's, merged by id.

    Nothing here raises: a broken entry or file becomes a warning.
    """
    platform = platform or current_platform()
    defaults_file = (
        defaults_file or Path(__file__).parent.parent / "data" / "caches.toml"
    )
    user_file = user_file if user_file is not None else user_registry_path()
    warnings: List[str] = []

    by_id: Dict[str, CacheLocation] = {}
    default_data = _read_toml(defaults_file, warnings, "default")
    for raw in default_data.get("location", []):
        location = _parse_location(raw, platform, "default", warnings)
        if location:
            by_id[location.id] = location

    user_data = _read_toml(user_file, warnings, "user")
    for raw in user_data.get("location", []):
        location = _parse_location(raw, platform, "user", warnings)
        if not location:
            continue
        existing = by_id.get(location.id)
        # A default report entry can be lowered but never raised
        if existing and existing.cls == CLASS_REPORT and location.cls != CLASS_REPORT:
            warnings.append(
                f"user registry: {location.id} is report-only by default; kept"
            )
            continue
        by_id[location.id] = location

    notice_table = user_data.get("notice", {})
    scratch_table = user_data.get("scratch", {})
    config = _notice_config(
        notice_table if isinstance(notice_table, dict) else {},
        scratch_table if isinstance(scratch_table, dict) else {},
        platform,
        warnings,
    )
    return Registry(
        locations=list(by_id.values()),
        notice=config,
        warnings=warnings,
        user_file=user_file,
    )


def _expand_glob(pattern: str) -> List[Path]:
    """Match a pattern whose wildcards are in its last components."""
    path = Path(pattern)
    parts = path.parts
    first_wild = next(
        (i for i, part in enumerate(parts) if any(c in part for c in "*?[")), None
    )
    if first_wild is None:
        return [path] if os.path.lexists(path) else []
    matches = [Path(*parts[:first_wild])]
    for part in parts[first_wild:]:
        found: List[Path] = []
        for base in matches:
            try:
                with os.scandir(base) as scan:
                    names = sorted(
                        e.name for e in scan if e.is_dir(follow_symlinks=False)
                    )
            except OSError:
                continue
            found.extend(base / n for n in names if fnmatch.fnmatchcase(n, part))
        matches = found
    return matches


def _entry_name(location: CacheLocation, pattern: str, path: Path) -> str:
    """A row's name: the registry name, or for a wildcard match the folder it matched.

    A match shows its own folder name (and the project folder above it for
    {scratch}/*/*), so rows in a list are told apart at a glance.
    """
    wild = len([p for p in re.split(r"[\\/]", pattern) if any(c in p for c in "*?[")])
    if not wild:
        return location.name
    return "/".join(path.parts[-wild:])


def resolve_entries(registry: Registry) -> List[CacheEntry]:
    """Turn the registry's patterns into the paths that exist right now."""
    entries: List[CacheEntry] = []
    seen = set()
    for location in registry.locations:
        for pattern in location.paths:
            for path in _expand_glob(pattern):
                if str(path) in seen:
                    continue
                seen.add(str(path))
                entries.append(
                    CacheEntry(
                        location_id=location.id,
                        name=_entry_name(location, pattern, path),
                        path=path,
                        cls=location.cls,
                        clean=location.clean,
                        remove=location.remove,
                        note=location.note,
                        group=location.group,
                    )
                )
    return entries


def find_unregistered(
    registered: List[CacheEntry], platform: Optional[str] = None
) -> List[CacheEntry]:
    """List the cache folder's children that no registry entry names.

    Linux, WSL and macOS have a cache folder. Windows does not, so nothing is
    listed there.

    A child that is, or holds, a registered path is not unregistered. They are
    report-only: shown so the space is visible, never deleted.
    """
    platform = platform or current_platform()
    if platform == "windows":
        return []  # no cache folder to take stock of; AppData holds app data
    base = cache_dir(platform)
    known = [str(e.path) for e in registered]
    scratch = str(scratch_root())
    found: List[CacheEntry] = []
    try:
        with os.scandir(base) as scan:
            children = sorted(e.path for e in scan if e.is_dir(follow_symlinks=False))
    except OSError:
        return found
    for child in children:
        prefix = child + os.sep
        if child in known or any(k.startswith(prefix) for k in known):
            continue
        if scratch.startswith(prefix):
            continue
        found.append(
            CacheEntry(
                location_id="",
                name=Path(child).name,
                path=Path(child),
                cls=CLASS_UNREGISTERED,
                note="Not in the registry",
            )
        )
    return found
