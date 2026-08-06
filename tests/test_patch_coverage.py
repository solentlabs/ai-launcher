"""Tests for the local patch-coverage reporter.

Reproduces the v0.4.2 situation it exists to catch: a one-character edit to a
line inside an untested ``except`` branch, which the project-wide coverage floor
happily ignored and Codecov failed the PR for.

Author: Solent Labs™
Created: 2026-08-06
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

_spec = importlib.util.spec_from_file_location(
    "patch_coverage", SCRIPTS / "patch_coverage.py"
)
patch_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(patch_coverage)


DIFF = """diff --git a/src/ai_launcher/ui/_preview_helper.py b/src/ai_launcher/ui/_preview_helper.py
index 1d6fc12..d6d4501 100644
--- a/src/ai_launcher/ui/_preview_helper.py
+++ b/src/ai_launcher/ui/_preview_helper.py
@@ -376 +376 @@ def main() -> None:
+                        print(f"\\n! Error loading provider context: {e}")
diff --git a/src/ai_launcher/ui/formatter.py b/src/ai_launcher/ui/formatter.py
index aaa..bbb 100644
--- a/src/ai_launcher/ui/formatter.py
+++ b/src/ai_launcher/ui/formatter.py
@@ -616,2 +616,3 @@ class PreviewFormatter:
+        lines = [f"header"]
+        more = 1
+        extra = 2
"""


class TestChangedLines:
    """Parsing the diff into touched line numbers."""

    def _parsed(self):
        completed = type("R", (), {"stdout": DIFF})()
        with patch.object(patch_coverage.subprocess, "run", return_value=completed):
            return patch_coverage.changed_lines("origin/main")

    def test_single_line_hunk(self):
        result = self._parsed()
        assert result["src/ai_launcher/ui/_preview_helper.py"] == {376}

    def test_multi_line_hunk_expands_to_a_range(self):
        result = self._parsed()
        assert result["src/ai_launcher/ui/formatter.py"] == {616, 617, 618}

    def test_only_touched_files_appear(self):
        assert set(self._parsed()) == {
            "src/ai_launcher/ui/_preview_helper.py",
            "src/ai_launcher/ui/formatter.py",
        }

    def test_empty_diff_yields_nothing(self):
        completed = type("R", (), {"stdout": ""})()
        with patch.object(patch_coverage.subprocess, "run", return_value=completed):
            assert patch_coverage.changed_lines("origin/main") == {}


class TestUncoveredInPatch:
    """Intersecting touched lines with lines no test reached."""

    def _coverage_file(self, tmp_path, files):
        path = tmp_path / "coverage.json"
        path.write_text(json.dumps({"files": files}), encoding="utf-8")
        return path

    def test_flags_an_edited_line_that_no_test_reaches(self, tmp_path):
        """The exact v0.4.2 case: an emoji swap inside an untested except branch."""
        cov = self._coverage_file(
            tmp_path,
            {"src/ai_launcher/ui/_preview_helper.py": {"missing_lines": [376, 400]}},
        )
        result = patch_coverage.uncovered_in_patch(
            cov, {"src/ai_launcher/ui/_preview_helper.py": {376}}
        )
        assert result == {"src/ai_launcher/ui/_preview_helper.py": [376]}

    def test_silent_when_touched_lines_are_covered(self, tmp_path):
        cov = self._coverage_file(
            tmp_path, {"src/ai_launcher/ui/formatter.py": {"missing_lines": [999]}}
        )
        assert (
            patch_coverage.uncovered_in_patch(
                cov, {"src/ai_launcher/ui/formatter.py": {616}}
            )
            == {}
        )

    def test_unmeasured_files_are_skipped(self, tmp_path):
        """Test files and anything outside --cov scope are not reported."""
        cov = self._coverage_file(tmp_path, {})
        assert (
            patch_coverage.uncovered_in_patch(cov, {"tests/test_thing.py": {10}}) == {}
        )

    def test_absolute_coverage_keys_still_match_relative_paths(self, tmp_path):
        """coverage.py may emit absolute paths; matching must survive that."""
        cov = self._coverage_file(
            tmp_path,
            {"/build/src/ai_launcher/ui/formatter.py": {"missing_lines": [616]}},
        )
        assert patch_coverage.uncovered_in_patch(
            cov, {"src/ai_launcher/ui/formatter.py": {616}}
        ) == {"src/ai_launcher/ui/formatter.py": [616]}


class TestMainExitCodes:
    """Exit behaviour, including the warn-only mode ci-local.sh uses."""

    def test_missing_coverage_json_warns_but_passes_in_warn_only(self, tmp_path):
        code = patch_coverage.main(
            ["--coverage-json", str(tmp_path / "nope.json"), "--warn-only"]
        )
        assert code == 0

    def test_missing_coverage_json_fails_when_enforcing(self, tmp_path):
        code = patch_coverage.main(["--coverage-json", str(tmp_path / "nope.json")])
        assert code == 1

    @pytest.mark.parametrize("warn_only,expected", [(True, 0), (False, 1)])
    def test_uncovered_lines_respect_warn_only(self, tmp_path, warn_only, expected):
        cov = tmp_path / "coverage.json"
        cov.write_text(
            json.dumps(
                {"files": {"src/ai_launcher/ui/formatter.py": {"missing_lines": [616]}}}
            ),
            encoding="utf-8",
        )
        args = ["--coverage-json", str(cov)]
        if warn_only:
            args.append("--warn-only")

        with patch.object(
            patch_coverage,
            "changed_lines",
            return_value={"src/ai_launcher/ui/formatter.py": {616}},
        ):
            assert patch_coverage.main(args) == expected
