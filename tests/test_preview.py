"""Tests for preview generation (active code paths)."""

from ai_launcher.ui.preview import build_tree_view, generate_provider_preview


def test_build_tree_view_empty():
    """Test tree view with no projects."""
    lines, mapping = build_tree_view([])
    assert lines == []
    assert mapping == {}


def test_build_tree_view_single_project(tmp_path):
    """Test tree view with a single project."""
    from ai_launcher.core.models import Project

    project = Project(
        path=tmp_path / "my-project",
        name="my-project",
        parent_path=tmp_path,
        is_git_repo=True,
        is_manual=False,
    )
    (tmp_path / "my-project").mkdir()

    lines, mapping = build_tree_view([project])
    assert len(lines) > 0
    assert any("my-project" in line for line in lines)


def test_build_tree_view_with_manual_projects(tmp_path):
    """Test tree view shows manual projects in separate section."""
    from ai_launcher.core.models import Project

    base = tmp_path / "projects"
    base.mkdir()
    (base / "repo1").mkdir()

    external = tmp_path / "external" / "manual-project"
    external.mkdir(parents=True)

    projects = [
        Project(
            path=base / "repo1",
            name="repo1",
            parent_path=base,
            is_git_repo=True,
            is_manual=False,
        ),
        Project(
            path=external,
            name="manual-project",
            parent_path=external.parent,
            is_git_repo=False,
            is_manual=True,
        ),
    ]

    lines, mapping = build_tree_view(projects, base_path=base)
    # Manual projects outside base should appear in a separate section
    assert any("Manual Projects" in line for line in lines)


def test_generate_provider_preview_invalid_provider(tmp_path):
    """Test preview with invalid provider name."""
    project_path = tmp_path / "project"
    project_path.mkdir()

    result = generate_provider_preview(project_path, "nonexistent")
    assert "not found" in result.lower()
