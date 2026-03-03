"""Tests for context preview helper.

Author: Solent Labs™
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.ui._context_preview import (
    main,
    show_project_context,
    show_provider_context,
)


class TestShowProjectContext:
    """Tests for show_project_context()."""

    def test_nonexistent_path(self, capsys, tmp_path):
        show_project_context(tmp_path / "nonexistent")
        captured = capsys.readouterr()
        assert "Project not found" in captured.out

    def test_basic_project_info(self, capsys, tmp_path):
        show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert tmp_path.name in captured.out
        assert "Path:" in captured.out
        assert "Directory" in captured.out

    def test_git_repo_type(self, capsys, tmp_path):
        (tmp_path / ".git").mkdir()
        show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "Git repository" in captured.out

    def test_context_files_shown(self, capsys, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Claude\n")
        (tmp_path / "README.md").write_text("# Readme\n")

        show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "CONTEXT FILES" in captured.out
        assert "CLAUDE.md" in captured.out
        assert "README.md" in captured.out

    def test_missing_context_files(self, capsys, tmp_path):
        show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "CLAUDE.md" in captured.out  # Listed as missing

    def test_no_context_files_message(self, capsys, tmp_path):
        show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "No context files found" in captured.out

    def test_git_status_clean(self, capsys, tmp_path):
        (tmp_path / ".git").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "Working tree clean" in captured.out

    def test_git_status_changes(self, capsys, tmp_path):
        (tmp_path / ".git").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=" M file.py\n M other.py\n"
            )
            show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "file.py" in captured.out

    def test_git_status_truncated(self, capsys, tmp_path):
        (tmp_path / ".git").mkdir()
        lines = "\n".join(f" M file{i}.py" for i in range(15))
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=lines)
            show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "and more changes" in captured.out

    def test_git_status_error(self, capsys, tmp_path):
        (tmp_path / ".git").mkdir()
        with patch("subprocess.run", side_effect=Exception("fail")):
            show_project_context(tmp_path)
        captured = capsys.readouterr()
        assert "Could not get git status" in captured.out


class TestShowProviderContext:
    """Tests for show_provider_context()."""

    def test_provider_not_found(self, capsys):
        with patch(
            "ai_launcher.ui._context_preview.ProviderDiscovery"
        ) as MockDiscovery:
            mock_instance = MockDiscovery.return_value
            mock_instance.get_provider_by_name.return_value = None

            show_provider_context("unknown")
        captured = capsys.readouterr()
        assert "Provider not found" in captured.out

    def test_not_installed_provider(self, capsys):
        from ai_launcher.core.models import ProviderInfo

        provider = ProviderInfo(
            name="Test Provider",
            command="testcmd",
            context=None,
            install_url="https://example.com",
        )
        with patch(
            "ai_launcher.ui._context_preview.ProviderDiscovery"
        ) as MockDiscovery:
            mock_instance = MockDiscovery.return_value
            mock_instance.get_provider_by_name.return_value = provider

            show_provider_context("test")
        captured = capsys.readouterr()
        assert "Not installed" in captured.out
        assert "testcmd" in captured.out

    def test_installed_provider(self, capsys, tmp_path):
        from ai_launcher.core.models import ProviderContext, ProviderInfo

        context = ProviderContext(
            name="Test",
            version="1.0.0",
            installed=True,
            executable_path=Path("/usr/bin/testcmd"),
            global_config=[tmp_path / "config"],
            file_count=3,
            total_size=1024,
        )
        provider = ProviderInfo(
            name="Test Provider",
            command="testcmd",
            context=context,
        )
        with patch(
            "ai_launcher.ui._context_preview.ProviderDiscovery"
        ) as MockDiscovery:
            mock_instance = MockDiscovery.return_value
            mock_instance.get_provider_by_name.return_value = provider

            show_provider_context("test")
        captured = capsys.readouterr()
        assert "Installed" in captured.out
        assert "1.0.0" in captured.out
        assert "3 files" in captured.out

    def test_installed_provider_with_existing_config(self, capsys, tmp_path):
        from ai_launcher.core.models import ProviderContext, ProviderInfo

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        context = ProviderContext(
            name="Test",
            version="1.0.0",
            installed=True,
            global_config=[config_dir],
            file_count=0,
            total_size=0,
        )
        provider = ProviderInfo(
            name="Test Provider",
            command="testcmd",
            context=context,
        )
        with patch(
            "ai_launcher.ui._context_preview.ProviderDiscovery"
        ) as MockDiscovery:
            mock_instance = MockDiscovery.return_value
            mock_instance.get_provider_by_name.return_value = provider

            show_provider_context("test")
        captured = capsys.readouterr()
        assert "directory" in captured.out


class TestMain:
    """Tests for main() entry point."""

    def test_no_args(self, capsys):
        with patch.object(sys, "argv", ["_context_preview.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_provider_item(self, capsys):
        with patch.object(
            sys, "argv", ["_context_preview.py", "PROVIDER:test-provider"]
        ):
            with patch(
                "ai_launcher.ui._context_preview.show_provider_context"
            ) as mock_show:
                main()
                mock_show.assert_called_once_with("test-provider")

    def test_project_item(self, capsys, tmp_path):
        with patch.object(sys, "argv", ["_context_preview.py", f"PROJECT:{tmp_path}"]):
            with patch(
                "ai_launcher.ui._context_preview.show_project_context"
            ) as mock_show:
                main()
                mock_show.assert_called_once_with(Path(str(tmp_path)))

    def test_header_item(self, capsys):
        with patch.object(sys, "argv", ["_context_preview.py", "__HEADER__:title"]):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_spacer_item(self, capsys):
        with patch.object(sys, "argv", ["_context_preview.py", "__SPACER__"]):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_info_item(self, capsys):
        with patch.object(sys, "argv", ["_context_preview.py", "__INFO__:something"]):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_unknown_item(self, capsys):
        with patch.object(sys, "argv", ["_context_preview.py", "something_else"]):
            main()
        captured = capsys.readouterr()
        assert "Unknown item type" in captured.out
