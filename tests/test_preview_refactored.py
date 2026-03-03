"""Tests for refactored preview generation.

Tests the new provider-based preview architecture where:
- Providers collect structured data
- Formatter handles presentation

Author: Solent Labs™
Created: 2026-02-12
"""

from unittest.mock import MagicMock, patch

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.ui.preview import generate_provider_preview


class TestGenerateProviderPreview:
    """Tests for generate_provider_preview() function."""

    def test_generate_provider_preview_success(self, tmp_path):
        """Test successful preview generation."""
        # Create a test CLAUDE.md file
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Test Project\nTest content")

        # Mock ProviderRegistry and provider
        mock_provider = MagicMock()
        mock_provider.collect_preview_data.return_value = ProviderPreviewData(
            provider_name="Claude Code",
            context_files=[
                ContextFile(
                    path=claude_md,
                    label="CLAUDE.md",
                    exists=True,
                    size_bytes=100,
                    line_count=2,
                )
            ],
        )

        # Patch where ProviderRegistry is imported
        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value.get.return_value = mock_provider

            result = generate_provider_preview(tmp_path)

            # Should contain formatted output
            assert isinstance(result, str)
            assert len(result) > 0
            # Should have called provider methods
            mock_provider.collect_preview_data.assert_called_once_with(tmp_path)

    def test_generate_provider_preview_provider_not_found(self, tmp_path):
        """Test preview generation when provider not found."""
        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value.get.return_value = None

            result = generate_provider_preview(tmp_path, "nonexistent")

            assert "Provider 'nonexistent' not found" in result

    def test_generate_provider_preview_data_collection_error(self, tmp_path):
        """Test preview generation when data collection fails."""
        mock_provider = MagicMock()
        mock_provider.collect_preview_data.side_effect = Exception(
            "Data collection failed"
        )

        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value.get.return_value = mock_provider

            result = generate_provider_preview(tmp_path)

            assert "Error collecting preview data" in result
            assert "Data collection failed" in result

    def test_generate_provider_preview_formatting_error(self, tmp_path):
        """Test preview generation when formatting fails."""
        # Mock provider to return valid data
        mock_provider = MagicMock()
        mock_provider.collect_preview_data.return_value = ProviderPreviewData(
            provider_name="Test"
        )

        # Mock formatter to raise error
        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            with patch("ai_launcher.ui.formatter.PreviewFormatter") as MockFormatter:
                MockRegistry.return_value.get.return_value = mock_provider
                MockFormatter.return_value.format_complete_preview.side_effect = (
                    Exception("Formatting failed")
                )

                result = generate_provider_preview(tmp_path)

                assert "Error formatting preview" in result
                assert "Formatting failed" in result

    def test_generate_provider_preview_default_provider(self, tmp_path):
        """Test preview generation uses default provider."""
        mock_provider = MagicMock()
        mock_provider.collect_preview_data.return_value = ProviderPreviewData(
            provider_name="Claude Code"
        )

        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value.get.return_value = mock_provider

            generate_provider_preview(tmp_path)

            # Should request claude-code by default
            MockRegistry.return_value.get.assert_called_once_with("claude-code")

    def test_generate_provider_preview_custom_provider(self, tmp_path):
        """Test preview generation with custom provider."""
        mock_provider = MagicMock()
        mock_provider.collect_preview_data.return_value = ProviderPreviewData(
            provider_name="Gemini"
        )

        with patch("ai_launcher.providers.registry.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value.get.return_value = mock_provider

            generate_provider_preview(tmp_path, provider_name="gemini")

            # Should request gemini provider
            MockRegistry.return_value.get.assert_called_once_with("gemini")


class TestIntegrationWithRealProviders:
    """Integration tests with real provider implementations."""

    def test_generate_preview_with_claude_provider(self, tmp_path):
        """Test generating preview with real Claude provider."""
        # Create test context
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Test Project\nTest instructions")

        result = generate_provider_preview(tmp_path, "claude-code")

        # Should generate a valid preview with project-specific content
        assert isinstance(result, str)
        assert len(result) > 0
        assert "CLAUDE.md" in result
        assert "Context Files" in result

    def test_generate_preview_no_context_files(self, tmp_path):
        """Test generating preview for project with no context files."""
        # Empty project directory
        result = generate_provider_preview(tmp_path, "claude-code")

        # Should still generate a preview (at minimum context files + footer)
        assert isinstance(result, str)
        assert "Context Files" in result

    def test_generate_preview_with_session_data(self, tmp_path, monkeypatch):
        """Test preview generation includes session data if available."""
        # Set up home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create project
        project_path = tmp_path / "my-project"
        project_path.mkdir()

        # Create Claude session directory with session data
        from ai_launcher.providers.claude import _encode_project_path

        encoded = _encode_project_path(project_path)
        session_dir = tmp_path / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True)

        # Create a session file
        session_file = session_dir / "session1.jsonl"
        session_file.write_text('{"event":"start"}\n')

        result = generate_provider_preview(project_path, "claude-code")

        # Should include session information
        assert "Session History" in result or "sessions" in result
