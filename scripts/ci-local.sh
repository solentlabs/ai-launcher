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

# Step 1: the lint toolchain must be pinned to one version everywhere.
# Shared with the CI lint job via scripts/check-tool-pins.sh so both sides apply
# the identical rule. See that script for why this is a hard failure.
echo -e "${YELLOW}[1/5]${NC} Checking tool pins match CI..."
if ! bash scripts/check-tool-pins.sh "${VENV}"; then
    echo -e "${RED}Push blocked.${NC} Align the ruff versions before pushing."
    exit 1
fi
echo ""

# Step 2: Ruff lint
echo -e "${YELLOW}[2/5]${NC} Running ruff check..."
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
echo -e "${YELLOW}[3/5]${NC} Running ruff format --check..."
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
    echo -e "${YELLOW}[4/5]${NC} Skipping tests (--quick mode)"
    echo -e "  ${YELLOW}⚠ Tests skipped${NC}"
    echo ""
    echo -e "${YELLOW}[5/5]${NC} Skipping patch coverage (needs a test run)"
    echo -e "  ${YELLOW}⚠ Patch coverage skipped${NC}"
    echo ""
    echo -e "${GREEN}━━━ All checks passed ━━━${NC}"
    exit 0
fi

echo -e "${YELLOW}[4/5]${NC} Running pytest..."
if ${VENV}pytest --tb=short -q --cov-report=json ; then
    echo -e "  ${GREEN}✓ tests passed${NC}"
else
    echo -e "  ${RED}✗ tests failed${NC}"
    echo -e "${RED}Push blocked.${NC} Fix test failures before pushing."
    exit 1
fi
echo ""

# Step 5: Patch coverage.
#
# The suite enforces a project-wide floor, which a patch can satisfy while still
# adding untested lines. Codecov judges the diff instead, so its verdict used to
# be visible only after a push -- that cost a round trip on v0.4.2. Warn-only:
# the intent is to surface what Codecov will say, not to invent a second gate
# stricter than the one CI actually enforces.
echo -e "${YELLOW}[5/5]${NC} Checking patch coverage..."
BASE_REF="${PATCH_COVERAGE_BASE:-origin/main}"
if git rev-parse --verify --quiet "$BASE_REF" >/dev/null; then
    ${VENV}python scripts/patch_coverage.py --base "$BASE_REF" --warn-only \
        | sed 's/^/  /'
else
    echo -e "  ${YELLOW}⚠ base ref ${BASE_REF} not found — skipped${NC}"
fi

echo ""
echo -e "${GREEN}━━━ All checks passed ━━━${NC}"
