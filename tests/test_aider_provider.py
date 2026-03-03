"""Tests for Aider provider implementation.

Author: Solent Labs™
"""

import subprocess
from unittest.mock import patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.aider import AiderProvider


@pytest.fixture
def provider():
    return AiderProvider()


@pytest.fixture
def cleanup_config():
    return CleanupConfig(
        enabled=True,
        clean_provider_files=True,
        clean_system_cache=False,
        clean_npm_cache=False,
    )


class TestAiderMetadata:
    """Tests for Aider provider metadata."""

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("name", "aider"),
            ("display_name", "Aider"),
            ("command", "aider"),
            ("requires_installation", True),
        ],
    )
    def test_metadata_attributes(self, provider, attr, expected):
        assert getattr(provider.metadata, attr) == expected

    def test_metadata_config_files(self, provider):
        assert ".aider.conf.yml" in provider.metadata.config_files
        assert "AIDER.md" in provider.metadata.config_files


class TestAiderIsInstalled:
    """Tests for Aider installation check."""

    @pytest.mark.parametrize(
        "which_return,expected",
        [
            ("/usr/bin/aider", True),
            (None, False),
        ],
        ids=["installed", "not_installed"],
    )
    def test_is_installed(self, provider, which_return, expected):
        with patch("shutil.which", return_value=which_return):
            assert provider.is_installed() is expected


class TestAiderLaunch:
    """Tests for Aider launch."""

    def test_launch_basic(self, provider, tmp_path):
        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(tmp_path)
            mock_run.assert_called_once_with(["aider"], check=True)

    def test_launch_with_config_file(self, provider, tmp_path):
        config_file = tmp_path / ".aider.conf.yml"
        config_file.write_text("model: gpt-4")

        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(tmp_path)
            mock_run.assert_called_once_with(
                ["aider", "--config", str(config_file)], check=True
            )

    @pytest.mark.parametrize(
        "exception,exit_code",
        [
            (FileNotFoundError, 1),
            (KeyboardInterrupt, 0),
            (subprocess.CalledProcessError(1, "aider"), 1),
        ],
        ids=["not_found", "keyboard_interrupt", "process_error"],
    )
    def test_launch_error_handling(self, provider, tmp_path, exception, exit_code):
        with patch("subprocess.run", side_effect=exception), patch("os.chdir"):
            with pytest.raises(SystemExit) as exc_info:
                provider.launch(tmp_path)
            assert exc_info.value.code == exit_code


class TestAiderCleanup:
    """Tests for Aider cleanup."""

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
            aider_cache = tmp_path / ".aider" / "cache"
            aider_cache.mkdir(parents=True)
            (aider_cache / "data.txt").write_text("data")

            provider.cleanup_environment(verbose=False, cleanup_config=config)
            assert (aider_cache / "data.txt").exists()

    def test_cleanup_removes_cache(self, provider, tmp_path, cleanup_config):
        with patch("pathlib.Path.home", return_value=tmp_path):
            aider_cache = tmp_path / ".aider" / "cache"
            aider_cache.mkdir(parents=True)
            (aider_cache / "item.txt").write_text("cached")

            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)
            assert not aider_cache.exists()

    def test_cleanup_verbose(self, provider, tmp_path, cleanup_config, capsys):
        with patch("pathlib.Path.home", return_value=tmp_path):
            aider_cache = tmp_path / ".aider" / "cache"
            aider_cache.mkdir(parents=True)
            (aider_cache / "item.txt").write_text("cached")

            provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)
            captured = capsys.readouterr()
            assert "Cleaned Aider cache" in captured.out


class TestAiderCollectPreviewData:
    """Tests for Aider preview data collection."""

    def test_no_files(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.provider_name == "Aider"
        assert len(data.context_files) == 0

    def test_with_aider_config(self, provider, tmp_path):
        config_file = tmp_path / ".aider.conf.yml"
        config_file.write_text("model: gpt-4\napi_key: xxx\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == ".aider.conf.yml"
        assert data.context_files[0].exists is True
        assert data.context_files[0].line_count == 2

    def test_with_aider_md(self, provider, tmp_path):
        aider_md = tmp_path / "AIDER.md"
        aider_md.write_text("# Aider instructions\nLine 2\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == "AIDER.md"

    def test_with_both_files(self, provider, tmp_path):
        (tmp_path / ".aider.conf.yml").write_text("model: gpt-4\n")
        (tmp_path / "AIDER.md").write_text("# Instructions\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 2
        labels = {f.label for f in data.context_files}
        assert ".aider.conf.yml" in labels
        assert "AIDER.md" in labels

    def test_global_config_paths(self, provider):
        paths = provider.get_global_context_paths()
        assert len(paths) == 1
        assert ".aider" in str(paths[0])


class TestAiderDocumentationUrls:
    """Tests for Aider documentation URLs."""

    def test_has_documentation_urls(self, provider):
        assert len(provider.get_documentation_urls()) > 0

    @pytest.mark.parametrize(
        "key,url_fragment",
        [
            ("Documentation", "aider.chat"),
            ("Installation", "aider.chat"),
            ("Configuration", "aider.chat"),
        ],
    )
    def test_documentation_url_entries(self, provider, key, url_fragment):
        urls = provider.get_documentation_urls()
        assert key in urls
        assert url_fragment in urls[key]
