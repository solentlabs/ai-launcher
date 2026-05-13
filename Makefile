.PHONY: help test test-cov lint lint-fix format format-check type-check validate-ci install-hooks clean

# Pin tool invocations to the project venv so subprocesses without
# venv on PATH (release.py shelling out, fresh clones, CI subshells)
# get the project-pinned versions instead of whatever the system
# happens to have.
VENV_BIN := ./venv/bin

# Default target — show help
help:
	@echo "AI Launcher — Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Run the full test suite"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo "  make clean          - Remove caches and build artifacts"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run ruff linter"
	@echo "  make lint-fix       - Run ruff linter with auto-fix"
	@echo "  make format         - Format code with ruff format"
	@echo "  make format-check   - Check formatting without modifying"
	@echo "  make type-check     - Run mypy (advisory; not yet in CI)"
	@echo ""
	@echo "Pre-flight:"
	@echo "  make validate-ci    - Run everything CI runs (lint + format-check + tests)"
	@echo "  make install-hooks  - Install local git hooks (pre-commit, commit-msg, pre-push)"

# ── Tests ─────────────────────────────────────────────────────────────────

test:
	@$(VENV_BIN)/pytest tests/ -v --tb=short

test-cov:
	@$(VENV_BIN)/pytest tests/ --cov=src/ai_launcher --cov-report=term-missing --cov-report=html

# ── Linting / formatting ──────────────────────────────────────────────────

lint:
	@echo "Running ruff check..."
	@$(VENV_BIN)/ruff check .

lint-fix:
	@echo "Running ruff check with auto-fix..."
	@$(VENV_BIN)/ruff check --fix .

format:
	@echo "Formatting with ruff..."
	@$(VENV_BIN)/ruff format .

format-check:
	@echo "Checking format with ruff..."
	@$(VENV_BIN)/ruff format --check .

type-check:
	@echo "Running mypy..."
	@$(VENV_BIN)/mypy src/

# ── Pre-flight aggregate ──────────────────────────────────────────────────

# Delegates to scripts/ci-local.sh so the Makefile and the pre-push hook
# (.pre-commit-config.yaml → ci-local) share a single source of truth.
validate-ci:
	@bash scripts/ci-local.sh

# ── Hooks ─────────────────────────────────────────────────────────────────

install-hooks:
	@$(VENV_BIN)/pre-commit install --install-hooks
	@$(VENV_BIN)/pre-commit install --hook-type commit-msg
	@$(VENV_BIN)/pre-commit install --hook-type pre-push
	@echo ""
	@echo "✓ Hooks installed: pre-commit, commit-msg, pre-push"
	@echo "  Run 'pre-commit run --all-files' to test on the full tree."

# ── Cleanup ───────────────────────────────────────────────────────────────

clean:
	@echo "Cleaning build artifacts and caches..."
	@rm -rf build/ dist/ *.egg-info src/*.egg-info
	@rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
	@echo "✓ Clean."
