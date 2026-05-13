# Claude Rules

> How Claude behaves in this repository. Architecture, setup, and usage live in the docs below; this
> file points rather than restates.

## Where Things Live

| Topic                                      | Authoritative doc                                                  |
| ------------------------------------------ | ------------------------------------------------------------------ |
| Project overview, install, usage           | [README.md](README.md)                                             |
| Architecture (data/provider/UI layers)     | [docs/architecture.md](docs/architecture.md)                       |
| Adding a new provider                      | [docs/adding-providers.md](docs/adding-providers.md)               |
| Configuration reference                    | [docs/configuration.md](docs/configuration.md)                     |
| Context transparency                       | [docs/context-transparency.md](docs/context-transparency.md)       |
| Permission transparency                    | [docs/permission-transparency.md](docs/permission-transparency.md) |
| Development workflow, conventions, testing | [CONTRIBUTING.md](CONTRIBUTING.md)                                 |
| Release process                            | [docs/releasing.md](docs/releasing.md)                             |
| Version history                            | [CHANGELOG.md](CHANGELOG.md)                                       |

## Core Principles

Hard constraints. When in doubt, the principle wins.

### Process

1. **Never `git add`.** Staging is the developer's job — they may have unrelated work in the tree.
2. **Ask before committing.** Even when staged changes look obvious.
3. **No external actions without instruction.** No pushes, PRs, tags, issues, or releases.
4. **No "pre-existing" framing for failing tests.** Full tree is in scope; fix it or surface it.
5. **Read before writing.** Always read a file before overwriting it.
6. **Tests ship with the code, not after.** Every PR that adds or changes behavior must include
   tests for that behavior. Coverage targets in
   [CONTRIBUTING.md](CONTRIBUTING.md#coverage-expectations) are floors, not goals. A patch-coverage
   shortfall on the Codecov comment is a blocker, not a follow-up item.

### Project Invariants

1. **Providers return DATA, not strings.** Strongly-typed dataclasses from `core/provider_data.py` —
   no dicts, no formatted strings.
2. **All ANSI formatting goes through `PreviewFormatter`.** No raw escape codes scattered in
   providers or UI helpers.
3. **No hardcoded provider lists.** `ProviderRegistry` auto-discovers. Adding a provider is adding a
   file.
4. **Bash prototype and Python package stay in feature sync.** Intentional divergence must be noted
   in the changelog.
5. **Preserve symlinks.** Don't resolve to real paths during discovery or display.
6. **Folders before files in every listing.**
7. **Preview pane order is fixed:** `CLAUDE.md` → git status → directory contents.
8. **Branding.** "AI Launcher" (two words, title case); "by Solent Labs™" in UI headers.

### Secrets

1. **No secrets in commits.** Pause and confirm on credential-shaped files (`.env*`,
   `*credentials*`, `*secret*`, `*.pem`, `*.key`).

## Verification

- Run `make validate-ci` before pushing — same gate as `scripts/ci-local.sh` (ruff + pytest).
- For UI/terminal changes, render the actual output and inspect it. Type checks won't catch
  box-drawing overflow.
- `venv` is at `./venv/`; no `python` on PATH — use `python3` or `./venv/bin/...`.

## Shell & Commits

- Conventional Commits: `<type>: <subject>` where type ∈ {feat, fix, docs, refactor, test, chore}.
- No `git push --force`, `git reset --hard`, or `git clean -fd` without explicit instruction _for
  that operation_. Prior authorization doesn't carry forward.
- Release flow is automated — see [docs/releasing.md](docs/releasing.md).
