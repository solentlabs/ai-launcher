"""Tests for the project scope guard (core/scope_guard.py).

The guard decides whether a Claude Code tool call would write into a project
other than the one AI Launcher opened. Reads are always allowed; writes under a
scan root but outside the selected project must ask first.

Author: Solent Labs™
"""

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_launcher.core.scope_guard import ProjectScope, decide, main


@pytest.fixture
def layout(mock_home):
    """~/projects holding the launched project and a sibling project."""
    root = mock_home / "projects"
    project = root / "cable_modem_monitor"
    other = root / "angel-captain"
    for repo in (project, other):
        (repo / ".git").mkdir(parents=True)
    outside = mock_home / "elsewhere"
    outside.mkdir()
    return {
        "home": mock_home,
        "root": root,
        "project": project,
        "other": other,
        "outside": outside,
    }


@pytest.fixture
def scope(layout):
    return ProjectScope(project=layout["project"], roots=[layout["root"]])


def _fill(template, layout):
    """Substitute fixture paths (POSIX form, as a shell command carries them)."""
    return template.format(**{k: v.as_posix() for k, v in layout.items()})


class TestFileTools:
    """Write, Edit, MultiEdit and NotebookEdit carry the target path directly."""

    @pytest.mark.parametrize(
        ("tool", "key", "path", "asks"),
        [
            ("Write", "file_path", "{project}/src/app.py", False),
            ("Edit", "file_path", "{project}/README.md", False),
            ("Write", "file_path", "{other}/README.md", True),
            ("Edit", "file_path", "{other}/src/app.py", True),
            ("MultiEdit", "file_path", "{other}/src/app.py", True),
            ("NotebookEdit", "notebook_path", "{other}/nb.ipynb", True),
            ("Write", "file_path", "{root}/notes.txt", True),
            ("Write", "file_path", "{outside}/scratch.txt", False),
            ("Write", "file_path", "{home}/.claude/memory/MEMORY.md", False),
            ("Write", "file_path", "../angel-captain/README.md", True),
            ("Read", "file_path", "{other}/README.md", False),
            ("Grep", "path", "{other}", False),
        ],
        ids=[
            "write-inside",
            "edit-inside",
            "write-sibling",
            "edit-sibling",
            "multiedit-sibling",
            "notebook-sibling",
            "write-under-root-not-a-project",
            "write-outside-root",
            "write-claude-memory",
            "relative-path-into-sibling",
            "read-sibling",
            "grep-sibling",
        ],
    )
    def test_file_tool(self, scope, layout, tool, key, path, asks):
        tool_input = {key: _fill(path, layout)}
        targets = scope.write_targets(tool, tool_input, layout["project"])
        assert bool(targets) is asks

    def test_symlink_into_sibling_counts_as_sibling(self, scope, layout, make_symlink):
        """A link inside the project that points at another project is not a way out."""
        link = layout["project"] / "vendor"
        make_symlink(link, layout["other"], target_is_directory=True)
        targets = scope.write_targets(
            "Write", {"file_path": str(link / "x.py")}, layout["project"]
        )
        assert targets

    def test_claude_folder_inside_scan_root_is_exempt(self, layout):
        """Scanning ~ must not turn Claude's own memory writes into prompts."""
        home_scope = ProjectScope(project=layout["project"], roots=[layout["home"]])
        memory = layout["home"] / ".claude" / "projects" / "x" / "memory" / "a.md"
        assert (
            home_scope.write_targets(
                "Write", {"file_path": str(memory)}, layout["project"]
            )
            == []
        )

    @pytest.mark.parametrize(
        ("tool", "tool_input"),
        [("Write", {}), ("Edit", {"file_path": None}), ("Bash", {"command": 5})],
        ids=["missing-path", "null-path", "non-string-command"],
    )
    def test_unusable_input_is_left_alone(self, scope, layout, tool, tool_input):
        assert scope.write_targets(tool, tool_input, layout["project"]) == []

    def test_explicit_exempt_replaces_claude_folder(self, layout):
        notes = layout["root"] / "shared-notes"
        custom = ProjectScope(layout["project"], [layout["root"]], exempt=[notes])
        assert (
            custom.write_targets(
                "Write", {"file_path": str(notes / "a.md")}, layout["project"]
            )
            == []
        )

    def test_scan_root_equal_to_project_guards_nothing(self, layout):
        """Scanning a single repo: nothing is 'another project'."""
        solo = ProjectScope(project=layout["project"], roots=[layout["project"]])
        assert (
            solo.write_targets(
                "Write", {"file_path": str(layout["outside"] / "x")}, layout["project"]
            )
            == []
        )


class TestBashCommands:
    """Shell commands: reading another project is fine, changing it asks."""

    @pytest.mark.parametrize(
        ("command", "asks"),
        [
            # Reads of another project pass.
            ("cat ../angel-captain/README.md", False),
            ("ls {other}", False),
            ("grep -rn TODO ../angel-captain", False),
            ("cd ../angel-captain && git status && git log --oneline", False),
            ("git -C ../angel-captain diff HEAD~1", False),
            ("sed -n 1,5p ../angel-captain/setup.cfg", False),
            ("find ../angel-captain -name '*.py'", False),
            ("cp ../angel-captain/setup.cfg ./", False),
            ("cat ../angel-captain/a.txt > notes.txt", False),
            ("echo 'see ../angel-captain/README.md'", False),
            # Writes that stay home pass.
            ("rm -rf build && mkdir build", False),
            ("git commit -m 'port fix from ../angel-captain'", False),
            ("echo hi > /dev/null 2>&1", False),
            ("echo hi > {outside}/x.txt", False),
            ("cat <<'EOF' > notes.md\ndon't edit ../angel-captain\nEOF", False),
            # Writes into another project ask.
            ("echo hi > ../angel-captain/x.txt", True),
            ("echo hi >> {other}/x.txt", True),
            ("cd ../angel-captain && git commit -m wip", True),
            ("git -C ../angel-captain commit -am wip", True),
            ("rm -rf ../angel-captain/build", True),
            ("mv ../angel-captain/a.py ./", True),
            ("cp local.txt ../angel-captain/", True),
            ("cp -t ../angel-captain local.txt", True),
            ("sed -i s/a/b/ ../angel-captain/setup.cfg", True),
            ("touch ~/projects/angel-captain/new.txt", True),
            ("touch $HOME/projects/angel-captain/new.txt", True),
            ("mkdir -p ../angel-captain/docs", True),
            ("cat x.txt | tee ../angel-captain/y.txt", True),
            ("cd ../angel-captain\nmake build", True),
            ("(cd ../angel-captain && npm install)", True),
            ("echo $(rm ../angel-captain/x.txt)", True),
            ("find ../angel-captain -name '*.pyc' -delete", True),
            ("FOO=1 rm ../angel-captain/x.txt", True),
            ("sudo rm {other}/x.txt", True),
            ("echo hi > {root}/notes.txt", True),
            ("cp --target-directory=../angel-captain local.txt", True),
            ("git -c core.pager=cat -C ../angel-captain commit -m wip", True),
            ("git --work-tree=../angel-captain add .", True),
            ("git --no-pager -C ../angel-captain log", False),
            ("git -C ../angel-captain --version", False),
            ("FOO=1 && touch ../angel-captain/x.txt", True),
            ("cat <<A > a.md; cat <<B > b.md\none\nA\ntwo\nB", False),
        ],
        ids=[
            "cat-sibling",
            "ls-sibling",
            "grep-sibling",
            "git-read-in-sibling",
            "git-C-read",
            "sed-print",
            "find-plain",
            "cp-from-sibling",
            "redirect-local-from-sibling",
            "echo-mentions-sibling",
            "local-rm-mkdir",
            "local-commit-mentions-sibling",
            "redirect-dev-null",
            "redirect-outside-root",
            "heredoc-with-apostrophe",
            "redirect-into-sibling",
            "append-into-sibling",
            "cd-then-commit",
            "git-C-commit",
            "rm-in-sibling",
            "mv-out-of-sibling",
            "cp-into-sibling",
            "cp-target-dir",
            "sed-in-place",
            "tilde-path",
            "env-var-path",
            "mkdir-in-sibling",
            "pipe-to-tee",
            "newline-separated",
            "subshell-cd",
            "command-substitution",
            "find-delete",
            "env-assignment-prefix",
            "sudo-prefix",
            "redirect-under-root",
            "cp-target-dir-long-option",
            "git-config-option-then-commit",
            "git-work-tree-add",
            "git-global-option-then-log",
            "git-no-subcommand",
            "bare-assignment-segment",
            "two-heredocs-one-line",
        ],
    )
    def test_bash(self, scope, layout, command, asks):
        tool_input = {"command": _fill(command, layout)}
        targets = scope.write_targets("Bash", tool_input, layout["project"])
        assert bool(targets) is asks

    @pytest.mark.parametrize(
        ("command", "asks"),
        [
            ("ls", False),
            ("git status", False),
            ("python build.py", True),
            ("git commit -m wip", True),
        ],
        ids=["ls", "git-status", "run-script", "commit"],
    )
    def test_session_cwd_inside_sibling(self, scope, layout, command, asks):
        """If the shell is already sitting in another project, running there asks."""
        targets = scope.write_targets("Bash", {"command": command}, layout["other"])
        assert bool(targets) is asks

    @pytest.mark.parametrize(
        "command",
        ["rm ../angel-captain/*.pyc", "rm ../angel-captain/*/cache"],
        ids=["wildcard-name", "wildcard-folder"],
    )
    def test_unresolvable_path_still_checked(self, scope, layout, monkeypatch, command):
        """Windows before Python 3.10 raises on resolve() for names like *.pyc.

        The guard must not crash (and so let the write through); the folder the
        name sits in still decides which project it touches.
        """
        real_resolve = Path.resolve

        def windows_resolve(self, strict=False):
            if "*" in str(self):
                raise OSError(123, "The filename syntax is incorrect", str(self))
            return real_resolve(self, strict)

        monkeypatch.setattr(Path, "resolve", windows_resolve)
        targets = scope.write_targets("Bash", {"command": command}, layout["project"])
        assert targets

    def test_unbalanced_quotes_still_checked(self, scope, layout):
        """A command shlex cannot parse falls back to a coarse check, not a pass."""
        command = "echo \"it's > ../angel-captain/x.txt"
        targets = scope.write_targets("Bash", {"command": command}, layout["project"])
        assert targets


class TestDecide:
    """decide() turns a PreToolUse event into Claude Code's hook output."""

    def test_write_into_sibling_asks_with_reason(self, scope, layout):
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(layout["other"] / "README.md")},
            "cwd": str(layout["project"]),
        }
        output = decide(event, scope)
        assert output is not None
        hook = output["hookSpecificOutput"]
        assert hook["hookEventName"] == "PreToolUse"
        assert hook["permissionDecision"] == "ask"
        assert "cable_modem_monitor" in hook["permissionDecisionReason"]
        assert "angel-captain" in hook["permissionDecisionReason"]
        # The permission dialog does not show the reason; as a systemMessage
        # Claude prints it under the tool call.
        assert output["systemMessage"] == hook["permissionDecisionReason"]

    def test_write_inside_project_has_no_opinion(self, scope, layout):
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(layout["project"] / "a.py")},
            "cwd": str(layout["project"]),
        }
        assert decide(event, scope) is None

    def test_event_without_tool_input_is_left_alone(self, scope):
        assert decide({"tool_name": "Write", "tool_input": "x"}, scope) is None

    def test_path_outside_home_shown_in_full(self, tmp_path):
        """Reasons use ~ only for paths under the home directory."""
        root = tmp_path / "srv"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir()
        scope = ProjectScope(root / "a", [root])
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(root / "b" / "f")},
        }
        with patch(
            "ai_launcher.core.scope_guard.Path.home", return_value=tmp_path / "home"
        ):
            output = decide(event, scope)
        # Compare against the decoded reason: JSON text escapes Windows backslashes.
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert str((root / "b" / "f").resolve()) in reason

    def test_several_targets_are_counted(self, scope, layout):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "touch ../angel-captain/a ../angel-captain/b"},
            "cwd": str(layout["project"]),
        }
        reason = decide(event, scope)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "(and 1 more)" in reason

    def test_missing_cwd_defaults_to_project(self, scope):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "touch ../angel-captain/x"},
        }
        assert decide(event, scope) is not None


class TestHookEntryPoint:
    """The module runs as Claude Code's PreToolUse hook command."""

    @pytest.fixture
    def argv(self, layout):
        return ["--project", str(layout["project"]), "--root", str(layout["root"])]

    @staticmethod
    def _event(layout, target):
        return json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(layout[target] / "a.py")},
                "cwd": str(layout["project"]),
            }
        )

    @pytest.mark.parametrize(
        ("target", "exit_code", "asks"),
        [("other", 0, True), ("project", 0, False)],
        ids=["sibling-write-asks", "inside-write-silent"],
    )
    def test_main(self, layout, argv, monkeypatch, capsys, target, exit_code, asks):
        monkeypatch.setattr("sys.stdin", io.StringIO(self._event(layout, target)))
        assert main(argv) == exit_code
        out = capsys.readouterr().out
        if asks:
            decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
            assert decision == "ask"
        else:
            assert out == ""

    @pytest.mark.parametrize(
        ("tool_name", "tool_input"),
        [
            ("Write", {"file_path": "{other}/journal/2026-09/a.md"}),
            ("Bash", {"command": "mkdir -p {other}/journal/2026-09"}),
            ("Write", {"file_path": "{home}/.claude/projects/x/memory/a.md"}),
        ],
        ids=["file-in-allowed", "bash-in-allowed", "claude-folder-still-exempt"],
    )
    def test_exempt_folders_write_silently(
        self, layout, argv, monkeypatch, capsys, tool_name, tool_input
    ):
        """--exempt adds to Claude's own folder; writes under either pass."""
        argv = [*argv, "--exempt", str(layout["other"] / "journal")]
        event = {
            "tool_name": tool_name,
            "tool_input": {k: _fill(v, layout) for k, v in tool_input.items()},
            "cwd": str(layout["project"]),
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
        assert main(argv) == 0
        assert capsys.readouterr().out == ""

    def test_exempt_does_not_cover_rest_of_sibling(
        self, layout, argv, monkeypatch, capsys
    ):
        argv = [*argv, "--exempt", str(layout["other"] / "journal")]
        monkeypatch.setattr("sys.stdin", io.StringIO(self._event(layout, "other")))
        assert main(argv) == 0
        assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]

    def test_malformed_input_fails_visibly_without_blocking(
        self, argv, monkeypatch, capsys
    ):
        """Exit 1 is a non-blocking hook error: Claude shows it and carries on."""
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        assert main(argv) == 1
        assert "AI Launcher scope guard" in capsys.readouterr().err

    def test_runs_as_module(self, layout, argv):
        """The exact entry point the hook command uses: python -m ..."""
        result = subprocess.run(
            [sys.executable, "-m", "ai_launcher.core.scope_guard", *argv],
            input=self._event(layout, "other"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
