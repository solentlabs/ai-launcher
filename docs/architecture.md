# Architecture Documentation

## Overview

AI Launcher is designed as a local-first, privacy-focused tool for managing AI coding assistant
contexts across multiple projects. This document explains the architectural decisions and design
patterns.

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

```text
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

```text
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

```text
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

```text
~/projects/solentlabs/devkit/shared-context/
├── README.md                # How to use this system
├── STANDARDS.md             # Coding standards
├── DEVKIT-PATTERNS.md       # Common patterns
├── OPERATIONS.md            # Ops procedures
├── SECURITY.md              # Security guidelines
└── TESTING.md               # Testing standards
```

**2. Project Integration:**

```text
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

**Format:** TOML (Tom's Obvious, Minimal Language) **Location:** Platform-specific via
`platformdirs`

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

```text
1738856400|/home/user/projects/my-app
1738855000|/home/user/projects/other-app
```

Timestamp | Path

**Note:** The Python version does not track history or last-opened projects. This feature is
exclusive to the bash script prototype.

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

```text
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

Enter on a project launches the default tool, as drawn. Ctrl-O opens the
[Open With list](#open-with-list) first.

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

```text
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

| Platform | Status     | Notes                        |
| -------- | ---------- | ---------------------------- |
| Linux    | ✅ Full    | Primary development platform |
| WSL      | ✅ Full    | Windows Subsystem for Linux  |
| macOS    | ✅ Full    | Tested with homebrew         |
| Windows  | ⚠️ Partial | PowerShell for install only  |

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

### 1. Input Validation

```bash
# Always quote variables
cd "$selected_path"  # Not: cd $selected_path

# Validate paths exist
[[ -d "$path" ]] || die "Invalid path"
```

### 2. No Arbitrary Code Execution

- Don't eval user input
- Don't source unknown files
- Config is data (TOML), not code

### 3. Symlink Handling

- Preserve symlinks (don't resolve)
- Validate target exists before following
- Don't allow .. traversal

### 4. Secure Defaults

- Config files created with 0644 permissions
- History/data files with 0600 permissions
- No world-writable files

---

## Performance Characteristics

### Benchmarks (Estimated)

| Operation              | Time   | Notes                |
| ---------------------- | ------ | -------------------- |
| Launch + scan 100 dirs | <500ms | Cold start           |
| Launch (cached)        | <100ms | Warm start           |
| Fuzzy search keystroke | <10ms  | fzf is very fast     |
| Preview update         | <50ms  | Read CLAUDE.md + git |
| Project switch         | <100ms | cd + exec claude     |

### Optimization Strategies

### 1. Prune Directories

```toml
prune_dirs = [
    "node_modules",  # Can have 1000s of dirs
    "venv",          # Python packages
    ".cache",        # Build artifacts
]
```

### 2. Limit Scan Depth

```toml
max_depth = 5  # Don't recurse forever
```

### 3. Lazy Loading

- Only scan when needed
- Cache discovery results
- Update incrementally on rescan

### 4. Async Operations (Future)

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

```text
tests/
├── test_cli.py           # CLI entry point
├── test_config.py        # Config loading/saving
├── test_discovery.py     # Project discovery
├── test_storage.py       # SQLite operations
└── test_integration.py   # End-to-end flows
```

**Coverage Target:** 80%+

---

## Permission Transparency Layer

### Problem

Claude Code's three-layer permission system accumulates narrow auto-approved patterns when users
click "allow" on command prompts. These exact-match patterns (e.g.,
`Bash(python3 -m pytest tests/ -v)`) never match again with different arguments, causing persistent
permission prompts. Users have no visibility into their effective permissions across layers.

### Where It Sits in the Stack

```text
┌─────────────────────────────────────────────────────┐
│  CLI Layer (cli.py)                                 │
│  --check-permissions flag → permissions_report.py   │
├─────────────────────────────────────────────────────┤
│  Presentation Layer (formatter.py, startup_report)  │
│  Formats SessionConfig → warnings, counts, status   │
├─────────────────────────────────────────────────────┤
│  Data Transport (provider_data.py)                  │
│  SessionConfig carries data + diagnostics           │
├─────────────────────────────────────────────────────┤
│  Analysis Layer (claude.py)                         │
│  _analyze_permissions() → warnings, recommendations │
├─────────────────────────────────────────────────────┤
│  Settings Files (read-only)                         │
│  <project>/.claude/settings.local.json              │
│  ~/.claude/settings.json                            │
│  ~/.claude/settings.local.json                      │
└─────────────────────────────────────────────────────┘
```

### Data Flow

```text
Settings files → _get_claude_session_config() → _analyze_permissions()
                                                       │
                                                       ↓
                                                 SessionConfig
                                                (data + diagnostics)
                                                 /     |     \
                                                /      |      \
                                               ↓       ↓       ↓
                                          formatter  startup  permissions
                                           (pane)    (box)    (--check)
```

### SessionConfig as Data + Diagnostics Carrier

`SessionConfig` (in `provider_data.py`) carries both raw data and analyzed results:

- **Raw data**: `permissions`, `global_permissions`, `global_deny`, `global_ask`, `mcp_servers`,
  `hooks_configured`, `model`
- **Diagnostics**: `permission_warnings`, `permission_recommendations`, `has_broad_bash`
- **Provenance**: `config_file_path`, `global_config_file_path`

The analysis runs once in `_get_claude_session_config()`. Presentation layers read the pre-computed
diagnostics — they never re-analyze.

### Why the Analysis Lives in `claude.py`

Permission accumulation is Claude Code-specific. Other providers don't have:

- A three-layer settings hierarchy
- Auto-approved pattern accumulation
- Ask/deny override semantics

Putting the analysis in `claude.py` (the provider module) keeps it co-located with the settings file
reading logic and avoids polluting the core or presentation layers with Claude-specific knowledge.
Non-Claude providers return `SessionConfig` with empty diagnostic fields.

See [Permission Transparency](permission-transparency.md) for the full feature specification.

---

## Project Scope Guard

### Problem

A session launched in one project was handed work for another (a pasted handoff prompt). It did that
work from the wrong folder, under the wrong project's CLAUDE.md, settings and memory. Nothing
stopped it: broad allow rules (`Edit`, `Write`, `Bash(*)`) let Claude Code write outside its launch
folder without a prompt. That was reproduced with `claude -p` before the fix.

### Where It Sits in the Stack

```text
cli.py            scope_roots = scan paths + manual projects
                  scope_exempt = --allow-writes folders
   ↓
launch_ai()       → display_launch_info(..., scope_roots, scope_exempt)   "🔒 Scope" line
   ↓
provider.launch(project_path, scope_roots, scope_exempt)
   ↓ (ClaudeProvider only)
claude --append-system-prompt "<launched in PROJECT; flag other-project requests>"
       --settings '{"hooks": {"PreToolUse": [scope_guard]}}'
   ↓ (on every Write / Edit / MultiEdit / NotebookEdit / Bash)
python -m ai_launcher.core.scope_guard --project P --root R... [--exempt E...]
   → nothing, or {"permissionDecision": "ask", "systemMessage": reason}
```

### Decisions

- **Two layers.** The appended system prompt catches a request for another project when it arrives,
  before any reading or planning under the wrong rules. The hook catches the write itself, and it is
  enforced by code rather than left to the model.
- **Ask, not deny.** Some cross-project edits are deliberate; the user approves them in the prompt.
- **Reads are never gated.** Only writes can do damage, and prompting on reads would teach users to
  approve without reading.
- **Only writes under a scan root count.** Writes elsewhere (`/tmp`, `~/.bashrc`) are not another
  project. Claude's own folder (`~/.claude`, or `CLAUDE_CONFIG_DIR`) is exempt even under a root, so
  memory saves never prompt. Folders passed to `--allow-writes` are exempt too, for places every
  session writes on purpose, such as a shared journal.
- **Hook via `--settings`.** Verified on Claude Code 2.1.270: a `--settings` hook adds to the user's
  and project's hooks rather than replacing them, and its `ask` overrides allow rules. The
  permission dialog does not show the hook's reason, so it is also sent as `systemMessage`, which
  Claude prints under the tool call once the dialog is answered.
- **Shell commands are classified from their text** (`core/scope_guard.py`): redirects,
  file-changing commands, copy destinations and git's changing subcommands are writes; a short list
  of commands is read-only; anything else run inside another project is a write. It is a guard
  against accidents, not a sandbox.
- **Not Claude Code's sandbox.** It confines shell writes at the OS level, but it also restricts
  network access (breaking `gh`, `pip`, `git push` until configured) and needs bubblewrap on Linux.
  That is too much for a launcher to impose.
- **Fails open, visibly.** A guard error exits 1, which Claude Code shows as a non-blocking hook
  error. A bug in the guard must not stop work. The module is stdlib-only and takes about 0.1s per
  call.
- **Other providers get nothing extra.** Copilot already asks for paths outside its folder, Gemini's
  file tools refuse them, and Aider asks before editing any file not in the chat. Cursor's CLI
  behaviour is undocumented. Their `launch()` accepts `scope_roots` and ignores it; the table in
  [project-scope.md](project-scope.md) records each one. Gemini passes `scope_exempt` as
  `--include-directories`, since its own confinement would otherwise refuse an allowed folder; the
  others ignore it.
- **Bash prototype diverges.** The hook needs the Python package, so `bin/ai-launcher` has no guard.
  This is noted in the changelog.
- **Launching by name was considered and dropped.** The failure is not picking the wrong project in
  the selector. It is a session being given another project's work after launch.

---

## Open With List

### Problem

The tool is fixed when the launcher starts: `ai-launcher claude ~/projects` can only open a project
in Claude Code. Opening the same project in another installed tool, or in a plain shell, meant
leaving the launcher and finding the folder again.

### Behaviour

The picker header gains one hint line:

```text
14 projects in ~/projects/solentlabs
Type to filter • Arrows to navigate
Ctrl-O for other tools
```

| Where          | Key    | On                                       | Result                                 |
| -------------- | ------ | ---------------------------------------- | -------------------------------------- |
| Picker         | Enter  | a project                                | Launches the default tool, as before   |
| Picker         | Ctrl-O | a project                                | Opens the Open With list for it        |
| Picker         | Ctrl-O | a folder header or the Configuration row | Returns to the picker, as Enter does   |
| Open With list | Enter  | the default tool's row                   | Same as Enter in the picker            |
| Open With list | Enter  | another tool's row                       | Launches that tool in the project      |
| Open With list | Enter  | the Shell row                            | Opens a shell in the project           |
| Open With list | Esc    | anything                                 | Returns to the picker, nothing started |

The list is a dialog: a small box centred over the picker, which stays on screen behind it as it was
when Ctrl-O was pressed, greyed out where the terminal can do that. It has no preview pane. Its rows
are the installed tools, the default first and marked, then Shell:

```text
│   ai-journal          ╭─────────── Open ai-launcher with ────────────╮            │ │
│ > ai-launcher         │   Enter to open • Esc to go back             │            │ │
│   cable_modem_monitor │ Open with:                                   │            │ │
│   har-capture         │ > Claude Code   (default)                    │            │ │
│                       │   Gemini CLI                                 │            │ │
│   🔧 Configuration    │   Shell                                      │            │ │
│                       ╰──────────────────────────────────────────────╯            │ │
```

The box is 50 columns wide, or wider for a long project name, and as tall as its rows. On a terminal
smaller than the box it fills what there is.

A tool chosen from the list launches with the flags this run was given: the same cleanup flags,
launch box, terminal title and scope arguments, of which each tool uses what it supports. Only the
`claude` and `gemini` subcommands take `--allow-writes`, so a run started from another subcommand
has no exempt folders to pass on.

The Shell row sets the terminal title, changes into the project and runs the first of `$SHELL`,
`%COMSPEC%` and `/bin/sh` that can be found. It prints one line saying that `exit` leaves the shell,
and nothing else: no cleanup, no launch box, no scope guard. If none of the three can be found it
says so and exits with an error. When the shell exits, the launcher exits with the shell's status.

### Where It Sits in the Stack

```text
select_project()                    picker: fzf --expect=ctrl-o
   │ Enter            │ Ctrl-O on a project
   │                  ↓
   │               select_open_with()     second fzf, a box over the picker
   │                  rows: registry.list_installed(), default first, then Shell
   │                  Esc → back to the picker
   ↓                  ↓
Selection           project + what to open it with
                    (the default, a provider name, or the shell)
   ↓
cli.py
   default or a provider  → launch_ai(...)      cleanup, launch box, scope guard
   shell                  → launch_shell(...)   title, cd, run the shell
```

`Selection` is a dataclass in `core/models.py`. `select_project()` returns it in place of a bare
`Project`.

### Decisions

- **Enter is unchanged.** Launching the default tool is nearly every use, so it gains no step and no
  prompt. Everything new is behind one key.
- **A list, not a key per tool.** The rows come from `ProviderRegistry.list_installed()`, so a new
  provider file appears in the list without touching the selector. A key per tool would put provider
  names in the UI.
- **The subcommand names the default, not the only tool.** `ai-launcher claude` still decides what
  Enter launches and which tool's context the preview pane shows.
- **Shell is a built-in row, not a provider.** It has no context files, permissions or cleanup to
  report, so an `AIProvider` subclass would be empty methods. It would also show up in `--discover`
  as an AI tool.
- **The shell gets no scope guard.** The guard exists because a model can be handed another
  project's work. In a shell the user types the commands.
- **A nested shell, not a `cd` of the calling shell.** A child process cannot change its parent's
  directory. Doing that needs a shell function in the user's rc file, which is setup the launcher
  would have to explain and maintain. Leaving the shell ends the launcher, as leaving a tool does.
- **One shell rule for every platform.** Linux, macOS and WSL set `$SHELL`; Windows sets
  `%COMSPEC%`. Taking the first of `$SHELL`, `%COMSPEC%` and `/bin/sh` that can be found needs no
  platform check, and skips a `$SHELL` that names a program the launcher cannot run. On Windows the
  result is `cmd.exe` even when the launcher was started from PowerShell, because nothing in the
  environment says which shell started it. A Windows user who has set `SHELL` to a program that can
  be run gets that instead. `cmd.exe` cannot start in a UNC path, such as a network share or a WSL
  folder reached as `\\wsl.localhost\...`: it says so and starts in the Windows directory.
- **A symlinked manual project keeps its path.** The shell is started with `PWD` set to the
  project's path as listed, made absolute, so a `--manual-paths` project that is a symlink shows its
  own path in the prompt. Scanned projects are resolved during discovery, before the picker, so for
  them the listed path is already the target's.
- **The list is a dialog, drawn by a second fzf.** The picker runs with `--no-clear`, so its last
  frame stays on screen when it exits. The list then runs in fzf's height mode, also with
  `--no-clear`, which draws only inside its margins and leaves the rest of the screen alone. The
  margins are computed from the terminal size to centre a box of fixed size. Checked on fzf 0.44.1
  and 0.74.4.
- **Height mode, not a second full-screen fzf with margins.** That also works in tmux, but a
  full-screen fzf switches to the alternate screen again on start, and xterm defines that switch as
  clearing the screen, so the picker behind the box would vanish in some terminals. Height mode
  never switches screens.
- **The picker sits one row down.** fzf clears the first row of its area when it starts, and the
  list's area begins at the top of the screen. A one-row top margin on the picker keeps that row
  empty, so nothing of the picker is lost.
- **Where the frame does not survive, the box is drawn on an empty screen.** That is the fallback
  where the picker is cleared on exit despite `--no-clear`, and it is what native Windows does: run
  from PowerShell with fzf 0.70.0, the screen is empty once the picker exits, so the box has nothing
  behind it and there is nothing to grey. The list works the same either way. The dialog over the
  picker was seen on Linux and WSL; macOS has not been checked.
- **The picker behind the dialog is greyed by the terminal, not redrawn.** The launcher does not
  know what fzf drew, so it cannot repaint it. One escape sequence (DECCARA, "change attributes in
  rectangular area") asks the terminal to give everything already on screen a grey foreground, just
  before the box is drawn. Windows Terminal does it; a terminal without the feature, tmux among
  them, ignores the sequence and the picker keeps its colours. Drawing the picker a second time in
  grey was rejected: the preview pane and the typed filter would not survive it.
- **The header names only the new key.** A line saying what Enter launches was tried and cut as
  noise: Enter is the obvious key, and the subcommand already says which tool it starts. The list
  pane is 30% of the terminal and fzf cuts a header line that does not fit, so the hint is short
  enough to show in full at 100 columns.
- **Rows are tools, not session modes.** A launch mode earns a row only if it cannot be reached from
  inside a running session. Claude Code's resume, continue, remote control and teleport
  (`/teleport`, `/tp`) are all available in a session, so none qualifies. Rows such as "Claude Code:
  teleport…" were drafted and cut on that rule. It also spares every provider from declaring its own
  modes.
- **No passthrough of tool arguments.** `ai-launcher claude ~/projects -- --teleport <id>` was
  considered for teleport and dropped with it. It would also let a passed `--settings` collide with
  the one the scope guard sends.
- **`--expect`, not a `print()` binding.** fzf's newer way to report a key is `print(...)+accept`.
  fzf 0.44.1, the Ubuntu 24.04 package, rejects it as an unknown action and accepts `--expect`. The
  current fzf release still documents `--expect`, so one flag covers old and new.
- **Bash prototype has the same key, list and shell rule.** Three differences follow from what the
  prototype already is. It launches only Claude, so its list has two rows, Claude Code and Shell. It
  never sets a terminal title, for Claude or for the shell. It records the project in its
  last-opened history when a shell is opened, as it does for Claude.

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

- **fzf:** <https://github.com/junegunn/fzf>
- **platformdirs:** <https://pypi.org/project/platformdirs/>
- **TOML spec:** <https://toml.io/en/>
- **Claude Code:** <https://code.claude.com/docs/en/setup>

---

**Last Updated:** 2026-09-13 **Status:** Living document, will evolve with project
