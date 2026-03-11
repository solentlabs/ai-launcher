# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-03-11

### Changed
- **Rename "Boundary Protection" to "Sibling Projects"** — the old name implied enforcement that doesn't exist. The feature only shows nearby projects for awareness, so the labeling now reflects that honestly. "Forbidden"/"Allowed" replaced with "Other"/"Selected".

## [0.3.0] - 2026-03-05

### Removed
- **Dead code cleanup** — removed `ConfigManager` (`core/config.py`), `settings.py`, and `shared_context.py` which were never called by the CLI
- Removed `HistoryConfig` dataclass from `core/models.py` (only used by deleted ConfigManager)
- Removed `docs/terminal-title.md` — folded troubleshooting content into `docs/troubleshooting.md`
- Removed `docs/CONTEXT_TRANSPARENCY_IMPLEMENTATION.md` and `docs/REFACTORING_2026_02.md` (completed checklists, archived to journal)
- Removed tests for deleted code (`test_config.py`, `test_integration.py`, `test_settings_menu.py`, `test_shared_context.py`)

### Changed
- **CLAUDE.md rewrite** — trimmed from 698 to ~320 lines by removing duplication and linking to canonical docs
- **Documentation accuracy pass** — fixed all CLI syntax (`ai-launcher ~/projects` → `ai-launcher claude ~/projects`), removed references to non-existent flags (`--providers`, `--startup-report`, `--context-health`)
- **README.md** — converted relative doc links to full GitHub URLs for PyPI compatibility, added PyPI downloads badge
- **docs/configuration.md** — complete rewrite from config.toml reference to CLI flags reference
- **docs/troubleshooting.md** — removed stale config.toml references, added terminal title troubleshooting section
- **docs/adding-providers.md** — updated provider status table, replaced manual registration with auto-discovery
- **docs/context-transparency.md** — removed proposed/unimplemented CLI commands
- Renamed docs to lowercase kebab-case for consistency (`ARCHITECTURE.md` → `architecture.md`, etc.)
- Added `docs/README.md` index for documentation navigation

## [0.2.1] - 2026-03-04

### Fixed
- Quote `sys.executable` and helper script paths in all fzf `--preview` commands — fixes `'C:\Program' is not recognized` errors on Windows when Python is installed under `C:\Program Files\...`

### Changed
- Added `quote_for_fzf` and `fzf_preview_cmd` helpers to `utils/paths.py` to centralise fzf command quoting
- Removed redundant `import sys` from UI modules that no longer reference it directly

## [0.2.0] - 2026-03-03

### Added
- Auto-download fzf when missing — prompts user and fetches from GitHub releases
- Cross-platform Python helpers for fzf preview commands (`_browser_preview.py`, `_file_preview.py`)

### Fixed
- Cross-platform encoding: all fzf subprocess calls use binary mode with explicit UTF-8 encode/decode, fixing Windows cp1252 mangling
- Delimiter escaping: consistent `\\t\\t` in all fzf `--delimiter` args (raw tab chars were mangled by Windows command-line processing)
- Project discovery on native Windows — follow NTFS junctions and symlinks (Python 3.12+ treats junctions as symlinks, causing `os.walk` to silently skip them)
- Circular symlink protection during project scanning via real-path cycle detection
- Detect `.git` files (Git submodules) in addition to `.git` directories
- Replace hardcoded `:` path separators with `os.pathsep` for Windows
- Fix root path detection to work on Windows (no hardcoded `/`)
- Cross-platform test compatibility (macOS symlink resolution, Windows subprocess handling)
- Removed references to non-existent `--setup` CLI flag
- Codecov integration (tokenless org-level auth)

### Changed
- All fzf callers (settings, shared context, browser, context viewer) use consistent binary-mode pattern
- Release script (`scripts/release.py`) extended with full lifecycle automation: PR merge, CI wait, tag, and GitHub release creation
- Tag protection and publish workflows hardened for CI reliability

> **Note:** Versions 0.1.1–0.1.3 were incremental debugging releases and have been yanked from PyPI. All their fixes are included in 0.2.0.

## [0.1.0] - 2026-03-03

### Added

#### Multi-Provider Support (NEW)
- **Provider abstraction layer** - Extensible system for multiple AI tools
- **ClaudeProvider** - Full Claude Code integration
- **GeminiProvider** - Google Gemini CLI support
- **CursorProvider** - Cursor IDE integration
- **AiderProvider** - Aider pair programmer integration
- **CopilotProvider** - GitHub Copilot CLI integration
- **Provider registry** - Centralized provider management
- **Discovery mode** (`--discover`) - Shows installed providers and context
- **Context viewer** (`--context`) - Interactive visualization of AI context files
- **Provider listing** (via `--discover`) - Quick overview of available tools
- **Per-project provider override** - Different AI tools per project
- **Context analysis** - Categorizes and analyzes provider context files
- **Provider metadata** - Version detection, installation status, context stats

#### Enhanced Startup Report - Complete Context Transparency
- **Session Configuration** - Shows all session-affecting settings
  - Auto-approved commands count (from `.claude/settings.local.json`)
  - MCP servers status (from `~/.claude/mcp.json`)
  - Hooks configuration (from `~/.claude/hooks.json`)
  - Model selection (from `~/.claude/settings.json`)
- **Claude Memory** - Personal and project memory files with line counts
- **Claude Skills** - Installed skills count and names
- **Global Context** - Complete breakdown of all loaded context files
  - Cache files (changelog, etc.)
  - Plan files (active plans)
  - Plugin READMEs
  - Project memories and journals from other projects
- **Sibling Projects** - Sibling project awareness
  - Shows nearby projects in the same parent directory
  - Highlights which project is selected
- **Complete transparency** - Every file loaded into context is now visible
- Available in both Python and bash implementations

#### Terminal Window Title
- **Automatic title setting** - Terminal title shows project and provider
- **Customizable format** - Configure via `terminal_title_format` in config
- **Format variables** - `{project}`, `{provider}`, `{path}`, `{parent}`
- **Smart terminal detection** - Works with xterm, iTerm2, GNOME Terminal, Windows Terminal, tmux, etc.
- **tmux support** - Special handling for tmux sessions
- **Enable/disable** - Control via `set_terminal_title` config option
- **Example formats:**
  - `"{project} → {provider}"` → "my-app → Claude Code" (default)
  - `"🤖 {project} | {provider}"` → "🤖 my-app | Claude Code"
  - `"{parent}/{project}"` → "projects/my-app"

#### Project Management
- Interactive project selector with tree-structured navigation
- fzf-powered fuzzy search interface
- Automatic git repository discovery with configurable scan paths
- Manual project management (add/remove paths)
- Rich preview pane showing:
  - CLAUDE.md and other context files (first 20 lines)
  - Git status (up to 15 changed files)
  - Directory contents (20 items, folders first) - always shown
- Tree view with hierarchical folder structure
- Smart cursor positioning (starts on last opened project)
- Symlink support for manual paths
- Exact substring matching for project filtering
- Action menu (Rescan, Add path, Remove path)

#### Infrastructure
- Cross-platform support (Linux, macOS, Windows/WSL)
- Pre-commit hooks for code quality
- Comprehensive test suite with pytest
- **Solent Labs™ branding** in UI headers
- **Claude CLI auto-install** with platform detection
- Platform-specific installation instructions and prompts
- Automatic config directory creation

### Changed
- **Complete rebranding** from claude-launcher to ai-launcher (23 files)
- **Replaced hardcoded Claude logic** with provider abstraction system
- `launch_claude()` → `launch_ai()` with provider parameter
- Updated all module docstrings and references
- Config paths now use `~/.config/ai-launcher/` instead of `~/.claude/`
- Config now includes `[provider]` section for multi-tool support
- Preview pane now **always shows contents** (not either/or with git)
- Directory listings now show **folders first**, then files
- Simplified menu header text to avoid truncation
- Enhanced bash script with 665 lines of functionality
- CLI help text updated to reflect multi-provider support

### Fixed
- Config directory creation errors (mkdir -p before writes)
- Preview pane folders-first sorting logic
- Text truncation in fzf headers
- Manual path directory creation bug

### Technical Details
- Python 3.8+ compatibility
- SQLite storage for manual paths and history
- Platform-specific config and data directories (`~/.config/ai-launcher/`)
- Robust error recovery (database corruption, missing paths)
- TOML-based configuration
- First-run setup wizard
- Dual implementation: Bash prototype + Python package
