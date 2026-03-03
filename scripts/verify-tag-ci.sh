#!/usr/bin/env bash
# verify-tag-ci.sh — Block tag push if CI hasn't passed on the tagged commit
# Used as a pre-push hook via .pre-commit-config.yaml
#
# How it works:
#   1. Detects if this is a tag push (detached HEAD)
#   2. Uses `gh` CLI to check if CI passed on the commit
#   3. Exits 1 to block the push if CI hasn't passed
#   4. Gracefully skips if `gh` is not installed

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Only run on tag pushes (detached HEAD with a tag pointing to HEAD)
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
if [ "$CURRENT_BRANCH" != "DETACHED" ]; then
    exit 0
fi

# Get the tag name pointing at HEAD
TAG=$(git tag --points-at HEAD 2>/dev/null | head -1)
if [ -z "$TAG" ]; then
    exit 0
fi

echo -e "${YELLOW}Tag push detected:${NC} $TAG"

# Check if gh CLI is available
if ! command -v gh &>/dev/null; then
    echo -e "${YELLOW}⚠ gh CLI not installed — skipping CI verification${NC}"
    echo "  Install: https://cli.github.com/"
    exit 0
fi

# Check if gh is authenticated
if ! gh auth status &>/dev/null; then
    echo -e "${YELLOW}⚠ gh CLI not authenticated — skipping CI verification${NC}"
    echo "  Run: gh auth login"
    exit 0
fi

COMMIT=$(git rev-parse HEAD)
echo "Checking CI status for commit ${COMMIT:0:8}..."

# Use check-runs API (matches tag-protection.yml) — only look at CI test jobs
STATUS=$(gh api "repos/{owner}/{repo}/commits/$COMMIT/check-runs" \
    --paginate \
    --jq '[.check_runs[] | select(.name | startswith("test ("))] |
          if length == 0 then "pending"
          elif all(.status == "completed") then
            if all(.conclusion == "success") then "success"
            else "failure"
            end
          else "pending"
          end' 2>/dev/null || echo "unknown")

case "$STATUS" in
    success)
        echo -e "${GREEN}✓ CI passed — tag push allowed${NC}"
        exit 0
        ;;
    pending)
        echo -e "${RED}✗ CI is still running on ${COMMIT:0:8}${NC}"
        echo "  Wait for CI to complete before pushing tags."
        exit 1
        ;;
    failure)
        echo -e "${RED}✗ CI failed on ${COMMIT:0:8}${NC}"
        echo "  Fix CI failures before pushing tags."
        exit 1
        ;;
    *)
        echo -e "${YELLOW}⚠ Could not determine CI status (got: $STATUS)${NC}"
        echo "  Allowing push — verify CI manually."
        exit 0
        ;;
esac
