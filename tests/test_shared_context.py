"""Tests for shared context UI.

Author: Solent Labs™
"""

from unittest.mock import MagicMock, patch

from ai_launcher.ui.shared_context import (
    _find_markdown_files,
    add_global_files,
    clear_screen,
    remove_global_files,
)


class TestFindMarkdownFiles:
    """Tests for _find_markdown_files()."""

    def test_finds_md_files(self, tmp_path):
        scan = tmp_path / "projects"
        scan.mkdir()
        (scan / "README.md").write_text("# Readme")
        (scan / "STANDARDS.md").write_text("# Standards")
        (scan / "code.py").write_text("print('hi')")

        with patch("pathlib.Path.home", return_value=tmp_path):
            files = _find_markdown_files([scan])

        md_names = {f.name for f in files}
        assert "README.md" in md_names
        assert "STANDARDS.md" in md_names
        assert "code.py" not in md_names

    def test_skips_node_modules(self, tmp_path):
        scan = tmp_path / "projects"
        scan.mkdir()
        nm = scan / "node_modules"
        nm.mkdir()
        (nm / "pkg.md").write_text("# Module")

        with patch("pathlib.Path.home", return_value=tmp_path):
            files = _find_markdown_files([scan])

        names = {f.name for f in files}
        assert "pkg.md" not in names

    def test_skips_git_dirs(self, tmp_path):
        scan = tmp_path / "projects"
        scan.mkdir()
        git_dir = scan / ".git"
        git_dir.mkdir()
        (git_dir / "notes.md").write_text("git")

        with patch("pathlib.Path.home", return_value=tmp_path):
            files = _find_markdown_files([scan])

        names = {f.name for f in files}
        assert "notes.md" not in names

    def test_depth_limit(self, tmp_path):
        scan = tmp_path / "projects"
        # Create deeply nested .md file (depth > 5)
        deep = scan
        for i in range(7):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        (deep / "deep.md").write_text("deep")

        # Create shallow .md file
        (scan / "shallow.md").write_text("shallow")

        with patch("pathlib.Path.home", return_value=tmp_path):
            files = _find_markdown_files([scan])

        names = {f.name for f in files}
        assert "shallow.md" in names
        assert "deep.md" not in names

    def test_nonexistent_path(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            files = _find_markdown_files([tmp_path / "nonexistent"])
        assert files == []

    def test_default_scan_paths(self, tmp_path):
        """When no scan_paths provided, uses default locations."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            # Create .claude dir with a file
            claude_dir = tmp_path / ".claude"
            claude_dir.mkdir()
            (claude_dir / "notes.md").write_text("notes")

            files = _find_markdown_files()

        names = {f.name for f in files}
        assert "notes.md" in names


class TestAddGlobalFiles:
    """Tests for add_global_files()."""

    def test_no_md_files_found(self, tmp_path, capsys):
        config_manager = MagicMock()
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch(
                "ai_launcher.ui.shared_context._find_markdown_files", return_value=[]
            ):
                with patch("builtins.input", return_value=""):
                    result = add_global_files(config_manager, [tmp_path])

        assert result is False
        captured = capsys.readouterr()
        assert "No markdown files found" in captured.out

    def test_all_files_already_configured(self, tmp_path, capsys):
        config = MagicMock()
        config.context.global_files = ["~/projects/STANDARDS.md"]
        config_manager = MagicMock()
        config_manager.load.return_value = config

        md_file = tmp_path / "projects" / "STANDARDS.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("standards")

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch(
                "ai_launcher.ui.shared_context._find_markdown_files",
                return_value=[md_file],
            ):
                with patch("builtins.input", return_value=""):
                    result = add_global_files(config_manager, [tmp_path])

        assert result is False

    def test_fzf_not_found(self, tmp_path, capsys):
        config = MagicMock()
        config.context.global_files = []
        config_manager = MagicMock()
        config_manager.load.return_value = config

        md_file = tmp_path / "STANDARDS.md"
        md_file.write_text("standards")

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch(
                "ai_launcher.ui.shared_context._find_markdown_files",
                return_value=[md_file],
            ):
                with patch("subprocess.Popen", side_effect=FileNotFoundError):
                    with patch("builtins.input", return_value=""):
                        result = add_global_files(config_manager, [tmp_path])

        assert result is False
        captured = capsys.readouterr()
        assert "fzf not found" in captured.out

    def test_fzf_cancelled(self, tmp_path):
        config = MagicMock()
        config.context.global_files = []
        config_manager = MagicMock()
        config_manager.load.return_value = config

        md_file = tmp_path / "STANDARDS.md"
        md_file.write_text("standards")

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 1

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch(
                "ai_launcher.ui.shared_context._find_markdown_files",
                return_value=[md_file],
            ):
                with patch("subprocess.Popen", return_value=mock_process):
                    result = add_global_files(config_manager, [tmp_path])

        assert result is False


class TestRemoveGlobalFiles:
    """Tests for remove_global_files()."""

    def test_no_files_configured(self, tmp_path, capsys):
        config = MagicMock()
        config.context.global_files = []
        config_manager = MagicMock()
        config_manager.load.return_value = config

        with patch("builtins.input", return_value=""):
            result = remove_global_files(config_manager)

        assert result is False
        captured = capsys.readouterr()
        assert "No global files configured" in captured.out

    def test_fzf_not_found(self, tmp_path, capsys):
        config = MagicMock()
        config.context.global_files = ["~/projects/STANDARDS.md"]
        config_manager = MagicMock()
        config_manager.load.return_value = config

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            with patch("builtins.input", return_value=""):
                result = remove_global_files(config_manager)

        assert result is False
        captured = capsys.readouterr()
        assert "fzf not found" in captured.out

    def test_fzf_cancelled(self, tmp_path):
        config = MagicMock()
        config.context.global_files = ["~/projects/STANDARDS.md"]
        config_manager = MagicMock()
        config_manager.load.return_value = config

        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 1

        with patch("subprocess.Popen", return_value=mock_process):
            result = remove_global_files(config_manager)

        assert result is False


class TestClearScreen:
    """Tests for clear_screen()."""

    def test_prints_escape_sequence(self, capsys):
        clear_screen()
        captured = capsys.readouterr()
        assert "\033[2J" in captured.out
