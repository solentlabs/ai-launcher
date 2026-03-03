"""Tests for Claude data collection functions.

Tests the private helper functions in claude.py that collect
Claude-specific data for preview generation.

Author: Solent Labs™
Created: 2026-02-12
Updated: 2026-02-18 (Updated after consolidating claude_data.py into claude.py)
Updated: 2026-03-03 (Cross-platform compatibility: mock_home fixture, os.sep)
"""

import os
from datetime import datetime

from ai_launcher.providers.claude import (
    _encode_project_path,
    _get_claude_session_config,
    _get_global_context_summary,
    _get_memory_files,
    _get_memory_info,
    _get_personal_context_file,
    _get_project_context_file,
    _get_session_dir,
    _get_session_stats,
    _get_skills,
)


class TestPersonalContextFile:
    """Tests for get_personal_context_file()."""

    def test_personal_context_file_in_home(self, mock_home):
        """Test finding CLAUDE.md in home directory."""
        # Create CLAUDE.md in home
        claude_md = mock_home / "CLAUDE.md"
        claude_md.write_text("# Personal Context\nLine 2\nLine 3\n")

        result = _get_personal_context_file()

        assert result is not None
        assert result.path == claude_md
        assert result.label == "CLAUDE.md"
        assert result.exists is True
        assert result.size_bytes > 0
        assert result.line_count == 3
        assert result.file_type == "personal"
        assert result.content_preview == "# Personal Context\nLine 2\nLine 3\n"

    def test_personal_context_file_in_dotclaude(self, mock_home):
        """Test finding CLAUDE.md in ~/.claude/ directory."""
        # Create CLAUDE.md in ~/.claude/
        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        claude_md = claude_dir / "CLAUDE.md"
        claude_md.write_text("# Personal Context from .claude\n")

        result = _get_personal_context_file()

        assert result is not None
        assert result.path == claude_md
        assert result.exists is True

    def test_personal_context_file_not_found(self, mock_home):
        """Test when personal CLAUDE.md doesn't exist."""
        result = _get_personal_context_file()

        assert result is None

    def test_personal_context_file_preview_truncated(self, mock_home):
        """Test that content preview is limited to 10 lines."""
        claude_md = mock_home / "CLAUDE.md"
        content = "\n".join([f"Line {i}" for i in range(1, 21)])  # 20 lines
        claude_md.write_text(content)

        result = _get_personal_context_file()

        assert result is not None
        assert result.line_count == 20
        # Preview should only include first 10 lines
        preview_lines = result.content_preview.strip().split("\n")
        assert len(preview_lines) == 10
        assert preview_lines[0] == "Line 1"
        assert preview_lines[9] == "Line 10"


class TestProjectContextFile:
    """Tests for get_project_context_file()."""

    def test_project_context_file_exists(self, tmp_path):
        """Test getting project CLAUDE.md that exists."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project Context\nProject rules here\n")

        result = _get_project_context_file(tmp_path)

        assert result.path == claude_md
        assert result.label == "CLAUDE.md"
        assert result.exists is True
        assert result.size_bytes > 0
        assert result.line_count == 2
        assert result.file_type == "project"
        assert "# Project Context" in result.content_preview

    def test_project_context_file_not_exists(self, tmp_path):
        """Test getting project CLAUDE.md that doesn't exist."""
        result = _get_project_context_file(tmp_path)

        assert result.path == tmp_path / "CLAUDE.md"
        assert result.label == "CLAUDE.md"
        assert result.exists is False
        assert result.size_bytes == 0
        assert result.line_count == 0
        assert result.file_type == "project"
        assert result.content_preview is None

    def test_project_context_file_preview_truncated(self, tmp_path):
        """Test that content preview is limited to 10 lines."""
        claude_md = tmp_path / "CLAUDE.md"
        content = "\n".join([f"Line {i}" for i in range(1, 16)])  # 15 lines
        claude_md.write_text(content)

        result = _get_project_context_file(tmp_path)

        assert result.line_count == 15
        preview_lines = result.content_preview.strip().split("\n")
        assert len(preview_lines) == 10


class TestEncodeProjectPath:
    """Tests for encode_project_path()."""

    def test_encode_project_path(self, tmp_path):
        """Test encoding a real path uses os.sep replacement."""
        project_path = tmp_path / "my-app"
        project_path.mkdir()
        encoded = _encode_project_path(project_path)

        # Should replace all separators with hyphens
        expected = str(project_path).replace(os.sep, "-")
        assert encoded == expected

    def test_encode_relative_path(self, tmp_path):
        """Test encoding converts to absolute path first."""
        result = _encode_project_path(tmp_path)

        # Should be absolute path with separators replaced
        assert str(tmp_path).replace(os.sep, "-") == result


class TestGetSessionDir:
    """Tests for get_session_dir()."""

    def test_session_dir_exists(self, mock_home):
        """Test getting session directory that exists."""
        # Create session directory
        project_path = mock_home / "my-project"
        project_path.mkdir()

        encoded = _encode_project_path(project_path)
        session_dir = mock_home / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True)

        result = _get_session_dir(project_path)

        assert result == session_dir

    def test_session_dir_not_exists(self, mock_home):
        """Test getting session directory that doesn't exist."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        result = _get_session_dir(project_path)

        assert result is None


class TestGetMemoryFiles:
    """Tests for get_memory_files()."""

    def test_memory_files_exist(self, tmp_path):
        """Test getting memory files from session directory."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # Create some memory files
        mem1 = memory_dir / "MEMORY.md"
        mem1.write_text("Memory content 1")
        mem2 = memory_dir / "patterns.md"
        mem2.write_text("Memory content 2")

        # Create a non-.md file (should be ignored)
        other = memory_dir / "other.txt"
        other.write_text("Other content")

        result = _get_memory_files(tmp_path)

        assert len(result) == 2
        assert all(mf.name.endswith(".md") for mf in result)
        assert any(mf.name == "MEMORY.md" for mf in result)
        assert any(mf.name == "patterns.md" for mf in result)

        # Check MemoryFile structure
        mem_file = next(mf for mf in result if mf.name == "MEMORY.md")
        assert mem_file.path == mem1
        assert mem_file.size_bytes > 0
        assert isinstance(mem_file.last_modified, datetime)

    def test_memory_dir_not_exists(self, tmp_path):
        """Test when memory directory doesn't exist."""
        result = _get_memory_files(tmp_path)

        assert result == []

    def test_memory_dir_empty(self, tmp_path):
        """Test when memory directory exists but is empty."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        result = _get_memory_files(tmp_path)

        assert result == []


class TestGetSessionStats:
    """Tests for get_session_stats()."""

    def test_session_stats_with_sessions(self, mock_home):
        """Test getting session stats when sessions exist."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create session directory
        encoded = _encode_project_path(project_path)
        session_dir = mock_home / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True)

        # Create session files
        sess1 = session_dir / "session1.jsonl"
        sess1.write_text('{"event":"start"}\n')
        sess2 = session_dir / "session2.jsonl"
        sess2.write_text('{"event":"start"}\n{"event":"end"}\n')

        # Create memory files
        memory_dir = session_dir / "memory"
        memory_dir.mkdir()
        mem = memory_dir / "MEMORY.md"
        mem.write_text("Memory content")

        result = _get_session_stats(project_path)

        assert result is not None
        assert result.session_count == 2
        assert result.total_size_bytes > 0
        assert isinstance(result.last_session_time, datetime)
        assert len(result.memory_files) == 1
        assert result.session_dir == session_dir

    def test_session_stats_no_sessions(self, mock_home):
        """Test when session directory doesn't exist."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        result = _get_session_stats(project_path)

        assert result is None

    def test_session_stats_empty_session_dir(self, mock_home):
        """Test when session directory exists but has no .jsonl files."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create empty session directory
        encoded = _encode_project_path(project_path)
        session_dir = mock_home / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True)

        result = _get_session_stats(project_path)

        assert result is None


class TestGetClaudeSessionConfig:
    """Tests for _get_claude_session_config()."""

    def test_session_config_with_permissions(self, mock_home):
        """Test getting session config with project permissions."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create project settings with permissions
        import json

        claude_dir = project_path / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.local.json"
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Bash(git *)", "Read(*)"]}})
        )

        result = _get_claude_session_config(project_path)

        assert result is not None
        assert result.permissions_count == 2
        assert "Bash(git *)" in result.permissions

    def test_session_config_with_model(self, mock_home):
        """Test getting session config with global model setting."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create global settings with model
        import json

        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        settings.write_text(json.dumps({"model": "opus"}))

        result = _get_claude_session_config(project_path)

        assert result is not None
        assert result.model == "opus"

    def test_session_config_with_mcp_servers(self, mock_home):
        """Test getting session config with MCP servers."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create MCP config
        import json

        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        mcp = claude_dir / "mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"filesystem": {}, "github": {}}}))

        result = _get_claude_session_config(project_path)

        assert result is not None
        assert "filesystem" in result.mcp_servers
        assert "github" in result.mcp_servers

    def test_session_config_with_hooks(self, mock_home):
        """Test getting session config with hooks."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create hooks config
        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        hooks = claude_dir / "hooks.json"
        hooks.write_text("{}")

        result = _get_claude_session_config(project_path)

        assert result is not None
        assert result.hooks_configured is True

    def test_session_config_empty(self, mock_home):
        """Test getting session config when nothing is configured."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        result = _get_claude_session_config(project_path)

        assert result is None


class TestGetMemoryInfo:
    """Tests for _get_memory_info()."""

    def test_memory_info_with_project_memory(self, mock_home):
        """Test getting memory info when project memory exists."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Create project memory
        encoded = _encode_project_path(project_path)
        memory_dir = mock_home / ".claude" / "projects" / encoded / "memory"
        memory_dir.mkdir(parents=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text("Line 1\nLine 2\nLine 3\n")

        result = _get_memory_info(project_path)

        assert result is not None
        assert result.project_memory == memory_file
        assert result.project_lines == 3

    def test_memory_info_no_memory(self, mock_home):
        """Test getting memory info when no memory exists."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        result = _get_memory_info(project_path)

        assert result is None

    def test_memory_info_uses_dynamic_encoding(self, mock_home):
        """Test that memory info uses _encode_project_path, not hardcoded paths."""
        project_path = mock_home / "my-project"
        project_path.mkdir()

        # Verify encoding is dynamic by checking the encoded path
        encoded = _encode_project_path(project_path)
        memory_dir = mock_home / ".claude" / "projects" / encoded / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("test")

        result = _get_memory_info(project_path)
        assert result is not None
        assert result.project_memory is not None


class TestGetSkills:
    """Tests for _get_skills()."""

    def test_get_skills_with_skills(self, mock_home):
        """Test getting skills when skills directory has entries."""
        # Create skills
        skills_dir = mock_home / ".claude" / "skills"
        commit_dir = skills_dir / "commit"
        commit_dir.mkdir(parents=True)
        (commit_dir / "SKILL.md").write_text("# Commit Skill")

        review_dir = skills_dir / "review"
        review_dir.mkdir()
        (review_dir / "SKILL.md").write_text("# Review Skill")

        # Dir without SKILL.md should be ignored
        empty_dir = skills_dir / "empty"
        empty_dir.mkdir()

        result = _get_skills()

        assert len(result) == 2
        names = [s.name for s in result]
        assert "commit" in names
        assert "review" in names
        assert "empty" not in names

    def test_get_skills_no_skills_dir(self, mock_home):
        """Test getting skills when skills directory doesn't exist."""
        result = _get_skills()

        assert result == []


class TestGetGlobalContextSummary:
    """Tests for _get_global_context_summary()."""

    def test_global_context_with_plans(self, mock_home):
        """Test getting global context with plans directory."""
        # Create plans
        plans_dir = mock_home / ".claude" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "plan1.md").write_text("# Plan 1")
        (plans_dir / "plan2.md").write_text("# Plan 2")

        result = _get_global_context_summary()

        assert result is not None
        assert result.total_files == 2
        assert "Plans" in result.categories
        assert result.categories["Plans"] == 2

    def test_global_context_with_project_memories(self, mock_home):
        """Test getting global context with project memories."""
        # Create project memory
        proj_dir = mock_home / ".claude" / "projects" / "-home-user-project"
        mem_dir = proj_dir / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text("# Memory")

        result = _get_global_context_summary()

        assert result is not None
        assert result.total_files >= 1
        assert "Memories (all projects)" in result.categories

    def test_global_context_empty(self, mock_home):
        """Test getting global context when directories exist but are empty."""
        # Create empty .claude dir
        (mock_home / ".claude").mkdir()

        result = _get_global_context_summary()

        assert result is None

    def test_global_context_no_claude_dir(self, mock_home):
        """Test getting global context when ~/.claude doesn't exist."""
        result = _get_global_context_summary()

        assert result is None
