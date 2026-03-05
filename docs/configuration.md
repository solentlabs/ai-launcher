# Configuration

AI Launcher is configured entirely through CLI flags. There is no config file.

## CLI Options

All options are passed as flags to a provider subcommand:

```bash
ai-launcher claude [OPTIONS] [PATH]
```

| Flag | Description | Example |
|------|-------------|---------|
| `PATH` | Directory to scan for projects | `~/projects` |
| `--global-files` | Comma-separated context files to load for all projects | `--global-files ~/standards.md,~/ops.md` |
| `--manual-paths` | Comma-separated non-git directories to include | `--manual-paths ~/scripts,~/notes` |
| `--discover` / `-d` | Show discovery report (installed providers, projects) | |
| `--context` / `-c` | Interactive context viewer | |
| `--list` | List all discovered projects | |
| `--verbose` | Enable verbose logging | |
| `--debug` | Enable debug mode | |
| `--cleanup` | Clean AI assistant cache/logs before launch | |
| `--clean-provider` | Clean provider-specific files only | |
| `--clean-cache` | Clean system cache | |
| `--clean-npm` | Clean npm cache | |

## Available Providers

Each provider is a subcommand:

```bash
ai-launcher claude ~/projects
ai-launcher gemini ~/projects
ai-launcher cursor ~/projects
ai-launcher aider ~/projects
ai-launcher copilot ~/projects
```

## Examples

**Basic usage:**
```bash
ai-launcher claude ~/projects
```

**With global context files and manual paths:**
```bash
ai-launcher claude ~/projects/solentlabs \
  --global-files ~/projects/solentlabs/operations/ai-skills/insights-journal.md \
  --manual-paths ~/projects/personal
```

**Discovery mode (no fzf needed):**
```bash
ai-launcher claude --discover ~/projects
```

## Windows Terminal Integration

See [windows-terminal.md](windows-terminal.md) for setting up AI Launcher as a Windows Terminal profile.
