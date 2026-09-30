# Configuration

AI Launcher is configured entirely through CLI flags. There is no config file.

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
| `--clean-cache`     | Clean system cache                                     |                                          |
| `--clean-npm`       | Clean npm cache                                        |                                          |

(\*) `claude` and `gemini` only: folders exempt from the
[project scope](project-scope.md#allowing-shared-folders) guard (for Gemini, added to its
workspace), such as a journal every project writes to.

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
