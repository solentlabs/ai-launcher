"""Tests for permission health check report.

Author: Solent Labs™
Created: 2026-03-24
"""

import json

import pytest

from ai_launcher.core.models import Project
from ai_launcher.ui.permissions_report import check_project_permissions


def _make_project(path):
    return Project(
        path=path,
        name=path.name,
        parent_path=path.parent,
        is_git_repo=False,
        is_manual=False,
    )


@pytest.fixture
def make_project_with_settings(mock_home):
    """Factory that writes a project with a .claude/settings.local.json and returns a Project.

    Avoids per-test boilerplate of mkdir + write_text + Project(...).
    """

    def _factory(name: str, settings: dict) -> Project:
        project_path = mock_home / name
        project_path.mkdir()
        claude_dir = project_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(json.dumps(settings))
        return _make_project(project_path)

    return _factory


class TestProjectStatusDisplay:
    """Per-project status line driven by settings shape."""

    @pytest.mark.parametrize(
        "settings,expected_substrings,forbidden_substrings",
        [
            # Bash(*) in allow → healthy with broad marker
            (
                {"permissions": {"allow": ["Bash(*)"]}},
                ["✓", "Bash(*)"],
                ["⚠"],
            ),
            # Narrow allow rules (no Bash(*)) → rule count
            (
                {"permissions": {"allow": ["Bash(npm test)", "Bash(npm run lint)"]}},
                ["✓", "2 rules"],
                ["⚠"],
            ),
            # Empty allow + MCP server keeps config non-None → inherits global
            (
                {
                    "permissions": {"allow": []},
                    "mcpServers": {"some-server": {"command": "echo"}},
                },
                ["✓", "inherits global"],
                ["⚠"],
            ),
            # Accumulated narrow patterns → warning + fix recommendation
            (
                {"permissions": {"allow": [f"Bash(cmd{i}:*)" for i in range(15)]}},
                ["⚠", "15 accumulated", "Bash(*)"],
                [],
            ),
        ],
        ids=[
            "broad_bash_star",
            "narrow_rule_count",
            "mcp_only_inherits_global",
            "accumulated_warning",
        ],
    )
    def test_status_line(
        self,
        make_project_with_settings,
        capsys,
        settings,
        expected_substrings,
        forbidden_substrings,
    ):
        """Project status line matches the shape of its settings file."""
        project = make_project_with_settings("test-project", settings)
        check_project_permissions([project], "claude-code")
        captured = capsys.readouterr()
        assert "test-project" in captured.out
        for s in expected_substrings:
            assert s in captured.out, f"missing {s!r} in:\n{captured.out}"
        for s in forbidden_substrings:
            assert s not in captured.out, f"unexpected {s!r} in:\n{captured.out}"


class TestNoProjects:
    """No discoverable projects with settings."""

    def test_no_settings_shows_informational(self, mock_home, capsys):
        project_path = mock_home / "new-project"
        project_path.mkdir()
        check_project_permissions([_make_project(project_path)], "claude-code")
        captured = capsys.readouterr()
        assert "No projects with Claude Code settings found" in captured.out

    def test_non_claude_provider_exits_cleanly(self, capsys):
        with pytest.raises(SystemExit):
            check_project_permissions([], "gemini")
        captured = capsys.readouterr()
        assert "only available for Claude Code" in captured.out


class TestGlobalSettingsRendering:
    """Global settings.json + settings.local.json output."""

    @pytest.fixture
    def with_global_settings(self, mock_home, make_project_with_settings):
        """Set up global settings and a single trigger project; returns the capsys output."""

        def _setup(global_settings=None, global_local=None):
            claude_global = mock_home / ".claude"
            claude_global.mkdir(parents=True, exist_ok=True)
            if global_settings is not None:
                (claude_global / "settings.json").write_text(global_settings)
            if global_local is not None:
                (claude_global / "settings.local.json").write_text(global_local)
            # At least one project is needed to trigger the report path.
            project = make_project_with_settings(
                "trigger", {"permissions": {"allow": ["Bash(*)"]}}
            )
            return project

        return _setup

    @pytest.mark.parametrize(
        "global_settings,global_local,expected,forbidden",
        [
            # Full settings.json with allow/deny/ask + local allow
            (
                json.dumps(
                    {
                        "permissions": {
                            "allow": [
                                "Bash(npm:*)",
                                "Bash(pytest:*)",
                                "Bash(git commit:*)",
                                "Bash(git push:*)",
                                "Read",
                                "Edit",
                                "Bash(make:*)",
                                "Bash(echo:*)",
                            ],
                            "deny": ["Bash(git add:*)", "Bash(git reset --hard:*)"],
                            "ask": ["Bash(rm:*)"],
                        }
                    }
                ),
                json.dumps(
                    {"permissions": {"allow": [f"Bash(local{i}:*)" for i in range(8)]}}
                ),
                [
                    "Bash(npm:*)",
                    "and 2 more",  # 8 allow rules - 6 shown
                    "Bash(git add:*)",  # deny rendered
                    "rm",  # ask label parsed
                    "Local allow",
                ],
                [],
            ),
            # Invalid JSON in both files → graceful error message, no crash
            (
                "{not valid json",
                "{also not valid",
                ["invalid JSON"],
                [],
            ),
            # No global files → "No ~/.claude/..." lines
            (
                None,
                None,
                ["No ~/.claude/settings.json", "No ~/.claude/settings.local.json"],
                [],
            ),
        ],
        ids=["full_rendering", "invalid_json", "absent"],
    )
    def test_global_settings_output(
        self,
        with_global_settings,
        capsys,
        global_settings,
        global_local,
        expected,
        forbidden,
    ):
        project = with_global_settings(global_settings, global_local)
        check_project_permissions([project], "claude-code")
        captured = capsys.readouterr()
        for s in expected:
            assert s in captured.out, f"missing {s!r} in:\n{captured.out}"
        for s in forbidden:
            assert s not in captured.out, f"unexpected {s!r}"


class TestSummary:
    """Aggregate summary line at the end of the report."""

    @pytest.mark.parametrize(
        "num_issues,expected_text",
        [
            (0, "All projects healthy"),
            (1, "1 project(s) with permission issues"),
        ],
        ids=["all_healthy", "one_issue"],
    )
    def test_summary_line(
        self, make_project_with_settings, capsys, num_issues, expected_text
    ):
        projects = []
        for i in range(3):
            if i < num_issues:
                perms = [f"Bash(cmd{j}:*)" for j in range(12)]
            else:
                perms = ["Bash(*)"]
            projects.append(
                make_project_with_settings(
                    f"project-{i}", {"permissions": {"allow": perms}}
                )
            )

        check_project_permissions(projects, "claude-code")
        captured = capsys.readouterr()
        assert expected_text in captured.out
