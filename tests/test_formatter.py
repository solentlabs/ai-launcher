"""Tests for preview formatter.

Author: Solent Labs™
Created: 2026-02-12
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ai_launcher.core.provider_data import (
    ContextFile,
    DirectoryListing,
    GitStatus,
    GlobalFiles,
    MarketplaceInfo,
    MarketplacePlugin,
    MemoryFile,
    ProviderPreviewData,
    SessionStats,
)
from ai_launcher.ui.formatter import PreviewFormatter


class TestPreviewFormatter:
    """Tests for PreviewFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create a formatter instance."""
        return PreviewFormatter()

    def test_formatter_initialization(self, formatter):
        """Test formatter is initialized correctly."""
        assert formatter.max_preview_lines == 20
        assert hasattr(formatter, "BOLD")
        assert hasattr(formatter, "RESET")

    def test_format_header(self, formatter):
        """Test header formatting."""
        result = formatter._format_header("Claude Code")

        assert "Claude Code" in result
        assert formatter.BOLD in result
        assert formatter.RESET in result


class TestContextFileFormatting:
    """Tests for context file formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_context_file_exists(self, formatter):
        """Test formatting existing context file."""
        ctx_file = ContextFile(
            path=Path("/test/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
            size_bytes=2048,
            line_count=50,
            file_type="project",
            content_preview="# Test\nLine 2\nLine 3",
        )

        result = formatter.format_context_files([ctx_file])

        assert "CLAUDE.md" in result
        assert "50 lines" in result
        assert "2.0KB" in result
        assert "# Test" in result

    def test_format_context_file_not_exists(self, formatter):
        """Test formatting non-existent context file."""
        ctx_file = ContextFile(
            path=Path("/test/CLAUDE.md"),
            label="CLAUDE.md",
            exists=False,
        )

        result = formatter.format_context_files([ctx_file])

        assert "CLAUDE.md" in result
        assert "not found" in result

    def test_format_context_files_multiple(self, formatter):
        """Test formatting multiple context files."""
        files = [
            ContextFile(
                path=Path("/test/CLAUDE.md"),
                label="CLAUDE.md",
                exists=True,
                size_bytes=1024,
                line_count=20,
            ),
            ContextFile(
                path=Path("/test/GEMINI.md"),
                label="GEMINI.md",
                exists=False,
            ),
        ]

        result = formatter.format_context_files(files)

        assert "CLAUDE.md" in result
        assert "GEMINI.md" in result
        assert "20 lines" in result
        assert "not found" in result

    def test_format_context_file_preview_truncated(self, formatter):
        """Test that long previews are truncated."""
        # Create content with 30 lines
        content = "\n".join([f"Line {i}" for i in range(1, 31)])

        ctx_file = ContextFile(
            path=Path("/test/file.md"),
            label="file.md",
            exists=True,
            size_bytes=1024,
            line_count=30,
            content_preview=content,
        )

        result = formatter.format_context_files([ctx_file])

        # Should only show max_preview_lines (20 by default)
        assert "Line 1" in result
        assert "Line 20" in result
        # Lines after 20 should not appear
        assert "Line 25" not in result
        assert "Line 30" not in result


class TestSessionStatsFormatting:
    """Tests for session stats formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_session_stats_basic(self, formatter):
        """Test basic session stats formatting."""
        now = datetime.now()
        stats = SessionStats(
            session_count=5,
            total_size_bytes=10 * 1024 * 1024,  # 10 MB
            last_session_time=now,
        )

        result = formatter.format_session_stats(stats)

        assert "5 sessions" in result
        assert "10.00MB" in result
        assert "just now" in result

    def test_format_session_stats_with_memory_files(self, formatter):
        """Test session stats with memory files."""
        now = datetime.now()
        mem_files = [
            MemoryFile(
                path=Path("/mem/MEMORY.md"),
                name="MEMORY.md",
                size_bytes=2048,
                last_modified=now,
            ),
            MemoryFile(
                path=Path("/mem/patterns.md"),
                name="patterns.md",
                size_bytes=1024,
                last_modified=now,
            ),
        ]

        stats = SessionStats(
            session_count=3,
            total_size_bytes=5 * 1024 * 1024,
            memory_files=mem_files,
        )

        result = formatter.format_session_stats(stats)

        assert "3 sessions" in result
        assert "MEMORY.md" in result
        assert "patterns.md" in result
        assert "2.0KB" in result
        assert "1.0KB" in result

    def test_format_session_stats_many_memory_files(self, formatter):
        """Test session stats with many memory files (should truncate)."""
        now = datetime.now()
        # Create 10 memory files
        mem_files = [
            MemoryFile(
                path=Path(f"/mem/file{i}.md"),
                name=f"file{i}.md",
                size_bytes=1024,
                last_modified=now,
            )
            for i in range(10)
        ]

        stats = SessionStats(
            session_count=1,
            total_size_bytes=1024,
            memory_files=mem_files,
        )

        result = formatter.format_session_stats(stats)

        # Should show first 5
        assert "file0.md" in result
        assert "file4.md" in result
        # Should indicate there are more
        assert "and 5 more" in result


class TestGlobalConfigFormatting:
    """Tests for global config paths formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_global_config_paths(self, formatter, tmp_path):
        """Test formatting global config paths."""
        # Create test file
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": true}')

        # Create test directory
        config_dir = tmp_path / "config_dir"
        config_dir.mkdir()

        paths = [config_file, config_dir]

        result = formatter.format_global_config_paths(paths)

        assert str(config_file) in result
        assert str(config_dir) in result
        assert "(directory)" in result

    def test_format_global_config_paths_not_exist(self, formatter):
        """Test formatting non-existent config paths."""
        paths = [Path("/nonexistent/config")]

        result = formatter.format_global_config_paths(paths)

        assert "not found" in result


class TestCustomDataFormatting:
    """Tests for custom data formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_custom_data(self, formatter):
        """Test formatting custom data."""
        data = {
            "model_version": "4.0",
            "api_key_set": True,
            "custom_setting": "value",
        }

        result = formatter.format_custom_data(data)

        assert "Model Version" in result
        assert "4.0" in result
        assert "Api Key Set" in result
        assert "True" in result

    def test_format_custom_data_empty(self, formatter):
        """Test formatting empty custom data."""
        result = formatter.format_custom_data({})

        assert result == ""


class TestGitStatusFormatting:
    """Tests for git status formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_git_status_not_repo(self, formatter):
        """Test formatting git status for non-repo."""
        status = GitStatus(is_repo=False)

        result = formatter.format_git_status(status)

        assert "Not a git repository" in result

    def test_format_git_status_clean(self, formatter):
        """Test formatting clean git status."""
        status = GitStatus(
            is_repo=True,
            is_clean=True,
            branch="main",
        )

        result = formatter.format_git_status(status)

        assert "main" in result
        assert "Clean" in result

    def test_format_git_status_dirty(self, formatter):
        """Test formatting dirty git status."""
        status = GitStatus(
            is_repo=True,
            is_clean=False,
            branch="feature",
            changed_files=["file1.py", "file2.py", "file3.py"],
            has_changes=True,
        )

        result = formatter.format_git_status(status)

        assert "feature" in result
        assert "3 files changed" in result
        assert "file1.py" in result
        assert "file2.py" in result

    def test_format_git_status_many_files(self, formatter):
        """Test formatting git status with many changed files shows all."""
        # Create 20 changed files
        changed_files = [f"file{i}.py" for i in range(20)]

        status = GitStatus(
            is_repo=True,
            is_clean=False,
            changed_files=changed_files,
        )

        result = formatter.format_git_status(status)

        # Should show all files (no truncation)
        assert "file0.py" in result
        assert "file14.py" in result
        assert "file19.py" in result
        assert "20 files changed" in result


class TestDirectoryListingFormatting:
    """Tests for directory listing formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_directory_listing_empty(self, formatter):
        """Test formatting empty directory."""
        listing = DirectoryListing()

        result = formatter.format_directory_listing(listing)

        assert "Empty directory" in result

    def test_format_directory_listing_basic(self, formatter):
        """Test formatting basic directory listing."""
        listing = DirectoryListing(
            directories=["src", "tests", "docs"],
            files=["README.md", "setup.py"],
            total_items=5,
        )

        result = formatter.format_directory_listing(listing)

        assert "src/" in result
        assert "tests/" in result
        assert "README.md" in result
        assert "setup.py" in result

    def test_format_directory_listing_many_items(self, formatter):
        """Test formatting directory with many items shows all."""
        # Create 30 directories
        directories = [f"dir{i}" for i in range(30)]

        listing = DirectoryListing(
            directories=directories,
            files=[],
            total_items=30,
        )

        result = formatter.format_directory_listing(listing)

        # Should show all items (no truncation)
        assert "dir0/" in result
        assert "dir19/" in result
        assert "dir29/" in result


class TestProviderPreviewFormatting:
    """Tests for complete provider preview formatting."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_provider_preview_full(self, formatter):
        """Test formatting complete provider preview with all sections."""
        now = datetime.now()

        ctx_file = ContextFile(
            path=Path("/test/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
            size_bytes=2048,
            line_count=50,
        )

        stats = SessionStats(
            session_count=5,
            total_size_bytes=10 * 1024 * 1024,
            last_session_time=now,
        )

        data = ProviderPreviewData(
            provider_name="Claude Code",
            context_files=[ctx_file],
            session_stats=stats,
            global_config_paths=[Path.home() / ".claude"],
            custom_data={"version": "1.0"},
        )

        result = formatter.format_complete_preview(Path("/test"), data)

        # Check sections rendered in per-project preview
        assert "Claude Code" in result
        assert "CLAUDE.md" in result
        assert "5 sessions" in result
        # Note: global_config_paths and custom_data are rendered
        # on the scan root panel, not in format_complete_preview()

    def test_format_provider_preview_minimal(self, formatter):
        """Test formatting minimal provider preview."""
        data = ProviderPreviewData(
            provider_name="Test Provider",
            context_files=[],
        )

        result = formatter.format_complete_preview(Path("/test"), data)

        # Should at least have header
        assert "Test Provider" in result


class TestHelperMethods:
    """Tests for helper formatting methods."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    @pytest.mark.parametrize(
        "delta,expected_fragment",
        [
            (timedelta(0), "just now"),
            (timedelta(minutes=5), "5 minute"),
            (timedelta(hours=3), "3 hour"),
            (timedelta(days=2), "2 day"),
        ],
        ids=["just_now", "minutes", "hours", "days"],
    )
    def test_format_relative_time(self, formatter, delta, expected_fragment):
        """Test relative time formatting for various deltas."""
        time = datetime.now() - delta
        result = formatter._format_relative_time(time)
        assert expected_fragment in result

    @pytest.mark.parametrize(
        "size,expected",
        [
            (512, "512B"),
            (2048, "2.0KB"),
            (5 * 1024 * 1024, "5.0MB"),
            (2 * 1024 * 1024 * 1024, "2.0GB"),
        ],
        ids=["bytes", "kilobytes", "megabytes", "gigabytes"],
    )
    def test_humanize_size(self, formatter, size, expected):
        """Test humanizing various byte sizes."""
        assert expected in formatter._humanize_size(size)


class TestProviderContextSection:
    """Tests for _format_provider_context_section with dynamic provider name."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_provider_context_with_custom_name(self, formatter):
        """Test that provider context section uses dynamic provider name."""
        provider_context = GlobalFiles(
            files=[Path("/home/user/.gemini/config.md")],
            common_root="~/.gemini",
            by_category={
                "📋 Rule: Gemini provider instructions": [
                    Path("/home/user/.gemini/config.md")
                ]
            },
        )

        result = formatter._format_provider_context_section(provider_context, "Gemini")

        assert "Gemini Context" in result
        assert "Claude Context" not in result

    def test_format_provider_context_default_name(self, formatter):
        """Test provider context section with default provider name."""
        provider_context = GlobalFiles(
            files=[Path("/home/user/.claude/skills/test.md")],
            common_root="~/.claude",
            by_category={
                "🔧 Skill: Custom capabilities and tools": [
                    Path("/home/user/.claude/skills/test.md")
                ]
            },
        )

        result = formatter._format_provider_context_section(provider_context)

        assert "Provider Context" in result

    def test_format_provider_context_claude_name(self, formatter):
        """Test provider context section with Claude Code name."""
        provider_context = GlobalFiles(
            files=[Path("/home/user/.claude/skills/test.md")],
            common_root="~/.claude",
            by_category={
                "🔧 Skill: Custom capabilities and tools": [
                    Path("/home/user/.claude/skills/test.md")
                ]
            },
        )

        result = formatter._format_provider_context_section(
            provider_context, "Claude Code"
        )

        assert "Claude Code Context" in result


class TestPluginsSection:
    """Tests for _format_plugins_section marketplace plugin summary."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_format_plugins_multiple_capabilities(self, formatter):
        """Test compact plugin summary shows plugin names and total count."""
        marketplace = MarketplaceInfo(
            name="claude-plugins-official",
            plugins=[
                MarketplacePlugin(
                    name="hookify",
                    description="Hook management",
                    commands=["hookify", "configure", "list"],
                    agents=["conversation-analyzer"],
                    skills=["writing-rules"],
                    has_hooks=True,
                ),
                MarketplacePlugin(
                    name="code-review",
                    description="Code review",
                    commands=["code-review"],
                    agents=["code-reviewer"],
                ),
                MarketplacePlugin(
                    name="github",
                    description="GitHub MCP",
                    source_type="external",
                    has_mcp=True,
                ),
            ],
        )

        result = formatter._format_plugins_section(marketplace)

        assert "Plugins:" in result
        assert "hookify" in result
        assert "code-review" in result
        assert "github" in result
        # 3 plugins = no "+ more" suffix
        assert "+ " not in result

    def test_format_plugins_truncation(self, formatter):
        """Test that >3 plugins shows top 3 names + N more."""
        marketplace = MarketplaceInfo(
            name="test-marketplace",
            plugins=[
                MarketplacePlugin(name="alpha", description="A"),
                MarketplacePlugin(name="beta", description="B"),
                MarketplacePlugin(name="gamma", description="C"),
                MarketplacePlugin(name="delta", description="D"),
                MarketplacePlugin(name="epsilon", description="E"),
            ],
        )

        result = formatter._format_plugins_section(marketplace)

        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        assert "+ 2 more" in result  # 5 total - 3 shown
        assert "delta" not in result
        assert "epsilon" not in result

    def test_format_plugins_minimal(self, formatter):
        """Test plugin summary with a single plugin, no '+ more'."""
        marketplace = MarketplaceInfo(
            name="test-marketplace",
            plugins=[
                MarketplacePlugin(
                    name="simple-plugin",
                    description="A simple plugin",
                ),
            ],
        )

        result = formatter._format_plugins_section(marketplace)

        assert "Plugins:" in result
        assert "simple-plugin" in result
        assert "+ " not in result

    def test_format_plugins_empty(self, formatter):
        """Test plugin summary with empty plugins list."""
        marketplace = MarketplaceInfo(
            name="test-marketplace",
            plugins=[],
        )

        result = formatter._format_plugins_section(marketplace)

        assert result == ""

    def test_format_plugins_mcp_aggregation(self, formatter):
        """Test compact summary with 7 MCP plugins shows top 3 + 4 more."""
        marketplace = MarketplaceInfo(
            name="claude-plugins-official",
            plugins=[
                MarketplacePlugin(
                    name="github",
                    description="GitHub",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="slack",
                    description="Slack",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="stripe",
                    description="Stripe",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="supabase",
                    description="Supabase",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="firebase",
                    description="Firebase",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="linear",
                    description="Linear",
                    source_type="external",
                    has_mcp=True,
                ),
                MarketplacePlugin(
                    name="asana",
                    description="Asana",
                    source_type="external",
                    has_mcp=True,
                ),
            ],
        )

        result = formatter._format_plugins_section(marketplace)

        assert "github" in result
        assert "slack" in result
        assert "stripe" in result
        assert "+ 4 more" in result  # 7 total - 3 shown

    def test_format_plugins_includes_docs_link(self, formatter):
        """Test that the docs URL and /plugin hint appear in output."""
        marketplace = MarketplaceInfo(
            name="test-marketplace",
            plugins=[
                MarketplacePlugin(name="my-plugin", description="Test"),
            ],
        )

        result = formatter._format_plugins_section(marketplace)

        assert "/plugin to browse" in result
        assert "https://code.claude.com/docs/en/discover-plugins" in result

    def test_format_plugins_not_in_project_preview(self, formatter):
        """Test that plugins section does NOT appear in project preview.

        Global context (plugins, provider context, global files) is shown
        on the scan root panel, not per-project previews.
        """
        marketplace = MarketplaceInfo(
            name="claude-plugins-official",
            plugins=[
                MarketplacePlugin(
                    name="hookify", description="Hooks", commands=["hookify"]
                ),
            ],
        )

        data = ProviderPreviewData(
            provider_name="Claude Code",
            marketplace_plugins=marketplace,
        )

        result = formatter.format_complete_preview(
            project_path=Path("/test/project"),
            provider_data=data,
        )

        assert "Plugins" not in result
        assert "hookify" not in result


class TestSessionConfigFormatting:
    """Tests for _format_session_config_section."""

    @pytest.fixture
    def formatter(self):
        return PreviewFormatter()

    def test_permissions_shown(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(
            permissions_count=3,
            permissions=["Bash(npm test)", "Bash(git status)", "Bash(make build)"],
        )
        result = formatter._format_session_config_section(config)
        assert "3 auto-approved commands" in result
        assert "npm test" in result
        assert "git status" in result

    def test_permissions_truncated_over_5(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        perms = [f"Bash(cmd{i})" for i in range(8)]
        config = SessionConfig(permissions_count=8, permissions=perms)
        result = formatter._format_session_config_section(config)
        assert "8 auto-approved commands" in result
        assert "cmd0" in result
        assert "cmd4" in result
        assert "and 3 more" in result

    def test_long_permission_truncated(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        long_perm = "Bash(" + "x" * 70 + ")"
        config = SessionConfig(permissions_count=1, permissions=[long_perm])
        result = formatter._format_session_config_section(config)
        assert "..." in result

    def test_mcp_servers(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(mcp_servers=["github", "linear"])
        result = formatter._format_session_config_section(config)
        assert "MCP Servers" in result
        assert "github" in result
        assert "linear" in result

    def test_mcp_servers_truncated(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(mcp_servers=["s1", "s2", "s3", "s4", "s5"])
        result = formatter._format_session_config_section(config)
        assert "+2 more" in result

    def test_hooks_configured(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(hooks_configured=True)
        result = formatter._format_session_config_section(config)
        assert "Hooks: Configured" in result

    def test_model_shown(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(model="opus")
        result = formatter._format_session_config_section(config)
        assert "Model: opus" in result

    def test_config_file_path_relative_to_home(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        home = Path.home()
        config = SessionConfig(config_file_path=str(home / ".claude" / "settings.json"))
        result = formatter._format_session_config_section(config)
        assert "Source:" in result
        assert "~/" in result

    def test_config_file_path_absolute(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig(config_file_path="/etc/ai-launcher/config.json")
        result = formatter._format_session_config_section(config)
        assert "Source:" in result
        # Path separator varies by platform
        assert "ai-launcher" in result
        assert "config.json" in result

    def test_empty_config(self, formatter):
        from ai_launcher.core.provider_data import SessionConfig

        config = SessionConfig()
        result = formatter._format_session_config_section(config)
        assert "Session Configuration" in result
