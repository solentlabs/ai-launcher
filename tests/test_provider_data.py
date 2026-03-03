"""Tests for provider data structures.

Author: Solent Labs™
Created: 2026-02-12
"""

from datetime import datetime
from pathlib import Path

from ai_launcher.core.provider_data import (
    ContextFile,
    DirectoryListing,
    GitStatus,
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


class TestContextFile:
    """Tests for ContextFile dataclass."""

    def test_context_file_creation(self):
        """Test creating a context file."""
        ctx = ContextFile(
            path=Path("/home/user/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
            size_bytes=1024,
            line_count=50,
            file_type="personal",
        )

        assert ctx.path == Path("/home/user/CLAUDE.md")
        assert ctx.label == "CLAUDE.md"
        assert ctx.exists is True
        assert ctx.size_bytes == 1024
        assert ctx.line_count == 50
        assert ctx.file_type == "personal"

    def test_context_file_with_preview(self):
        """Test context file with content preview."""
        ctx = ContextFile(
            path=Path("/project/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
            content_preview="# Project\nTest content",
        )

        assert ctx.content_preview == "# Project\nTest content"

    def test_context_file_defaults(self):
        """Test context file default values."""
        ctx = ContextFile(
            path=Path("/test.md"),
            label="test.md",
            exists=False,
        )

        assert ctx.size_bytes == 0
        assert ctx.line_count == 0
        assert ctx.file_type == "unknown"
        assert ctx.content_preview is None


class TestMemoryFile:
    """Tests for MemoryFile dataclass."""

    def test_memory_file_creation(self):
        """Test creating a memory file."""
        now = datetime.now()
        mem = MemoryFile(
            path=Path("/memory/MEMORY.md"),
            name="MEMORY.md",
            size_bytes=2048,
            last_modified=now,
        )

        assert mem.path == Path("/memory/MEMORY.md")
        assert mem.name == "MEMORY.md"
        assert mem.size_bytes == 2048
        assert mem.last_modified == now


class TestSessionStats:
    """Tests for SessionStats dataclass."""

    def test_session_stats_creation(self):
        """Test creating session stats."""
        now = datetime.now()
        mem_file = MemoryFile(
            path=Path("/memory.md"),
            name="MEMORY.md",
            size_bytes=1024,
            last_modified=now,
        )

        stats = SessionStats(
            session_count=5,
            total_size_bytes=10240,
            last_session_time=now,
            memory_files=[mem_file],
            session_dir=Path("/sessions"),
        )

        assert stats.session_count == 5
        assert stats.total_size_bytes == 10240
        assert stats.last_session_time == now
        assert len(stats.memory_files) == 1
        assert stats.session_dir == Path("/sessions")

    def test_session_stats_defaults(self):
        """Test session stats default values."""
        stats = SessionStats(
            session_count=0,
            total_size_bytes=0,
        )

        assert stats.last_session_time is None
        assert stats.memory_files == []
        assert stats.session_dir is None


class TestProviderPreviewData:
    """Tests for ProviderPreviewData dataclass."""

    def test_provider_preview_data_creation(self):
        """Test creating provider preview data."""
        ctx_file = ContextFile(
            path=Path("/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
        )

        data = ProviderPreviewData(
            provider_name="Claude Code",
            context_files=[ctx_file],
            global_config_paths=[Path("~/.claude")],
        )

        assert data.provider_name == "Claude Code"
        assert len(data.context_files) == 1
        assert len(data.global_config_paths) == 1

    def test_provider_preview_data_defaults(self):
        """Test provider preview data defaults."""
        data = ProviderPreviewData(provider_name="Test Provider")

        assert data.context_files == []
        assert data.session_stats is None
        assert data.global_config_paths == []
        assert data.custom_data == {}

    def test_provider_preview_data_full(self):
        """Test provider preview data with all fields."""
        ctx_file = ContextFile(
            path=Path("/CLAUDE.md"),
            label="CLAUDE.md",
            exists=True,
        )

        now = datetime.now()
        stats = SessionStats(
            session_count=3,
            total_size_bytes=5120,
            last_session_time=now,
        )

        data = ProviderPreviewData(
            provider_name="Claude Code",
            context_files=[ctx_file],
            session_stats=stats,
            global_config_paths=[Path("~/.claude")],
            custom_data={"key": "value"},
        )

        assert data.session_stats == stats
        assert data.custom_data == {"key": "value"}


class TestGitStatus:
    """Tests for GitStatus dataclass."""

    def test_git_status_repo_clean(self):
        """Test git status for clean repo."""
        status = GitStatus(
            is_repo=True,
            is_clean=True,
            branch="main",
        )

        assert status.is_repo is True
        assert status.is_clean is True
        assert status.branch == "main"
        assert status.has_changes is False

    def test_git_status_repo_dirty(self):
        """Test git status for repo with changes."""
        status = GitStatus(
            is_repo=True,
            is_clean=False,
            changed_files=["file1.py", "file2.py"],
            branch="feature",
            has_changes=True,
        )

        assert status.is_clean is False
        assert len(status.changed_files) == 2
        assert status.has_changes is True

    def test_git_status_not_repo(self):
        """Test git status for non-repo."""
        status = GitStatus(is_repo=False)

        assert status.is_repo is False
        assert status.is_clean is True  # Default
        assert status.changed_files == []


class TestDirectoryListing:
    """Tests for DirectoryListing dataclass."""

    def test_directory_listing(self):
        """Test directory listing."""
        listing = DirectoryListing(
            directories=["src", "tests", "docs"],
            files=["README.md", "setup.py"],
            total_items=5,
        )

        assert len(listing.directories) == 3
        assert len(listing.files) == 2
        assert listing.total_items == 5

    def test_directory_listing_empty(self):
        """Test empty directory listing."""
        listing = DirectoryListing()

        assert listing.directories == []
        assert listing.files == []
        assert listing.total_items == 0


class TestMemoryInfo:
    """Tests for MemoryInfo dataclass."""

    def test_memory_info_defaults(self):
        """Test MemoryInfo default values."""
        info = MemoryInfo()

        assert info.personal_memory is None
        assert info.personal_lines == 0
        assert info.project_memory is None
        assert info.project_lines == 0

    def test_memory_info_with_data(self):
        """Test MemoryInfo with actual data."""
        info = MemoryInfo(
            personal_memory=Path(
                "/home/user/.claude/projects/-home-user/memory/MEMORY.md"
            ),
            personal_lines=42,
            project_memory=Path(
                "/home/user/.claude/projects/-home-user-project/memory/MEMORY.md"
            ),
            project_lines=15,
        )

        assert info.personal_memory is not None
        assert info.personal_lines == 42
        assert info.project_memory is not None
        assert info.project_lines == 15


class TestSkillInfo:
    """Tests for SkillInfo dataclass."""

    def test_skill_info_creation(self):
        """Test creating a SkillInfo."""
        skill = SkillInfo(
            name="commit",
            path=Path("/home/user/.claude/skills/commit/SKILL.md"),
        )

        assert skill.name == "commit"
        assert skill.path is not None

    def test_skill_info_no_path(self):
        """Test SkillInfo without path."""
        skill = SkillInfo(name="review")

        assert skill.name == "review"
        assert skill.path is None


class TestGlobalContextSummary:
    """Tests for GlobalContextSummary dataclass."""

    def test_global_context_summary_defaults(self):
        """Test GlobalContextSummary default values."""
        summary = GlobalContextSummary()

        assert summary.total_files == 0
        assert summary.categories == {}
        assert summary.file_list == []

    def test_global_context_summary_with_data(self):
        """Test GlobalContextSummary with data."""
        files = [Path("/a/b.md"), Path("/c/d.md")]
        summary = GlobalContextSummary(
            total_files=2,
            categories={"Plans": 1, "Memories (all projects)": 1},
            file_list=files,
        )

        assert summary.total_files == 2
        assert len(summary.categories) == 2
        assert summary.categories["Plans"] == 1
        assert len(summary.file_list) == 2


class TestProviderPreviewDataExpanded:
    """Tests for expanded ProviderPreviewData fields."""

    def test_provider_preview_data_new_fields_defaults(self):
        """Test that new fields have correct defaults."""
        data = ProviderPreviewData(provider_name="Test")

        assert data.session_config is None
        assert data.memory_info is None
        assert data.skills == []
        assert data.global_context_summary is None

    def test_provider_preview_data_with_new_fields(self):
        """Test ProviderPreviewData with all new fields populated."""
        config = SessionConfig(
            permissions=["Bash(git *)"],
            permissions_count=1,
            mcp_servers=["filesystem"],
            hooks_configured=True,
            model="opus",
        )
        memory = MemoryInfo(
            personal_lines=10,
            project_lines=20,
        )
        skills = [SkillInfo(name="commit"), SkillInfo(name="review")]
        global_ctx = GlobalContextSummary(total_files=5, categories={"Plans": 5})

        data = ProviderPreviewData(
            provider_name="Claude Code",
            session_config=config,
            memory_info=memory,
            skills=skills,
            global_context_summary=global_ctx,
        )

        assert data.session_config is not None
        assert data.session_config.permissions_count == 1
        assert data.memory_info is not None
        assert data.memory_info.project_lines == 20
        assert len(data.skills) == 2
        assert data.global_context_summary is not None
        assert data.global_context_summary.total_files == 5


class TestMarketplacePlugin:
    """Tests for MarketplacePlugin dataclass."""

    def test_marketplace_plugin_creation(self):
        """Test creating a marketplace plugin with all fields."""
        plugin = MarketplacePlugin(
            name="hookify",
            description="Create hooks to prevent unwanted behaviors",
            source_type="internal",
            commands=["hookify", "configure"],
            agents=["conversation-analyzer"],
            skills=["writing-rules"],
            has_hooks=True,
            has_mcp=False,
        )

        assert plugin.name == "hookify"
        assert plugin.description == "Create hooks to prevent unwanted behaviors"
        assert plugin.source_type == "internal"
        assert plugin.commands == ["hookify", "configure"]
        assert plugin.agents == ["conversation-analyzer"]
        assert plugin.skills == ["writing-rules"]
        assert plugin.has_hooks is True
        assert plugin.has_mcp is False

    def test_marketplace_plugin_defaults(self):
        """Test MarketplacePlugin default values."""
        plugin = MarketplacePlugin(
            name="test-plugin",
            description="A test plugin",
        )

        assert plugin.source_type == "internal"
        assert plugin.commands == []
        assert plugin.agents == []
        assert plugin.skills == []
        assert plugin.has_hooks is False
        assert plugin.has_mcp is False

    def test_marketplace_plugin_external(self):
        """Test external marketplace plugin."""
        plugin = MarketplacePlugin(
            name="github",
            description="GitHub MCP server",
            source_type="external",
            has_mcp=True,
        )

        assert plugin.source_type == "external"
        assert plugin.has_mcp is True


class TestMarketplaceInfo:
    """Tests for MarketplaceInfo dataclass."""

    def test_marketplace_info_creation(self):
        """Test creating marketplace info with plugins."""
        plugins = [
            MarketplacePlugin(name="hookify", description="Hook management"),
            MarketplacePlugin(
                name="github",
                description="GitHub MCP",
                source_type="external",
                has_mcp=True,
            ),
        ]

        info = MarketplaceInfo(name="claude-plugins-official", plugins=plugins)

        assert info.name == "claude-plugins-official"
        assert len(info.plugins) == 2
        assert info.plugins[0].name == "hookify"
        assert info.plugins[1].has_mcp is True

    def test_marketplace_info_defaults(self):
        """Test MarketplaceInfo default values."""
        info = MarketplaceInfo(name="test-marketplace")

        assert info.name == "test-marketplace"
        assert info.plugins == []

    def test_provider_preview_data_marketplace_default(self):
        """Test that marketplace_plugins defaults to None on ProviderPreviewData."""
        data = ProviderPreviewData(provider_name="Test")

        assert data.marketplace_plugins is None

    def test_provider_preview_data_with_marketplace(self):
        """Test ProviderPreviewData with marketplace_plugins set."""
        marketplace = MarketplaceInfo(
            name="claude-plugins-official",
            plugins=[MarketplacePlugin(name="hookify", description="Hooks")],
        )

        data = ProviderPreviewData(
            provider_name="Claude Code",
            marketplace_plugins=marketplace,
        )

        assert data.marketplace_plugins is not None
        assert data.marketplace_plugins.name == "claude-plugins-official"
        assert len(data.marketplace_plugins.plugins) == 1
