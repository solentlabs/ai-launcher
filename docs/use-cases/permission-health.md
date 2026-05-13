# Use Cases: Permission Health

Real-world scenarios showing how Permission Transparency behaves for different user configurations.
Each scenario includes the starting state, what the user sees, and what to do about it.

---

## 1. New User, No Settings Files

**Starting state:**

- No `~/.claude/settings.json`
- No `~/.claude/settings.local.json`
- No `<project>/.claude/settings.local.json`

**What the user sees in the startup box:**

```text
│ 🔧 Session Configuration:
│   ⚠ No permissions configured — all commands will prompt
│   💡 Set Bash(*) in .claude/settings.local.json
│   ○ No MCP servers configured
│   ○ No hooks configured
│   ○ Model: default (sonnet)
```

**What to do:** Create a project or global settings file with broad permissions:

```bash
mkdir -p .claude
echo '{"permissions":{"allow":["Bash(*)"]}}' > .claude/settings.local.json
```

**After fixing:**

```text
│ 🔧 Session Configuration:
│   ✓ Bash(*) (project)
│   ✓ Permission health: clean
│   ○ No MCP servers configured
│   ○ No hooks configured
│   ○ Model: default (sonnet)
```

---

## 2. User with Bash(\*) Globally, Clean Project

**Starting state:**

- `~/.claude/settings.json` contains `{"permissions":{"allow":["Bash(*)","WebFetch(*)"]}}`
- No project-level settings file

**What the user sees in the startup box:**

```text
│ 🔧 Session Configuration:
│   ○ No project permissions (inherits global)
│   ✓ Bash(*) + 1 more (global)
│   ✓ Permission health: clean
│   ○ No MCP servers configured
│   ○ No hooks configured
```

**What to do:** Nothing. This is the ideal state.

---

## 3. User with Accumulated Patterns, No Global Config

**Starting state:**

- No global settings files
- `<project>/.claude/settings.local.json` has 18 individual Bash patterns:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 -m pytest tests/ -v --tb=short)",
      "Bash(python3 -m pytest tests/test_formatter.py -v)",
      "Bash(ruff check src/ tests/)",
      "Bash(git status)",
      "Bash(git diff --cached)",
      "...13 more patterns..."
    ]
  }
}
```

**What the user sees in the startup box:**

```text
│ 🔧 Session Configuration:
│   ⚠ 18 accumulated patterns — use Bash(*)
│   💡 Set Bash(*) in .claude/settings.local.json
│
│   ✓ 18 auto-approved commands (project)
│     • Bash(python3 -m pytest tests/ -v --tb=short)
│     • Bash(python3 -m pytest tests/test_formatter.py -v)
│     • Bash(ruff check src/ tests/)
│     • Bash(git status)
│     • Bash(git diff --cached)
│     ...and 13 more
```

**What to do:** Replace the accumulated patterns with a wildcard:

```bash
echo '{"permissions":{"allow":["Bash(*)"]}}' > .claude/settings.local.json
```

**After fixing:**

```text
│ 🔧 Session Configuration:
│   ✓ Bash(*) (project)
│   ✓ Permission health: clean
```

---

## 4. User with Accumulated Patterns AND Global Bash(\*)

**Starting state:**

- `~/.claude/settings.json` has `Bash(*)` in allow list
- `<project>/.claude/settings.local.json` has 25 narrow patterns (accumulated before the user set up
  global Bash(\*))

**What the user sees in the startup box:**

```text
│ 🔧 Session Configuration:
│   ⚠ 25 redundant patterns — global has Bash(*)
│   💡 Set Bash(*) in .claude/settings.local.json
│
│   ✓ 25 auto-approved commands (project)
│     • Bash(python3 -m pytest tests/ -v)
│     • Bash(git status)
│     • Bash(ruff check src/)
│     • Bash(git log --oneline -10)
│     • Bash(pip install -e .)
│     ...and 20 more
│   ✓ Bash(*) + 2 more (global)
```

**What to do:** The project patterns are dead weight — global `Bash(*)` already covers everything.
Clean up the project file:

```bash
echo '{"permissions":{"allow":["Bash(*)"]}}' > .claude/settings.local.json
```

Or remove it entirely to inherit global:

```bash
rm .claude/settings.local.json
```

**After fixing (if removed):**

```text
│ 🔧 Session Configuration:
│   ○ No project permissions (inherits global)
│   ✓ Bash(*) + 2 more (global)
│   ✓ Permission health: clean
```

---

## 5. User with Ask Gates for Git

**Starting state:**

- `~/.claude/settings.json`:

  ```json
  {
    "permissions": {
      "allow": ["Bash(*)"],
      "ask": ["Bash(git push:*)", "Bash(git push --force:*)"]
    }
  }
  ```

- Clean project settings (or none)

**What the user sees in the startup box:**

```text
│ 🔧 Session Configuration:
│   ✓ Bash(*) (project)
│   ✓ Bash(*) + 0 more (global)
│   🚫 Ask before: git push, git push --force
│   ✓ Permission health: clean
```

**What to do:** Nothing. Ask gates are intentional safety gates. They override `Bash(*)` for
specific dangerous commands, ensuring Claude always asks before pushing code. This is the
recommended setup.

Note: Ask gates are shown as info lines, not warnings. They are not a problem to fix.

---

## 6. User Runs --check-permissions Across 20 Projects

**Starting state:**

- Global: `Bash(*)` in `~/.claude/settings.json`
- 20 projects discovered under `~/projects/solentlabs`
- 3 projects have accumulated patterns
- 15 projects have no project-level settings
- 2 projects have clean `Bash(*)` project settings

**Command:**

```bash
ai-launcher claude ~/projects/solentlabs --check-permissions
```

**What the user sees:**

```text
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code Permission Health Check                           │
│  Scans projects for accumulated permission patterns            │
└─────────────────────────────────────────────────────────────────┘

Global Settings:
  ✓ Allow: Bash(*), WebFetch(*)
  🚫 Ask before: git push

⚠  ai-launcher
   /home/user/projects/solentlabs/utilities/ai-launcher
   ⚠ 18 redundant patterns — global has Bash(*)
   💡 Set Bash(*) in .claude/settings.local.json

⚠  cable-modem-monitor
   /home/user/projects/solentlabs/network-monitoring/cable_modem_monitor
   ⚠ 12 redundant patterns — global has Bash(*)
   💡 Set Bash(*) in .claude/settings.local.json

⚠  devkit
   /home/user/projects/solentlabs/devkit
   ⚠ 7 redundant patterns — global has Bash(*)
   💡 Set Bash(*) in .claude/settings.local.json

✓  operations (Bash(*))
✓  web-frontend (Bash(*))

─────────────────────────────────────────────────────────────────
Checked 5 project(s) with settings files
⚠  3 project(s) with permission issues
```

**What to do:** Fix each flagged project by replacing accumulated patterns with `Bash(*)` or
removing the project settings file to inherit global.

**After fixing all 3:**

```text
✓  ai-launcher (inherits global)
✓  cable-modem-monitor (inherits global)
✓  devkit (inherits global)
✓  operations (Bash(*))
✓  web-frontend (Bash(*))

─────────────────────────────────────────────────────────────────
Checked 5 project(s) with settings files
✓  All projects healthy
```

---

## 7. Developer Adding a New Provider

**Context:** A developer is implementing `WindsurfProvider` following the
[Adding Providers](../adding-providers.md) guide.

**What they need to know about permission checking:**

Nothing. Permission transparency is Claude Code-specific. The `SessionConfig` dataclass has fields
for permissions, warnings, and recommendations, but they all default to empty lists and `False`. A
non-Claude provider's `collect_preview_data()` can return `session_config=None` (or populate only
the fields relevant to it like `mcp_servers` or `model`).

The `--check-permissions` CLI flag is gated by `provider_name != "claude-code"`:

```python
# permissions_report.py
if provider_name != "claude-code":
    print(f"Permission checking is only available for Claude Code (not {provider_name})")
    sys.exit(0)
```

**If the new provider has its own permission system:**

If a future provider has accumulation issues, the developer would:

1. Add provider-specific analysis in their provider module (like `_analyze_permissions()` in
   `claude.py`)
2. Populate `SessionConfig.permission_warnings` and `permission_recommendations`
3. The existing formatter and startup report will display them automatically — no presentation
   changes needed

---

## Keeping This Doc Current

Update this document when:

- **Thresholds change** in `_analyze_permissions()` — update scenario 3 (moderate) and scenario 4
  (redundant)
- **Output format changes** in `startup_report.py` or `permissions_report.py` — update the example
  output blocks
- **New detection heuristics** are added — add a new scenario or update existing ones
- **New providers** gain permission checking — add a variant of scenario 7

---

**Made by Solent Labs™** - Building tools for developers who value transparency and local-first
software.
