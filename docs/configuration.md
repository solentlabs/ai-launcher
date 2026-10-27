# Configuration

AI Launcher is configured through CLI flags. The one file it reads is an optional `caches.toml` for
the [cache page](cache-and-scratch.md#registry), which also holds the opt-in
[`[update]` check](updating.md#checking-automatically); nothing needs it.

## CLI Options

All options are passed as flags to a provider subcommand:

```bash
ai-launcher claude [OPTIONS] [PATH]
```

| Flag                | Description                                            | Example                                  |
| ------------------- | ------------------------------------------------------ | ---------------------------------------- |
| `PATH`              | Directory to scan for projects                         | `~/projects`                             |
| `--global-files`    | Comma-separated context files to load for all projects | `--global-files ~/standards.md,~/ops.md` |
| `--manual-paths`    | Comma-separated non-git directories to include         | `--manual-paths ~/scripts,~/notes`       |
| `--allow-writes`    | Comma-separated folders writable without asking (\*)   | `--allow-writes ~/projects/journal`      |
| `--discover` / `-d` | Show discovery report (installed providers, projects)  |                                          |
| `--context` / `-c`  | Interactive context viewer                             |                                          |
| `--list`            | List all discovered projects                           |                                          |
| `--verbose`         | Enable verbose logging                                 |                                          |
| `--debug`           | Enable debug mode                                      |                                          |
| `--cleanup`         | Clean AI assistant cache/logs before launch            |                                          |
| `--clean-provider`  | Clean provider-specific files only                     |                                          |
| `--clean-npm`       | Clean npm cache                                        |                                          |

(\*) `claude` and `gemini` only: folders exempt from the
[project scope](project-scope.md#allowing-shared-folders) guard (for Gemini, added to its
workspace), such as a journal every project writes to.

## Cache and Scratch Commands

| Command                                      | What it does                                              |
| -------------------------------------------- | --------------------------------------------------------- |
| `ai-launcher cache [PATH...]`                | The [cache page](cache-and-scratch.md#the-page)           |
| `ai-launcher cache --list [PATH...]`         | The same table as plain text; nothing can be deleted      |
| `ai-launcher scratch prune --older-than 14d` | Remove old session scratch folders (`--dry-run`, `--yes`) |

`PATH` is a scan folder, as for a provider subcommand; `--manual-paths` works too. They tell the
page which folders are projects, so it never offers one for deletion. The optional file is
`caches.toml` in the config folder (`~/.config/ai-launcher/` on Linux and WSL); see
[Registry](cache-and-scratch.md#registry). Sessions also get a scratch folder, named in the
`AI_SCRATCH_DIR` environment variable; see
[Scratch Directory](cache-and-scratch.md#scratch-directory).

## Update Command

| Command                      | What it does                                                      |
| ---------------------------- | ----------------------------------------------------------------- |
| `ai-launcher update --check` | Says whether a newer release exists on PyPI; changes nothing      |
| `ai-launcher update`         | Shows the upgrade command for how you installed it, asks, runs it |

It contacts PyPI only when you run it, unless you opt in to a daily background check with
`[update] check = true` in `caches.toml`. That adds a one-line launch notice when a newer release
exists. See [Updating](updating.md).

## Available Providers

Each provider is a subcommand:

```bash
ai-launcher claude ~/projects
ai-launcher gemini ~/projects
ai-launcher cursor ~/projects
ai-launcher aider ~/projects
ai-launcher copilot ~/projects
```

The subcommand sets the default tool: the one Enter launches, and the one whose context the preview
pane shows.

## Picker Keys

| Key    | What it does                                                             |
| ------ | ------------------------------------------------------------------------ |
| Enter  | Opens the highlighted project with the default tool                      |
| Ctrl-O | Lists your installed tools and a plain shell, to open the project with   |
| Esc    | Leaves the launcher; in the Ctrl-O list, goes back to the project picker |

A tool picked from the Ctrl-O list gets the same flags you passed (`--cleanup`, `--allow-writes` and
so on) and uses the ones it supports. The Shell row runs your shell in the project with no cleanup
and no [project scope](project-scope.md#other-tools) guard. Type `exit` to leave it; the launcher
then exits with the shell's exit status.

| Platform          | Shell the Shell row runs                                                                                                                                                      |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux, macOS, WSL | `$SHELL`, or `/bin/sh` if it is not set or cannot be run                                                                                                                      |
| Windows           | `%COMSPEC%` (`cmd.exe`), also from PowerShell, unless `SHELL` names a program that can be run. For a project on a UNC path, `cmd.exe` starts in the Windows directory instead |

## Examples

**Basic usage:**

```bash
ai-launcher claude ~/projects
```

**With global context files and manual paths:**

```bash
ai-launcher claude ~/projects/solentlabs \
  --global-files ~/.claude/RULES.md \
  --manual-paths ~/projects/personal
```

**Discovery mode (no fzf needed):**

```bash
ai-launcher claude --discover ~/projects
```

## Windows Terminal Integration

See [windows-terminal.md](windows-terminal.md) for setting up AI Launcher as a Windows Terminal
profile.
