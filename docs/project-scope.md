# Project Scope

AI Launcher opens an AI session in one project, and that session runs under that project's
instructions, settings and memory. If a request for a _different_ project reaches it (a pasted
handoff, or "while you're at it, fix this over there"), the work would be done from the wrong folder
under the wrong project's rules. AI Launcher makes that obvious, and asks you before any change
lands in another project.

## The Rule

Say you run `ai-launcher claude ~/projects` and pick `cable_modem_monitor`. For the rest of that
session:

| The session tries to…                                     | What happens                     |
| --------------------------------------------------------- | -------------------------------- |
| read any file, anywhere                                   | Goes ahead                       |
| write inside `cable_modem_monitor`                        | Goes ahead                       |
| write inside another project, e.g. `angel-captain`        | **Stops and asks you first**     |
| write any other file under `~/projects`                   | **Stops and asks you first**     |
| write Claude's own files (`~/.claude`: memory, plans)     | Goes ahead, even if you scan `~` |
| write anywhere outside `~/projects` (`/tmp`, `~/.bashrc`) | Goes ahead                       |

"Under `~/projects`" means under any folder you passed to scan, plus any `--manual-paths` project.

## What You See (Claude Code)

- **Launch box:** `🔒 Scope: writes to other projects ask first`.
- **When a request is for another project:** Claude is told which project it was launched in, so it
  says so before starting and suggests opening a session there. A pasted handoff for another project
  gets that answer before any file is touched.
- **When a write would land in another project:** you get Claude Code's normal permission prompt
  (`Do you want to create w.txt?`), even if your allow rules (`Edit`, `Write`, `Bash(*)`) would
  otherwise let it through silently. Approve it if the cross-project change is deliberate. Once you
  answer, the session shows why it asked, under the tool call:

  ```text
  PreToolUse:Write says: AI Launcher: this writes to ~/projects/angel-captain/README.md,
  outside cable_modem_monitor, the project this session was launched in.
  ```

## How Shell Commands Are Judged

File edits name their target, so those are exact. Shell commands are judged from their text:

| Counts as a write to another project                                      | Counts as a read                                     |
| ------------------------------------------------------------------------- | ---------------------------------------------------- |
| output redirected there: `echo x > ../angel-captain/f`                    | `cat`, `ls`, `grep`, `find`, `head`…                 |
| a file-changing command aimed there: `rm`, `mv`, `mkdir`, `sed -i`, `tee` | `sed` without `-i`, `find` without `-delete`/`-exec` |
| copying _into_ it: `cp local.txt ../angel-captain/`                       | copying _out of_ it: `cp ../angel-captain/f ./`      |
| git changing it: `cd ../angel-captain && git commit`, `git -C … add`      | `git status`, `log`, `diff`, `show`, `blame`         |
| running any other command inside it: `cd ../angel-captain && make`        |                                                      |

This is a check for accidents, not a sandbox. A script, a variable the session sets, or a program
that writes on its own can change another project without the command text saying so.

## Other Tools

The guard is built for Claude Code, where the incident that prompted it happened, and where broad
allow rules (`Edit`, `Write`, `Bash(*)`) let out-of-folder writes through without asking. The other
tools behave as follows, according to their documentation. AI Launcher passes them nothing extra.

| Tool             | Writes outside the project                                                       |
| ---------------- | -------------------------------------------------------------------------------- |
| GitHub Copilot   | Asks for any path outside the launch folder, shell commands included             |
| Gemini CLI       | File tools refuse outright; shell commands ask only in its default approval mode |
| Aider            | Asks before editing any file not added to the chat, wherever it is               |
| Cursor (`agent`) | Not documented for the CLI; not verified                                         |

## Bash Prototype

`bin/ai-launcher` does not have the guard; it needs the Python package. See the
[changelog](../CHANGELOG.md).
