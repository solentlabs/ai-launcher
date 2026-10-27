"""Tests for project discovery."""

from pathlib import Path

from ai_launcher.core.discovery import get_all_projects, scan_for_git_repos


def test_scan_for_git_repos(tmp_project_dir):
    """Test git repository scanning."""
    projects = scan_for_git_repos(
        [tmp_project_dir],
        max_depth=5,
        prune_dirs=["node_modules", ".cache"],
    )

    # Should find project1, project2, and work/project3
    assert len(projects) == 3

    # All should be git repos
    assert all(p.is_git_repo for p in projects)

    # None should be manual
    assert all(not p.is_manual for p in projects)

    # Should not include node_modules or .cache
    paths = {str(p.path) for p in projects}
    assert not any("node_modules" in p for p in paths)
    assert not any(".cache" in p for p in paths)


def test_scan_respects_max_depth(tmp_path):
    """Test that max_depth is respected."""
    # Create deep directory structure
    deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"
    (deep_path / ".git").mkdir(parents=True)

    # Scan with max_depth=3
    projects = scan_for_git_repos([tmp_path], max_depth=3, prune_dirs=[])

    # Should not find the deep repo
    assert len(projects) == 0

    # Scan with max_depth=5
    projects = scan_for_git_repos([tmp_path], max_depth=5, prune_dirs=[])

    # Should find it now
    assert len(projects) == 1


def test_get_all_projects_removes_duplicates(tmp_project_dir):
    """Test that manual and discovered projects are deduplicated."""
    from ai_launcher.core.models import Project

    # Create a manual project that overlaps with a discovered one
    manual_path = (tmp_project_dir / "project1").resolve()
    manual_projects = [
        Project(
            path=manual_path,
            name=manual_path.name,
            parent_path=manual_path.parent,
            is_git_repo=True,
            is_manual=True,
        )
    ]

    all_projects = get_all_projects(
        [tmp_project_dir],
        max_depth=5,
        prune_dirs=["node_modules", ".cache"],
        manual_projects=manual_projects,
    )

    # Should have 3 unique projects (project1 appears in both but deduplicated)
    assert len(all_projects) == 3

    # The project1 entry should be marked as manual (manual takes precedence)
    project1 = next(p for p in all_projects if p.path == manual_path)
    assert project1.is_manual


def test_get_all_projects_alphabetical_sort(tmp_project_dir):
    """Test that projects are sorted alphabetically."""
    projects = get_all_projects(
        [tmp_project_dir],
        max_depth=5,
        prune_dirs=["node_modules", ".cache"],
        manual_projects=[],
    )

    # Check that projects are sorted by path
    paths = [str(p.path) for p in projects]
    assert paths == sorted(paths)


def test_scan_handles_missing_directory():
    """Test that scanning handles non-existent directories gracefully."""
    projects = scan_for_git_repos(
        [Path("/nonexistent/path")],
        max_depth=5,
        prune_dirs=[],
    )

    # Should return empty list, not crash
    assert projects == []


def test_scan_follows_symlinks(tmp_path, make_symlink):
    """Test that symlinks/junctions are followed during scanning."""
    # Create a real repo in a separate location
    real_dir = tmp_path / "real_repos" / "my-project"
    (real_dir / ".git").mkdir(parents=True)

    # Create the scan root with a symlink to the real location
    scan_root = tmp_path / "projects"
    scan_root.mkdir()
    link_target = scan_root / "linked-org"
    make_symlink(link_target, tmp_path / "real_repos", target_is_directory=True)

    projects = scan_for_git_repos([scan_root], max_depth=5, prune_dirs=[])

    assert len(projects) == 1
    assert projects[0].name == "my-project"


def test_scan_handles_symlink_cycles(tmp_path, make_symlink):
    """Test that circular symlinks don't cause infinite loops."""
    # Create a repo
    repo = tmp_path / "projects" / "repo"
    (repo / ".git").mkdir(parents=True)

    # Create a circular symlink: projects/loop -> projects
    loop = tmp_path / "projects" / "loop"
    make_symlink(loop, tmp_path / "projects", target_is_directory=True)

    projects = scan_for_git_repos([tmp_path / "projects"], max_depth=5, prune_dirs=[])

    # Should find the repo exactly once, not loop infinitely
    assert len(projects) == 1
    assert projects[0].name == "repo"


def test_scan_detects_git_file(tmp_path):
    """Test that .git files (submodules) are detected, not just .git dirs."""
    # Create a submodule-style repo where .git is a file
    repo = tmp_path / "my-submodule"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: /some/other/path")

    projects = scan_for_git_repos([tmp_path], max_depth=5, prune_dirs=[])

    assert len(projects) == 1
    assert projects[0].name == "my-submodule"


class TestSymlinksArePreserved:
    """Invariant: projects keep the path as listed; duplicates go by real path."""

    def test_a_symlinked_scan_folder_lists_projects_under_the_link(
        self, tmp_path, make_symlink
    ):
        (tmp_path / "real_projects" / "repo" / ".git").mkdir(parents=True)
        link = tmp_path / "projects"
        make_symlink(link, tmp_path / "real_projects", target_is_directory=True)

        (project,) = scan_for_git_repos([link], max_depth=5, prune_dirs=[])

        assert project.path == link / "repo"
        assert "real_projects" not in str(project.path)

    def test_the_real_folder_wins_over_a_link_to_it_whatever_the_names(
        self, tmp_path, make_symlink
    ):
        root = tmp_path / "projects"
        (root / "zzz-repo" / ".git").mkdir(parents=True)
        make_symlink(root / "aaa-alias", root / "zzz-repo", target_is_directory=True)

        (project,) = scan_for_git_repos([root], max_depth=5, prune_dirs=[])

        assert project.path == root / "zzz-repo"

    def test_the_result_does_not_depend_on_directory_order(self, tmp_path):
        root = tmp_path / "projects"
        for name in ("c", "a", "b"):
            (root / name / ".git").mkdir(parents=True)

        names = [p.name for p in scan_for_git_repos([root], max_depth=5, prune_dirs=[])]

        assert names == ["a", "b", "c"]

    def test_from_path_keeps_a_symlinked_project_as_listed(
        self, tmp_path, make_symlink
    ):
        from ai_launcher.core.models import Project

        (tmp_path / "real" / ".git").mkdir(parents=True)
        link = tmp_path / "link"
        make_symlink(link, tmp_path / "real", target_is_directory=True)

        project = Project.from_path(link, is_manual=False)

        assert project.path == link
        assert project.name == "link"
        assert project.is_git_repo is True

    def test_a_manual_symlink_and_the_scanned_real_folder_are_one_project(
        self, tmp_path, make_symlink
    ):
        from ai_launcher.core.models import Project

        root = tmp_path / "projects"
        (root / "repo" / ".git").mkdir(parents=True)
        alias = tmp_path / "shortcut"
        make_symlink(alias, root / "repo", target_is_directory=True)

        projects = get_all_projects(
            [root], 5, [], [Project.from_path(alias, is_manual=True)]
        )

        assert [p.path for p in projects] == [alias]  # the manual one wins


def test_two_manual_projects_that_are_the_same_folder_are_one(tmp_path, make_symlink):
    from ai_launcher.core.models import Project

    real = tmp_path / "repo"
    (real / ".git").mkdir(parents=True)
    alias = tmp_path / "alias"
    make_symlink(alias, real, target_is_directory=True)
    manual = [Project.from_path(alias, True), Project.from_path(real, True)]

    projects = get_all_projects([], 5, [], manual)

    assert len(projects) == 1
