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


class TestGitStatusPreview:
    """The preview reads git state without disturbing the repository."""

    @staticmethod
    def _run(project, monkeypatch, status_output):
        import subprocess
        from types import SimpleNamespace

        from ai_launcher.ui.preview import _get_git_status

        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            out = "main\n" if "rev-parse" in argv else status_output
            return SimpleNamespace(returncode=0, stdout=out)

        monkeypatch.setattr(subprocess, "run", fake)
        return _get_git_status(project), calls

    def test_never_takes_the_index_lock(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()

        _, calls = self._run(tmp_path, monkeypatch, "")

        status = next(c for c in calls if "status" in c)
        assert status[:2] == ["git", "--no-optional-locks"]

    def test_keeps_the_staged_and_unstaged_columns(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        output = " M unstaged.py\nM  staged.py\nMM both.py\n?? new.txt\n"

        status, _ = self._run(tmp_path, monkeypatch, output)

        assert status.changed_files == [
            " M unstaged.py",
            "M  staged.py",
            "MM both.py",
            "?? new.txt",
        ]
        assert status.has_changes is True

    def test_clean_tree(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()

        status, _ = self._run(tmp_path, monkeypatch, "\n")

        assert status.is_clean is True and status.changed_files == []


def test_the_context_preview_never_takes_the_index_lock(tmp_path, monkeypatch, capsys):
    import subprocess
    from types import SimpleNamespace

    from ai_launcher.ui import _context_preview

    seen = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kw: (
            seen.append(argv) or SimpleNamespace(returncode=0, stdout="")
        ),
    )
    (tmp_path / ".git").mkdir()

    _context_preview.show_project_context(tmp_path)

    assert any(a[:2] == ["git", "--no-optional-locks"] for a in seen)


def test_build_tree_view_shows_a_dimmed_folder_row_for_a_nested_project(tmp_path):
    from ai_launcher.core.models import Project

    base = tmp_path / "projects"
    repo = base / "org" / "repo"
    repo.mkdir(parents=True)
    project = Project(repo, "repo", repo.parent, True, False)

    lines, mapping = build_tree_view([project], base)

    folder = next(line for line in lines if "org" in line and "repo" not in line)
    assert folder.startswith(f"{base / 'org'}\t\t")
    assert "\033[2m" in folder and "📁 org/" in folder  # a dimmed folder row
    assert any(p is project for p in mapping.values())
