# Permission Transparency

## Overview

AI Launcher's Permission Transparency feature detects Claude Code permission accumulation problems before users launch a session. It reads Claude Code's three-layer settings system, analyzes permission health, and warns users when their project settings have accumulated narrow patterns that cause random permission prompts.

This is Claude Code-specific. Other providers (Gemini, Cursor, Aider, Copilot) don't have a permission system that accumulates patterns, so the feature is a no-op for them.

---

## Problem Statement

### Claude Code's Three-Layer Permission System

Claude Code resolves permissions from three JSON files, highest priority first:

1. **Project-level**: `<project>/.claude/settings.local.json`
   - Auto-approved patterns accumulate here when users click "allow"
   - This is the file that grows uncontrollably

2. **Global user**: `~/.claude/settings.json`
   - Shared allow/deny/ask lists set by the user
   - "ask" rules here override "allow" at any level

3. **Global local**: `~/.claude/settings.local.json`
   - Additional user permissions (often set via Claude Code's UI)
   - Merged with settings.json (union, not override)

### The Accumulation Problem

Each time a user approves a command prompt, Claude Code appends the **exact command string** as a pattern:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 -m pytest tests/ -v --tb=short)",
      "Bash(python3 -m pytest tests/test_formatter.py -v)",
      "Bash(python3 -m pytest tests/ -v --cov=ai_launcher)",
      "Bash(ruff check src/ tests/)",
      "Bash(git status)",
      "Bash(git diff --cached)",
      "...100+ more patterns..."
    ]
  }
}
```

These narrow patterns **never match again** because the next command will have slightly different arguments. The file grows to 100+ dead rules. Users then see constant permission prompts and think the system is broken — when the real fix is replacing all of these with `Bash(*)`.

### Why Users Can't Diagnose This Themselves

- No built-in command to view effective permissions across all three layers
- Settings files are scattered across `~/.claude/` and `<project>/.claude/`
- No way to tell which project rules are redundant with global rules
- No visibility into whether "ask" rules override "allow" rules

---

## How It Works

### Data Flow

```
Settings files                    Analysis                      Display
─────────────                    ────────                      ───────

<project>/.claude/               _get_claude_session_config()
  settings.local.json ──┐                                     Preview pane
                        ├──→ reads all 3 files ──→ SessionConfig ──→ formatter.py
~/.claude/              │        │                    │
  settings.json ────────┤        ↓                    │         Startup box
  settings.local.json ──┘  _analyze_permissions()     ├──→ startup_report.py
                               │                      │
                               ↓                      │         CLI diagnostic
                        warnings[]                    └──→ permissions_report.py
                        recommendations[]
                        has_broad_bash
```

### Settings File Reading (`_get_claude_session_config`)

Location: `src/ai_launcher/providers/claude.py:824`

Reads all three layers sequentially:

1. **Project settings** — extracts `permissions.allow`, `mcpServers`, `hooks`
2. **Global settings.json** — extracts `permissions.allow/deny/ask` and `model`
3. **Global settings.local.json** — merges permissions with settings.json (union, deduped)

Stores everything in a `SessionConfig` dataclass and calls `_analyze_permissions()` before returning.

### Detection Heuristics (`_analyze_permissions`)

Location: `src/ai_launcher/providers/claude.py:724`

The analysis function receives project-level and global-level permission lists and applies these rules:

| Condition | Severity | Warning |
|-----------|----------|---------|
| Narrow patterns > 0, global has `Bash(*)`, project doesn't | Redundant | `"N redundant patterns — global has Bash(*)"` |
| Narrow patterns > 10, no `Bash(*)` anywhere | Severe | `"N accumulated patterns — use Bash(*)"` |
| Narrow patterns > 5, no `Bash(*)` anywhere | Moderate | `"N patterns — may cause prompts"` |
| Any patterns > 120 chars | Accidental | `"N long pattern(s) — likely accidental"` |

**Narrow patterns** = any `Bash(...)` rule that isn't `Bash(*)`. Same logic applies to `WebFetch(domain:...)` patterns.

**Consolidation rule**: Multiple symptoms produce one warning and one fix recommendation. A project with 15 narrow Bash patterns and 3 narrow WebFetch patterns gets a single `"18 redundant patterns"` warning, not separate warnings per tool type.

**What's NOT warned about**: Ask gates (`permissions.ask`) are shown as info lines ("Ask before: git push"), not warnings. They're intentional safety gates, not accumulation symptoms.

### Where Results Are Displayed

**Preview pane** (`formatter.py:603` — `_format_session_config_section`):
- Warnings shown first with yellow icon
- Fix recommendations below warnings
- Project/global permission counts
- Ask/deny rules as info lines
- MCP servers, hooks, model

**Startup report** (`startup_report.py:646` — `display_launch_info`):
- Permission warnings in the launch box
- Fix recommendations
- Permission health: "clean" when `Bash(*)` is present and no warnings
- "No permissions configured" when no settings files exist

**CLI diagnostic** (`permissions_report.py:22` — `check_project_permissions`):
- Scans all discovered projects
- Shows global settings once
- Per-project: warnings + fixes, or brief status ("Bash(*)", "inherits global")
- Summary: total checked, issues found

---

## Design Decisions

### Claude-Specific

Other providers don't have a permission system that accumulates patterns. Gemini CLI doesn't prompt for permissions. Cursor uses its own settings format. The feature is gated by `provider_name != "claude-code"` in the CLI diagnostic and returns default (empty) `SessionConfig` fields for non-Claude providers.

### Read-Only

The feature **never modifies settings files**. It only reads and recommends. The fix recommendation is always a human-readable instruction like `"Set Bash(*) in .claude/settings.local.json"`, not an automated edit.

Why: Modifying Claude Code's settings from outside Claude Code could cause conflicts. Users should understand what they're changing.

### One Warning Per Problem

Multiple symptoms (narrow Bash patterns, narrow WebFetch patterns, long patterns, redundancy with global) are consolidated into a single warning with a single fix. This prevents the UI from showing 5 lines of warnings that all say "set Bash(*)".

Implementation: `_analyze_permissions()` uses if/elif priority — the first matching condition produces the warning. The fix recommendation is always the same: `"Set Bash(*) in {fix_path}"`.

### Ask Gates Are Info, Not Warnings

Ask rules (e.g., `Bash(git push:*)`) override allow rules for specific commands. They're intentional safety gates set by the user. Showing them as warnings would imply they're a problem to fix.

They're displayed in the formatter as `"🚫 Ask before: git push"` in the session config section, separate from the warnings section.

### Brief Text

Warning messages are designed to fit in the startup box without wrapping at 85 characters. They use the format `"{count} {qualifier} — {action}"` (e.g., `"18 redundant patterns — global has Bash(*)"`) rather than verbose explanations.

---

## Integration Points

### Architecture Fit

The feature follows the existing provider → data → formatter architecture:

- **Data collection**: `_get_claude_session_config()` and `_analyze_permissions()` live in `claude.py` (provider-specific)
- **Data transport**: `SessionConfig` dataclass in `provider_data.py` carries both data and diagnostics
- **Presentation**: `formatter.py` and `startup_report.py` format the data (no analysis)
- **CLI entry point**: `cli.py` routes `--check-permissions` to `permissions_report.py`

### What Changes If Claude Code's Settings Format Changes

**If key names change** (e.g., `permissions` → `allowList`):
- Update `_get_claude_session_config()` in `claude.py` (JSON key references)
- No changes needed in formatter, startup report, or permissions report

**If file locations change** (e.g., settings move out of `~/.claude/`):
- Update the three file path variables in `_get_claude_session_config()`
- Update `_print_global_settings()` in `permissions_report.py`

**If new tool types are added** (e.g., `Agent()`, `mcp__`):
- Add pattern detection in `_analyze_permissions()` (same as `WebFetch` handling)
- The consolidation logic already handles multiple tool types — they sum into `total_narrow`

### Extending for New Tool Types

To add detection for a new tool pattern (e.g., `Agent(name:...)`):

1. In `_analyze_permissions()`, add a filter after the WebFetch block:
   ```python
   project_agent_patterns = [
       p for p in project_permissions
       if p.startswith("Agent(") and p != "Agent(*)"
   ]
   agent_narrow_count = len(project_agent_patterns)
   ```

2. Add to `total_narrow`:
   ```python
   total_narrow = narrow_count + webfetch_narrow_count + agent_narrow_count
   ```

No other files need changes — the consolidated warning already handles the total.

---

## Keeping This Doc Current

Update this document when:

- **Thresholds change** in `_analyze_permissions()` (>5 moderate, >10 severe, >120 char long)
- **New tool patterns** are added to the analysis (beyond Bash and WebFetch)
- **SessionConfig fields** are added or removed in `provider_data.py`
- **Display format changes** in `formatter.py` or `startup_report.py`
- **Claude Code's settings format changes** (file locations, key names, new layers)

Code references to verify:
- `_analyze_permissions()`: `src/ai_launcher/providers/claude.py:724`
- `_get_claude_session_config()`: `src/ai_launcher/providers/claude.py:824`
- `SessionConfig`: `src/ai_launcher/core/provider_data.py:245`
- `_format_session_config_section()`: `src/ai_launcher/ui/formatter.py:603`
- `display_launch_info()`: `src/ai_launcher/ui/startup_report.py:561`
- `check_project_permissions()`: `src/ai_launcher/ui/permissions_report.py:22`

---

**Made by Solent Labs™** - Building tools for developers who value transparency and local-first software.
