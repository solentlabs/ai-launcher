"""Tests for Gemini provider implementation.

Author: Solent Labs™
"""

import subprocess
from unittest.mock import patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.gemini import GeminiProvider


@pytest.fixture
def provider():
    return GeminiProvider()


@pytest.fixture
def cleanup_config():
    return CleanupConfig(
        enabled=True,
        clean_provider_files=True,
        clean_system_cache=False,
        clean_npm_cache=False,
    )


class TestGeminiMetadata:
    """Tests for Gemini provider metadata."""

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("name", "gemini"),
            ("display_name", "Gemini CLI"),
            ("command", "gemini"),
        ],
    )
    def test_metadata_attributes(self, provider, attr, expected):
        assert getattr(provider.metadata, attr) == expected

    def test_metadata_config_files(self, provider):
        assert "GEMINI.md" in provider.metadata.config_files
        assert ".geminirc" not in provider.metadata.config_files

    def test_metadata_description(self, provider):
        assert "Google" in provider.metadata.description


class TestGeminiIsInstalled:
    """Tests for Gemini installation check."""

    @pytest.mark.parametrize(
        "which_return,expected",
        [
            ("/usr/bin/gemini", True),
            (None, False),
        ],
        ids=["installed", "not_installed"],
    )
    def test_is_installed(self, provider, which_return, expected):
        with patch("shutil.which", return_value=which_return):
            assert provider.is_installed() is expected


class TestGeminiLaunch:
    """Tests for Gemini launch."""

    def test_launch_basic(self, provider, tmp_path):
        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(tmp_path)
            mock_run.assert_called_once_with(["gemini"], check=True)

    @pytest.mark.parametrize(
        "exception,exit_code",
        [
            (FileNotFoundError, 1),
            (KeyboardInterrupt, 0),
            (subprocess.CalledProcessError(1, "gemini"), 1),
        ],
        ids=["not_found", "keyboard_interrupt", "process_error"],
    )
    def test_launch_error_handling(self, provider, tmp_path, exception, exit_code):
        with patch("subprocess.run", side_effect=exception), patch("os.chdir"):
            with pytest.raises(SystemExit) as exc_info:
                provider.launch(tmp_path)
            assert exc_info.value.code == exit_code


class TestGeminiCleanup:
    """Tests for Gemini cleanup."""

    @pytest.mark.parametrize(
        "config",
        [
            None,
            CleanupConfig(enabled=False),
            CleanupConfig(enabled=True, clean_provider_files=False),
        ],
        ids=["no_config", "disabled", "provider_files_disabled"],
    )
    def test_cleanup_noop(self, provider, config):
        """Test that cleanup is a no-op under various disabled configs."""
        provider.cleanup_environment(verbose=False, cleanup_config=config)

    def test_cleanup_removes_cache(self, provider, tmp_path, cleanup_config):
        with patch("pathlib.Path.home", return_value=tmp_path):
            gemini_cache = tmp_path / ".gemini" / "cache"
            gemini_cache.mkdir(parents=True)
            (gemini_cache / "data.txt").write_text("cached")

            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)
            assert not gemini_cache.exists()

    def test_cleanup_verbose(self, provider, tmp_path, cleanup_config, capsys):
        with patch("pathlib.Path.home", return_value=tmp_path):
            gemini_cache = tmp_path / ".gemini" / "cache"
            gemini_cache.mkdir(parents=True)
            (gemini_cache / "data.txt").write_text("cached")

            provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)
            captured = capsys.readouterr()
            assert "Cleaned Gemini cache" in captured.out


class TestGeminiCollectPreviewData:
    """Tests for Gemini preview data collection."""

    def test_no_files(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.provider_name == "Gemini CLI"
        assert len(data.context_files) == 0

    def test_with_gemini_md(self, provider, tmp_path):
        gemini_md = tmp_path / "GEMINI.md"
        gemini_md.write_text("# Gemini Instructions\nLine 2\nLine 3\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == "GEMINI.md"
        assert data.context_files[0].exists is True
        assert data.context_files[0].line_count == 3

    def test_global_config_paths(self, provider):
        paths = provider.get_global_context_paths()
        assert len(paths) == 1
        assert any(".gemini" in str(p) for p in paths)


class TestGeminiDocumentationUrls:
    """Tests for Gemini documentation URLs."""

    def test_has_documentation_urls(self, provider):
        assert len(provider.get_documentation_urls()) > 0

    @pytest.mark.parametrize(
        "key",
        ["Getting started", "GEMINI.md guide", "Installation", "Configuration"],
    )
    def test_documentation_url_entries(self, provider, key):
        urls = provider.get_documentation_urls()
        assert key in urls
