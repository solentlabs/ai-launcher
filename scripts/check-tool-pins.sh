#!/usr/bin/env bash
# Verify the lint toolchain is pinned to one version everywhere.
#
# ruff changes both its lint rules and its formatting between releases, so three
# copies of "ruff" at three versions means three different answers about the same
# source. That is not hypothetical: pyproject once declared `ruff>=0.5.0`, CI
# resolved 0.16.1, the pre-commit hook pinned 0.11.0 and the venv sat at 0.15.4.
# 0.16.1 dropped an S310 diagnostic that older versions still emit, so the
# required `# noqa` became an unused-directive error -- no source text satisfied
# both, and all 15 CI matrix jobs failed on code that passed locally.
#
# Run by scripts/ci-local.sh (pre-push) and by the lint job in CI, so drift is
# caught on whichever side introduces it.
#
# Usage: check-tool-pins.sh [venv-bin-prefix]
#
# Author: Solent Labs™

set -euo pipefail

VENV_PREFIX="${1:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

fail() {
    echo -e "  ${RED}✗ $1${NC}" >&2
    exit 1
}

PINNED=$(grep -oE '"ruff==[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)

if [ -z "$PINNED" ]; then
    fail "no exact ruff pin in pyproject.toml — use ruff==X.Y.Z, not a >= floor"
fi

# pre-commit hook rev
HOOK=$(grep -A2 'ruff-pre-commit' .pre-commit-config.yaml \
    | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d 'v' || true)

if [ -n "$HOOK" ] && [ "$HOOK" != "$PINNED" ]; then
    fail "pre-commit ruff rev v${HOOK} != pyproject pin ${PINNED} — set both the same"
fi

# installed ruff
if command -v "${VENV_PREFIX}ruff" >/dev/null 2>&1; then
    LOCAL=$("${VENV_PREFIX}ruff" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
    if [ "$LOCAL" != "$PINNED" ]; then
        echo -e "  ${RED}✗ ruff version drift: installed ${LOCAL:-none}, pinned ${PINNED}${NC}" >&2
        echo -e "    Lint results would not match CI. Run:" >&2
        echo -e "      ${VENV_PREFIX}pip install 'ruff==${PINNED}'" >&2
        exit 1
    fi
    echo -e "  ${GREEN}✓ ruff ${LOCAL} matches pin (pyproject, pre-commit, installed)${NC}"
else
    echo -e "  ${GREEN}✓ ruff pin ${PINNED} consistent (pyproject, pre-commit)${NC}"
fi
