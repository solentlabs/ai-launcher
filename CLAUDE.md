# AI Launcher - AI Coding Assistant Guide

**Project:** Universal AI CLI launcher with local context management
**Organization:** Solent Labs™
**Version:** 0.1.0 (unreleased)
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
- **Size:** ~665 lines of bash
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
pipx install ai-launcher  # When published to PyPI
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

### Refactored Provider Abstraction (v0.1.0 - February 2026)

The system now uses a **clean, layered architecture** with proper separation of concerns:

#### 1. **Data Layer** (`core/provider_data.py`)
Strongly-typed dataclasses for structured data:
- `ContextFile` - Information about context files (CLAUDE.md, etc.)
- `SessionStats` - Session history and memory files
- `SharedContext` - Organization-wide shared context
- `ProviderPreviewData` - Complete preview data from a provider
- `GitStatus`, `DirectoryListing` - Additional data structures

**Design:** No dicts with magic keys - all data is typed and validated.

#### 2. **Provider Layer** (`providers/`)
Provider implementations that collect data:
- **AIProvider ABC** (`base.py`) - Abstract base class
  - `metadata` - Provider information
  - `is_installed()` - Installation check
  - `launch()` - Launch the provider
  - `cleanup_environment()` - Provider-specific cleanup
  - `collect_preview_data()` - Returns structured ProviderPreviewData
  - Helper methods: `get_global_context_paths()`, etc.

- **Built-in Providers:**
  - `ClaudeProvider` (`claude.py`) - Anthropic's Claude Code (includes data collection)
  - `GeminiProvider` (`gemini.py`) - Google's Gemini CLI
  - `CursorProvider` (`cursor.py`) - Cursor IDE
  - `AiderProvider` (`aider.py`) - Aider pair programmer
  - `CopilotProvider` (`copilot.py`) - GitHub Copilot CLI

- **ProviderRegistry** (`registry.py`)
  - Auto-discovers all providers at runtime
  - No hardcoded provider lists
  - Easy to extend with new providers

**Design:** Providers return DATA (dataclasses), not formatted strings.

#### 3. **Presentation Layer** (`ui/formatter.py`)
Centralized formatting for all preview content:
- **PreviewFormatter** - Handles all ANSI formatting
  - `format_complete_preview()` - Format complete preview
  - `format_context_files()` - Format context file list
  - `format_session_stats()` - Format session information
  - `format_git_status()` - Format git status
  - And more...

**Design:** Single source of truth for formatting logic.

#### 4. **Integration Layer** (`ui/preview.py`)
Orchestrates the complete flow:
- `generate_provider_preview()` - Main entry point
  - Gets provider from ProviderRegistry
  - Calls `collect_preview_data()` on provider
  - Passes data to PreviewFormatter
  - Returns formatted string

**Architecture Flow:**
```
User selects project in fzf
    ↓
_preview_helper.py called
    ↓
generate_provider_preview(path, provider_name)
    ↓
ProviderRegistry.get(provider_name)
    ↓
provider.collect_preview_data(path)
    → Returns ProviderPreviewData (structured)
    ↓
PreviewFormatter.format_complete_preview(path, data)
    → Returns formatted string
    ↓
Display in fzf preview pane
```

**Key Benefits:**
- ✅ Separation of concerns: Data vs Presentation
- ✅ No hardcoded provider lists (auto-discovery)
- ✅ Easy to add new providers (extend AIProvider)
- ✅ Strongly typed (no dict coupling)
- ✅ Centralized formatting (easier to maintain)
- ✅ Testable components (644 tests and growing)

### Project Discovery
1. Scans configured paths for `.git` directories
2. Respects `max_depth` and `prune_dirs` settings
3. Supports manual path registration (non-git projects)
4. Preserves symlinks (doesn't resolve to real paths)

### Storage
- **Config:** `~/.config/ai-launcher/config.toml` (TOML format)
- **History:** `~/.config/ai-launcher/history` (bash)
- **Manual Paths:** Passed via `--manual-paths` CLI flag (no persistent storage)

### Provider Configuration
```toml
[provider]
default = "claude-code"  # Default provider for all projects

# Per-project overrides (optional)
[provider.per_project]
"/home/user/my-project" = "gemini"
```

### UI Components
- **Welcome Screen:** Shows on startup, checks dependencies
- **Project Selector:** fzf-powered tree view with fuzzy search
- **Preview Pane:** Shows CLAUDE.md, git status, and directory contents
- **Action Menu:** Rescan, Add path, Remove path
- **Startup Report:** Context transparency display showing:
  - Context sources (CLAUDE.md, memory, settings, git)
  - Session configuration (permissions, MCP servers, hooks, model)
  - Provider context (config files, shared context)
  - Session activity (last used, history size)

### Preview Pane Order (Important!)
1. **CLAUDE.md** (first 20 lines) - if exists
2. **Git status** (up to 15 changed files) - if git repo
3. **Contents** (20 items, folders first) - always shown

## File Structure

```
ai-launcher/
├── bin/
│   └── ai-launcher              # Bash prototype
├── src/ai_launcher/             # Python package
│   ├── __init__.py              # Version: 0.1.0
│   ├── __main__.py              # Entry point
│   ├── cli.py                   # Main CLI (Typer)
│   ├── core/                    # Core logic
│   │   ├── config.py            # TOML config management
│   │   ├── discovery.py         # Project discovery
│   │   ├── models.py            # Data models (Project)
│   │   ├── provider_data.py     # Data structures (ProviderPreviewData, etc.)
│   │   ├── provider_discovery.py # Provider detection
│   │   ├── context_analyzer.py  # Context analysis
│   │   ├── context_composer.py  # Context composition
│   │   ├── context_layers.py    # Context layer abstractions
│   │   └── org_detector.py      # Organization detection
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
│   │   ├── configuration.py     # Configuration UI
│   │   ├── settings.py          # Settings menu
│   │   ├── startup_report.py    # Startup transparency report
│   │   ├── shared_context.py    # Shared context display
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
├── tests/                       # Test suite (644 tests)
│   ├── conftest.py              # Shared fixtures
│   ├── test_browser.py          # Directory browser tests
│   ├── test_cli.py              # CLI tests
│   ├── test_config.py           # Config tests
│   ├── test_claude_data.py      # Claude data collection tests
│   ├── test_claude_provider.py  # Claude provider tests
│   ├── test_configuration_preview.py  # Configuration preview tests
│   ├── test_discovery.py        # Project discovery tests
│   ├── test_formatter.py        # Formatter tests
│   ├── test_git.py              # Git utility tests
│   ├── test_integration.py      # Integration tests
│   ├── test_integration_phase7.py  # Phase 7 integration tests
│   ├── test_logging.py          # Logging tests
│   ├── test_paths.py            # Path utility tests
│   ├── test_preview.py          # Preview tests
│   ├── test_preview_refactored.py  # Refactored preview tests
│   ├── test_provider_data.py    # Data structure tests
│   ├── test_provider_discovery_refactored.py  # Discovery tests
│   ├── test_providers.py        # Provider tests
│   ├── test_selector.py         # Selector tests
│   ├── test_startup_report.py   # Startup report tests
│   ├── test_terminal.py         # Terminal title tests
│   └── test_copilot_provider.py # Copilot provider tests
├── docs/                        # Documentation
│   ├── configuration.md
│   ├── installation.md
│   ├── troubleshooting.md
│   └── windows-terminal.md
├── CHANGELOG.md                 # Version history
├── README.md                    # User documentation
├── pyproject.toml               # Package configuration
└── CLAUDE.md                    # This file!
```

## Recent Changes (February 2026 Refactoring)

### What Changed
Between Feb 9-12, 2026, the codebase underwent a major refactoring to improve architecture and maintainability:

1. **Separation of Concerns** (Feb 12)
   - Split data collection from presentation
   - Providers now return structured data (dataclasses)
   - Formatting centralized in PreviewFormatter
   - Removed dict coupling and magic keys

2. **Provider Abstraction Enhanced** (Feb 12)
   - Added `collect_preview_data()` to all providers
   - Claude-specific data collection integrated into `claude.py`
   - Added helper methods to base class with sensible defaults
   - Each provider now owns its cleanup logic

3. **Dynamic Provider Discovery** (Feb 12)
   - Removed hardcoded `SUPPORTED_PROVIDERS` list
   - ProviderDiscovery now uses ProviderRegistry
   - Auto-discovery makes adding providers easier
   - Follows open/closed principle

4. **Comprehensive Testing** (Feb 12)
   - Added comprehensive tests across all new components (301 total)
   - Test coverage: 87-99% on new code
   - Integration tests verify complete flow
   - All tests passing

5. **Terminal Window Title** (Feb 12)
   - Automatic terminal title setting when launching projects
   - Customizable format: `{project} → {provider}` (default)
   - Smart terminal detection (xterm, iTerm2, GNOME Terminal, Windows Terminal, tmux)
   - Configurable via `set_terminal_title` and `terminal_title_format` in config
   - Improves multi-window workflow identification

### Preview API
```python
from ai_launcher.ui.preview import generate_provider_preview

# Generate formatted preview for a project
preview_text = generate_provider_preview(project_path, "claude-code")
print(preview_text)
```

## Multi-Provider Usage

### Discovery Commands

**Full discovery report:**
```bash
ai-launcher --discover ~/projects
```
Shows:
- Discovered projects (git repos + manual paths)
- Installed AI providers with versions
- Context statistics (file count, total size)
- Next steps and usage tips

**Interactive context viewer:**
```bash
ai-launcher --context ~/projects
```
Two-panel fzf interface showing:
- Left panel: Providers and projects
- Right panel: Detailed context breakdown
  - For providers: config files, cache size, categories
  - For projects: context files, git status

### Adding a New Provider

The refactored architecture makes adding providers **much easier**. No hardcoded lists needed!

**Step 1:** Create provider class in `src/ai_launcher/providers/your_provider.py`:

```python
# src/ai_launcher/providers/windsurf.py
import shutil
from pathlib import Path
from typing import List, Optional

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.providers.base import AIProvider, ProviderMetadata

class WindsurfProvider(AIProvider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="windsurf",
            display_name="Windsurf",
            command="windsurf",
            description="AI-powered IDE",
            config_files=["WINDSURF.md", ".windsurfrc"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        return shutil.which("windsurf") is not None

    def launch(self, project_path: Path) -> None:
        import os, subprocess
        os.chdir(project_path)
        subprocess.run(["windsurf", "."], check=True)

    def cleanup_environment(self, verbose=False, cleanup_config=None) -> None:
        if cleanup_config is None or not cleanup_config.enabled:
            return
        # Clean windsurf-specific files
        cache = Path.home() / ".windsurf" / "cache"
        if cache.exists():
            import shutil
            shutil.rmtree(cache, ignore_errors=True)

    # Optional: Provide preview data
    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        context_files = []

        # Check for WINDSURF.md
        windsurf_md = project_path / "WINDSURF.md"
        if windsurf_md.exists():
            stat = windsurf_md.stat()
            with open(windsurf_md, "r") as f:
                lines = f.readlines()
                context_files.append(ContextFile(
                    path=windsurf_md,
                    label="WINDSURF.md",
                    exists=True,
                    size_bytes=stat.st_size,
                    line_count=len(lines),
                    file_type="project",
                ))

        return ProviderPreviewData(
            provider_name=self.metadata.display_name,
            context_files=context_files,
            global_config_paths=self.get_global_context_paths(),
        )

    # Optional: Provide global config paths
    def get_global_context_paths(self) -> List[Path]:
        return [Path.home() / ".windsurf"]
```

**Step 2:** That's it! The provider is **auto-discovered** by ProviderRegistry.

**Step 3:** Test it:
```bash
ai-launcher --providers  # Should show Windsurf
ai-launcher --discover   # Should detect if installed
```

**No registry updates needed!** The ProviderRegistry automatically:
- Scans `providers/` directory
- Finds all AIProvider subclasses
- Instantiates and registers them

**Optional Enhancements:**
- Create `windsurf_data.py` for complex data collection
- Override `get_context_categories()` for custom file categorization
- Override `get_project_data_pattern()` for session data location
- Add comprehensive tests in `tests/test_windsurf_provider.py`

## Development Conventions

### Code Style
- **Python:** Black (88 char), strict type hints, docstrings
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

## Recent Changes (2026-02-06)

### Rebranding Complete
- Removed all `claude-launcher` references (23 files)
- Updated to `ai-launcher` throughout
- Deleted old `bin/claude-launcher` (664 lines)
- Created new `bin/ai-launcher` with enhancements

### Bash Script Enhancements
- ✅ Added Solent Labs™ branding to headers
- ✅ Added platform detection (Linux/macOS/WSL/Windows)
- ✅ Added auto-install for Claude CLI with prompts
- ✅ Fixed preview pane to show folders first
- ✅ Fixed preview pane to always show contents
- ✅ Fixed config directory creation bugs
- ✅ Improved header centering and layout

### Documentation Updates
- ✅ Rewrote CHANGELOG.md for fresh v0.1.0 launch
- ✅ Created this CLAUDE.md file
- ✅ Documented layered context architecture (see SESSION_NOTES.md)

## Layered Context Architecture (Planned)

### Vision
Support organization-wide shared context across projects.

### Structure
```
~/projects/solentlabs/
├── devkit/
│   └── shared-context/          # Central knowledge base
│       ├── STANDARDS.md         # Solent Labs coding standards
│       ├── DEVKIT-PATTERNS.md   # Common patterns
│       ├── OPERATIONS.md        # Ops procedures
│       ├── SECURITY.md          # Security guidelines
│       └── TESTING.md           # Testing standards
│
├── my-app/
│   ├── CLAUDE.md                # Project-specific rules
│   └── .solent/
│       └── context -> ../../devkit/shared-context/
```

### Usage Pattern
Each project's CLAUDE.md references shared context:
```markdown
## Solent Labs™ Standards
Reference materials:
- [Coding Standards](/.solent/context/STANDARDS.md)
- [DevKit Patterns](/.solent/context/DEVKIT-PATTERNS.md)
- [Security Guidelines](/.solent/context/SECURITY.md)
```

### Future Enhancements
- AI Launcher could detect `.solent/` and show shared context status
- `ai-launcher --init-solent` command to set up symlinks
- Preview pane could show "✓ Solent Labs Standards" indicator

## Common Commands

### Development
```bash
# Run bash prototype
./bin/ai-launcher ~/projects

# Install Python package locally
pip install -e .

# Run Python package
ai-launcher ~/projects

# Run tests
pytest tests/ -v --cov=ai_launcher

# Format code
black src/ tests/

# Type check
mypy src/

# Lint
flake8 src/ tests/
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

### Test Suite (644 Tests)
The project has comprehensive test coverage:

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

### Bash Script
- `bash` 4.0+
- `fzf` (auto-installs if missing)
- `claude` CLI (auto-prompts for installation)
- Standard UNIX tools: `grep`, `find`, `ls`, `sed`, `awk`

### Python Package
- Python 3.8+
- `iterfzf>=1.4.0` (Python wrapper for fzf)
- `typer>=0.12.0` (CLI framework)
- `platformdirs>=4.0.0` (Platform-specific directories)
- `tomli>=2.0.0` (TOML parsing, Python <3.11)
- `tomli-w>=1.0.0` (TOML writing)

### Development Dependencies
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0`
- `black>=23.0.0`
- `mypy>=1.0.0`
- `flake8>=6.0.0`
- `isort>=5.12.0`
- `pre-commit>=3.0.0`

## Security Considerations

- **No cloud dependencies:** All data stays local
- **No telemetry:** No usage tracking or analytics
- **Shell injection:** All user input is properly quoted/escaped
- **Path traversal:** Paths are validated before use
- **Symlink handling:** Preserved but not exploited

## Troubleshooting

### "Claude Code CLI is not installed"
The launcher will auto-prompt for installation. Manual install:
```bash
# Linux/macOS/WSL
curl -fsSL https://claude.ai/install.sh | bash

# Windows PowerShell
irm https://claude.ai/install.ps1 | iex
```

### "No projects found"
- Check scan paths in config: `~/.config/ai-launcher/config.toml`
- Or pass paths as arguments: `ai-launcher ~/projects`

### Preview pane shows errors
- Ensure CLAUDE.md is valid UTF-8
- Check git repository isn't corrupted
- Verify file permissions

### fzf not found
The bash script will auto-install fzf on Linux/WSL. Manual install:
```bash
# Linux
sudo apt install fzf

# macOS
brew install fzf

# Or build from source
git clone https://github.com/junegunn/fzf.git ~/.fzf
~/.fzf/install
```

## Links

- **Repository:** https://github.com/solentlabs/ai-launcher
- **Issues:** https://github.com/solentlabs/ai-launcher/issues
- **Claude Code Docs:** https://code.claude.com/docs/en/setup
- **Solent Labs:** https://github.com/solentlabs

---

**Made by Solent Labs™** - Building tools for developers who value privacy and local-first software.
