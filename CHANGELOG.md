# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- **Provider listing** (`--providers`) - Quick overview of available tools
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
- **Boundary Protection** - Sibling project detection for security
  - Shows forbidden projects
  - Confirms allowed project scope
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

## [0.1.0] - TBD

Initial release.
