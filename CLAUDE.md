# AI Launcher - AI Coding Assistant Guide

**Project:** Universal AI CLI launcher with local context management
**Organization:** Solent Labs™
**Version:** See `pyproject.toml` and `src/ai_launcher/__init__.py`
**License:** MIT

## Project Overview

AI Launcher is a terminal-first tool that provides a single entry point to launch AI coding assistants (Claude Code, Gemini CLI, Cursor, Aider, GitHub Copilot CLI, and more) across multiple projects. It maintains persistent context, discovers projects automatically, and provides an interactive fuzzy-search interface.

**Core Philosophy:**
- **Local-first** - All data stays on your machine
- **Privacy-first** - No cloud dependencies
- **Developer experience** - Tools should be delightful to use

## Two Implementations

### 1. Bash Script (Prototype) - `bin/ai-launcher`
- **Purpose:** Rapid prototyping and iteration
- **Features:** Complete, working implementation
- **Use case:** Direct execution for development/testing
- **Status:** Functional prototype with latest features

**Run it:**
```bash
~/projects/solentlabs/utilities/ai-launcher/bin/ai-launcher ~/projects
```

### 2. Python Package (Production) - `src/ai_launcher/`
- **Purpose:** Production-ready, distributable package
- **Tech:** Python 3.8+, Typer, iterfzf, platformdirs
- **Features:** Same as bash, plus SQLite persistence
- **Use case:** Install via pipx/pip for end users
- **Status:** In development, feature parity with bash script

**Install it:**
```bash
pipx install ai-launcher
```

**Why both?**
- Bash script = fast iteration and prototyping
- Python package = proper distribution and testing
- Keep bash script as reference implementation
- Python package inherits proven features from bash

## Development Setup (Python Package)

This project uses **editable install** for development, so changes to source code are immediately reflected without reinstalling.

### One-Time Setup

```bash
# Remove any existing installed version
pipx uninstall ai-launcher 2>/dev/null || true

# Install in editable mode (development)
cd ~/projects/solentlabs/utilities/ai-launcher
pip install -e .
```

After this setup, the `ai-launcher` command always uses your current source code. Changes are immediately reflected - no reinstalling needed.

### Development Workflow

1. **Make changes** with Claude Code (edit Python files in `src/ai_launcher/`)
2. **Test immediately** - just run the normal command:
   ```bash
   ai-launcher claude ~/projects/solentlabs \
     --global-files ~/projects/solentlabs/operations/ai-skills/insights-journal.md,~/projects/solentlabs/operations/ai-skills/contributor-assessment.md \
     --manual-paths ~/projects/personal
   ```
3. **Changes work instantly** - no build step, no reinstall

### Windows Terminal Integration

The "Solent Labs - Claude Code" profile in Windows Terminal runs:
```bash
wsl.exe -d Ubuntu bash -lic 'ai-launcher claude ~/projects/solentlabs --global-files ~/projects/solentlabs/operations/ai-skills/insights-journal.md,~/projects/solentlabs/operations/ai-skills/contributor-assessment.md --manual-paths ~/projects/personal'
```

This command represents the **production user experience** (what users get from PyPI). With editable install, it also reflects your latest development changes.

### Testing Package Installation (Before Release)

Before publishing to PyPI, test the actual installation flow:

```bash
# Test real package install
pip uninstall ai-launcher
pip install .
ai-launcher claude ~/projects/solentlabs --global-files ... --manual-paths ...

# Test thoroughly, then back to dev mode
pip uninstall ai-launcher
pip install -e .
```

### Important Notes

- **Consistent behavior:** Always use `ai-launcher` command (not `python -m ai_launcher.cli`)
- **Immediate feedback:** Code changes → test immediately
- **Same as production:** Testing the exact command users will run
- **Claude Code awareness:** When making changes, they take effect immediately

## Architecture

The system uses a **clean, layered architecture** with separation of concerns. See [docs/architecture.md](docs/architecture.md) for full details.

**Key layers:**
1. **Data Layer** (`core/provider_data.py`) — Strongly-typed dataclasses (no dicts with magic keys)
2. **Provider Layer** (`providers/`) — AIProvider ABC + auto-discovered implementations
3. **Presentation Layer** (`ui/formatter.py`) — Centralized ANSI formatting
4. **Integration Layer** (`ui/preview.py`) — Orchestrates data collection → formatting

**Key design rules:**
- Providers return DATA (dataclasses), never formatted strings
- All ANSI formatting goes through PreviewFormatter
- ProviderRegistry auto-discovers providers (no hardcoded lists)
- Preview pane order: CLAUDE.md → git status → directory contents (folders first)

## File Structure

```
ai-launcher/
├── bin/
│   └── ai-launcher              # Bash prototype
├── src/ai_launcher/             # Python package
│   ├── __init__.py              # Version (source of truth)
│   ├── __main__.py              # Entry point
│   ├── cli.py                   # Main CLI (Typer)
│   ├── core/                    # Core logic
│   │   ├── discovery.py         # Project discovery
│   │   ├── models.py            # Data models (Project)
│   │   ├── provider_data.py     # Data structures (ProviderPreviewData, etc.)
│   │   ├── provider_discovery.py # Provider detection
│   │   └── context_analyzer.py  # Context analysis
│   ├── providers/               # Provider abstraction
│   │   ├── __init__.py          # Package exports
│   │   ├── base.py              # AIProvider ABC + ProviderMetadata
│   │   ├── claude.py            # ClaudeProvider (includes data collection)
│   │   ├── gemini.py            # GeminiProvider implementation
│   │   ├── cursor.py            # CursorProvider implementation
│   │   ├── aider.py             # AiderProvider implementation
│   │   ├── copilot.py           # CopilotProvider implementation
│   │   └── registry.py          # ProviderRegistry (auto-discovery)
│   ├── ui/                      # User interface
│   │   ├── browser.py           # Directory browser
│   │   ├── preview.py           # Preview generation + tree view
│   │   ├── selector.py          # Project selector (fzf)
│   │   ├── formatter.py         # PreviewFormatter (all ANSI formatting)
│   │   ├── _preview_helper.py   # Preview subprocess helper
│   │   ├── _context_preview.py  # Context preview helper
│   │   ├── _settings_preview.py # Settings preview helper
│   │   ├── _file_preview.py     # File preview helper
│   │   ├── _browser_preview.py  # Browser preview helper
│   │   ├── startup_report.py    # Startup transparency report
│   │   ├── discovery.py         # Discovery report
│   │   └── context_viewer.py    # Context viewer
│   └── utils/                   # Utilities
│       ├── git.py               # Git operations (clone)
│       ├── logging.py           # Logging config
│       ├── paths.py             # Path utilities
│       ├── cleanup.py           # Environment cleanup (legacy)
│       ├── humanize.py          # Size/count formatting
│       ├── session.py           # Session management
│       └── terminal.py          # Terminal title management
├── tests/                       # Test suite (run `pytest --co -q` for count)
│   ├── conftest.py              # Shared fixtures
│   └── test_*.py                # See tests/ directory for full list
├── docs/                        # Documentation (see docs/ for full list)
│   ├── configuration.md
│   ├── installation.md
│   ├── troubleshooting.md
│   ├── windows-terminal.md
│   ├── adding-providers.md
│   ├── architecture.md
│   └── context-transparency.md
├── CHANGELOG.md                 # Version history
├── README.md                    # User documentation
├── pyproject.toml               # Package configuration
└── CLAUDE.md                    # This file!
```

## Multi-Provider Usage

```bash
ai-launcher claude --discover ~/projects   # Discovery report
ai-launcher claude --context ~/projects    # Interactive context viewer
ai-launcher claude ~/projects              # Launch with project selector
```

### Adding a New Provider

Create a single file in `src/ai_launcher/providers/` — it's auto-discovered. See [docs/adding-providers.md](docs/adding-providers.md) for the full guide with examples.

## Development Conventions

### Code Style
- **Python:** Ruff (88 char), strict type hints, docstrings
- **Bash:** ShellCheck compliant, `set -euo pipefail`, quoted variables
- **Commits:** Conventional commits (feat/fix/docs/refactor/test/chore)

### Naming Conventions
- **Python modules:** snake_case
- **Python classes:** PascalCase
- **Bash functions:** snake_case
- **Bash variables:** UPPER_CASE for globals, lower_case for locals

### Testing
- **Python:** pytest with coverage (aim for 80%+)
- **Bash:** Manual testing (no automated tests yet)
- **CI:** GitHub Actions runs tests and linting

### Branding
- **Name:** AI Launcher (two words, title case)
- **Tag line:** "by Solent Labs™" (with trademark symbol)
- **Colors:** Cyan for branding, green for success, yellow for warnings, dim for help

## Common Commands

### Development
```bash
# Run bash prototype
./bin/ai-launcher ~/projects

# Install Python package locally
pip install -e .

# Run Python package
ai-launcher claude ~/projects

# Run tests
pytest tests/ -v --cov=ai_launcher

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/
```

### Testing Bash Script
```bash
# Show usage
./bin/ai-launcher --help

# Add a path interactively
./bin/ai-launcher --add

# Remove a path
./bin/ai-launcher --remove

# List discovered projects
./bin/ai-launcher --list ~/projects
```

## Testing

### Test Suite
The project has comprehensive test coverage (run `pytest tests/ --co -q` for current count):

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/ai_launcher --cov-report=term-missing
```

### Coverage Goals
- **New code:** 80%+ coverage (currently 87-99% on refactored modules)
- **Data structures:** 100% coverage
- **Formatters:** 95%+ coverage
- **Providers:** 70%+ coverage (some platform-specific code hard to test)

### Test Categories
1. **Unit tests** - Individual components in isolation
2. **Integration tests** - Complete workflows end-to-end
3. **Mocked tests** - Using mocks for external dependencies
4. **Real tests** - Using actual provider implementations

## Important Notes

### For AI Assistants Working on This Project
- **Architecture:** Follow separation of concerns - data vs presentation
- **Providers return DATA:** Use dataclasses, never dicts or formatted strings
- **Formatting is centralized:** All ANSI codes in PreviewFormatter
- **Auto-discovery:** Don't hardcode provider lists, use ProviderRegistry
- **Test everything:** Maintain 80%+ coverage on new code
- **Two implementations:** Keep bash and Python in sync for features
- **Don't commit secrets:** No API keys, no .env files
- **Preserve symlinks:** Don't resolve to real paths
- **Folders first:** Always sort directories before files in listings
- **Solent Labs branding:** Use "by Solent Labs™" in UI headers

### For Future Development
- **Multi-tool support:** Plan for Gemini CLI, other AI tools
- **Context templates:** Generate CLAUDE.md templates
- **Shared context:** Implement .solent/ directory support
- **Configuration UI:** Interactive setup wizard
- **Testing:** Add integration tests for bash script

## Dependencies

See `pyproject.toml` for Python package dependencies and `[project.optional-dependencies] dev` for dev tools.

## Further Documentation

- [Architecture](docs/architecture.md) — Detailed system design
- [Adding Providers](docs/adding-providers.md) — How to add new AI tool providers
- [Configuration](docs/configuration.md) — Config file reference
- [Installation](docs/installation.md) — Install guide
- [Troubleshooting](docs/troubleshooting.md) — Common issues and fixes
- [Windows Terminal](docs/windows-terminal.md) — Windows Terminal integration
- [Context Transparency](docs/context-transparency.md) — What context AI tools see

---

**Made by Solent Labs™** - Building tools for developers who value privacy and local-first software.
