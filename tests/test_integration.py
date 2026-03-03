"""Integration tests for ai-launcher."""

from ai_launcher.core.config import ConfigManager
from ai_launcher.core.discovery import get_all_projects
from ai_launcher.core.models import Project


def test_full_workflow(tmp_path):
    """Test complete workflow from config to project discovery."""
    # Setup: Create config
    config_path = tmp_path / "config" / "config.toml"
    config_path.parent.mkdir(parents=True)

    manager = ConfigManager(config_path)
    config = manager._get_defaults()

    # Create project structure
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    (projects_dir / "project-a" / ".git").mkdir(parents=True)
    (projects_dir / "project-b" / ".git").mkdir(parents=True)

    config.scan.paths = [projects_dir]
    manager.save(config)

    # Load config
    loaded_config = manager.load()
    assert len(loaded_config.scan.paths) == 1

    # Get projects (no manual projects)
    all_projects = get_all_projects(
        loaded_config.scan.paths,
        loaded_config.scan.max_depth,
        loaded_config.scan.prune_dirs,
        [],
    )

    # Should find both projects
    assert len(all_projects) == 2

    # Projects should be alphabetically sorted
    assert all_projects[0].name == "project-a"
    assert all_projects[1].name == "project-b"


def test_manual_and_discovered_integration(tmp_path):
    """Test integration of manual and discovered projects."""
    # Setup directories
    discovered_dir = tmp_path / "discovered"
    manual_dir = tmp_path / "manual"

    (discovered_dir / "discovered-repo" / ".git").mkdir(parents=True)
    manual_dir.mkdir(parents=True)

    # Create manual project (as the CLI does from --manual-paths)
    manual_project = Project(
        path=manual_dir,
        name=manual_dir.name,
        parent_path=manual_dir.parent,
        is_git_repo=False,
        is_manual=True,
    )

    # Get all projects
    all_projects = get_all_projects(
        [discovered_dir],
        5,
        ["node_modules"],
        [manual_project],
    )

    # Should have both projects
    assert len(all_projects) == 2

    # One should be manual, one discovered
    manual_count = sum(1 for p in all_projects if p.is_manual)
    discovered_count = sum(1 for p in all_projects if not p.is_manual)

    assert manual_count == 1
    assert discovered_count == 1


def test_error_recovery_config(tmp_path):
    """Test that config system recovers from corrupted files."""
    config_path = tmp_path / "config.toml"

    # Create corrupted config
    config_path.write_text("this is not valid toml [[[")

    # ConfigManager should recover gracefully with defaults
    manager = ConfigManager(config_path)
    config = manager.load()

    # Should get valid defaults
    assert config.scan.max_depth == 5
    assert config.scan.paths == []


def test_empty_config_workflow(tmp_path):
    """Test workflow with empty/new configuration."""
    config_path = tmp_path / "config.toml"
    manager = ConfigManager(config_path)

    # Load non-existent config (should get defaults)
    config = manager.load()

    assert config.scan.paths == []
    assert config.scan.max_depth == 5

    # With empty scan paths, should get empty project list
    all_projects = get_all_projects(
        config.scan.paths,
        config.scan.max_depth,
        config.scan.prune_dirs,
        [],
    )

    assert all_projects == []
