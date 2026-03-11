"""Extended tests for startup report UI.

Tests for functions not covered by existing test_startup_report.py.

Author: Solent Labs™
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from ai_launcher.core.provider_data import (
    ContextFile,
    GlobalContextSummary,
    MarketplaceInfo,
    MarketplacePlugin,
    MemoryFile,
    MemoryInfo,
    ProviderPreviewData,
    SessionConfig,
    SessionStats,
    SkillInfo,
)
from ai_launcher.providers.base import ProviderMetadata
from ai_launcher.ui.startup_report import (
    _check_sibling_projects,
    _get_file_description,
    _pad_line,
    _visual_length,
    display_launch_info,
    generate_startup_report,
)


class TestCheckSiblingProjects:
    """Tests for _check_sibling_projects()."""

    def test_no_siblings(self, tmp_path):
        project = tmp_path / "only-project"
        project.mkdir()
        result = _check_sibling_projects(project)
        assert result["sibling_count"] == 0
        assert result["selected_project"] == "only-project"
        assert result["sibling_names"] == []

    def test_with_siblings(self, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        (tmp_path / "sibling1").mkdir()
        (tmp_path / "sibling2").mkdir()

        result = _check_sibling_projects(project)
        assert result["sibling_count"] == 2
        assert result["selected_project"] == "my-project"
        assert len(result["sibling_names"]) == 2

    def test_hidden_dirs_excluded(self, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()

        result = _check_sibling_projects(project)
        assert result["sibling_count"] == 1
        assert ".hidden" not in result["sibling_names"]

    def test_limit_to_6_siblings(self, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        for i in range(10):
            (tmp_path / f"sibling-{i}").mkdir()

        result = _check_sibling_projects(project)
        assert result["sibling_count"] == 10
        assert len(result["sibling_names"]) == 6


class TestGetFileDescription:
    """Tests for _get_file_description()."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("STANDARDS.md", "coding standards"),
            ("TESTING.md", "testing guidelines"),
            ("SECURITY.md", "security best practices"),
            ("OPERATIONS.md", "operational procedures"),
            ("DEVKIT-PATTERNS.md", "common patterns"),
            ("DEPLOYMENT.md", "deployment guide"),
            ("ARCHITECTURE.md", "architecture docs"),
            ("CONTRIBUTING.md", "contribution guide"),
        ],
    )
    def test_known_files(self, filename, expected):
        assert _get_file_description(filename) == expected

    @pytest.mark.parametrize("filename", ["RANDOM.md", "unknown.txt"])
    def test_unknown_file(self, filename):
        assert _get_file_description(filename) == "documentation"


class TestVisualLength:
    """Tests for _visual_length()."""

    def test_ascii_text(self):
        assert _visual_length("hello") == 5

    def test_empty_string(self):
        assert _visual_length("") == 0


class TestPadLine:
    """Tests for _pad_line()."""

    def test_pads_to_width(self):
        result = _pad_line("│ hello", 20)
        assert result.endswith("│")
        assert len(result) >= 20

    def test_no_negative_padding(self):
        result = _pad_line("│" + "x" * 100, 10)
        assert result.endswith("│")


class TestDisplayLaunchInfo:
    """Tests for display_launch_info()."""

    def _make_provider(
        self,
        preview_data=None,
        display_name="Test Provider",
        config_files=None,
        has_get_version=False,
        version=None,
    ):
        """Create a mock provider."""
        provider = MagicMock()
        metadata = ProviderMetadata(
            name="test",
            display_name=display_name,
            command="test",
            description="Test provider",
            config_files=config_files or ["TEST.md"],
        )
        type(provider).metadata = PropertyMock(return_value=metadata)

        if preview_data is None:
            preview_data = ProviderPreviewData(provider_name=display_name)
        provider.collect_preview_data.return_value = preview_data

        if has_get_version:
            provider.get_version.return_value = version
        else:
            del provider.get_version

        return provider

    def test_non_verbose_minimal_output(self, tmp_path, capsys):
        provider = self._make_provider()
        display_launch_info(tmp_path, provider, verbose=False)
        captured = capsys.readouterr()
        assert "Launching Test Provider" in captured.out
        # Should NOT contain detailed sections
        assert "Context Sources" not in captured.out

    def test_verbose_shows_header(self, tmp_path, capsys):
        provider = self._make_provider()
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "AI Launcher" in captured.out
        assert tmp_path.name in captured.out

    def test_verbose_shows_provider_info(self, tmp_path, capsys):
        provider = self._make_provider()
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Provider:" in captured.out
        assert "Test Provider" in captured.out

    def test_verbose_with_version(self, tmp_path, capsys):
        provider = self._make_provider(has_get_version=True, version="1.2.3")
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "v1.2.3" in captured.out

    def test_verbose_context_files(self, tmp_path, capsys):
        ctx = ContextFile(
            path=tmp_path / "CLAUDE.md",
            label="CLAUDE.md",
            exists=True,
            size_bytes=100,
            line_count=50,
            file_type="project",
        )
        data = ProviderPreviewData(
            provider_name="Test",
            context_files=[ctx],
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "CLAUDE.md" in captured.out
        assert "50 lines" in captured.out

    def test_verbose_no_context_files(self, tmp_path, capsys):
        data = ProviderPreviewData(provider_name="Test", context_files=[])
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "no context loaded" in captured.out

    def test_verbose_session_config_with_data(self, tmp_path, capsys):
        session = SessionConfig(
            permissions_count=5,
            mcp_servers=["server1", "server2"],
            hooks_configured=True,
            model="opus",
        )
        data = ProviderPreviewData(
            provider_name="Test",
            session_config=session,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "5 auto-approved" in captured.out
        assert "server1" in captured.out
        assert "Hooks configured" in captured.out
        assert "opus" in captured.out

    def test_verbose_session_config_empty(self, tmp_path, capsys):
        session = SessionConfig(
            permissions_count=0,
            mcp_servers=[],
            hooks_configured=False,
            model=None,
        )
        data = ProviderPreviewData(
            provider_name="Test",
            session_config=session,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "No pre-approved permissions" in captured.out
        assert "No MCP servers" in captured.out
        assert "No hooks" in captured.out
        assert "default (sonnet)" in captured.out

    def test_verbose_no_session_config(self, tmp_path, capsys):
        data = ProviderPreviewData(provider_name="Test", session_config=None)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "No pre-approved permissions" in captured.out

    def test_verbose_memory_info(self, tmp_path, capsys):
        memory = MemoryInfo(
            personal_memory=tmp_path / "personal.md",
            personal_lines=10,
            project_memory=tmp_path / "project.md",
            project_lines=25,
        )
        data = ProviderPreviewData(
            provider_name="Test",
            memory_info=memory,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Personal: 10 lines" in captured.out
        assert "Project: 25 lines" in captured.out

    def test_verbose_no_memory(self, tmp_path, capsys):
        data = ProviderPreviewData(provider_name="Test", memory_info=None)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "No memory files" in captured.out

    def test_verbose_skills(self, tmp_path, capsys):
        skills = [
            SkillInfo(name="commit"),
            SkillInfo(name="review"),
            SkillInfo(name="test"),
        ]
        data = ProviderPreviewData(provider_name="Test", skills=skills)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "3 available" in captured.out
        assert "commit" in captured.out

    def test_verbose_no_skills(self, tmp_path, capsys):
        data = ProviderPreviewData(provider_name="Test", skills=[])
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "No skills installed" in captured.out

    def test_verbose_marketplace_plugins(self, tmp_path, capsys):
        plugins = MarketplaceInfo(
            name="test-marketplace",
            plugins=[
                MarketplacePlugin(name="plugin1", description="desc1"),
                MarketplacePlugin(name="plugin2", description="desc2"),
            ],
        )
        data = ProviderPreviewData(
            provider_name="Test",
            marketplace_plugins=plugins,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "plugin1" in captured.out

    def test_verbose_global_context(self, tmp_path, capsys):
        global_ctx = GlobalContextSummary(
            total_files=3,
            categories={"standards": 2, "guidelines": 1},
        )
        data = ProviderPreviewData(
            provider_name="Test",
            global_context_summary=global_ctx,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "3 files loaded" in captured.out
        assert "standards" in captured.out

    def test_verbose_no_global_context(self, tmp_path, capsys):
        data = ProviderPreviewData(
            provider_name="Test",
            global_context_summary=None,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "No global context files" in captured.out

    def test_verbose_sibling_projects(self, tmp_path, capsys):
        project = tmp_path / "my-proj"
        project.mkdir()
        (tmp_path / "sibling1").mkdir()
        (tmp_path / "sibling2").mkdir()

        data = ProviderPreviewData(provider_name="Test")
        provider = self._make_provider(preview_data=data)
        display_launch_info(project, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Sibling Projects" in captured.out
        assert "2 nearby projects" in captured.out

    def test_verbose_session_stats(self, tmp_path, capsys):
        stats = SessionStats(
            session_count=10,
            total_size_bytes=2048,
            last_session_time=datetime.now(),
            memory_files=[
                MemoryFile(
                    path=tmp_path / "MEMORY.md",
                    name="MEMORY.md",
                    size_bytes=100,
                    last_modified=datetime.now(),
                ),
            ],
        )
        data = ProviderPreviewData(
            provider_name="Test",
            session_stats=stats,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Session Activity" in captured.out
        assert "10 sessions" in captured.out
        assert "MEMORY.md" in captured.out

    def test_collect_preview_data_error_fallback(self, tmp_path, capsys):
        provider = self._make_provider()
        provider.collect_preview_data.side_effect = Exception("fail")
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Launching" in captured.out

    def test_verbose_mcp_servers_truncated(self, tmp_path, capsys):
        session = SessionConfig(
            mcp_servers=["s1", "s2", "s3", "s4", "s5"],
        )
        data = ProviderPreviewData(
            provider_name="Test",
            session_config=session,
        )
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "+2 more" in captured.out

    def test_verbose_skills_truncated(self, tmp_path, capsys):
        skills = [SkillInfo(name=f"skill{i}") for i in range(6)]
        data = ProviderPreviewData(provider_name="Test", skills=skills)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "+3 more" in captured.out

    def test_tilde_path(self, capsys):
        home = Path.home()
        project = home / "test-project"
        data = ProviderPreviewData(provider_name="Test")
        provider = self._make_provider(preview_data=data)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "iterdir", return_value=[]):
                display_launch_info(project, provider, verbose=True)
        captured = capsys.readouterr()
        assert "~/test-project" in captured.out


class TestGenerateStartupReport:
    """Tests for generate_startup_report()."""

    def test_full_report(self, tmp_path):
        report = generate_startup_report(tmp_path)
        assert "Startup Context Report" in report
        assert str(tmp_path) in report

    def test_summary_report(self, tmp_path):
        report = generate_startup_report(tmp_path, summary_only=True)
        assert "CONTEXT LOADED" in report

    def test_string_path(self, tmp_path):
        report = generate_startup_report(str(tmp_path))
        assert "Startup Context Report" in report

    def test_with_provider(self, tmp_path):
        provider = MagicMock()
        metadata = ProviderMetadata(
            name="test",
            display_name="Test",
            command="test",
            description="desc",
            config_files=["TEST.md"],
        )
        type(provider).metadata = PropertyMock(return_value=metadata)

        data = ProviderPreviewData(provider_name="Test")
        provider.collect_preview_data.return_value = data
        provider.get_documentation_urls.return_value = {}

        report = generate_startup_report(tmp_path, provider=provider)
        assert "Test" in report


class TestAnalyzeWithProviderEdgeCases:
    """Test edge cases in _analyze_with_provider and display_launch_info."""

    def _make_provider(self, preview_data=None, display_name="Test Provider"):
        provider = MagicMock()
        metadata = ProviderMetadata(
            name="test",
            display_name=display_name,
            command="test",
            description="desc",
            config_files=["TEST.md"],
        )
        type(provider).metadata = PropertyMock(return_value=metadata)
        if preview_data is None:
            preview_data = ProviderPreviewData(provider_name=display_name)
        provider.collect_preview_data.return_value = preview_data
        provider.get_documentation_urls.return_value = {}
        del provider.get_version
        return provider

    def test_large_context_file_hints(self, tmp_path):
        """Test that large context files produce hints in StartupReport."""
        from ai_launcher.ui.startup_report import StartupReport

        ctx = ContextFile(
            path=tmp_path / "CLAUDE.md",
            label="CLAUDE.md",
            exists=True,
            size_bytes=60000,
            line_count=600,
            file_type="project",
        )
        data = ProviderPreviewData(
            provider_name="Test",
            context_files=[ctx],
        )
        provider = self._make_provider(preview_data=data)
        report = StartupReport(tmp_path, provider=provider)
        report.analyze()

        # Should have both large file hints
        all_hints = []
        for source in report.sources:
            all_hints.extend(source.hints)
        hint_text = " ".join(all_hints)
        assert "large" in hint_text.lower() or "splitting" in hint_text.lower()
        assert "detailed docs" in hint_text.lower() or "linking" in hint_text.lower()

    def test_memory_over_200_lines_hint(self, tmp_path):
        """Test memory over 200 lines gets truncation hint."""
        from ai_launcher.ui.startup_report import StartupReport

        mem_path = tmp_path / "MEMORY.md"
        mem_path.write_text("\n".join([f"line {i}" for i in range(210)]))

        memory = MemoryInfo(project_memory=mem_path, project_lines=210)
        data = ProviderPreviewData(
            provider_name="Test",
            memory_info=memory,
        )
        provider = self._make_provider(preview_data=data)
        report = StartupReport(tmp_path, provider=provider)
        report.analyze()

        all_hints = []
        for source in report.sources:
            all_hints.extend(source.hints)
        hint_text = " ".join(all_hints)
        assert "200" in hint_text

    def test_memory_under_20_lines_hint(self, tmp_path):
        """Test small memory gets 'good' hint."""
        from ai_launcher.ui.startup_report import StartupReport

        mem_path = tmp_path / "MEMORY.md"
        mem_path.write_text("line 1\nline 2\n")

        memory = MemoryInfo(project_memory=mem_path, project_lines=2)
        data = ProviderPreviewData(
            provider_name="Test",
            memory_info=memory,
        )
        provider = self._make_provider(preview_data=data)
        report = StartupReport(tmp_path, provider=provider)
        report.analyze()

        all_hints = []
        for source in report.sources:
            all_hints.extend(source.hints)
        hint_text = " ".join(all_hints)
        assert "concise" in hint_text.lower() or "Good" in hint_text

    def test_display_empty_personal_memory(self, tmp_path, capsys):
        """Test display when personal_memory exists but has 0 lines."""
        memory = MemoryInfo(
            personal_memory=tmp_path / "personal.md",
            personal_lines=0,
            project_memory=None,
            project_lines=0,
        )
        data = ProviderPreviewData(provider_name="Test", memory_info=memory)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Personal: empty" in captured.out

    def test_display_empty_project_memory(self, tmp_path, capsys):
        """Test display when project_memory exists but has 0 lines."""
        memory = MemoryInfo(
            personal_memory=None,
            personal_lines=0,
            project_memory=tmp_path / "project.md",
            project_lines=0,
        )
        data = ProviderPreviewData(provider_name="Test", memory_info=memory)
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "Project: empty" in captured.out

    def test_display_existing_config_file(self, tmp_path, capsys):
        """Test provider context section when config file exists."""
        (tmp_path / "TEST.md").write_text("# Test\n")
        data = ProviderPreviewData(provider_name="Test")
        provider = self._make_provider(preview_data=data)
        display_launch_info(tmp_path, provider, verbose=True)
        captured = capsys.readouterr()
        assert "TEST.md" in captured.out
        assert "local project instructions" in captured.out
