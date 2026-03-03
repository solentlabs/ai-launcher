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

# Step 1: Ruff lint
echo -e "${YELLOW}[1/2]${NC} Running ruff check..."
if ${VENV}ruff check . ; then
    echo -e "  ${GREEN}✓ ruff check passed${NC}"
else
    echo -e "  ${RED}✗ ruff check failed${NC}"
    echo -e "${RED}Push blocked.${NC} Fix lint errors before pushing."
    exit 1
fi
echo ""

# Step 2: Tests (skip with --quick)
if [ "$QUICK" = true ]; then
    echo -e "${YELLOW}[2/2]${NC} Skipping tests (--quick mode)"
    echo -e "  ${YELLOW}⚠ Tests skipped${NC}"
else
    echo -e "${YELLOW}[2/2]${NC} Running pytest..."
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
