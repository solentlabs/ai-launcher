# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - TBD

### Fixed

- **Release no longer tags into a still-running CI** — `poll_main_ci()` took the latest CI run on
  main with no commit filter. Immediately after a squash-merge the new run has not registered, so it
  read the _previous_ run, found it green, and returned instantly. v0.4.2 then pushed its tag while
  CI on the real commit had not started. It now matches on the merge commit's SHA and waits for that
  run specifically.
- **Tag protection can tell "running" from "failed"** — it collapsed check runs with
  `all(.conclusion == "success")`, and an unfinished run carries `conclusion: null`, so a CI that
  was merely still going read as a hard failure. That is what turned the v0.4.2 race into a red gate
  on a commit whose CI went on to pass. It now waits out a pending CI, up to 30 minutes.
- **`release.py` can resume after the tag is pushed** — phase 1 fatally exited on any existing tag,
  so a release interrupted during phase 8 could not be finished by re-running it; v0.4.2's GitHub
  release had to be created by hand. An existing tag is now a conflict only when it points at a
  different commit, and a pushed tag resumes directly at phase 8.

### Added

- **The CI gates are now tested** — `scripts/gate_checks.py` holds the changelog and CI-status
  decisions as pure functions that both the workflows and `tests/test_gate_checks.py` call, so a
  test cannot pass while the gate does something else. Previously both lived as inline bash and jq
  inside workflow YAML, which nothing exercised — and both failed on first contact with a release.
  `tests/test_release_flow.py` covers the release script, which had no tests at all. Each scenario
  that actually broke has a named regression test, verified to fail against the old logic.
- **Local patch-coverage check** — `scripts/patch_coverage.py` reports coverage of the lines a
  branch changed, the measure Codecov applies. The project-wide floor can pass while a patch adds
  untested lines, so that verdict was previously visible only after a push. Wired into
  `scripts/ci-local.sh` as warn-only, to surface what Codecov will say rather than add a stricter
  gate than CI enforces.

### Changed

- **Lint runs once, before the test matrix** — it ran inside all 15 matrix jobs, so one lint error
  failed 15 jobs identically and burned the whole matrix to report a single line. A separate `lint`
  job reports the same error in seconds, and the matrix now `needs` it.
- **CI verifies the tool pins** — `scripts/check-tool-pins.sh` is shared by the pre-push gate and
  the CI lint job, so ruff version drift is caught on whichever side introduces it, including a
  pre-commit.ci autoupdate landing a new rev without the matching `pyproject.toml` bump.

## [0.4.2] - 2026-08-06

### Fixed

- **Preview pane no longer eats the last character of a row** — `⚙️`, `⚠️` and `🏗️` are an East
  Asian _Neutral_ base plus a U+FE0F variation selector. fzf's `go-runewidth` scores that as one
  column; terminals honor the selector and draw two. fzf therefore admitted one character too many
  onto any row carrying one, the overflow wrapped past the pane, and fzf's next redraw painted over
  the remainder — `Session Configuration` rendered as `Session Configuratio`. Replaced with glyphs
  whose base is already East Asian Wide, so no variation selector is needed and both agree: `⚙️` →
  `🔧` (session config header, matching the launch box), `⚙️` → `🔩` (Config category, since `🔧`
  already marks Skill), `🏗️` → `📐` (Arch category), `⚠️` → `❗` (warnings). Added
  `tests/test_terminal_width_safety.py`, which fails on any width-mismatched glyph reaching a
  shipped source file.
- **Release script: PR title now follows Conventional Commits** — was `"Release v{version}"`
  (rejected by the PR title gate); changed to `"chore(release): v{version}"`.
- **Release script: `poll_pr_checks` no longer times out on running checks** — `gh pr checks` exits
  non-zero for both pending and failed states, but stdout still contains the check list. The poller
  previously treated any non-zero exit as "no checks yet" and burned the full 1200s timeout. Fixed
  to only wait when stdout is actually empty.
- **Release script: phase 4 is now idempotent** — re-running after a timeout no longer fatals with
  "Could not find version string" when the version file is already at the target version.
- **Changelog gate no longer deadlocks the release flow** — the gate treats any change under
  `src/ai_launcher/` or `scripts/` as code needing a changelog entry, but a release PR bumps
  `src/ai_launcher/__init__.py` while its entry already landed with the feature PR. Every release PR
  therefore failed the gate, blocking phase 6. Caught on the v0.4.2 release, which stopped at phase
  6 before any tag was pushed. The verification step now skips PRs from a `release/` branch.

### Changed

- **Ruff pinned exactly, ending a three-way version drift** — `pyproject.toml` declared
  `ruff>=0.5.0`, so CI resolved whatever was newest (0.16.1) while the pre-commit hook pinned
  v0.11.0 and the local venv sat at 0.15.4. All 15 CI matrix jobs failed at the lint step on
  `RUF100 unused noqa: S310` in `utils/fzf.py` — 0.16.1 narrowed `S310` to the opener call, making a
  directive that every older ruff still requires into a dead one. The versions are mutually
  exclusive on that line, so no source edit satisfies both; `ruff` is now pinned to `==0.15.9` in
  `pyproject.toml` with the pre-commit `rev` in lockstep. Upgrading to 0.16.x is deliberate future
  work — it also reformats Python code blocks inside three Markdown docs.
- **`scripts/ci-local.sh` now mirrors CI** — it ran `ruff check .` but never
  `ruff format --check .`, so a formatter-only disagreement could reach CI unseen. Adds the format
  check plus two drift guards that block a push when the local ruff differs from the
  `pyproject.toml` pin, or when the pre-commit `rev` differs from it (pre-commit.ci autoupdates that
  rev weekly). Both print the exact command to fix.
- **Changelog gate added** — new `changelog-check.yml` CI workflow fails PRs that change Python
  source or scripts without updating `CHANGELOG.md`. Soft pre-commit warning added via
  `scripts/check-changelog.sh`.

## [0.4.1] - 2026-05-29

### Fixed

- **Startup box formatting consistency** — unified checkmarks (`✅` → `✓`), indented `💡`
  recommendations as sub-items under `⚠` warnings, broke sibling project names and skill names onto
  individual `•` bullet lines matching the Global Context section style, added `○` marker to the
  `/plugin to browse` line, and corrected a 4→3 space indent on that line.

### Changed

- **Coverage floor raised from 75%/80% to 84%** — added ~30 fixture- and table-based tests covering
  session-config permission branches, session-stats edge cases, formatter private methods
  (`_format_git_section`, `_format_session_section`, `_format_rich_header`), and selector edge cases
  (action items, `__SPACE__` separators, directory headers, env-var population, generic exception
  handler). `selector.py` 75% → 95%, `startup_report.py` 91% → 97%, `formatter.py` 85% → 90%.

## [0.4.0] - 2026-05-13

### Added

- **Permission transparency report** — new `ai-launcher permissions` command and launch-box section
  that audits Claude Code's effective permissions, flags accumulated narrow `Bash()` patterns,
  detects redundancy against global `Bash(*)`, and emits actionable fix recommendations. See
  `docs/permission-transparency.md`.
- **`.vscode/extensions.json` and `.vscode/settings.json`** — shared workspace config so every
  contributor sees the same ruff/mypy warnings as CI.
- **`CONTRIBUTING.md`** — development setup, code style, testing, and local hook installation.
- **`docs/releasing.md`** — full release procedure including pre-release wheel test, dry-run, and
  failure recovery.
- **`Makefile`** — wraps the common dev commands (`test`, `lint`, `validate-ci`, `install-hooks`);
  `validate-ci` delegates to `scripts/ci-local.sh` for single-source truth with the pre-push hook.
- **`.github/workflows/commit-lint.yml`** — PR-title gate enforcing Conventional Commits so
  squash-merge commits on `main` stay parseable.
- **Markdown linting via `.markdownlint.jsonc`** with prettier + markdownlint-cli2 pre-commit hooks.
  Prettier hard-wraps prose to 100 chars and aligns tables; markdownlint catches the rest. Every
  linter exception in the config carries an inline `// why` comment.

### Fixed

- **Launch box overflow on long paths and file lists** — the 85-column box no longer breaks when
  paths or memory file lists exceed its width. Memory display lists files when ≤5 or shows count +
  wrapped directory path otherwise; recommendation lines use project-relative paths instead of
  absolute.
- **Three unused-argument and one unused-variable lint issues** in `_analyze_permissions` and the
  memory-list wrapper.
- **Dead parameters removed from `_analyze_permissions`** — `global_deny`, `global_ask`, and
  `config_file_path` were accepted but never read. Caller and tests updated. Docstring documents why
  deny/ask are tracked elsewhere.

### Changed

- **CLAUDE.md rewrite** (322 → 57 lines) — restructured from a project overview into a behavior
  contract with numbered Core Principles (Process, Project Invariants, Secrets), a Where Things Live
  table, and Verification / Shell & Commits sections. Dev workflow content moved to
  `CONTRIBUTING.md`; release content moved to `docs/releasing.md`.
- **`.gitignore`** — removed the overly defensive `.vscode/*` exclusion. `.vscode/` is shared
  workspace config and now tracks all files.

## [0.3.1] - 2026-03-11

### Changed

- **Rename "Boundary Protection" to "Sibling Projects"** — the old name implied enforcement that
  doesn't exist. The feature only shows nearby projects for awareness, so the labeling now reflects
  that honestly. "Forbidden"/"Allowed" replaced with "Other"/"Selected".

## [0.3.0] - 2026-03-05

### Removed

- **Dead code cleanup** — removed `ConfigManager` (`core/config.py`), `settings.py`, and
  `shared_context.py` which were never called by the CLI
- Removed `HistoryConfig` dataclass from `core/models.py` (only used by deleted ConfigManager)
- Removed `docs/terminal-title.md` — folded troubleshooting content into `docs/troubleshooting.md`
- Removed `docs/CONTEXT_TRANSPARENCY_IMPLEMENTATION.md` and `docs/REFACTORING_2026_02.md` (completed
  checklists, archived to journal)
- Removed tests for deleted code (`test_config.py`, `test_integration.py`, `test_settings_menu.py`,
  `test_shared_context.py`)

### Changed

- **CLAUDE.md rewrite** — trimmed from 698 to ~320 lines by removing duplication and linking to
  canonical docs
- **Documentation accuracy pass** — fixed all CLI syntax (`ai-launcher ~/projects` →
  `ai-launcher claude ~/projects`), removed references to non-existent flags (`--providers`,
  `--startup-report`, `--context-health`)
- **README.md** — converted relative doc links to full GitHub URLs for PyPI compatibility, added
  PyPI downloads badge
- **docs/configuration.md** — complete rewrite from config.toml reference to CLI flags reference
- **docs/troubleshooting.md** — removed stale config.toml references, added terminal title
  troubleshooting section
- **docs/adding-providers.md** — updated provider status table, replaced manual registration with
  auto-discovery
- **docs/context-transparency.md** — removed proposed/unimplemented CLI commands
- Renamed docs to lowercase kebab-case for consistency (`ARCHITECTURE.md` → `architecture.md`, etc.)
- Added `docs/README.md` index for documentation navigation

## [0.2.1] - 2026-03-04

### Fixed

- Quote `sys.executable` and helper script paths in all fzf `--preview` commands — fixes
  `'C:\Program' is not recognized` errors on Windows when Python is installed under
  `C:\Program Files\...`

### Changed

- Added `quote_for_fzf` and `fzf_preview_cmd` helpers to `utils/paths.py` to centralise fzf command
  quoting
- Removed redundant `import sys` from UI modules that no longer reference it directly

## [0.2.0] - 2026-03-03

### Added

- Auto-download fzf when missing — prompts user and fetches from GitHub releases
- Cross-platform Python helpers for fzf preview commands (`_browser_preview.py`, `_file_preview.py`)

### Fixed

- Cross-platform encoding: all fzf subprocess calls use binary mode with explicit UTF-8
  encode/decode, fixing Windows cp1252 mangling
- Delimiter escaping: consistent `\\t\\t` in all fzf `--delimiter` args (raw tab chars were mangled
  by Windows command-line processing)
- Project discovery on native Windows — follow NTFS junctions and symlinks (Python 3.12+ treats
  junctions as symlinks, causing `os.walk` to silently skip them)
- Circular symlink protection during project scanning via real-path cycle detection
- Detect `.git` files (Git submodules) in addition to `.git` directories
- Replace hardcoded `:` path separators with `os.pathsep` for Windows
- Fix root path detection to work on Windows (no hardcoded `/`)
- Cross-platform test compatibility (macOS symlink resolution, Windows subprocess handling)
- Removed references to non-existent `--setup` CLI flag
- Codecov integration (tokenless org-level auth)

### Changed

- All fzf callers (settings, shared context, browser, context viewer) use consistent binary-mode
  pattern
- Release script (`scripts/release.py`) extended with full lifecycle automation: PR merge, CI wait,
  tag, and GitHub release creation
- Tag protection and publish workflows hardened for CI reliability

> **Note:** Versions 0.1.1–0.1.3 were incremental debugging releases and have been yanked from PyPI.
> All their fixes are included in 0.2.0.

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
- **Smart terminal detection** - Works with xterm, iTerm2, GNOME Terminal, Windows Terminal, tmux,
  etc.
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
