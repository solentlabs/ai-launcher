"""Integration tests for Phase 7: complete flow testing.

Tests the full integration of:
- ProviderRegistry
- Provider data collection
- PreviewFormatter
- Preview generation

Author: Solent Labs™
Created: 2026-02-12
"""

from ai_launcher.ui.preview import generate_provider_preview


class TestEndToEndIntegration:
    """Test complete preview generation flow."""

    def test_generate_preview_for_empty_project(self, tmp_path):
        """Test generating preview for project with no context files."""
        # Create an empty project directory
        project_path = tmp_path / "empty-project"
        project_path.mkdir()

        # Generate preview
        result = generate_provider_preview(project_path, "claude-code")

        # Should succeed and return a string
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention Claude Code
        assert "Claude Code" in result

    def test_generate_preview_with_context_file(self, tmp_path):
        """Test generating preview for project with CLAUDE.md."""
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Create CLAUDE.md
        claude_md = project_path / "CLAUDE.md"
        claude_md.write_text("# Test Project\n\nThis is a test project.\n")

        # Generate preview
        result = generate_provider_preview(project_path, "claude-code")

        # Should include the context file
        assert isinstance(result, str)
        assert "CLAUDE.md" in result
        # Should show file stats
        assert "lines" in result.lower() or "3 lines" in result

    def test_generate_preview_with_session_data(self, tmp_path, monkeypatch):
        """Test preview includes session data when available."""
        monkeypatch.setenv("HOME", str(tmp_path))

        project_path = tmp_path / "my-project"
        project_path.mkdir()

        # Create session directory
        from ai_launcher.providers.claude import _encode_project_path

        encoded = _encode_project_path(project_path)
        session_dir = tmp_path / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True)

        # Create session file
        session_file = session_dir / "session1.jsonl"
        session_file.write_text('{"event":"start"}\n')

        # Generate preview
        result = generate_provider_preview(project_path, "claude-code")

        # Should include session information
        assert isinstance(result, str)
        # Should mention sessions or history
        assert "session" in result.lower() or "history" in result.lower()

    def test_generate_preview_with_personal_context(self, tmp_path, monkeypatch):
        """Test preview includes personal CLAUDE.md."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create personal CLAUDE.md
        personal_claude = tmp_path / "CLAUDE.md"
        personal_claude.write_text("# Personal Preferences\n\nMy personal settings.\n")

        # Create project
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Generate preview
        result = generate_provider_preview(project_path, "claude-code")

        # Should include personal context
        assert isinstance(result, str)
        # The formatter should show context files
        assert "CLAUDE.md" in result

    def test_generate_preview_different_providers(self, tmp_path):
        """Test generating previews for different providers."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Test Claude
        claude_result = generate_provider_preview(project_path, "claude-code")
        assert "Claude Code" in claude_result

        # Test Gemini (even if not installed, should return something)
        gemini_result = generate_provider_preview(project_path, "gemini")
        assert isinstance(gemini_result, str)
        # May say provider not found, or show Gemini info
        assert len(gemini_result) > 0

    def test_generate_preview_invalid_provider(self, tmp_path):
        """Test handling of invalid provider name."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        result = generate_provider_preview(project_path, "nonexistent-provider")

        # Should return error message, not crash
        assert isinstance(result, str)
        assert "not found" in result.lower() or "error" in result.lower()

    def test_preview_formatting_has_structure(self, tmp_path):
        """Test that preview output has expected structure."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Create some context
        claude_md = project_path / "CLAUDE.md"
        claude_md.write_text("# Project Instructions\n\nTest content.\n")

        result = generate_provider_preview(project_path, "claude-code")

        # Should have structured sections
        # At minimum should have provider name
        assert "Claude Code" in result
        # Should be multi-line
        lines = result.split("\n")
        assert len(lines) > 1

    def test_preview_handles_large_context(self, tmp_path):
        """Test preview handles large context files gracefully."""
        project_path = tmp_path / "large-project"
        project_path.mkdir()

        # Create large CLAUDE.md (100 lines)
        claude_md = project_path / "CLAUDE.md"
        large_content = "\n".join([f"Line {i}" for i in range(1, 101)])
        claude_md.write_text(large_content)

        result = generate_provider_preview(project_path, "claude-code")

        # Should succeed
        assert isinstance(result, str)
        assert "CLAUDE.md" in result
        # Should mention 100 lines
        assert "100" in result


class TestPreviewHelperIntegration:
    """Test preview helper script integration."""

    def test_preview_helper_can_import_new_function(self):
        """Test that preview helper can import new function."""
        # This tests the import we added
        from ai_launcher.ui._preview_helper import generate_provider_preview as gpp

        assert gpp is not None
        assert callable(gpp)

    def test_preview_workflow_components_integrated(self):
        """Test all workflow components are available and connected."""
        from ai_launcher.providers.registry import ProviderRegistry
        from ai_launcher.ui.formatter import PreviewFormatter
        from ai_launcher.ui.preview import generate_provider_preview

        # All components should be importable
        assert ProviderRegistry is not None
        assert PreviewFormatter is not None
        assert generate_provider_preview is not None

        # Registry should have providers
        registry = ProviderRegistry()
        providers = registry.list_all()
        assert len(providers) > 0

        # Formatter should be instantiable
        formatter = PreviewFormatter()
        assert formatter is not None
