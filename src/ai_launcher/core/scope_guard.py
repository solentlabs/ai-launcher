"""Project scope guard: ask before a session writes into another project.

AI Launcher opens an AI session in one project. A request meant for a
different project (a pasted handoff, a "while you're at it") would otherwise
be carried out from the wrong folder, under the wrong project's rules. This
module is the Claude Code ``PreToolUse`` hook that catches that: a write that
lands under a scan root but outside the launched project asks the user first.

Rules:
    - Reads are never gated, anywhere.
    - Writes inside the launched project pass.
    - Writes under a scan root (or manual project) but outside the launched
      project ask first. That covers sibling projects and loose files between
      them.
    - Writes outside every scan root pass (``/tmp``, ``~/.bashrc``), and so do
      writes to Claude's own folder (memory, plans) even when it sits under a
      scan root.

File tools name their target directly. Shell commands are classified by
reading the command text: output redirects, file-changing commands and git's
changing subcommands count as writes; a known read-only command does not.
That is a heuristic for catching accidents, not a sandbox: a script or a
variable can write where the text does not say.

Paths are resolved (symlinks followed) for comparison only, so a link inside
the project that points into another project is still that other project.

Runs as ``python -m ai_launcher.core.scope_guard --project P --root R...``
with the hook event JSON on stdin. Stdlib only: it runs on every file edit and
shell command, so it must start fast.

Author: Solent Labs™
"""

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

# Tools whose input names the file they write.
FILE_TOOL_KEYS = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}

# Hook matcher: every tool the guard inspects.
GUARDED_TOOLS = (*FILE_TOOL_KEYS, "Bash")

# Commands that only read. Anything not listed is treated as a possible write
# when it targets another project.
READ_ONLY_COMMANDS = frozenset(
    {
        "[",
        "basename",
        "cat",
        "cmp",
        "diff",
        "dirname",
        "du",
        "echo",
        "egrep",
        "false",
        "fd",
        "fgrep",
        "file",
        "find",
        "grep",
        "head",
        "jq",
        "less",
        "ls",
        "more",
        "printf",
        "pwd",
        "readlink",
        "realpath",
        "rg",
        "sed",
        "stat",
        "tail",
        "test",
        "tree",
        "true",
        "type",
        "wc",
        "which",
    }
)

# sed edits in place with -i, -i.bak, -i'' or --in-place.
SED_IN_PLACE_PREFIXES = ("-i", "--in-place")

# find actions that change or run things (matched exactly: -executable only reads).
FIND_WRITING_ACTIONS = frozenset(
    {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls"}
)

# git subcommands that only read. Every other subcommand changes the repo.
GIT_READ_SUBCOMMANDS = frozenset(
    {
        "blame",
        "cat-file",
        "describe",
        "diff",
        "grep",
        "help",
        "log",
        "ls-files",
        "ls-tree",
        "rev-list",
        "rev-parse",
        "shortlog",
        "show",
        "show-ref",
        "status",
        "version",
    }
)

# Copy-style commands: only the destination is written.
COPY_COMMANDS = frozenset({"cp", "install", "ln", "rsync", "scp"})

# Words that prefix a command without being the command.
COMMAND_PREFIXES = frozenset(
    {
        "!",
        "{",
        "command",
        "do",
        "else",
        "env",
        "exec",
        "if",
        "nice",
        "nohup",
        "sudo",
        "then",
        "time",
        "until",
        "while",
    }
)

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# Shell operator characters; a newline separates commands like ';'.
_PUNCTUATION_CHARS = "();<>|&\n"
_PUNCTUATION = set(_PUNCTUATION_CHARS)


def _within(path: Path, base: Path) -> bool:
    """True if path is base or below it (Python 3.8 compatible)."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _claude_config_dir() -> Path:
    """Claude Code's own folder, which holds memory and plans."""
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".claude"


class ProjectScope:
    """The launched project and the roots that hold other projects."""

    def __init__(
        self,
        project: Path,
        roots: Sequence[Path],
        exempt: Optional[Sequence[Path]] = None,
    ) -> None:
        self.project = project.resolve()
        self.roots = [root.resolve() for root in roots]
        if exempt is None:
            exempt = [_claude_config_dir()]
        self.exempt = [path.resolve() for path in exempt]

    def resolve(self, word: str, cwd: Path) -> Path:
        """Resolve a path as the shell would see it, following symlinks."""
        path = Path(os.path.expandvars(word)).expanduser()
        if not path.is_absolute():
            path = cwd / path
        return path.resolve()

    def is_other_project(self, path: Path) -> bool:
        """True if writing to path would change something outside the project."""
        return (
            any(_within(path, root) for root in self.roots)
            and not _within(path, self.project)
            and not any(_within(path, exempt) for exempt in self.exempt)
        )

    def write_targets(
        self, tool_name: str, tool_input: Dict[str, Any], cwd: Path
    ) -> List[Path]:
        """Paths in other projects that this tool call would write."""
        if tool_name in FILE_TOOL_KEYS:
            target = tool_input.get(FILE_TOOL_KEYS[tool_name])
            if not isinstance(target, str) or not target:
                return []
            path = self.resolve(target, cwd)
            return [path] if self.is_other_project(path) else []
        if tool_name == "Bash":
            command = tool_input.get("command")
            if not isinstance(command, str):
                return []
            return _bash_write_targets(command, cwd, self)
        return []


def _strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc bodies: they are data, and their quotes break shlex."""
    kept: List[str] = []
    pending: List[str] = []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
                if not pending:
                    kept.append("")
            continue
        kept.append(line)
        pending.extend(match.group(2) for match in _HEREDOC.finditer(line))
    return "\n".join(kept)


def _tokenize(command: str) -> List[str]:
    """Split a command into words and shell operators."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=_PUNCTUATION_CHARS)
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    return list(lexer)


def _is_operator(token: str) -> bool:
    return bool(token) and set(token) <= _PUNCTUATION


def _split_segments(tokens: List[str]) -> List[List[str]]:
    """Split tokens into simple commands, keeping redirects with their command."""
    segments: List[List[str]] = [[]]
    for token in tokens:
        if _is_operator(token) and "<" not in token and ">" not in token:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _bash_write_targets(command: str, cwd: Path, scope: ProjectScope) -> List[Path]:
    """Paths in other projects that a shell command would write."""
    try:
        tokens = _tokenize(_strip_heredoc_bodies(command))
    except ValueError:
        # Unparseable (unbalanced quotes): any path into another project asks.
        words = command.split()
        return [
            path
            for path in (scope.resolve(word, cwd) for word in words)
            if scope.is_other_project(path)
        ]

    targets: List[Path] = []
    for segment in _split_segments(tokens):
        cwd = _check_segment(segment, cwd, scope, targets)
    return targets


def _check_segment(
    segment: List[str], cwd: Path, scope: ProjectScope, targets: List[Path]
) -> Path:
    """Add this command's writes into other projects to targets.

    Returns the working directory for the commands that follow (after ``cd``).
    """

    def add(path: Path) -> None:
        if scope.is_other_project(path):
            targets.append(path)

    words = _take_redirects(segment, cwd, scope, add)
    while words and (words[0] in COMMAND_PREFIXES or _ASSIGNMENT.match(words[0])):
        words = words[1:]
    if not words:
        return cwd

    name = Path(words[0]).name
    args = words[1:]
    operands = [arg for arg in args if not arg.startswith("-")]

    if name in ("cd", "pushd"):
        return scope.resolve(operands[0], cwd) if operands else Path.home()
    if name == "git":
        _check_git(args, cwd, scope, add)
    elif name in READ_ONLY_COMMANDS and not _has_writing_option(name, args):
        pass
    elif name in COPY_COMMANDS:
        destination = _copy_destination(args, operands)
        add(scope.resolve(destination, cwd) if destination else cwd)
    else:
        # Unknown or file-changing command: running it inside another project,
        # or pointing it at one, asks.
        add(cwd)
        for operand in operands:
            add(scope.resolve(operand, cwd))
    return cwd


def _take_redirects(
    segment: List[str], cwd: Path, scope: ProjectScope, add: Callable[[Path], None]
) -> List[str]:
    """Record output-redirect targets; return the remaining words."""
    words: List[str] = []
    index = 0
    while index < len(segment):
        token = segment[index]
        if _is_operator(token):
            target = segment[index + 1] if index + 1 < len(segment) else None
            is_fd_copy = target is not None and (target.isdigit() or target == "-")
            if ">" in token and target is not None and not is_fd_copy:
                add(scope.resolve(target, cwd))
            if words and words[-1].isdigit():
                words.pop()  # the "2" in "2>file"
            index += 2
            continue
        words.append(token)
        index += 1
    return words


def _has_writing_option(name: str, args: List[str]) -> bool:
    """True if a read-only command was given an option that writes."""
    if name == "sed":
        return any(arg.startswith(SED_IN_PLACE_PREFIXES) for arg in args)
    if name == "find":
        return any(arg in FIND_WRITING_ACTIONS for arg in args)
    return False


def _copy_destination(args: List[str], operands: List[str]) -> Optional[str]:
    """The destination of cp/install/ln/rsync/scp, if the text names one."""
    for index, arg in enumerate(args):
        if arg in ("-t", "--target-directory") and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--target-directory="):
            return arg.split("=", 1)[1]
    return operands[-1] if len(operands) >= 2 else None


def _check_git(
    args: List[str], cwd: Path, scope: ProjectScope, add: Callable[[Path], None]
) -> None:
    """git changes the repo it runs in unless the subcommand only reads."""
    repo = cwd
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-C" and index + 1 < len(args):
            repo = scope.resolve(args[index + 1], repo)
            index += 2
        elif arg == "-c":
            index += 2
        elif arg.startswith("--work-tree="):
            repo = scope.resolve(arg.split("=", 1)[1], repo)
            index += 1
        elif arg.startswith("-"):
            index += 1
        else:
            if arg not in GIT_READ_SUBCOMMANDS:
                add(repo)
            return


def _display(path: Path) -> str:
    """Show a path with ~ for the home directory."""
    try:
        return f"~/{path.relative_to(Path.home()).as_posix()}"
    except ValueError:
        return str(path)


def decide(event: Dict[str, Any], scope: ProjectScope) -> Optional[Dict[str, Any]]:
    """Hook output asking the user first, or None to leave the call alone."""
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    cwd = Path(event["cwd"]) if event.get("cwd") else scope.project
    targets = scope.write_targets(str(event.get("tool_name", "")), tool_input, cwd)
    if not targets:
        return None

    target = _display(targets[0])
    more = f" (and {len(targets) - 1} more)" if len(targets) > 1 else ""
    reason = (
        f"AI Launcher: this writes to {target}{more}, outside "
        f"{scope.project.name}, the project this session was launched in. "
        "Approve only if you meant to change another project from here."
    )
    return {
        # Claude Code's permission dialog shows the path but not this reason
        # (checked on 2.1.270). As a systemMessage it is printed under the
        # tool call once the dialog is answered, so the session records why.
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Hook entry point: event JSON on stdin, decision JSON on stdout."""
    parser = argparse.ArgumentParser(prog="ai_launcher.core.scope_guard")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--root", action="append", default=[], type=Path)
    args = parser.parse_args(argv)

    try:
        event = json.load(sys.stdin)
        output = decide(event, ProjectScope(args.project, args.root))
    except Exception as error:
        # Exit 1 is a non-blocking hook error: Claude shows it and proceeds.
        sys.stderr.write(f"AI Launcher scope guard failed: {error}\n")
        return 1
    if output is not None:
        sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
