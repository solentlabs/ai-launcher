"""Tests for permission health check report.

Author: Solent Labs™
Created: 2026-03-24
"""

import json

import pytest

from ai_launcher.core.models import Project
from ai_launcher.ui.permissions_report import check_project_permissions


class TestCheckProjectPermissions:
    """Tests for the --check-permissions CLI feature."""

    def _make_project(self, path):
        return Project(
            path=path,
            name=path.name,
            parent_path=path.parent,
            is_git_repo=False,
            is_manual=False,
        )

    def test_healthy_project_shows_checkmark(self, mock_home, capsys):
        """Project with Bash(*) shows as healthy."""
        project = mock_home / "healthy-project"
        project.mkdir()
        claude_dir = project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(*)"]}})
        )

        check_project_permissions([self._make_project(project)], "claude-code")
        captured = capsys.readouterr()
        assert "✓" in captured.out
        assert "healthy-project" in captured.out

    def test_accumulated_project_shows_warning(self, mock_home, capsys):
        """Project with accumulated patterns shows warnings and fix."""
        project = mock_home / "messy-project"
        project.mkdir()
        claude_dir = project / ".claude"
        claude_dir.mkdir()
        perms = [f"Bash(cmd{i}:*)" for i in range(15)]
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": perms}})
        )

        check_project_permissions([self._make_project(project)], "claude-code")
        captured = capsys.readouterr()
        assert "⚠" in captured.out
        assert "messy-project" in captured.out
        assert "15 accumulated" in captured.out
        assert "Bash(*)" in captured.out

    def test_no_settings_shows_informational(self, mock_home, capsys):
        """Project without settings files shows informational message."""
        project = mock_home / "new-project"
        project.mkdir()

        check_project_permissions([self._make_project(project)], "claude-code")
        captured = capsys.readouterr()
        assert "No projects with Claude Code settings found" in captured.out

    def test_non_claude_provider_exits_cleanly(self, capsys):
        """Non-Claude providers get an informational message."""
        with pytest.raises(SystemExit):
            check_project_permissions([], "gemini")
        captured = capsys.readouterr()
        assert "only available for Claude Code" in captured.out

    @pytest.mark.parametrize(
        "num_issues,expected_text",
        [
            (0, "All projects healthy"),
            (1, "1 project(s) with permission issues"),
        ],
        ids=["all_healthy", "one_issue"],
    )
    def test_summary_line(self, mock_home, capsys, num_issues, expected_text):
        """Summary shows correct count of issues."""
        projects = []
        for i in range(3):
            p = mock_home / f"project-{i}"
            p.mkdir()
            claude_dir = p / ".claude"
            claude_dir.mkdir()
            if i < num_issues:
                # Accumulated patterns
                perms = [f"Bash(cmd{j}:*)" for j in range(12)]
            else:
                perms = ["Bash(*)"]
            (claude_dir / "settings.local.json").write_text(
                json.dumps({"permissions": {"allow": perms}})
            )
            projects.append(self._make_project(p))

        check_project_permissions(projects, "claude-code")
        captured = capsys.readouterr()
        assert expected_text in captured.out
