"""Tests for Cursor CLI provider implementation.

Author: Solent Labs™
"""

import subprocess
from unittest.mock import patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.cursor import CursorProvider


@pytest.fixture
def provider():
    return CursorProvider()


class TestCursorMetadata:
    """Tests for Cursor CLI provider metadata."""

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("name", "cursor"),
            ("display_name", "Cursor CLI"),
            ("command", "agent"),
            ("requires_installation", True),
        ],
    )
    def test_metadata_attributes(self, provider, attr, expected):
        assert getattr(provider.metadata, attr) == expected

    def test_metadata_config_files(self, provider):
        assert "AGENTS.md" in provider.metadata.config_files
        assert ".cursorrules" in provider.metadata.config_files


class TestCursorIsInstalled:
    """Tests for Cursor CLI installation check."""

    @pytest.mark.parametrize(
        "which_return,expected",
        [
            ("/usr/bin/agent", True),
            (None, False),
        ],
        ids=["installed", "not_installed"],
    )
    def test_is_installed(self, provider, which_return, expected):
        with patch("shutil.which", return_value=which_return):
            assert provider.is_installed() is expected


class TestCursorLaunch:
    """Tests for Cursor CLI launch."""

    def test_launch_basic(self, provider, tmp_path):
        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(tmp_path)
            mock_run.assert_called_once_with(["agent"], check=True)

    @pytest.mark.parametrize(
        "exception,exit_code",
        [
            (FileNotFoundError, 1),
            (KeyboardInterrupt, 0),
            (subprocess.CalledProcessError(1, "agent"), 1),
        ],
        ids=["not_found", "keyboard_interrupt", "process_error"],
    )
    def test_launch_error_handling(self, provider, tmp_path, exception, exit_code):
        with patch("subprocess.run", side_effect=exception), patch("os.chdir"):
            with pytest.raises(SystemExit) as exc_info:
                provider.launch(tmp_path)
            assert exc_info.value.code == exit_code


class TestCursorCleanup:
    """Tests for Cursor CLI cleanup."""

    @pytest.mark.parametrize(
        "config",
        [
            None,
            CleanupConfig(enabled=False),
            CleanupConfig(enabled=True, clean_provider_files=False),
        ],
        ids=["no_config", "disabled", "provider_files_disabled"],
    )
    def test_cleanup_noop(self, provider, tmp_path, config):
        """Test that cleanup is a no-op under various disabled configs."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            provider.cleanup_environment(verbose=False, cleanup_config=config)

    def test_cleanup_removes_cache(self, provider, tmp_path, cleanup_config):
        with patch("pathlib.Path.home", return_value=tmp_path):
            cache_dir = tmp_path / ".cursor" / "cache"
            cache_dir.mkdir(parents=True)
            (cache_dir / "data.txt").write_text("cached")

            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)
            assert not cache_dir.exists()

    def test_cleanup_verbose(self, provider, tmp_path, cleanup_config, capsys):
        with patch("pathlib.Path.home", return_value=tmp_path):
            cache_dir = tmp_path / ".cursor" / "cache"
            cache_dir.mkdir(parents=True)
            (cache_dir / "data.txt").write_text("cached")

            provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)
            captured = capsys.readouterr()
            assert "Cleaned Cursor cache" in captured.out


class TestCursorCollectPreviewData:
    """Tests for Cursor CLI preview data collection."""

    def test_no_files(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.provider_name == "Cursor CLI"
        assert len(data.context_files) == 0

    def test_with_agents_md(self, provider, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Agents\nInstructions\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == "AGENTS.md"
        assert data.context_files[0].exists is True
        assert data.context_files[0].line_count == 2

    def test_with_cursorrules(self, provider, tmp_path):
        rules = tmp_path / ".cursorrules"
        rules.write_text("rule1\nrule2\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == ".cursorrules"

    def test_with_both_files(self, provider, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agents\n")
        (tmp_path / ".cursorrules").write_text("rules\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 2

    def test_global_config_paths(self, provider):
        paths = provider.get_global_context_paths()
        assert len(paths) == 1
        assert ".cursor" in str(paths[0])


class TestCursorDocumentationUrls:
    """Tests for Cursor CLI documentation URLs."""

    def test_has_documentation_urls(self, provider):
        assert len(provider.get_documentation_urls()) > 0

    @pytest.mark.parametrize(
        "key,url_fragment",
        [
            ("Documentation", "cursor.com"),
            ("Installation", "cursor.com"),
            ("Rules", "cursor.com"),
        ],
    )
    def test_documentation_url_entries(self, provider, key, url_fragment):
        urls = provider.get_documentation_urls()
        assert key in urls
        assert url_fragment in urls[key]
