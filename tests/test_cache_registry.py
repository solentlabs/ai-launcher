"""Tests for the cache registry: loading, platforms, validation, resolution."""

from pathlib import Path

import pytest

from ai_launcher.core import cache_registry as reg
from ai_launcher.core.cache_data import CLASS_REPORT, CLASS_UNREGISTERED


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load(cache_home, user_text=None, platform="linux"):
    user = (
        write(cache_home / "user.toml", user_text)
        if user_text is not None
        else cache_home / "missing.toml"
    )
    return reg.load_registry(platform=platform, user_file=user)


def by_id(registry):
    return {loc.id: loc for loc in registry.locations}


def test_defaults_load_clean(cache_home):
    registry = load(cache_home)

    assert registry.warnings == []
    ids = by_id(registry)
    assert {"pip", "npm-cache", "npm-npx", "playwright", "claude-home"} <= set(ids)
    assert ids["claude-home"].cls == CLASS_REPORT
    assert ids["pip"].clean == ["pip", "cache", "purge"]


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("linux", "/.cache/pip"),
        ("wsl", "/.cache/pip"),  # wsl falls back to the linux paths
        ("macos", "/Library/Caches/pip"),
        ("windows", "pip"),
    ],
)
def test_paths_follow_the_platform(cache_home, platform, expected):
    paths = by_id(load(cache_home, platform=platform))["pip"].paths

    assert len(paths) == 1
    assert expected in paths[0].replace("\\", "/")


def test_missing_env_var_drops_the_path(cache_home, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA")

    assert by_id(load(cache_home, platform="windows"))["pip"].paths == []


@pytest.mark.parametrize(
    ("pattern", "expected_tail"),
    [
        ("~/x", "x"),
        ("{cache}/pip", "pip"),
        ("$HOME/x", "x"),
        ("${HOME}/x", "x"),
        ("%USERPROFILE%/x", "x"),
    ],
)
def test_expand_path_tokens(cache_home, pattern, expected_tail):
    expanded = reg.expand_path(pattern, "linux")

    assert expanded is not None
    assert expanded.startswith(str(cache_home))
    assert expanded.endswith(expected_tail)


def test_user_entry_replaces_default_by_id(cache_home):
    text = '[[location]]\nid = "pip"\nname = "my pip"\nclass = "report"\n'
    pip = by_id(load(cache_home, text))["pip"]

    assert pip.name == "my pip"
    assert pip.cls == CLASS_REPORT
    assert pip.source == "user"


def test_user_cannot_raise_a_default_report_entry(cache_home):
    text = '[[location]]\nid = "claude-home"\nclass = "clean"\nremove = true\n'
    registry = load(cache_home, text)

    assert by_id(registry)["claude-home"].cls == CLASS_REPORT
    assert any("report-only by default" in w for w in registry.warnings)


@pytest.mark.parametrize(
    ("entry", "warning"),
    [
        ('name = "no id"\nclass = "clean"', "no id"),
        ('id = "x"\nclass = "bogus"', "bad class"),
        ('id = "x"\nclass = "clean"\nclean = "pip"', "clean must be a list"),
        ('id = "x"\nclass = "clean"\npaths.linux = ["~/a/*/b"]', "last path component"),
        ('id = "x"\nclass = "clean"\nfrobnicate = 1', "unknown keys"),
    ],
    ids=["no-id", "bad-class", "bad-clean", "mid-glob", "unknown-key"],
)
def test_bad_user_entries_warn_and_never_raise(cache_home, entry, warning):
    registry = load(cache_home, f"[[location]]\n{entry}\n")

    assert any(warning in w for w in registry.warnings)


def test_broken_user_file_warns(cache_home):
    registry = load(cache_home, "this is not [ toml")

    assert any("could not be read" in w for w in registry.warnings)
    assert "pip" in by_id(registry)  # defaults still load


def test_notice_thresholds_from_user_file(cache_home):
    text = (
        "[notice]\nstale_days = 3\nscratch_min_gb = 2\nbogus = 1\n"
        'min_free_gb = "ten"\n[scratch]\nin_use_minutes = 30\nother = 1\n'
    )
    registry = load(cache_home, text)

    assert registry.notice.stale_days == 3
    assert registry.notice.scratch_min_gb == 2
    assert registry.notice.min_free_gb == 10.0  # wrong type: default kept
    assert registry.notice.in_use_minutes == 30.0
    assert len(registry.warnings) == 3


@pytest.mark.parametrize(
    ("platform", "extra"), [("wsl", ["/mnt/c"]), ("linux", [])], ids=["wsl", "linux"]
)
def test_extra_disk_paths_default_only_on_wsl(cache_home, platform, extra):
    assert load(cache_home, platform=platform).notice.extra_disk_paths == extra


def test_resolve_entries_only_existing_paths_and_globs(cache_home):
    cache = cache_home / ".cache"
    (cache / "pip").mkdir()
    for name in ("agent-1", "agent-2", "other"):
        (cache / name).mkdir()
    (cache / "agent-file").write_text("x")
    text = (
        '[[location]]\nid = "agents"\nname = "Agents"\nclass = "review"\n'
        'remove = true\npaths.linux = ["{cache}/agent-*"]\n'
    )
    entries = reg.resolve_entries(load(cache_home, text))
    names = sorted(e.path.name for e in entries)

    assert names == ["agent-1", "agent-2", "pip"]  # files do not match; absent skipped
    # a wildcard match is named for the folder it matched
    assert {e.name for e in entries if e.location_id == "agents"} == {
        "agent-1",
        "agent-2",
    }


def test_scratch_pattern_matches_two_levels(cache_home):
    session = reg.scratch_root() / "proj" / "20261015-1"
    session.mkdir(parents=True)
    (reg.scratch_root() / "proj" / "stray.txt").write_text("x")

    entries = reg.resolve_entries(load(cache_home))

    scratch = [e for e in entries if e.location_id == "ai-launcher-scratch"]
    assert [e.path for e in scratch] == [session]
    assert scratch[0].name == "proj/20261015-1"  # project and session, both wildcards


def test_find_unregistered_skips_registered_and_containers(cache_home):
    cache = cache_home / ".cache"
    for name in ("pip", "mystery", "big-thing"):
        (cache / name).mkdir()
    (cache / "ai-launcher" / "scratch").mkdir(parents=True)
    registered = reg.resolve_entries(load(cache_home))

    found = reg.find_unregistered(registered)

    assert sorted(e.path.name for e in found) == ["big-thing", "mystery"]
    assert all(e.cls == CLASS_UNREGISTERED for e in found)


def test_find_unregistered_without_a_cache_dir(cache_home, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home / "nope"))

    assert reg.find_unregistered([]) == []


@pytest.mark.parametrize(
    ("platform", "expected"), [("linux", False), ("wsl", True)], ids=["linux", "wsl"]
)
def test_current_platform_detects_wsl(monkeypatch, tmp_path, platform, expected):
    version = tmp_path / "version"
    version.write_text(
        "Linux version 6 (microsoft-standard-WSL2)" if expected else "Linux"
    )
    real_read = Path.read_text

    def fake_read(self, *args, **kwargs):
        if self == Path("/proc/version"):
            return real_read(version, *args, **kwargs)
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(reg.sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", fake_read)

    assert reg.current_platform() == platform


@pytest.mark.parametrize(
    ("sys_platform", "expected"), [("win32", "windows"), ("darwin", "macos")]
)
def test_current_platform_other_systems(monkeypatch, sys_platform, expected):
    monkeypatch.setattr(reg.sys, "platform", sys_platform)

    assert reg.current_platform() == expected
