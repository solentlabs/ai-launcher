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
| write inside a folder passed to `--allow-writes`          | Goes ahead                       |
| write anywhere outside `~/projects` (`/tmp`, `~/.bashrc`) | Goes ahead                       |
| write inside the session's `AI_SCRATCH_DIR`               | Goes ahead, even if you scan `~` |

"Under `~/projects`" means under any folder you passed to scan, plus any `--manual-paths` project.

## Allowing Shared Folders

Some folders are written by every session on purpose, such as a journal that all your projects log
to. If that folder sits under a scan root or a manual project, every write to it would ask. Pass it
to `--allow-writes` (comma-separated, like `--manual-paths`) and writes inside it go ahead:

```bash
ai-launcher claude ~/projects --allow-writes ~/projects/journal
```

Only the named folder is allowed. The rest of the project it sits in still asks first. The launch
box lists each allowed folder under the scope line.

`ai-launcher gemini` takes the same flag. Gemini's file tools refuse writes outside its workspace,
so a journal outside the project would otherwise be refused, not asked. AI Launcher passes each
allowed folder as `--include-directories`, which adds it to that workspace.

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

### Commands that carry a path or a command inside them

The text of these is read more closely, because the path is not an ordinary argument:

- **Wrapped commands.** `bash -c '…'`, `sh -c`, `zsh -c`, `eval '…'` (and `-lc`, `-ec` and the like)
  are read as if the inner command had been typed: `bash -c 'touch ../angel-captain/x'` asks.
- **Inline code.** `python -c`, `node -e`, `perl -e`, `ruby -e` and `php -r` cannot be read as
  shell. If the code names a path inside another project, the call asks, even when the code would
  only read it, since the text cannot say.
- **Paths attached to an option.** `dd of=…`, `curl -o/path`, `tar --file=…`, `--output=…`.
- **Flags joined together.** `sed -Ei`, `sed -ni` and `sed -i.bak` all edit in place. `fd -x` and
  `fd -X` run a command per match. `find -fprint0` writes a file.
- **Git pointed elsewhere.** `git --git-dir=…`, `git --work-tree …` (with `=` or a space).
- **`cd -`** goes back to the folder you were in, not to `~`.

Disk use is a separate matter: [Cache and Scratch](cache-and-scratch.md) reports what sessions leave
behind, which this guard does not look at.

This is a check for accidents, not a sandbox. A script, a variable the session sets, a program that
writes on its own, or a command whose paths arrive on a pipe (`find … | xargs rm`) can change
another project without the command text saying so. `xargs` is not read, for that reason.

### When the guard itself fails

- **A bug while judging a call asks.** The prompt says the guard could not check the call and names
  the error, so a failure never lets a write through silently.
- **Unreadable hook input** (not JSON) is a hook error that Claude Code shows and then carries on.
  It is not a real tool call, so there is nothing to judge.
- **The hook runs by file path**, not as `python -m ai_launcher…`, so a project that contains its
  own `ai_launcher` folder cannot take the guard's place. Claude Code runs hooks from the project
  folder, and `-m` makes Python look there first. (`python -I` would also close that, but it drops
  the user site-packages, which breaks `pip install --user`.) The guard imports only the standard
  library.
- **If the program is gone** (a virtual environment that was moved or deleted, or a package upgrade
  under a running session), the hook cannot start, Claude Code shows a hook error and carries on,
  and nothing asks. Start AI Launcher again.

## Other Tools

The guard is built for Claude Code, where the incident that prompted it happened, and where broad
allow rules (`Edit`, `Write`, `Bash(*)`) let out-of-folder writes through without asking. The other
tools behave as follows, according to their documentation. AI Launcher passes them nothing extra,
except Gemini's `--allow-writes` folders (see [above](#allowing-shared-folders)).

| Tool             | Writes outside the project                                                       |
| ---------------- | -------------------------------------------------------------------------------- |
| GitHub Copilot   | Asks for any path outside the launch folder, shell commands included             |
| Gemini CLI       | File tools refuse outright; shell commands ask only in its default approval mode |
| Aider            | Asks before editing any file not added to the chat, wherever it is               |
| Cursor (`agent`) | Not documented for the CLI; not verified                                         |

A tool picked from the Ctrl-O list is launched with the same guard arguments as the default tool, so
Claude Code gets the guard there too, with whatever `--allow-writes` folders the run was given. The
Shell row in that list has no guard: it is not an AI session, and you type the commands yourself.

## Bash Prototype

`bin/ai-launcher` does not have the guard; it needs the Python package. See the
[changelog](../CHANGELOG.md).
