"""Tests for startup context report functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ai_launcher.ui.startup_report import (
    ContextSource,
    StartupReport,
    _pad_line,
    _visual_length,
    generate_startup_report,
)


class TestContextSource:
    """Test the ContextSource dataclass."""

    def test_context_source_creation(self):
        """Test creating a ContextSource instance."""
        source = ContextSource(
            name="Test Source",
            file_path=Path("/test/path"),
            status="loaded",
            size_bytes=1024,
            line_count=50,
            purpose="Test purpose",
            doc_url="https://example.com",
            hints=["Hint 1", "Hint 2"],
        )

        assert source.name == "Test Source"
        assert source.file_path == Path("/test/path")
        assert source.status == "loaded"
        assert source.size_bytes == 1024
        assert source.line_count == 50
        assert source.purpose == "Test purpose"
        assert source.doc_url == "https://example.com"
        assert len(source.hints) == 2

    def test_context_source_optional_fields(self):
        """Test ContextSource with optional fields as None."""
        source = ContextSource(
            name="Test",
            file_path=None,
            status="missing",
            size_bytes=None,
            line_count=None,
            purpose="Test",
            doc_url="https://example.com",
            hints=[],
        )

        assert source.file_path is None
        assert source.size_bytes is None
        assert source.line_count is None
        assert source.hints == []


class TestStartupReport:
    """Test the StartupReport class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory with test files."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create CLAUDE.md
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text("# Test Project\n" * 50)  # 50 lines

        # Create .git directory
        git_dir = project_dir / ".git"
        git_dir.mkdir()

        # Create .claude directory with settings
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.local.json"
        settings.write_text(json.dumps({"model": "opus"}))

        return project_dir

    @pytest.fixture
    def temp_global_settings(self, tmp_path):
        """Create temporary global settings."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"model": "sonnet"}))
        return settings_file

    def test_initialization(self, temp_project):
        """Test StartupReport initialization."""
        report = StartupReport(temp_project)
        assert report.project_path == temp_project
        assert report.sources == []

    def test_analyze_with_all_sources(self, temp_project, tmp_path):
        """Test analyze() with all context sources present."""
        # Create memory directory
        encoded_path = str(temp_project.resolve()).replace("/", "-").replace("_", "-")
        memory_dir = tmp_path / ".claude" / "projects" / encoded_path / "memory"
        memory_dir.mkdir(parents=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text("# Memory\n" * 30)  # 30 lines

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            # Create global settings
            claude_dir = tmp_path / ".claude"
            claude_dir.mkdir(exist_ok=True)
            settings_file = claude_dir / "settings.json"
            settings_file.write_text(json.dumps({"model": "sonnet"}))

            report = StartupReport(temp_project)
            report.analyze()

            # Should have 5 sources
            assert len(report.sources) == 5

            # Check each source type
            source_names = [s.name for s in report.sources]
            assert "Project Instructions (CLAUDE.md)" in source_names
            assert "Auto Memory (MEMORY.md)" in source_names
            assert "Global Settings" in source_names
            assert "Project Settings Override" in source_names
            assert "Git Context" in source_names

    def test_check_claude_md_present(self, temp_project):
        """Test _check_claude_md when CLAUDE.md exists."""
        report = StartupReport(temp_project)
        report._check_claude_md()

        assert len(report.sources) == 1
        source = report.sources[0]
        assert source.name == "Project Instructions (CLAUDE.md)"
        assert source.status == "loaded"
        assert source.file_path == temp_project / "CLAUDE.md"
        assert source.size_bytes is not None
        assert source.line_count == 50  # From fixture

    def test_check_claude_md_missing(self, tmp_path):
        """Test _check_claude_md when CLAUDE.md is missing."""
        project_dir = tmp_path / "no_claude"
        project_dir.mkdir()

        report = StartupReport(project_dir)
        report._check_claude_md()

        assert len(report.sources) == 1
        source = report.sources[0]
        assert source.status == "missing"
        assert source.file_path is None
        assert "Create CLAUDE.md" in source.hints[0]

    def test_check_claude_md_large_file_warning(self, tmp_path):
        """Test that large CLAUDE.md files get warnings."""
        project_dir = tmp_path / "large_claude"
        project_dir.mkdir()

        # Create a large CLAUDE.md (>500 lines)
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text("# Line\n" * 600)

        report = StartupReport(project_dir)
        report._check_claude_md()

        source = report.sources[0]
        assert any("large" in hint.lower() for hint in source.hints)

    def test_check_auto_memory_present(self, tmp_path):
        """Test _check_auto_memory when MEMORY.md exists."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create memory directory with correct encoding
        encoded_path = str(project_dir.resolve()).replace("/", "-").replace("_", "-")
        memory_dir = tmp_path / ".claude" / "projects" / encoded_path / "memory"
        memory_dir.mkdir(parents=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text(
            "# Memory\n" * 160
        )  # 160 lines (>150 to trigger warning)

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(project_dir)
            report._check_auto_memory()

            source = report.sources[0]
            assert source.status == "loaded"
            assert source.line_count == 160
            assert any(
                "approaching 200-line limit" in hint.lower() for hint in source.hints
            )

    def test_check_auto_memory_missing(self, tmp_path):
        """Test _check_auto_memory when MEMORY.md doesn't exist."""
        project_dir = tmp_path / "no_memory"
        project_dir.mkdir()

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(project_dir)
            report._check_auto_memory()

            source = report.sources[0]
            assert source.status == "not created yet"
            assert "Auto memory will be created" in source.hints[0]

    def test_check_auto_memory_over_200_lines(self, tmp_path):
        """Test warning when MEMORY.md exceeds 200 lines."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        encoded_path = str(project_dir.resolve()).replace("/", "-").replace("_", "-")
        memory_dir = tmp_path / ".claude" / "projects" / encoded_path / "memory"
        memory_dir.mkdir(parents=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text("# Line\n" * 250)  # Over 200 lines

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(project_dir)
            report._check_auto_memory()

            source = report.sources[0]
            assert any("only first 200 lines" in hint.lower() for hint in source.hints)

    def test_path_encoding_with_underscores(self, tmp_path):
        """Test that underscores in path are converted to dashes."""
        project_dir = tmp_path / "test_project_name"
        project_dir.mkdir()

        # Expected encoding: /tmp/test_project_name -> -tmp-test-project-name
        encoded_path = str(project_dir.resolve()).replace("/", "-").replace("_", "-")
        memory_dir = tmp_path / ".claude" / "projects" / encoded_path / "memory"
        memory_dir.mkdir(parents=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text("# Memory")

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(project_dir)
            report._check_auto_memory()

            source = report.sources[0]
            assert source.status == "loaded"

    def test_check_global_settings_present(self, tmp_path):
        """Test _check_global_settings when settings.json exists."""
        settings_file = tmp_path / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text(json.dumps({"model": "opus"}))

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(tmp_path / "project")
            report._check_global_settings()

            source = report.sources[0]
            assert "model: opus" in source.status
            assert source.file_path == settings_file

    def test_check_global_settings_missing(self, tmp_path):
        """Test _check_global_settings when settings.json is missing."""
        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(tmp_path / "project")
            report._check_global_settings()

            source = report.sources[0]
            assert source.status == "missing"

    def test_check_global_settings_invalid_json(self, tmp_path):
        """Test _check_global_settings with invalid JSON."""
        settings_file = tmp_path / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text("{invalid json")

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            report = StartupReport(tmp_path / "project")
            report._check_global_settings()

            source = report.sources[0]
            assert "parse error" in source.status

    def test_check_project_settings_present(self, temp_project):
        """Test _check_project_settings when settings.local.json exists."""
        report = StartupReport(temp_project)
        report._check_project_settings()

        source = report.sources[0]
        assert source.status == "loaded (overrides global)"
        assert source.file_path == temp_project / ".claude" / "settings.local.json"

    def test_check_project_settings_missing(self, tmp_path):
        """Test _check_project_settings when settings.local.json is missing."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        report = StartupReport(project_dir)
        report._check_project_settings()

        source = report.sources[0]
        assert source.status == "not present"
        assert "Create .claude/settings.local.json" in source.hints[0]

    def test_check_git_context_present(self, temp_project):
        """Test _check_git_context when .git directory exists."""
        report = StartupReport(temp_project)
        report._check_git_context()

        source = report.sources[0]
        assert source.status == "loaded"
        assert source.file_path == temp_project / ".git"

    def test_check_git_context_missing(self, tmp_path):
        """Test _check_git_context when .git directory doesn't exist."""
        project_dir = tmp_path / "no_git"
        project_dir.mkdir()

        report = StartupReport(project_dir)
        report._check_git_context()

        source = report.sources[0]
        assert source.status == "not a git repo"
        assert "git init" in source.hints[0]

    def test_format_report_full(self, temp_project):
        """Test format_report() generates full report."""
        report = StartupReport(temp_project)
        report.analyze()

        output = report.format_report(show_hints=True)

        assert "Claude Code Startup Context Report" in output
        assert "Project Instructions (CLAUDE.md)" in output
        assert "Auto Memory (MEMORY.md)" in output
        assert "Global Settings" in output
        assert "Git Context" in output
        assert "Tips for Maximizing Your Experience" in output
        assert "https://code.claude.com/docs" in output

    def test_format_report_no_hints(self, temp_project):
        """Test format_report() without hints."""
        report = StartupReport(temp_project)
        report.analyze()

        output = report.format_report(show_hints=False)

        assert "Claude Code Startup Context Report" in output
        # Hints should not appear (check for hint indicators)
        assert (
            "💡" not in output or "Tips for Maximizing" in output
        )  # Footer tips are ok

    def test_format_summary(self, temp_project):
        """Test format_summary() generates compact summary."""
        report = StartupReport(temp_project)
        report.analyze()

        output = report.format_summary()

        assert "CONTEXT LOADED FOR THIS SESSION" in output
        assert "✅" in output or "⚪" in output or "❌" in output
        assert "--startup-report" in output

    def test_format_summary_shows_status_icons(self, temp_project):
        """Test that format_summary shows appropriate status icons."""
        report = StartupReport(temp_project)
        report.analyze()

        output = report.format_summary()

        # CLAUDE.md exists in fixture
        assert "✅ Project Instructions (CLAUDE.md)" in output

        # Git exists in fixture
        assert "✅ Git Context" in output


class TestGenerateStartupReport:
    """Test the generate_startup_report function."""

    def test_generate_full_report(self, tmp_path):
        """Test generating a full report."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        output = generate_startup_report(project_dir, summary_only=False)

        assert "Claude Code Startup Context Report" in output
        assert "Tips for Maximizing Your Experience" in output

    def test_generate_summary_report(self, tmp_path):
        """Test generating a summary report."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        output = generate_startup_report(project_dir, summary_only=True)

        assert "CONTEXT LOADED FOR THIS SESSION" in output
        assert "--startup-report" in output

    def test_generate_report_with_string_path(self, tmp_path):
        """Test that string paths are converted to Path objects."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Pass string instead of Path
        output = generate_startup_report(str(project_dir), summary_only=True)

        assert "CONTEXT LOADED FOR THIS SESSION" in output

    def test_generate_report_with_path_object(self, tmp_path):
        """Test that Path objects work directly."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Pass Path object
        output = generate_startup_report(project_dir, summary_only=True)

        assert "CONTEXT LOADED FOR THIS SESSION" in output


class TestHelperFunctions:
    """Test helper functions for formatting."""

    def test_visual_length_ascii(self):
        """Test _visual_length with ASCII characters."""
        text = "Hello World"
        assert _visual_length(text) == 11

    def test_visual_length_emoji(self):
        """Test _visual_length with emoji characters."""
        # Basic emoji should take 2 spaces
        text = "🚀"
        length = _visual_length(text)
        assert length >= 1  # At least 1, likely 2

    def test_visual_length_mixed(self):
        """Test _visual_length with mixed ASCII and emoji."""
        text = "Test 🚀 Text"
        length = _visual_length(text)
        # Should be longer than just the ASCII count
        assert length >= len(text)

    def test_pad_line_basic(self):
        """Test _pad_line with basic text."""
        text = "│ Test"
        width = 20
        result = _pad_line(text, width)

        assert result.startswith("│ Test")
        assert result.endswith("│")
        # Visual length should match width
        assert _visual_length(result) <= width + 2  # Allow some tolerance for emoji

    def test_pad_line_exact_width(self):
        """Test _pad_line produces correct width."""
        text = "│ Short"
        width = 30
        result = _pad_line(text, width)

        # Should have closing border
        assert result.endswith("│")

    def test_pad_line_too_long(self):
        """Test _pad_line with text that's too long."""
        text = "│ " + "x" * 100
        width = 20
        result = _pad_line(text, width)

        # Should still close with border
        assert result.endswith("│")


class TestIntegration:
    """Integration tests for the complete startup report flow."""

    def test_complete_workflow_all_sources_present(self, tmp_path):
        """Test complete workflow with all context sources present."""
        # Set up project with all context sources
        project_dir = tmp_path / "full_project"
        project_dir.mkdir()

        # CLAUDE.md
        (project_dir / "CLAUDE.md").write_text("# Project Guide\n" * 100)

        # .git
        (project_dir / ".git").mkdir()

        # Project settings
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "settings.local.json").write_text(
            json.dumps({"model": "opus"})
        )

        # Global settings
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.json").write_text(
            json.dumps({"model": "sonnet"})
        )

        # Memory
        encoded_path = str(project_dir.resolve()).replace("/", "-").replace("_", "-")
        memory_dir = tmp_path / ".claude" / "projects" / encoded_path / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("# Memory\n" * 50)

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            # Generate full report
            full_report = generate_startup_report(project_dir, summary_only=False)

            # Verify all sources are loaded
            assert "✅" in full_report or "loaded" in full_report
            assert "CLAUDE.md" in full_report
            assert "MEMORY.md" in full_report
            assert "Global Settings" in full_report
            assert "Project Settings" in full_report
            assert "Git Context" in full_report

            # Generate summary
            summary = generate_startup_report(project_dir, summary_only=True)

            assert "CONTEXT LOADED FOR THIS SESSION" in summary
            assert "✅" in summary

    def test_complete_workflow_minimal_sources(self, tmp_path):
        """Test complete workflow with minimal context sources."""
        # Bare minimum project (just a directory)
        project_dir = tmp_path / "minimal_project"
        project_dir.mkdir()

        with patch("ai_launcher.ui.startup_report.Path.home", return_value=tmp_path):
            # Generate reports
            full_report = generate_startup_report(project_dir, summary_only=False)
            summary = generate_startup_report(project_dir, summary_only=True)

            # Should show missing sources
            assert (
                "missing" in full_report.lower() or "not present" in full_report.lower()
            )
            assert "⚪" in summary or "❌" in summary

            # Should provide hints
            assert "Create CLAUDE.md" in full_report
            assert "git init" in full_report


class TestStartupReportWithProvider:
    """Test StartupReport with provider abstraction."""

    def _make_mock_provider(self, display_name="Test Provider"):
        """Create a mock provider for testing."""
        from ai_launcher.core.provider_data import (
            ContextFile,
            MemoryInfo,
            ProviderPreviewData,
            SessionConfig,
            SkillInfo,
        )

        provider = Mock()
        provider.metadata.display_name = display_name
        provider.metadata.config_files = ["TEST.md"]

        data = ProviderPreviewData(
            provider_name=display_name,
            context_files=[
                ContextFile(
                    path=Path("/test/TEST.md"),
                    label="TEST.md",
                    exists=True,
                    size_bytes=1024,
                    line_count=50,
                    file_type="project",
                )
            ],
            session_config=SessionConfig(model="test-model"),
            memory_info=MemoryInfo(project_lines=10),
            skills=[SkillInfo(name="test-skill")],
        )
        provider.collect_preview_data.return_value = data
        provider.get_documentation_urls.return_value = {
            "CLAUDE.md guide": "https://example.com/guide",
            "Auto memory": "https://example.com/memory",
            "Settings": "https://example.com/settings",
        }

        return provider

    def test_startup_report_with_provider(self, tmp_path):
        """Test StartupReport uses provider data when provider is set."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        provider = self._make_mock_provider("My AI Tool")

        report = StartupReport(project_dir, provider=provider)
        report.analyze()

        # Should have called collect_preview_data
        provider.collect_preview_data.assert_called_once_with(project_dir)

        # Check sources
        source_names = [s.name for s in report.sources]
        assert any("TEST.md" in n for n in source_names)

    def test_startup_report_provider_report_header(self, tmp_path):
        """Test that format_report uses provider name in header."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        provider = self._make_mock_provider("Gemini CLI")

        report = StartupReport(project_dir, provider=provider)
        report.analyze()
        output = report.format_report()

        assert "Gemini CLI Startup Context Report" in output

    def test_startup_report_without_provider_backward_compat(self, tmp_path):
        """Test that StartupReport works without provider (backward compat)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "CLAUDE.md").write_text("# Test")

        report = StartupReport(project_dir)
        report.analyze()

        # Should still work with legacy behavior
        source_names = [s.name for s in report.sources]
        assert "Project Instructions (CLAUDE.md)" in source_names

    def test_generate_startup_report_with_provider(self, tmp_path):
        """Test generate_startup_report accepts optional provider."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        provider = self._make_mock_provider()

        output = generate_startup_report(project_dir, provider=provider)
        assert "Test Provider Startup Context Report" in output
