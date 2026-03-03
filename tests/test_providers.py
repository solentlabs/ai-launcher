"""Tests for provider abstraction layer.

Author: Solent Labs™
Created: 2026-02-09
"""

import pytest

from ai_launcher.providers.base import AIProvider, ProviderMetadata
from ai_launcher.providers.claude import ClaudeProvider
from ai_launcher.providers.gemini import GeminiProvider
from ai_launcher.providers.registry import ProviderRegistry, get_provider, get_registry


class TestProviderMetadata:
    """Tests for ProviderMetadata dataclass."""

    def test_provider_metadata_creation(self):
        """Test creating ProviderMetadata."""
        metadata = ProviderMetadata(
            name="test-provider",
            display_name="Test Provider",
            command="test",
            description="A test provider",
            config_files=["TEST.md"],
            requires_installation=True,
        )

        assert metadata.name == "test-provider"
        assert metadata.display_name == "Test Provider"
        assert metadata.command == "test"
        assert metadata.description == "A test provider"
        assert metadata.config_files == ["TEST.md"]
        assert metadata.requires_installation is True


class TestClaudeProvider:
    """Tests for ClaudeProvider."""

    def test_metadata(self):
        """Test ClaudeProvider metadata."""
        provider = ClaudeProvider()
        metadata = provider.metadata

        assert metadata.name == "claude-code"
        assert metadata.display_name == "Claude Code"
        assert metadata.command == "claude"
        assert "CLAUDE.md" in metadata.config_files

    def test_get_context_sources(self, tmp_path):
        """Test getting context sources."""
        provider = ClaudeProvider()

        # Create test files
        (tmp_path / "CLAUDE.md").write_text("# Test")
        (tmp_path / ".clauderc").write_text("")

        sources = provider.get_context_sources(tmp_path)

        assert len(sources) == 2
        assert tmp_path / "CLAUDE.md" in sources
        assert tmp_path / ".clauderc" in sources


class TestGeminiProvider:
    """Tests for GeminiProvider."""

    def test_metadata(self):
        """Test GeminiProvider metadata."""
        provider = GeminiProvider()
        metadata = provider.metadata

        assert metadata.name == "gemini"
        assert metadata.display_name == "Gemini CLI"
        assert metadata.command == "gemini"
        assert "GEMINI.md" in metadata.config_files

    def test_get_context_sources(self, tmp_path):
        """Test getting context sources."""
        provider = GeminiProvider()

        # Create test files
        (tmp_path / "GEMINI.md").write_text("# Test")

        sources = provider.get_context_sources(tmp_path)

        assert len(sources) == 1
        assert tmp_path / "GEMINI.md" in sources


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_registry_initialization(self):
        """Test registry initializes with built-in providers."""
        registry = ProviderRegistry()

        assert len(registry.list_all()) >= 2
        assert registry.get("claude-code") is not None
        assert registry.get("gemini") is not None

    def test_get_provider(self):
        """Test getting a provider by name."""
        registry = ProviderRegistry()

        claude = registry.get("claude-code")
        assert claude is not None
        assert isinstance(claude, ClaudeProvider)

        gemini = registry.get("gemini")
        assert gemini is not None
        assert isinstance(gemini, GeminiProvider)

    def test_get_nonexistent_provider(self):
        """Test getting a provider that doesn't exist."""
        registry = ProviderRegistry()

        provider = registry.get("nonexistent")
        assert provider is None

    def test_get_names(self):
        """Test getting all provider names."""
        registry = ProviderRegistry()

        names = registry.get_names()
        assert "claude-code" in names
        assert "gemini" in names


class TestGetProvider:
    """Tests for get_provider helper function."""

    def test_get_provider_unknown(self):
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")

    def test_get_registry_singleton(self):
        """Test registry is a singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_get_provider_not_installed(self):
        """Test getting a provider that exists but is not installed."""
        from unittest.mock import patch

        with patch.object(ClaudeProvider, "is_installed", return_value=False):
            with pytest.raises(ValueError, match="not installed"):
                get_provider("claude-code")


class TestProviderRegistryExtended:
    """Extended tests for ProviderRegistry."""

    def test_list_installed(self):
        """Test list_installed returns only installed providers."""

        registry = ProviderRegistry()
        installed = registry.list_installed()

        # All returned providers should report is_installed() = True
        for provider in installed:
            assert provider.is_installed() is True

    def test_list_installed_with_no_installed(self):
        """Test list_installed when nothing is installed."""

        registry = ProviderRegistry()
        # Patch all providers to be not installed
        for provider in registry.list_all():
            provider.is_installed = lambda: False

        result = registry.list_installed()
        assert result == []

        # Restore
        for provider in registry.list_all():
            del provider.is_installed

    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        from ai_launcher.providers.base import ProviderMetadata

        class CustomProvider(AIProvider):
            @property
            def metadata(self):
                return ProviderMetadata(
                    name="custom-test",
                    display_name="Custom",
                    command="custom",
                    description="Custom test provider",
                )

            def is_installed(self):
                return True

            def launch(self, project_path):
                pass

            def cleanup_environment(self, verbose=False, cleanup_config=None):
                pass

        registry = ProviderRegistry()
        custom = CustomProvider()
        registry.register(custom)
        assert registry.get("custom-test") is custom
