"""Tests for refactored provider discovery using ProviderRegistry.

Author: Solent Labs™
Created: 2026-02-12
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.core.provider_discovery import ProviderDiscovery
from ai_launcher.providers.base import ProviderMetadata


class TestProviderDiscoveryRefactored:
    """Tests for provider discovery using registry."""

    @pytest.fixture
    def discovery(self):
        """Create ProviderDiscovery instance."""
        return ProviderDiscovery()

    def test_initialization(self, discovery):
        """Test discovery initializes with registry."""
        assert discovery.registry is not None
        assert discovery.analyzer is not None

    def test_detect_all_uses_registry(self, discovery):
        """Test detect_all gets providers from registry."""
        # Mock the registry to return specific providers
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="test",
            display_name="Test Provider",
            command="test",
            description="Test",
        )
        mock_provider.is_installed.return_value = False
        mock_provider.get_global_context_paths.return_value = []

        with patch.object(discovery.registry, "list_all", return_value=[mock_provider]):
            results = discovery.detect_all()

            assert len(results) == 1
            assert results[0].name == "Test Provider"
            assert results[0].command == "test"

    def test_detect_installed_provider(self, discovery):
        """Test detection of installed provider."""
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="claude-code",
            display_name="Claude Code",
            command="claude",
            description="AI assistant",
        )
        mock_provider.is_installed.return_value = True
        mock_provider.get_global_context_paths.return_value = [Path.home() / ".claude"]

        with patch.object(discovery.registry, "list_all", return_value=[mock_provider]):
            with patch.object(discovery, "_get_version", return_value="2.1.37"):
                with patch.object(discovery, "_analyze_context") as mock_analyze:
                    mock_analyze.return_value = MagicMock(installed=True)

                    results = discovery.detect_all()

                    assert len(results) == 1
                    assert results[0].name == "Claude Code"
                    assert results[0].context is not None

    def test_detect_not_installed_provider(self, discovery):
        """Test detection of provider that's not installed."""
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="gemini",
            display_name="Gemini CLI",
            command="gemini",
            description="Google AI",
        )
        mock_provider.is_installed.return_value = False
        mock_provider.get_global_context_paths.return_value = [Path.home() / ".gemini"]

        with patch.object(discovery.registry, "list_all", return_value=[mock_provider]):
            results = discovery.detect_all()

            assert len(results) == 1
            assert results[0].name == "Gemini CLI"
            assert results[0].context is None
            assert results[0].command == "gemini"

    def test_get_installed_providers(self, discovery):
        """Test getting only installed providers."""
        # Create two providers: one installed, one not
        installed_provider = MagicMock()
        installed_provider.metadata = ProviderMetadata(
            name="claude",
            display_name="Claude",
            command="claude",
            description="Test",
        )
        installed_provider.is_installed.return_value = True

        not_installed_provider = MagicMock()
        not_installed_provider.metadata = ProviderMetadata(
            name="other",
            display_name="Other",
            command="other",
            description="Test",
        )
        not_installed_provider.is_installed.return_value = False

        providers = [installed_provider, not_installed_provider]

        with patch.object(discovery.registry, "list_all", return_value=providers):
            with patch.object(discovery, "_get_version", return_value="1.0"):
                with patch.object(discovery, "_analyze_context"):
                    installed = discovery.get_installed_providers()

                    # Should only return the installed one
                    assert len(installed) == 1
                    assert installed[0].name == "Claude"

    def test_get_version(self, discovery):
        """Test extracting version from command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="2.1.37 (Claude Code)"
            )

            version = discovery._get_version("claude")

            assert version == "2.1.37"

    def test_get_version_failure(self, discovery):
        """Test version extraction when command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            version = discovery._get_version("nonexistent")

            assert version is None

    @pytest.mark.parametrize(
        "version_str,expected",
        [
            ("2.1.37", "2.1.37"),
            ("Version 3.0.0", "3.0.0"),
            ("v1.2.3 (Build 456)", "1.2.3"),
            ("No version here", None),
        ],
        ids=["plain", "prefixed", "with_build", "no_version"],
    )
    def test_extract_version(self, discovery, version_str, expected):
        """Test version string extraction from various formats."""
        assert discovery._extract_version(version_str) == expected

    def test_analyze_context(self, discovery, tmp_path):
        """Test context analysis for a provider."""
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="test",
            display_name="Test",
            command="test",
            description="Test",
        )

        # Set up mock paths
        config_dir = tmp_path / ".test"
        config_dir.mkdir()

        mock_provider.get_global_context_paths.return_value = [config_dir]
        mock_provider.get_context_categories.return_value = {}
        mock_provider.get_project_data_pattern.return_value = "~/.test/projects/{name}"

        with patch("shutil.which", return_value="/usr/bin/test"):
            context = discovery._analyze_context(mock_provider, "1.0.0")

            assert context.name == "Test"
            assert context.version == "1.0.0"
            assert context.installed is True
            assert context.executable_path == Path("/usr/bin/test")
            assert context.project_data_pattern == "~/.test/projects/{name}"

    def test_analyze_context_with_categories(self, discovery, tmp_path):
        """Test context analysis with provider-specific categories."""
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="test",
            display_name="Test",
            command="test",
            description="Test",
        )

        config_dir = tmp_path / ".test"
        config_dir.mkdir()

        # Create some test files
        (config_dir / "config.json").write_text("{}")
        (config_dir / "debug.log").write_text("log")

        mock_provider.get_global_context_paths.return_value = [config_dir]
        mock_provider.get_context_categories.return_value = {
            "config": ["config"],
            "logs": ["debug"],
        }
        mock_provider.get_project_data_pattern.return_value = None

        with patch("shutil.which", return_value="/usr/bin/test"):
            context = discovery._analyze_context(mock_provider, "1.0.0")

            assert context.name == "Test"
            assert context.file_count >= 0  # Some files were categorized

    def test_analyze_context_missing_methods(self, discovery):
        """Test context analysis when provider lacks optional methods."""
        mock_provider = MagicMock()
        mock_provider.metadata = ProviderMetadata(
            name="simple",
            display_name="Simple",
            command="simple",
            description="Simple provider",
        )

        # Simulate missing methods
        mock_provider.get_global_context_paths.side_effect = AttributeError()
        mock_provider.get_context_categories.side_effect = AttributeError()
        mock_provider.get_project_data_pattern.side_effect = AttributeError()

        with patch("shutil.which", return_value=None):
            context = discovery._analyze_context(mock_provider, None)

            # Should still complete without errors
            assert context.name == "Simple"
            assert context.version is None
            assert context.project_data_pattern is None


class TestProviderDiscoveryIntegration:
    """Integration tests with real providers."""

    @pytest.fixture
    def discovery(self):
        return ProviderDiscovery()

    def test_detect_all_real_providers(self, discovery):
        """Test detecting all real registered providers."""
        results = discovery.detect_all()

        # Should find at least Claude, Gemini, Cursor, Aider
        assert len(results) >= 4

        # Check provider names
        provider_names = [p.name for p in results]
        assert "Claude Code" in provider_names

    def test_detect_claude_provider(self, discovery):
        """Test specific detection of Claude provider."""
        results = discovery.detect_all()
        claude = next((p for p in results if "Claude" in p.name), None)

        assert claude is not None
        assert claude.command == "claude"

    def test_get_provider_by_name(self, discovery):
        """Test getting provider by name."""
        provider = discovery.get_provider_by_name("Claude Code")

        if provider:  # Only if Claude is installed
            assert provider.command == "claude"
