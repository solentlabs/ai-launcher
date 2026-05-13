# Contributing to AI Launcher

Thanks for your interest in contributing. This guide covers how the project is developed day-to-day.
Architecture and behavior rules live elsewhere — see the table below.

## Where Things Live

| Topic                            | Doc                                                  |
| -------------------------------- | ---------------------------------------------------- |
| Project overview, install, usage | [README.md](README.md)                               |
| Claude/AI behavior rules         | [CLAUDE.md](CLAUDE.md)                               |
| Architecture (layers, data flow) | [docs/architecture.md](docs/architecture.md)         |
| Adding a new provider            | [docs/adding-providers.md](docs/adding-providers.md) |
| Configuration reference          | [docs/configuration.md](docs/configuration.md)       |
| Release process                  | [docs/releasing.md](docs/releasing.md)               |
| Version history                  | [CHANGELOG.md](CHANGELOG.md)                         |

## Development Setup

This project uses an **editable install** so source edits are picked up immediately by the
`ai-launcher` command — no rebuild step.

### One-time setup

```bash
cd ~/projects/solentlabs/utilities/ai-launcher
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
```

If you also have a published `ai-launcher` on your PATH (e.g. via `pipx install ai-launcher`),
uninstall it first so the editable copy wins:

```bash
pipx uninstall ai-launcher 2>/dev/null || true
pip uninstall ai-launcher 2>/dev/null || true
pip install -e .
```

### Day-to-day workflow

1. Edit Python sources under `src/ai_launcher/`.
2. Run `ai-launcher claude ~/projects` (or your preferred invocation) — changes are live; no
   reinstall needed.
3. Run tests: `./venv/bin/pytest tests/ -q`.

### Windows Terminal integration

See [docs/windows-terminal.md](docs/windows-terminal.md) for the "Solent Labs - Claude Code" profile
setup. The profile invokes the same `ai-launcher` command you use locally, so editable install means
the Windows Terminal entry point also reflects your latest changes.

## Two Implementations

The project maintains two parallel implementations:

- **`bin/ai-launcher`** — Bash prototype. Fast iteration, complete working implementation, used as
  reference.
- **`src/ai_launcher/`** — Python package. Production-ready, distributable via PyPI.

When adding a feature, decide which side it lands on first and confirm with the maintainer if it
should be ported. Feature parity is a goal, not an invariant — divergence is allowed when
intentional.

### Bash prototype CLI

```bash
./bin/ai-launcher --help              # Show usage
./bin/ai-launcher ~/projects          # Launch with project selector
./bin/ai-launcher --add               # Interactive directory browser
./bin/ai-launcher --remove            # Remove a saved path
./bin/ai-launcher --list ~/projects   # List discovered projects
```

The prototype reads `~/.claude/project-launcher.conf` when no paths are passed.

## Code Style

### Python

- Formatter / linter: **Ruff** (88-column line length).
- Strict type hints on public APIs; docstrings on public functions.
- Run: `./venv/bin/ruff check src/ tests/` and `./venv/bin/ruff format src/ tests/`.
- Type check: `./venv/bin/mypy src/`.

### Bash

- ShellCheck-clean.
- `set -euo pipefail` at the top of every script.
- Quote all variable expansions (`"$var"`, not `$var`).

### Naming

| Kind             | Convention   |
| ---------------- | ------------ |
| Python modules   | `snake_case` |
| Python classes   | `PascalCase` |
| Python functions | `snake_case` |
| Bash functions   | `snake_case` |
| Bash global vars | `UPPER_CASE` |
| Bash local vars  | `lower_case` |

## Local Hooks

The project enforces quality at three points before code leaves your machine. Install once:

```bash
make install-hooks
```

This installs `pre-commit`, `commit-msg`, and `pre-push` hooks driven by
[`.pre-commit-config.yaml`](.pre-commit-config.yaml):

| Stage        | What it checks                                                                            |
| ------------ | ----------------------------------------------------------------------------------------- |
| `pre-commit` | ruff lint + format, mypy, secret detection, file hygiene, blocks direct commits to `main` |
| `commit-msg` | Conventional Commits format (commitizen)                                                  |
| `pre-push`   | full ruff check + full pytest (via `scripts/ci-local.sh`); blocks tag push if CI red      |

To run the full CI gate manually:

```bash
make validate-ci
```

This calls the same `scripts/ci-local.sh` the pre-push hook uses, so there's only one source of
truth.

## Testing

- Run all tests: `./venv/bin/pytest tests/ -v`
- With coverage: `./venv/bin/pytest tests/ --cov=src/ai_launcher --cov-report=term-missing`
- Quick count: `./venv/bin/pytest tests/ --co -q`

### Coverage expectations

| Area            | Target |
| --------------- | ------ |
| New code        | 80%+   |
| Data structures | 100%   |
| Formatters      | 95%+   |
| Providers       | 70%+   |

### Test categories

1. **Unit** — single components in isolation.
2. **Integration** — full workflows end-to-end.
3. **Mocked** — external dependencies replaced with mocks.
4. **Real** — actual provider implementations exercised.

Test failures must be resolved before a change is considered done. "Pre-existing failures" is not a
valid pass — see [CLAUDE.md](CLAUDE.md) for the rule.

### Test structure: table-driven or fixture-driven

**No one-off test functions for repeated scenarios.** When several tests differ only in inputs and
expected outputs, use one of these patterns:

- **Table-driven** (`@pytest.mark.parametrize`) — when the test body is identical across cases. Each
  row in the parametrize table is a `(input..., expected)` tuple. Pair with `ids=[...]` so failures
  name the scenario, not just `[0]`.
- **Fixture-driven** (`@pytest.fixture`) — when several tests share non-trivial setup (a temp
  project layout, a mock provider, a fake home directory). Define the fixture once; inject it.

Reach for a one-off function only when the scenario is genuinely unique (an invariant check, a
regression guard, a workflow with no sibling). If you find yourself writing a third test that copies
the body of the first two, refactor to a parametrize table before adding it.

Reference: `tests/test_claude_data.py::TestAnalyzePermissions::test_analyze_permissions` is the
canonical table-driven example.

## Commits and Pull Requests

### Commit messages

Conventional Commits format:

```text
<type>: <short summary>

<optional body explaining the why>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Examples:

```text
feat: add Aider provider auto-discovery
fix: prevent box overflow in startup launch screen
docs: split CLAUDE.md behavior rules from dev workflow
```

### Staging discipline

**Do not have Claude stage files for you.** Review the working tree yourself, stage what belongs in
the commit, then ask Claude to commit what you staged. This prevents unrelated in-flight work from
being swept into a commit. See [CLAUDE.md](CLAUDE.md) for the rule.

### Pull requests

- Branch name: `<type>/<short-description>` (e.g. `fix/launch-box-overflow`).
- PR title: matches the intended squash-merge commit subject.
- PR body: what changed, why, and how it was verified.
- CI must pass before merge.

## Adding a Provider

See [docs/adding-providers.md](docs/adding-providers.md) for the full guide. The short version: drop
a single file into `src/ai_launcher/providers/` — `ProviderRegistry` auto-discovers it.

## Releasing

See [docs/releasing.md](docs/releasing.md). Releases are automated via `scripts/release.py`.
