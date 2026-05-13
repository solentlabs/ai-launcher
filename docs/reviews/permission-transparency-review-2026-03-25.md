# Permission Transparency Review Report

**Date:** 2026-03-25 **Reviewer:** Claude Code (Opus 4.6) **Scope:** Design and implementation
review of the Permission Transparency feature

---

## 1. Critical Issues

### 1.1 `global_has_broad_webfetch` computed but never used

**Where:** `src/ai_launcher/providers/claude.py:787`

`global_has_broad_webfetch = "WebFetch(*)" in global_permissions` is computed but never referenced
in any condition. The redundancy check (line 800) only uses `global_has_broad` (which checks
`Bash(*)`). Consequence: if a user has `WebFetch(*)` globally and 3 narrow `WebFetch(domain:...)`
patterns in their project, those 3 count toward `total_narrow` but the first condition
(`global_has_broad`) is False because it only checks Bash. The redundancy is undetected.

Worse: the accumulation warning (if `total_narrow > 10`) says "use Bash(_)" and the fix
recommendation is "Set Bash(_)" — even when the accumulated patterns are entirely WebFetch. The
diagnostic is misleading and the fix is wrong.

**Suggested fix:** Either fold `global_has_broad_webfetch` into the redundancy condition, or
generate tool-specific fix recommendations when the accumulated patterns are not Bash.

### 1.2 `_get_claude_session_config` returns None when user has only deny/ask rules

**Where:** `src/ai_launcher/providers/claude.py:958-967`

The return gate checks
`permissions_count > 0 or global_permissions_count > 0 or mcp_servers or hooks_configured or model`.
A user with only deny/ask rules (no allow, no MCP, no hooks, no model) gets `None` returned. The
startup report then shows "No permissions configured — all commands will prompt", which is factually
wrong — the user has intentionally configured safety gates.

This is the "no config at all" path being conflated with "config exists but has no allow rules."

**Suggested fix:** Add `config.global_deny` and `config.global_ask` to the return gate condition.

### 1.3 Use case 5 shows output that doesn't match the described scenario

**Where:** `docs/use-cases/permission-health.md:173-182`

The scenario says "Clean project settings (or none)" but the output shows `✓ Bash(*) (project)`,
which requires `Bash(*)` in the project-level settings file. If the project truly has no settings,
the output would be `○ No project permissions (inherits global)`. The use case is ambiguous and the
example output is only correct for one interpretation.

Also: `Bash(*) + 0 more (global)` is shown when global has exactly 1 permission. The "+0 more" is
technically correct but reads oddly. The formatter produces this unconditionally — there's no
special case for count=0.

**Suggested fix:** Split into two sub-scenarios (project has Bash(\*) vs. no project settings) with
separate expected output blocks. Consider special-casing the "+0 more" display.

---

## 2. Edge Cases

### 2.1 `mcpServers` as non-dict crashes the function

**Where:** `src/ai_launcher/providers/claude.py:868`

If a malformed settings file has `"mcpServers": ["server1"]` (list instead of dict),
`list(settings["mcpServers"].keys())` raises `AttributeError`. The except clause only catches
`json.JSONDecodeError` and `KeyError`. Same for `settings["hooks"].values()` at line 872. The
function would propagate an unhandled `AttributeError`.

The outer `collect_preview_data()` caller catches `Exception` so the app won't crash, but the entire
session config (permissions, model, everything) is lost — not just the malformed MCP field.

**Suggested fix:** Widen the except clause to include `(TypeError, AttributeError)`, or add
`isinstance` guards before calling `.keys()` / `.values()`.

### 2.2 `allow` as a string instead of list produces silently wrong results

**Where:** `src/ai_launcher/providers/claude.py:862-863`

If a malformed settings file has `"allow": "Bash(*)"` (string instead of array),
`config.permissions = "Bash(*)"` sets it to a string. Then `len("Bash(*)")` = 7, so
`permissions_count` = 7. The formatter shows "7 auto-approved commands" and iterates over individual
characters. `"Bash(*)" in project_permissions` on a string does substring search, returning True. No
crash, but completely wrong display.

**Suggested fix:** Add `isinstance(perms_list, list)` guard, or coerce to list.

### 2.3 Global hooks.json existence check is too permissive

**Where:** `src/ai_launcher/providers/claude.py:953-955`

```python
hooks_config = Path.home() / ".claude" / "hooks.json"
if hooks_config.exists() and not config.hooks_configured:
    config.hooks_configured = True
```

An empty `{}` file is treated as "hooks configured". The project-level check (line 872) correctly
uses `any(hook_config for hook_config in settings["hooks"].values())`, but the global check is
file-existence only. A user who deleted their hooks but left an empty file would see "Hooks
configured" in their startup report.

**Suggested fix:** Parse hooks.json and check for non-empty content, matching the project-level
check.

### 2.4 Hooks in global settings files are not detected

**Where:** `src/ai_launcher/providers/claude.py:878-915`

The code reads hooks from project `settings.local.json` and from `~/.claude/hooks.json`, but not
from `~/.claude/settings.json` or `~/.claude/settings.local.json`. Claude Code can store hooks in
any of these files. A user with hooks in `settings.json` would see "No hooks configured."

**Suggested fix:** Check for `hooks` key in global settings.json and settings.local.json during
layers 2/3 reading.

---

## 3. Design Questions

### 3.1 Long pattern warning suppressed by accumulation warning

**Where:** `src/ai_launcher/providers/claude.py:800-814` (if/elif chain)

If a user has 7 narrow patterns, one of which is 150 characters long, the `total_narrow > 5`
condition fires first and the `long_patterns` elif never runs. The user is told "7 patterns — may
cause prompts" but not that one of them looks like an accidental approval of a full command line.
The fix recommendation is the same, but the diagnostic loses information about the accidental
pattern.

This is documented as intentional ("one warning per problem"), but the long-pattern issue is
qualitatively different from accumulation — it suggests the user may have approved something they
didn't intend to.

### 3.2 Redundant warning fires for even 1 pattern

**Where:** `src/ai_launcher/providers/claude.py:800`

`total_narrow > 0 and global_has_broad` triggers for a single redundant pattern. In contrast,
without global `Bash(*)`, you need >5 patterns for even a moderate warning. A user who sets up
global `Bash(*)` and then notices a single leftover `Bash(git status)` in one project gets a
warning. This is technically correct (it is redundant) but the asymmetry in thresholds might feel
aggressive.

### 3.3 `_print_global_settings()` duplicates JSON parsing

**Where:** `src/ai_launcher/ui/permissions_report.py:106-158`

This function independently reads and parses `settings.json` and `settings.local.json`, duplicating
the logic in `_get_claude_session_config()`. It shows them as separate layers (useful for user
understanding) but doesn't merge them (the analysis does). If the settings format changes, two code
paths need updating. The function even imports `_analyze_permissions` without using it (line 40).

### 3.4 `total_narrow` consolidation loses tool-type specificity

**Where:** `src/ai_launcher/providers/claude.py:794`

`total_narrow = narrow_count + webfetch_narrow_count` sums across tool types, then all warnings use
generic language ("patterns", "accumulated"). A user with 5 Bash patterns and 7 WebFetch patterns
sees "12 accumulated patterns — use Bash(_)" with no mention of WebFetch. The fix only recommends
Bash(_), not WebFetch(\*).

---

## 4. Test Gaps

### 4.1 Missing boundary tests for thresholds

**Where:** `tests/test_claude_data.py:500-657`

The parametrized tests cover 7 (moderate) and 15 (severe) but miss the boundary values:

- **Exactly 5 patterns** — should produce NO warning (boundary, exclusive)
- **Exactly 6 patterns** — should trigger moderate (first above threshold)
- **Exactly 10 patterns** — should trigger moderate, NOT severe (boundary)
- **Exactly 11 patterns** — should trigger severe (first above threshold)

### 4.2 No test for WebFetch-only accumulation

**Where:** `tests/test_claude_data.py`

`test_webfetch_counted_in_total` tests mixed Bash+WebFetch. No test for WebFetch-only patterns
(e.g., 12 WebFetch patterns, 0 Bash). This would exercise the bug in 1.1 — the warning would say
"use Bash(\*)" which is the wrong fix for WebFetch accumulation.

### 4.3 No test for deny/ask-only configuration returning None

**Where:** `tests/test_claude_data.py:285-370`

`test_session_config_empty` tests "nothing configured" returning None. But there's no test for "only
deny/ask rules, no allow/MCP/hooks/model" — which also returns None incorrectly (Issue 1.2).

### 4.4 No test for malformed JSON type mismatches

**Where:** `tests/test_claude_data.py`

No tests for `mcpServers` as a list, `allow` as a string, `permissions` as a string, or `hooks` as a
non-dict. These would verify the error handling (or expose crashes per Issue 2.1).

### 4.5 No test for `_print_global_settings` in permissions_report

**Where:** `tests/test_permissions_report.py`

The tests cover `check_project_permissions` but never directly test `_print_global_settings`. The
global settings output (separate layer display, invalid JSON handling, merge behavior) is untested.

### 4.6 No test for "Permission health: clean" display

**Where:** `tests/test_startup_report_extended.py`

No test verifies that the `✓ Permission health: clean` line appears when `has_broad_bash=True` and
`permission_warnings=[]`. Similarly, no test verifies it's correctly suppressed when warnings exist
alongside `has_broad_bash=True` (the redundant-patterns case).

### 4.7 No test for contradictory SessionConfig state

**Where:** `tests/test_formatter.py`

No test passes `has_broad_bash=True` with `"Bash(*)" NOT in permissions` to the formatter. The
formatter checks `config.has_broad_bash and "Bash(*)" in config.permissions` — if `has_broad_bash`
comes from global but `Bash(*)` is not in project permissions, the project section should show
count, not "Bash(\*) (project)". This interaction is untested.

### 4.8 Unused import in permissions_report

**Where:** `src/ai_launcher/ui/permissions_report.py:40`

`_analyze_permissions` is imported but never called. Only `_get_claude_session_config` is used. This
is dead code in the import.
