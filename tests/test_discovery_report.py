"""Tests for discovery report UI.

Author: Solent Labs™
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_launcher.core.models import Project, ProviderContext, ProviderInfo
from ai_launcher.ui.discovery import generate_discovery_report, show_discovery_report


@pytest.fixture
def sample_projects(tmp_path):
    """Create sample projects for testing."""
    projects = []
    for i in range(3):
        p = tmp_path / f"project-{i}"
        p.mkdir()
        (p / ".git").mkdir()
        projects.append(
            Project(
                path=p,
                name=f"project-{i}",
                parent_path=tmp_path,
                is_git_repo=True,
                is_manual=False,
            )
        )
    return projects


@pytest.fixture
def sample_providers():
    """Create sample provider info for testing."""
    installed = ProviderInfo(
        name="Claude Code",
        command="claude",
        context=ProviderContext(
            name="Claude Code",
            version="2.1.37",
            installed=True,
            file_count=5,
            total_size=1024,
        ),
    )
    not_installed = ProviderInfo(
        name="Gemini CLI",
        command="gemini",
        context=None,
        install_url="https://ai.google.dev/gemini-api/docs/cli",
    )
    return [installed, not_installed]


class TestGenerateDiscoveryReport:
    """Tests for generate_discovery_report()."""

    def test_report_contains_header(self, sample_projects, sample_providers, tmp_path):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "AI Launcher - Discovery Report" in report
        assert "Solent Labs" in report

    def test_report_shows_projects(self, sample_projects, sample_providers, tmp_path):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "PROJECTS DISCOVERED" in report
        assert "3 projects" in report
        for p in sample_projects:
            assert p.name in report

    def test_report_shows_git_marker(self, sample_projects, sample_providers, tmp_path):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "[git]" in report

    def test_report_shows_manual_marker(self, tmp_path, sample_providers):
        manual_project = Project(
            path=tmp_path / "manual",
            name="manual",
            parent_path=tmp_path,
            is_git_repo=False,
            is_manual=True,
        )
        report = generate_discovery_report(
            [manual_project], sample_providers, [tmp_path]
        )
        assert "[manual]" in report

    def test_report_truncates_at_10_projects(self, tmp_path, sample_providers):
        projects = []
        for i in range(15):
            p = tmp_path / f"proj-{i}"
            p.mkdir()
            projects.append(
                Project(
                    path=p,
                    name=f"proj-{i}",
                    parent_path=tmp_path,
                    is_git_repo=True,
                    is_manual=False,
                )
            )
        report = generate_discovery_report(projects, sample_providers, [tmp_path])
        assert "5 more projects" in report

    def test_report_shows_installed_provider(
        self, sample_projects, sample_providers, tmp_path
    ):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "✓ Claude Code" in report
        assert "v2.1.37" in report
        assert "Ready to use" in report

    def test_report_shows_not_installed_provider(
        self, sample_projects, sample_providers, tmp_path
    ):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "✗ Gemini CLI" in report
        assert "Not installed" in report
        assert "https://ai.google.dev/gemini-api/docs/cli" in report

    def test_report_shows_context_stats(
        self, sample_projects, sample_providers, tmp_path
    ):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "5 files" in report

    def test_report_tilde_paths(self, sample_projects, sample_providers):
        home = Path.home()
        scan_path = home / "projects"
        report = generate_discovery_report(
            sample_projects, sample_providers, [scan_path]
        )
        assert "~/projects" in report

    def test_report_next_steps(self, sample_projects, sample_providers, tmp_path):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "NEXT STEPS" in report
        assert "ai-launcher ~/projects" in report
        assert "ai-launcher --context" in report
        assert "ai-launcher --list" in report

    def test_report_provider_count(self, sample_projects, sample_providers, tmp_path):
        report = generate_discovery_report(
            sample_projects, sample_providers, [tmp_path]
        )
        assert "1/2 installed providers" in report


class TestShowDiscoveryReport:
    """Tests for show_discovery_report()."""

    def test_show_prints_report(
        self, sample_projects, sample_providers, tmp_path, capsys
    ):
        with patch("builtins.input", return_value=""):
            show_discovery_report(sample_projects, sample_providers, [tmp_path])

        captured = capsys.readouterr()
        assert "AI Launcher - Discovery Report" in captured.out
        assert "Press Enter to continue..." in captured.out
