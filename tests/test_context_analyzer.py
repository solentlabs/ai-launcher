"""Tests for context analyzer.

Author: Solent Labs™
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_launcher.core.context_analyzer import ContextAnalyzer


@pytest.fixture
def analyzer():
    return ContextAnalyzer()


class TestCategorizeDirectory:
    """Tests for categorize_directory()."""

    def test_nonexistent_path(self, analyzer, tmp_path):
        result = analyzer.categorize_directory(tmp_path / "nonexistent")
        # All categories should be empty
        for files in result.values():
            assert files == []

    def test_file_not_dir(self, analyzer, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        result = analyzer.categorize_directory(f)
        for files in result.values():
            assert files == []

    def test_empty_directory(self, analyzer, tmp_path):
        result = analyzer.categorize_directory(tmp_path)
        for files in result.values():
            assert files == []

    def test_categorizes_config_files(self, analyzer, tmp_path):
        (tmp_path / "settings.json").write_text("{}")
        (tmp_path / "config.toml").write_text("")
        result = analyzer.categorize_directory(tmp_path)
        config_names = {f.name for f in result["config"]}
        assert "settings.json" in config_names
        assert "config.toml" in config_names

    def test_categorizes_credentials(self, analyzer, tmp_path):
        (tmp_path / "oauth_token.txt").write_text("secret")
        result = analyzer.categorize_directory(tmp_path)
        assert len(result["credentials"]) == 1

    def test_categorizes_logs(self, analyzer, tmp_path):
        debug_dir = tmp_path / "debug"
        debug_dir.mkdir()
        (debug_dir / "output.txt").write_text("log")
        result = analyzer.categorize_directory(tmp_path)
        assert len(result["logs"]) == 1

    def test_categorizes_cache(self, analyzer, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "item.bin").write_text("data")
        result = analyzer.categorize_directory(tmp_path)
        assert len(result["cache"]) == 1

    def test_uncategorized_goes_to_other(self, analyzer, tmp_path, monkeypatch):
        # Remove "tmp" from cache patterns since pytest's tmp_path is under /tmp/
        monkeypatch.setitem(ContextAnalyzer.CATEGORIES, "cache", ["cache", "downloads"])
        subdir = tmp_path / "mydir"
        subdir.mkdir()
        (subdir / "random_stuff.xyz").write_text("stuff")
        result = analyzer.categorize_directory(subdir)
        assert len(result["other"]) == 1

    def test_permission_error_handled(self, analyzer, tmp_path):
        with patch.object(Path, "rglob", side_effect=OSError("Permission denied")):
            result = analyzer.categorize_directory(tmp_path)
        # Should return empty categories without raising
        for files in result.values():
            assert files == []

    def test_has_all_categories(self, analyzer, tmp_path):
        result = analyzer.categorize_directory(tmp_path)
        assert "config" in result
        assert "credentials" in result
        assert "logs" in result
        assert "cache" in result
        assert "history" in result
        assert "projects" in result
        assert "executables" in result
        assert "other" in result


class TestCalculateSizes:
    """Tests for calculate_sizes()."""

    def test_basic_sizes(self, analyzer, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world!")
        categories = {"config": [f1, f2], "other": []}
        sizes = analyzer.calculate_sizes(categories)
        assert sizes["config"] == f1.stat().st_size + f2.stat().st_size
        assert sizes["other"] == 0

    def test_nonexistent_file_skipped(self, analyzer, tmp_path):
        categories = {"config": [tmp_path / "missing.txt"]}
        sizes = analyzer.calculate_sizes(categories)
        assert sizes["config"] == 0

    def test_permission_error_handled(self, analyzer, tmp_path):
        f = tmp_path / "locked.txt"
        f.write_text("data")
        with patch.object(Path, "stat", side_effect=PermissionError("denied")):
            sizes = analyzer.calculate_sizes({"config": [f]})
        assert sizes["config"] == 0


class TestGetTotalStats:
    """Tests for get_total_stats()."""

    def test_total_stats(self, analyzer, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaa")
        f2.write_text("bbbbb")
        categories = {"config": [f1], "other": [f2]}
        total_files, total_bytes = analyzer.get_total_stats(categories)
        assert total_files == 2
        assert total_bytes == f1.stat().st_size + f2.stat().st_size

    def test_empty_categories(self, analyzer):
        total_files, total_bytes = analyzer.get_total_stats({"config": [], "other": []})
        assert total_files == 0
        assert total_bytes == 0


class TestAnalyzeSingleFile:
    """Tests for analyze_single_file()."""

    def test_nonexistent_file(self, analyzer, tmp_path):
        result = analyzer.analyze_single_file(tmp_path / "gone.txt")
        assert result["exists"] is False
        assert result["size"] == 0
        assert result["category"] == "unknown"

    def test_config_file(self, analyzer, tmp_path):
        f = tmp_path / "settings.json"
        f.write_text('{"key": "val"}')
        result = analyzer.analyze_single_file(f)
        assert result["exists"] is True
        assert result["size"] > 0
        assert result["category"] == "config"

    def test_credential_file(self, analyzer, tmp_path):
        f = tmp_path / "auth_token.txt"
        f.write_text("secret")
        result = analyzer.analyze_single_file(f)
        assert result["category"] == "credentials"

    def test_uncategorized_file(self, analyzer, tmp_path, monkeypatch):
        # Remove "tmp" from cache patterns since pytest's tmp_path is under /tmp/
        monkeypatch.setitem(ContextAnalyzer.CATEGORIES, "cache", ["cache", "downloads"])
        subdir = tmp_path / "mydir"
        subdir.mkdir()
        f = subdir / "readme.xyz"
        f.write_text("hello")
        result = analyzer.analyze_single_file(f)
        assert result["category"] == "other"

    def test_permission_error(self, analyzer, tmp_path):
        f = tmp_path / "locked.json"
        f.write_text("{}")
        original_stat = Path.stat
        original_exists = Path.exists

        def failing_stat(self_path, *args, **kwargs):
            if self_path == f:
                raise OSError("denied")
            return original_stat(self_path, *args, **kwargs)

        def forced_exists(self_path):
            if self_path == f:
                return True
            return original_exists(self_path)

        # Patch exists() to return True (bypassing its internal stat call)
        # while stat() itself raises OSError in the try block
        with patch.object(Path, "stat", failing_stat), patch.object(
            Path, "exists", forced_exists
        ):
            result = analyzer.analyze_single_file(f)
        assert result["exists"] is True
        assert result["size"] == 0
        assert result["category"] == "unknown"
