#!/usr/bin/env bash
# ci-local.sh — Run local CI checks before pushing
# Used as a pre-push hook via .pre-commit-config.yaml
#
# Usage:
#   bash scripts/ci-local.sh          # Full check (ruff + pytest)
#   bash scripts/ci-local.sh --quick  # Quick check (ruff only)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No color

QUICK=false
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=true ;;
    esac
done

# Auto-detect venv
VENV=""
if [ -d "./venv" ]; then
    VENV="./venv/bin/"
elif [ -d "./.venv" ]; then
    VENV="./.venv/bin/"
fi

echo -e "${CYAN}━━━ Local CI Check ━━━${NC}"
echo ""

# Step 1: Ruff version must match the pin CI installs.
#
# CI runs `pip install -e ".[dev]"` and then the same two ruff commands below.
# If the local ruff differs from that pin, this script reports green on source
# that CI will reject -- ruff changes both its lint rules and its formatting
# between releases. A drifting version makes every check below meaningless, so
# it is checked first and treated as a hard failure.
PINNED_RUFF=$(grep -oE '"ruff==[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
LOCAL_RUFF=$(${VENV}ruff --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

echo -e "${YELLOW}[1/4]${NC} Checking ruff version matches CI..."
if [ -z "$PINNED_RUFF" ]; then
    echo -e "  ${RED}✗ no exact ruff pin found in pyproject.toml${NC}"
    echo -e "${RED}Push blocked.${NC} Pin ruff to an exact version (ruff==X.Y.Z)."
    exit 1
elif [ "$LOCAL_RUFF" != "$PINNED_RUFF" ]; then
    echo -e "  ${RED}✗ ruff version drift: local ${LOCAL_RUFF:-none}, CI installs ${PINNED_RUFF}${NC}"
    echo -e "${RED}Push blocked.${NC} Local lint results would not match CI. Run:"
    echo -e "    ${VENV}pip install 'ruff==${PINNED_RUFF}'"
    exit 1
else
    echo -e "  ${GREEN}✓ ruff ${LOCAL_RUFF} matches CI pin${NC}"
fi

# The pre-commit hook pins its own rev. pre-commit.ci autoupdates it on a
# schedule, so it can silently drift away from the pyproject pin -- which would
# reintroduce exactly the hook-passes/CI-fails split this guard exists to stop.
HOOK_RUFF=$(grep -A1 'ruff-pre-commit' .pre-commit-config.yaml | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d 'v')
if [ -n "$HOOK_RUFF" ] && [ "$HOOK_RUFF" != "$PINNED_RUFF" ]; then
    echo -e "  ${RED}✗ pre-commit ruff rev v${HOOK_RUFF} != pyproject pin ${PINNED_RUFF}${NC}"
    echo -e "${RED}Push blocked.${NC} Set both to the same version."
    exit 1
fi
echo ""

# Step 2: Ruff lint
echo -e "${YELLOW}[2/4]${NC} Running ruff check..."
if ${VENV}ruff check . ; then
    echo -e "  ${GREEN}✓ ruff check passed${NC}"
else
    echo -e "  ${RED}✗ ruff check failed${NC}"
    echo -e "${RED}Push blocked.${NC} Fix lint errors before pushing."
    exit 1
fi
echo ""

# Step 3: Ruff format check -- CI runs this too; omitting it here let a
# formatter-only disagreement reach CI undetected.
echo -e "${YELLOW}[3/4]${NC} Running ruff format --check..."
if ${VENV}ruff format --check . ; then
    echo -e "  ${GREEN}✓ ruff format check passed${NC}"
else
    echo -e "  ${RED}✗ ruff format check failed${NC}"
    echo -e "${RED}Push blocked.${NC} Run '${VENV}ruff format .' before pushing."
    exit 1
fi
echo ""

# Step 4: Tests (skip with --quick)
if [ "$QUICK" = true ]; then
    echo -e "${YELLOW}[4/4]${NC} Skipping tests (--quick mode)"
    echo -e "  ${YELLOW}⚠ Tests skipped${NC}"
else
    echo -e "${YELLOW}[4/4]${NC} Running pytest..."
    if ${VENV}pytest --tb=short -q ; then
        echo -e "  ${GREEN}✓ tests passed${NC}"
    else
        echo -e "  ${RED}✗ tests failed${NC}"
        echo -e "${RED}Push blocked.${NC} Fix test failures before pushing."
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}━━━ All checks passed ━━━${NC}"
