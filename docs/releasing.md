# Releasing AI Launcher

This guide covers cutting a new release. Releases are automated via `scripts/release.py`, which
handles version bumps, the release PR, tagging, and triggering the PyPI publish workflow.

## Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│  scripts/release.py X.Y.Z                                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Validation       version format, clean tree, tag available  │
│  2. Quality          ruff format check + pytest                 │
│  3. Changelog        verify entry exists for X.Y.Z              │
│  4. Update           bump pyproject.toml + __init__.py          │
│  5. Git              branch, commit, push, open PR              │
│  6. Merge            wait for PR CI, squash-merge               │
│  7. CI on main       wait for post-merge CI to pass             │
│  8. Tag + Release    push tag, wait for tag-protection,         │
│                      create GitHub release                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
            tag push triggers tag-protection.yml
                                ↓
            on success, triggers publish.yml → PyPI
```

## Before You Start

1. Make sure `main` is green and up to date locally:

   ```bash
   git checkout main
   git pull --ff-only
   ```

2. Ensure the working tree is clean — the script refuses to run with uncommitted changes.
3. Confirm `gh` CLI is installed and authenticated (`gh auth status`). Phases 6–8 require it.

## Step 1: Update the Changelog

The release script verifies that `CHANGELOG.md` already contains an entry for the version being
released. Add it before running the script.

**Important — when this entry must land:** `release.py` runs on `main` with a clean tree (phase 1).
It refuses to proceed if the changelog entry for the target version isn't already on `main`. In
practice this means:

- **Add the `## [X.Y.Z]` entry to the feature PR that contains the work being released.** The entry
  merges to `main` along with the feature.
- Do **not** plan to add it via the release branch that `release.py` creates — by the time that
  branch exists, phase 3 has already failed.
- If you only realize after merging that the entry is missing, open a small docs-only PR adding the
  entry to `main` before running `release.py`.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/):

```markdown
## [0.4.0] - YYYY-MM-DD

### Added

- ...

### Changed

- ...

### Fixed

- ...

### Removed

- ...
```

Only include sections that apply. Lead each bullet with a short verb phrase; expand inline if
context matters.

## Step 2: Choose the Version

The project follows [Semantic Versioning](https://semver.org):

| Change                             | Bump            |
| ---------------------------------- | --------------- |
| Backwards-incompatible change      | major (`X.0.0`) |
| New feature, backwards-compatible  | minor (`0.Y.0`) |
| Bug fix only, backwards-compatible | patch (`0.0.Z`) |

While the project is on `0.x`, breaking changes may land in a minor bump — flag them clearly in the
changelog.

## Step 3: Dry Run

Always do a dry run first to surface validation problems before making any state changes:

```bash
python3 scripts/release.py 0.4.0 --dry-run
```

This runs phases 1–3 fully (validation, quality, changelog) and reports what phases 4–8 _would_ do
without executing them.

## Step 4: Test the Built Wheel

`scripts/release.py` runs `pytest` and `ruff` against the editable install, but does **not** build
or install the wheel that PyPI will ship. Packaging bugs (missing files in `MANIFEST.in`, broken
entry points) only surface when you `pip install` the built artifact.

Build and smoke-test before tagging:

```bash
# In a throwaway venv to avoid polluting your dev install
python3 -m venv /tmp/ai-launcher-release-test
/tmp/ai-launcher-release-test/bin/pip install --upgrade build
/tmp/ai-launcher-release-test/bin/python -m build
/tmp/ai-launcher-release-test/bin/pip install dist/ai_launcher-*.whl
/tmp/ai-launcher-release-test/bin/ai-launcher --help
/tmp/ai-launcher-release-test/bin/ai-launcher claude ~/some/project
```

Verify:

- `--help` shows the current CLI surface.
- A real launch renders the startup box cleanly (no overflow, no missing sections).
- The version reported by `ai-launcher --version` matches what you're about to release.

Once verified, remove the throwaway venv:

```bash
rm -rf /tmp/ai-launcher-release-test
```

## Step 5: Execute the Release

```bash
python3 scripts/release.py 0.4.0
```

The script will:

1. Bump versions in `pyproject.toml` and `src/ai_launcher/__init__.py`.
2. Create branch `release/v0.4.0`, commit, push.
3. Open a PR titled `chore(release): v0.4.0`.
4. Wait for PR checks to pass, then squash-merge.
5. Wait for the post-merge CI run on `main` to pass.
6. Create tag `v0.4.0`, push it.
7. Wait for `tag-protection.yml` to pass.
8. Create the GitHub Release with changelog notes.

Tag push automatically triggers `publish.yml`, which builds the package and uploads to PyPI.

## Flags

| Flag             | Effect                                                        |
| ---------------- | ------------------------------------------------------------- |
| `--dry-run`      | Show what would happen; make no state changes from phase 4 on |
| `--no-push`      | Stop after phase 5 — local commits only, no PR opened         |
| `--skip-tests`   | Skip pytest in phase 2                                        |
| `--skip-quality` | Skip ruff format check in phase 2                             |

Skipping checks is only appropriate when you have already verified them in a separate run and need
to re-enter the flow (e.g. resuming after a network hiccup). Default behavior is to run everything.

## After the Release

1. **Verify PyPI**: `pip index versions ai-launcher` should show the new version once `publish.yml`
   completes (a few minutes after the tag is pushed). The GitHub Actions tab is the authoritative
   source for publish status.
2. **Smoke test the published package** in a clean environment:

   ```bash
   pipx install --force ai-launcher==0.4.0
   ai-launcher --version
   ```

3. **Verify the GitHub Release** page shows the changelog notes.

## Failure Recovery

The script is idempotent within a phase but does not roll back across phases on failure. Common
recovery paths:

- **Phase 2 fails (tests/lint)**: fix the issue, commit, restart from phase 1. The working tree
  won't be clean until you commit.
- **Phase 5 fails (push/PR)**: re-run; the script detects an existing release branch and PR and
  resumes.
- **Phase 6 fails (PR CI red)**: fix on the release branch, push, re-run — it will pick up the
  existing PR.
- **Phase 7 fails (main CI red after merge)**: investigate immediately. Tag has not been pushed yet,
  so PyPI is unaffected. Once main is green again, re-run the script with the same version to resume
  from phase 7.
- **Phase 8 fails (tag-protection)**: the tag is already pushed. Investigate the failing check; do
  not delete the tag without understanding why protection failed.

## When _Not_ to Use the Script

Use the script for normal releases. Hand-edit only when:

- Recovering from a botched release where the tag/PyPI state is inconsistent. Document what happened
  in the changelog or a follow-up commit so the next release flow has context.
- Cutting a Test PyPI release for verification — use the manual `workflow_dispatch` on `publish.yml`
  with `test_pypi: true`.

## Related Files

- `scripts/release.py` — release automation entry point
- `.github/workflows/ci.yml` — runs on PRs and pushes to main
- `.github/workflows/tag-protection.yml` — gates tag pushes
- `.github/workflows/publish.yml` — builds and uploads to PyPI
- `pyproject.toml` — version source (alongside `__init__.py`)
- `src/ai_launcher/__init__.py` — version source (alongside `pyproject.toml`)
