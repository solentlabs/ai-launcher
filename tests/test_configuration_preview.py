"""Tests for configuration preview output."""

import re


def strip_ansi(text):
    """Remove ANSI escape codes from text."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def test_configuration_preview_basic(tmp_path, monkeypatch, capsys):
    """Test basic configuration preview output."""
    monkeypatch.setenv("AI_LAUNCHER_SCAN_PATHS", str(tmp_path))
    monkeypatch.setenv("AI_LAUNCHER_PROVIDER", "claude-code")

    from ai_launcher.ui._preview_helper import show_configuration_preview

    show_configuration_preview()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    assert "Configuration" in output
    assert "Provider:" in output
    assert "claude-code" in output
    assert "Project Paths" in output
    assert "Global Files" in output
    assert "Available Options" in output
    assert "Current command:" in output
    assert "ai-launcher v" in output


def test_configuration_preview_with_global_files(monkeypatch, capsys, tmp_path):
    """Test configuration preview with global files."""
    file1 = tmp_path / "RULES.md"
    file2 = tmp_path / "STANDARDS.md"

    monkeypatch.setenv("AI_LAUNCHER_SCAN_PATHS", str(tmp_path))
    monkeypatch.setenv("AI_LAUNCHER_PROVIDER", "claude-code")
    monkeypatch.setenv("AI_LAUNCHER_GLOBAL_FILES", f"{file1},{file2}")

    from ai_launcher.ui._preview_helper import show_configuration_preview

    show_configuration_preview()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    assert "Configured: 2" in output
    assert "--global-files" in output


def test_configuration_preview_with_manual_paths(monkeypatch, capsys, tmp_path):
    """Test configuration preview with manual paths."""
    path1 = tmp_path / "project1"
    path2 = tmp_path / "project2"

    monkeypatch.setenv("AI_LAUNCHER_SCAN_PATHS", str(tmp_path))
    monkeypatch.setenv("AI_LAUNCHER_PROVIDER", "claude-code")
    monkeypatch.setenv("AI_LAUNCHER_MANUAL_PATHS", f"{path1},{path2}")

    from ai_launcher.ui._preview_helper import show_configuration_preview

    show_configuration_preview()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    assert "Manual paths: 2" in output
    assert "--manual-paths" in output


def test_configuration_preview_indentation(monkeypatch, capsys, tmp_path):
    """Test that indentation is consistent across sections."""
    monkeypatch.setenv("AI_LAUNCHER_SCAN_PATHS", str(tmp_path))
    monkeypatch.setenv("AI_LAUNCHER_PROVIDER", "claude-code")

    from ai_launcher.ui._preview_helper import show_configuration_preview

    show_configuration_preview()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)
    lines = output.split("\n")

    # Check that subsection labels have 3-space indent
    context_lines = [
        l for l in lines if "Context:" in l and l.strip().startswith("Context:")
    ]
    assert any(l.startswith("   ") for l in context_lines), (
        "Context should have 3-space indent"
    )

    # Check that option descriptions have 5-space indent
    global_files_lines = [
        l for l in lines if "--global-files" in l and "Load files" in l
    ]
    assert any(l.startswith("     --global-files") for l in global_files_lines), (
        "Options should have 5-space indent"
    )


def test_configuration_preview_multiline_command(monkeypatch, capsys, tmp_path):
    """Test that current command shows each option on separate line."""
    file1 = tmp_path / "file1.md"
    file2 = tmp_path / "file2.md"

    monkeypatch.setenv("AI_LAUNCHER_SCAN_PATHS", str(tmp_path))
    monkeypatch.setenv("AI_LAUNCHER_PROVIDER", "claude-code")
    monkeypatch.setenv("AI_LAUNCHER_GLOBAL_FILES", f"{file1},{file2}")

    from ai_launcher.ui._preview_helper import show_configuration_preview

    show_configuration_preview()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)

    # Verify multiline command format
    assert "Current command:" in output
    assert "  ai-launcher claude" in output
    assert "    --global-files" in output

    lines = output.split("\n")

    # Files appear in both Global Files section (with bullet) and Current command section
    # Filter to command section lines (no bullet, 6-space indent)
    command_file_lines = [
        l for l in lines if ("file1.md" in l or "file2.md" in l) and "\u2022" not in l
    ]
    assert len(command_file_lines) == 2, (
        "Each file should be on separate line in command section"
    )
    assert all(l.startswith("      ") for l in command_file_lines), (
        "Files should have 6-space indent"
    )
