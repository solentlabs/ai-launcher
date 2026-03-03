"""Tests for GitHub Copilot CLI provider implementation.

Author: Solent Labs™
"""

import subprocess
from unittest.mock import patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.copilot import CopilotProvider


@pytest.fixture
def provider():
    return CopilotProvider()


@pytest.fixture
def cleanup_config():
    return CleanupConfig(
        enabled=True,
        clean_provider_files=True,
        clean_system_cache=False,
        clean_npm_cache=False,
    )


class TestCopilotMetadata:
    """Tests for Copilot provider metadata."""

    @pytest.mark.parametrize(
        "attr,expected",
        [
            ("name", "copilot"),
            ("display_name", "GitHub Copilot CLI"),
            ("command", "copilot"),
            ("requires_installation", True),
        ],
    )
    def test_metadata_attributes(self, provider, attr, expected):
        assert getattr(provider.metadata, attr) == expected

    def test_metadata_config_files(self, provider):
        assert ".github/copilot-instructions.md" in provider.metadata.config_files
        assert "AGENTS.md" in provider.metadata.config_files

    def test_metadata_description(self, provider):
        assert "GitHub" in provider.metadata.description


class TestCopilotIsInstalled:
    """Tests for Copilot installation check."""

    @pytest.mark.parametrize(
        "which_return,expected",
        [
            ("/usr/bin/copilot", True),
            (None, False),
        ],
        ids=["installed", "not_installed"],
    )
    def test_is_installed(self, provider, which_return, expected):
        with patch("shutil.which", return_value=which_return):
            assert provider.is_installed() is expected


class TestCopilotLaunch:
    """Tests for Copilot launch."""

    def test_launch_basic(self, provider, tmp_path):
        with patch("subprocess.run") as mock_run, patch("os.chdir"):
            provider.launch(tmp_path)
            mock_run.assert_called_once_with(["copilot"], check=True)

    @pytest.mark.parametrize(
        "exception,exit_code",
        [
            (FileNotFoundError, 1),
            (KeyboardInterrupt, 0),
            (subprocess.CalledProcessError(1, "copilot"), 1),
        ],
        ids=["not_found", "keyboard_interrupt", "process_error"],
    )
    def test_launch_error_handling(self, provider, tmp_path, exception, exit_code):
        with patch("subprocess.run", side_effect=exception), patch("os.chdir"):
            with pytest.raises(SystemExit) as exc_info:
                provider.launch(tmp_path)
            assert exc_info.value.code == exit_code


class TestCopilotCleanup:
    """Tests for Copilot cleanup."""

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
            copilot_cache = tmp_path / ".config" / "github-copilot" / "cache"
            copilot_cache.mkdir(parents=True)
            (copilot_cache / "data.txt").write_text("data")

            provider.cleanup_environment(verbose=False, cleanup_config=config)
            assert (copilot_cache / "data.txt").exists()

    def test_cleanup_removes_cache(self, provider, tmp_path, cleanup_config):
        with patch("pathlib.Path.home", return_value=tmp_path):
            copilot_cache = tmp_path / ".config" / "github-copilot" / "cache"
            copilot_cache.mkdir(parents=True)
            (copilot_cache / "item.txt").write_text("cached")

            provider.cleanup_environment(verbose=False, cleanup_config=cleanup_config)
            assert not copilot_cache.exists()

    def test_cleanup_verbose(self, provider, tmp_path, cleanup_config, capsys):
        with patch("pathlib.Path.home", return_value=tmp_path):
            copilot_cache = tmp_path / ".config" / "github-copilot" / "cache"
            copilot_cache.mkdir(parents=True)
            (copilot_cache / "item.txt").write_text("cached")

            provider.cleanup_environment(verbose=True, cleanup_config=cleanup_config)
            captured = capsys.readouterr()
            assert "Cleaned Copilot cache" in captured.out


class TestCopilotCollectPreviewData:
    """Tests for Copilot preview data collection."""

    def test_no_files(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.provider_name == "GitHub Copilot CLI"
        assert len(data.context_files) == 0

    def test_with_copilot_instructions(self, provider, tmp_path):
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        instructions = github_dir / "copilot-instructions.md"
        instructions.write_text("# Copilot Instructions\nLine 2\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == ".github/copilot-instructions.md"
        assert data.context_files[0].exists is True
        assert data.context_files[0].line_count == 2

    def test_with_agents_md(self, provider, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Agents\nInstructions\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 1
        assert data.context_files[0].label == "AGENTS.md"

    def test_with_both_files(self, provider, tmp_path):
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("# Instructions\n")
        (tmp_path / "AGENTS.md").write_text("# Agents\n")

        data = provider.collect_preview_data(tmp_path)
        assert len(data.context_files) == 2
        labels = {f.label for f in data.context_files}
        assert ".github/copilot-instructions.md" in labels
        assert "AGENTS.md" in labels

    def test_global_config_paths(self, provider):
        paths = provider.get_global_context_paths()
        assert len(paths) == 1
        assert "github-copilot" in str(paths[0])


class TestCopilotDocumentationUrls:
    """Tests for Copilot documentation URLs."""

    def test_has_documentation_urls(self, provider):
        assert len(provider.get_documentation_urls()) > 0

    @pytest.mark.parametrize(
        "key,url_fragment",
        [
            ("Documentation", "github.com"),
            ("Installation", "github.com"),
            ("Custom instructions", "github.com"),
        ],
    )
    def test_documentation_url_entries(self, provider, key, url_fragment):
        urls = provider.get_documentation_urls()
        assert key in urls
        assert url_fragment in urls[key]
