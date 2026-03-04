"""Tests for path utilities.

- expand_path
- validate_directory
- get_relative_path
- quote_for_fzf
- fzf_preview_cmd
"""

from pathlib import Path

import pytest

from ai_launcher.utils.paths import (
    expand_path,
    fzf_preview_cmd,
    get_relative_path,
    quote_for_fzf,
    validate_directory,
)

P = Path  # shorthand for table readability


# -- expand_path --------------------------------------------------------------

# fmt: off
EXPAND_TILDE_CASES = [
    # input_str          expected_suffix
    ("~/projects",       ("projects",)),
    ("~/a/b/c",          ("a", "b", "c")),
]
# fmt: on


@pytest.mark.parametrize("input_str, expected_suffix", EXPAND_TILDE_CASES)
def test_expand_path_tilde(input_str, expected_suffix):
    assert expand_path(input_str) == Path.home().joinpath(*expected_suffix)


def test_expand_path_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_PATH", str(tmp_path))
    assert expand_path("$TEST_PATH/subdir") == (tmp_path / "subdir").resolve()


def test_expand_path_tilde_and_env_var(monkeypatch):
    monkeypatch.setenv("TEST_SUBDIR", "projects")
    assert expand_path("~/$TEST_SUBDIR/foo") == Path.home() / "projects" / "foo"


def test_expand_path_absolute(tmp_path):
    assert expand_path(str(tmp_path)) == tmp_path.resolve()


# -- validate_directory --------------------------------------------------------

# fmt: off
VALIDATE_DIR_CASES = [
    # setup      expected
    ("dir",      True),
    ("missing",  False),
    ("file",     False),
]
# fmt: on


@pytest.mark.parametrize("setup, expected", VALIDATE_DIR_CASES)
def test_validate_directory(tmp_path, setup, expected):
    if setup == "dir":
        path = tmp_path / "test_dir"
        path.mkdir()
    elif setup == "file":
        path = tmp_path / "test_file.txt"
        path.write_text("test")
    else:
        path = tmp_path / "nonexistent"

    assert validate_directory(path) is expected


# -- get_relative_path ---------------------------------------------------------


def test_get_relative_path_under_base(tmp_path):
    sub_path = tmp_path / "projects" / "foo"
    sub_path.mkdir(parents=True)
    assert get_relative_path(sub_path, tmp_path) == Path("projects/foo")


def test_get_relative_path_not_relative(tmp_path):
    other = tmp_path / "other" / "path"
    assert get_relative_path(other, tmp_path / "base") == other


def test_get_relative_path_same(tmp_path):
    assert get_relative_path(tmp_path, tmp_path) == Path()


# -- quote_for_fzf -------------------------------------------------------------

# fmt: off
QUOTE_CASES = [
    # id                  input_path                              expected
    ("string",            "/usr/bin/python3",                     '"/usr/bin/python3"'),
    ("string-spaces",     r"C:\Program Files\Python\python.exe",  r'"C:\Program Files\Python\python.exe"'),
    ("path-obj",          P("/usr/bin/python3"),                   f'"{P("/usr/bin/python3")}"'),
    ("path-obj-spaces",   P("/opt/my app/bin/tool"),               f'"{P("/opt/my app/bin/tool")}"'),
    ("empty",             "",                                      '""'),
]
# fmt: on


@pytest.mark.parametrize(
    "input_path, expected",
    [(path, exp) for _, path, exp in QUOTE_CASES],
    ids=[id for id, _, _ in QUOTE_CASES],
)
def test_quote_for_fzf(input_path, expected):
    assert quote_for_fzf(input_path) == expected


# -- fzf_preview_cmd ----------------------------------------------------------

PY = "/usr/bin/python3"
WIN_PY = r"C:\Program Files\Python\python.exe"


# Helper: build expected string using platform Path rendering for script args
def _expect(exe, script_str, *tail):
    return " ".join([f'"{exe}"', f'"{P(script_str)}"', *tail])


# fmt: off
PREVIEW_CMD_CASES = [
    # id                  executable  script                   extra_args                     expected
    ("basic",             PY,         P("/some/helper.py"),    ("{}",),                       _expect(PY, "/some/helper.py", "{}")),
    ("spaces-win",        WIN_PY,     P("/my scripts/h.py"),   ("{}",),                       _expect(WIN_PY, "/my scripts/h.py", "{}")),
    ("extra-quoted-arg",  PY,         P("/helper.py"),         ('"/path with spaces"', "{}"), _expect(PY, "/helper.py", '"/path with spaces"', "{}")),
    ("field-placeholder", PY,         P("/helper.py"),         ("{1}",),                      _expect(PY, "/helper.py", "{1}")),
]
# fmt: on


@pytest.mark.parametrize(
    "executable, script, extra_args, expected",
    [(exe, s, args, exp) for _, exe, s, args, exp in PREVIEW_CMD_CASES],
    ids=[id for id, *_ in PREVIEW_CMD_CASES],
)
def test_fzf_preview_cmd(monkeypatch, executable, script, extra_args, expected):
    monkeypatch.setattr("ai_launcher.utils.paths.sys.executable", executable)
    assert fzf_preview_cmd(script, *extra_args) == expected
