"""Tests for base provider default implementations.

Author: Solent Labs™
"""

from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from ai_launcher.core.models import CleanupConfig
from ai_launcher.providers.base import AIProvider, ProviderMetadata


class ConcreteProvider(AIProvider):
    """Minimal concrete provider for testing base class defaults."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="test-provider",
            display_name="Test Provider",
            command="testcmd",
            description="A test provider",
            config_files=["TEST.md", ".testrc"],
        )

    def is_installed(self) -> bool:
        return True

    def launch(self, project_path: Path) -> None:
        pass

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        pass


@pytest.fixture
def provider():
    return ConcreteProvider()


class TestCollectPreviewData:
    """Tests for default collect_preview_data()."""

    def test_no_config_files_exist(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.provider_name == "Test Provider"
        assert len(data.context_files) == 2
        assert all(not f.exists for f in data.context_files)

    def test_config_file_exists(self, provider, tmp_path):
        test_md = tmp_path / "TEST.md"
        test_md.write_text("# Test\nLine 2\nLine 3\n")

        data = provider.collect_preview_data(tmp_path)
        found = [f for f in data.context_files if f.exists]
        assert len(found) == 1
        assert found[0].label == "TEST.md"
        assert found[0].line_count == 3
        assert found[0].file_type == "project"
        assert found[0].content_preview is not None

    def test_both_config_files_exist(self, provider, tmp_path):
        (tmp_path / "TEST.md").write_text("test\n")
        (tmp_path / ".testrc").write_text("rc\n")

        data = provider.collect_preview_data(tmp_path)
        existing = [f for f in data.context_files if f.exists]
        assert len(existing) == 2

    def test_unreadable_file(self, provider, tmp_path):
        test_md = tmp_path / "TEST.md"
        test_md.write_text("content")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            data = provider.collect_preview_data(tmp_path)
            # Should mark as not existing due to read error
            test_files = [f for f in data.context_files if f.label == "TEST.md"]
            assert len(test_files) == 1
            assert test_files[0].exists is False

    def test_includes_global_config_paths(self, provider, tmp_path):
        data = provider.collect_preview_data(tmp_path)
        assert data.global_config_paths == []


class TestLaunchWithTitle:
    """Tests for launch_with_title()."""

    def test_sets_title_and_launches(self, provider, tmp_path):
        with patch("ai_launcher.providers.base.set_terminal_title") as mock_set:
            with patch(
                "ai_launcher.providers.base.format_terminal_title",
                return_value="my-proj → Test Provider",
            ):
                provider.launch_with_title(tmp_path)
                mock_set.assert_called_once_with("my-proj → Test Provider")

    def test_no_title_when_disabled(self, provider, tmp_path):
        with patch("ai_launcher.providers.base.set_terminal_title") as mock_set:
            provider.launch_with_title(tmp_path, set_title=False)
            mock_set.assert_not_called()

    def test_custom_title_format(self, provider, tmp_path):
        with patch("ai_launcher.providers.base.set_terminal_title"):
            with patch("ai_launcher.providers.base.format_terminal_title") as mock_fmt:
                mock_fmt.return_value = "custom"
                provider.launch_with_title(
                    tmp_path, title_format="{project} | {provider}"
                )
                mock_fmt.assert_called_once_with(
                    "{project} | {provider}", tmp_path, "Test Provider"
                )


class TestDefaultMethods:
    """Tests for other default method implementations."""

    def test_get_context_sources_found(self, provider, tmp_path):
        (tmp_path / "TEST.md").write_text("content")
        sources = provider.get_context_sources(tmp_path)
        assert len(sources) == 1
        assert sources[0].name == "TEST.md"

    def test_get_context_sources_none(self, provider, tmp_path):
        sources = provider.get_context_sources(tmp_path)
        assert sources == []

    def test_get_global_context_paths(self, provider):
        assert provider.get_global_context_paths() == []

    def test_get_project_data_pattern(self, provider):
        assert provider.get_project_data_pattern() is None

    def test_get_context_categories(self, provider):
        assert provider.get_context_categories() == {}

    def test_get_documentation_urls(self, provider):
        assert provider.get_documentation_urls() == {}
