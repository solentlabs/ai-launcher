# Architecture Documentation

## Overview

AI Launcher is designed as a local-first, privacy-focused tool for managing AI coding assistant contexts across multiple projects. This document explains the architectural decisions and design patterns.

---

## Design Principles

### 1. Local-First
- All data stays on the user's machine
- No cloud dependencies or telemetry
- Works completely offline
- User maintains full control

### 2. Privacy-First
- No data collection or tracking
- No external API calls (except Claude CLI itself)
- Sensitive paths stay local
- History stored locally only

### 3. Developer Experience
- Fast fuzzy search (<100ms response)
- Minimal configuration required
- Intuitive keyboard navigation
- Clear visual feedback

### 4. Extensibility
- Plugin architecture for future AI tools
- Shared context system for org-wide standards
- Configurable via simple TOML files

---

## Dual Implementation Strategy

### Why Two Versions?

**Bash Script (`bin/ai-launcher`):**
- **Purpose:** Rapid prototyping and iteration
- **Benefits:**
  - No dependencies to install
  - Instant testing of new features
  - Easy to read and modify
  - Works everywhere bash exists
- **Drawbacks:**
  - Harder to test automatically
  - Limited data structures
  - No typing or IDE support

**Python Package (`src/ai_launcher/`):**
- **Purpose:** Production-ready distribution
- **Benefits:**
  - Proper testing (pytest, coverage)
  - Type safety (mypy)
  - Better data structures (SQLite, dataclasses)
  - Installable via pip/pipx
- **Drawbacks:**
  - Slower to iterate
  - Requires Python runtime
  - More ceremony (imports, packaging)

### Development Flow
```
1. Prototype feature in bash
2. Test manually with real projects
3. Iterate quickly
4. Once proven, implement in Python
5. Add proper tests
6. Release
```

This approach lets us move fast while maintaining quality.

---

## Project Discovery

### Automatic Discovery

**Algorithm:**
```
for each scan_path in config.scan.paths:
    traverse_directory(scan_path, max_depth=config.scan.max_depth):
        if directory in config.scan.prune_dirs:
            skip  # Don't recurse into node_modules, venv, etc.
        if directory contains .git/:
            add to projects
```

**Why `.git` detection?**
- Reliable indicator of project root
- Most projects are git repos
- Faster than other heuristics
- Easy to understand

### Manual Projects

**Use cases:**
- Non-git projects (legacy, experimental)
- Symlinked directories
- Network mounts
- Specific subdirectories

**Storage:**
- Bash: Text file (`~/.config/ai-launcher/manual-paths`)
- Python: SQLite database

**Operations:**
- Add: Interactive directory browser
- Remove: Interactive selection from list
- List: Show all manual paths

---

## Layered Context System

### Problem Statement

Organizations often have:
- Common coding standards across projects
- Shared patterns and best practices
- Consistent security/testing guidelines
- Project-specific requirements

**Challenge:** How to maintain both without duplication?

### Solution: Three-Tier Hierarchy

```
┌─────────────────────────────────────────┐
│  Organization Level (Solent Labs™)      │  ← Shared standards
├─────────────────────────────────────────┤
│  Project Level                          │  ← Specific app rules
├─────────────────────────────────────────┤
│  Module Level (Optional)                │  ← Component rules
└─────────────────────────────────────────┘
```

### Implementation

**1. Central Knowledge Base:**
```
~/projects/solentlabs/devkit/shared-context/
├── README.md                # How to use this system
├── STANDARDS.md             # Coding standards
├── DEVKIT-PATTERNS.md       # Common patterns
├── OPERATIONS.md            # Ops procedures
├── SECURITY.md              # Security guidelines
└── TESTING.md               # Testing standards
```

**2. Project Integration:**
```
~/projects/solentlabs/my-app/
├── CLAUDE.md                # Project-specific rules
└── .solent/                 # Solent Labs integration
    └── context -> ../../devkit/shared-context/  # Symlink
```

**3. Reference Pattern:**
```markdown
# Project CLAUDE.md

## Solent Labs™ Standards
See shared context:
- [Coding Standards](/.solent/context/STANDARDS.md)
- [DevKit Patterns](/.solent/context/DEVKIT-PATTERNS.md)

## Project-Specific Rules
[Unique to this project...]
```

### Benefits

- **DRY:** Standards defined once, used everywhere
- **Consistency:** All projects follow same patterns
- **Maintainability:** Update one place, affects all projects
- **Flexibility:** Projects can override when needed
- **Offline:** Symlinks work without network
- **Versionable:** Shared context tracked in git

### Future Enhancements

**AI Launcher Integration:**
- Detect `.solent/` directory
- Show "✓ Solent Labs Standards" in preview
- `--init-solent` command to set up symlinks
- Validate CLAUDE.md references shared context

**DevKit CLI:**
```bash
# Future commands
devkit init-project my-app    # Create with Solent Labs structure
devkit validate-context       # Check CLAUDE.md references
devkit update-shared-context  # Pull latest standards
```

---

## Storage Architecture

### Configuration

**Format:** TOML (Tom's Obvious, Minimal Language)
**Location:** Platform-specific via `platformdirs`

```toml
[scan]
paths = ["~/projects"]
max_depth = 5
prune_dirs = ["node_modules", "venv"]

[ui]
preview_width = 70
show_git_status = true

[history]
max_entries = 50
```

**Why TOML?**
- Human-readable and writable
- Comments supported
- Strong typing (arrays, tables, strings)
- Better than JSON for config files
- Simpler than YAML (no footguns)

### History

**Purpose:** Remember last-opened project (Bash script only)

**Format (Bash only):**
```
1738856400|/home/user/projects/my-app
1738855000|/home/user/projects/other-app
```
Timestamp | Path

**Note:** The Python version does not track history or last-opened projects. This feature is exclusive to the bash script prototype.

**Benefits (Bash only):**
- Cursor starts on recent project (marked with ⭐)
- Reduce navigation time

### Manual Paths

**Storage:**
- Bash: Line-separated text file
- Python: SQLite table

**Why separate from config?**
- Config is manually edited
- Manual paths added via UI
- Don't mix user edits with programmatic changes

---

## User Interface

### Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Welcome Screen                       │
│  - Shows branding                                       │
│  - Checks dependencies (fzf, claude)                    │
│  - Offers to install missing tools                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Project Selector (fzf)                 │
│  ┌─────────────────────┬──────────────────────────────┐ │
│  │   Project List      │     Preview Pane             │ │
│  │   (tree view)       │                              │ │
│  │                     │  - CLAUDE.md (if exists)     │ │
│  │  ★ recent-project   │  - Git status (if git)       │ │
│  │    └─ module-a      │  - Contents (always)         │ │
│  │    └─ module-b      │                              │ │
│  │  another-project    │                              │ │
│  │    └─ frontend      │                              │ │
│  │                     │                              │ │
│  │  ↻ Rescan           │                              │ │
│  │  + Add path         │                              │ │
│  │  - Remove path      │                              │ │
│  └─────────────────────┴──────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Claude CLI Launch                      │
│  cd /selected/project && exec claude                    │
└─────────────────────────────────────────────────────────┘
```

### Preview Pane Order

**Critical: Always show in this order:**

1. **CLAUDE.md** (first 20 lines) - if exists
   - Shows project context immediately
   - Most important information

2. **Git Status** (up to 15 files) - if git repo
   - Shows uncommitted changes
   - Helps user decide if clean state

3. **Contents** (20 items) - always shown
   - Folders first, then files
   - Gives overview of project structure
   - Never omit this section

**Why this order?**
- Context before details
- Most relevant info first
- Consistent user experience

### Tree View Format

```
projects/
  utilities/
    ★ ai-launcher
    other-tool
  web/
    frontend/
      react-app
    backend/
      api-server
```

**Features:**
- Hierarchical display (2 spaces per level)
- ★ marks recently opened
- Folders end with `/` (visual distinction)
- Sorted alphabetically within each level

---

## Platform Compatibility

### Supported Platforms

| Platform     | Status | Notes                          |
|--------------|--------|--------------------------------|
| Linux        | ✅ Full | Primary development platform  |
| WSL          | ✅ Full | Windows Subsystem for Linux   |
| macOS        | ✅ Full | Tested with homebrew          |
| Windows      | ⚠️ Partial | PowerShell for install only |

### Platform-Specific Paths

**Config Directory:**
- Linux/WSL: `~/.config/ai-launcher/`
- macOS: `~/Library/Application Support/ai-launcher/`
- Windows: `%LOCALAPPDATA%\ai-launcher\`

**Data Directory:**
- Linux/WSL: `~/.local/share/ai-launcher/`
- macOS: `~/Library/Application Support/ai-launcher/`
- Windows: `%LOCALAPPDATA%\ai-launcher\`

**Log Directory:**
- Linux/WSL: `~/.local/state/ai-launcher/` or `~/.cache/ai-launcher/`
- macOS: `~/Library/Logs/ai-launcher/`
- Windows: `%LOCALAPPDATA%\ai-launcher\Logs\`

**Implementation:** Uses `platformdirs` library for correct paths

### Claude CLI Installation

**Platform Detection:**
```bash
detect_platform() {
    case "$(uname -s)" in
        Linux*)
            if grep -qi microsoft /proc/version; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        Darwin*)
            echo "macos"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "windows"
            ;;
    esac
}
```

**Install Commands:**
- Linux/macOS/WSL: `curl -fsSL https://claude.ai/install.sh | bash`
- Windows: `irm https://claude.ai/install.ps1 | iex`

---

## Security Considerations

### Threat Model

**In Scope:**
- Shell injection via user input
- Path traversal attacks
- Symlink exploits
- Malicious config files

**Out of Scope:**
- Physical access attacks
- Compromised Claude CLI
- OS-level vulnerabilities

### Mitigations

**1. Input Validation**
```bash
# Always quote variables
cd "$selected_path"  # Not: cd $selected_path

# Validate paths exist
[[ -d "$path" ]] || die "Invalid path"
```

**2. No Arbitrary Code Execution**
- Don't eval user input
- Don't source unknown files
- Config is data (TOML), not code

**3. Symlink Handling**
- Preserve symlinks (don't resolve)
- Validate target exists before following
- Don't allow .. traversal

**4. Secure Defaults**
- Config files created with 0644 permissions
- History/data files with 0600 permissions
- No world-writable files

---

## Performance Characteristics

### Benchmarks (Estimated)

| Operation              | Time     | Notes                    |
|------------------------|----------|--------------------------|
| Launch + scan 100 dirs | <500ms   | Cold start               |
| Launch (cached)        | <100ms   | Warm start               |
| Fuzzy search keystroke | <10ms    | fzf is very fast         |
| Preview update         | <50ms    | Read CLAUDE.md + git     |
| Project switch         | <100ms   | cd + exec claude         |

### Optimization Strategies

**1. Prune Directories**
```toml
prune_dirs = [
    "node_modules",  # Can have 1000s of dirs
    "venv",          # Python packages
    ".cache",        # Build artifacts
]
```

**2. Limit Scan Depth**
```toml
max_depth = 5  # Don't recurse forever
```

**3. Lazy Loading**
- Only scan when needed
- Cache discovery results
- Update incrementally on rescan

**4. Async Operations (Future)**
- Scan in background
- Update UI progressively
- Show partial results immediately

---

## Testing Strategy

### Bash Script

**Current State:**
- Manual testing only
- No automated tests

**Future:**
- BATS (Bash Automated Testing System)
- Integration tests with fixtures
- Mock fzf for testing selections

### Python Package

**Current State:**
- Unit tests for core logic
- pytest with coverage
- Type checking with mypy

**Test Structure:**
```
tests/
├── test_cli.py           # CLI entry point
├── test_config.py        # Config loading/saving
├── test_discovery.py     # Project discovery
├── test_storage.py       # SQLite operations
└── test_integration.py   # End-to-end flows
```

**Coverage Target:** 80%+

---

## Future Architecture

### Multi-Tool Support

**Goal:** Support multiple AI coding assistants

**Design:**
```toml
[ai-tools]
default = "claude-code"

[ai-tools.claude-code]
command = "claude"
supports_context = true

[ai-tools.gemini-cli]
command = "gemini"
supports_context = true

[ai-tools.cursor]
command = "cursor"
supports_context = false
```

**Launcher Logic:**
```bash
case "$tool" in
    claude-code)
        exec claude ;;
    gemini-cli)
        exec gemini ;;
    cursor)
        cursor "$path" ;;  # Different invocation
esac
```

### Plugin System (Aspirational)

**Goal:** Third-party extensions

**Example:**
```python
# ~/.config/ai-launcher/plugins/custom_preview.py
def preview(project: Project) -> str:
    # Custom preview logic
    return "My custom preview"
```

**Integration:**
```python
from ai_launcher.plugins import load_plugins

plugins = load_plugins()
for plugin in plugins:
    if plugin.provides("preview"):
        preview = plugin.preview(project)
```

---

## References

- **fzf:** https://github.com/junegunn/fzf
- **platformdirs:** https://pypi.org/project/platformdirs/
- **TOML spec:** https://toml.io/en/
- **Claude Code:** https://code.claude.com/docs/en/setup

---

**Last Updated:** 2026-02-06
**Status:** Living document, will evolve with project
