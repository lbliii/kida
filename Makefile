# Kida Makefile
# Wraps uv commands to ensure Python 3.14t is used

PYTHON_VERSION ?= 3.14t
VENV_DIR ?= .venv

.PHONY: all help setup install test test-cov test-thread test-async lint lint-fix format ty clean shell docs docs-serve build publish release

all: help

help:
	@echo "Kida Development CLI"
	@echo "===================="
	@echo "Python Version: $(PYTHON_VERSION)"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup      - Create virtual environment with Python $(PYTHON_VERSION)"
	@echo "  make install    - Install dependencies in development mode"
	@echo "  make test       - Run the test suite"
	@echo "  make test-cov   - Run tests with coverage report"
	@echo "  make test-thread - Run thread safety stress tests"
	@echo "  make test-async - Run async feature tests"
	@echo "  make lint       - Run ruff linter"
	@echo "  make lint-fix   - Run ruff linter with auto-fix"
	@echo "  make format     - Run ruff formatter"
	@echo "  make ty         - Run ty type checker (fast, Rust-based)"
	@echo "  make docs       - Build documentation site (requires bengal)"
	@echo "  make docs-serve - Start dev server for docs (requires bengal)"
	@echo "  make build      - Build distribution packages"
	@echo "  make publish    - Publish to PyPI (uses .env for token)"
	@echo "  make release    - Build and publish in one step"
	@echo "  make clean      - Remove venv, build artifacts, and caches"
	@echo "  make shell      - Start a shell with the environment activated"

setup:
	@echo "Creating virtual environment with Python $(PYTHON_VERSION)..."
	uv venv --python $(PYTHON_VERSION) $(VENV_DIR)

install:
	@echo "Installing dependencies..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Error: $(VENV_DIR) not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@bash -c 'source "$(VENV_DIR)/bin/activate" && uv sync --active --group dev --frozen'

test:
	uv run pytest -q --tb=short

test-cov:
	uv run pytest --cov=src/kida --cov-report=term-missing

test-thread:
	@echo "Running thread safety stress tests..."
	PYTHON_GIL=0 uv run pytest tests/test_kida_stress_test.py -v --tb=short

test-async:
	@echo "Running async feature tests..."
	PYTHON_GIL=0 uv run pytest tests/test_kida_async_features.py -v --tb=short

lint:
	@echo "Running ruff linter..."
	uv run ruff check src/ tests/

lint-fix:
	@echo "Running ruff linter with auto-fix..."
	uv run ruff check src/ tests/ --fix

format:
	@echo "Running ruff formatter..."
	uv run ruff format src/ tests/

ty:
	@echo "Running ty type checker (Astral, Rust-based)..."
	uv run ty check src/kida/

docs:
	@echo "Building documentation site..."
	uv sync --group docs
	cd site && uv run bengal site build

docs-serve:
	@echo "Starting documentation dev server..."
	uv sync --group docs
	cd site && uv run bengal site serve

# =============================================================================
# Build & Release
# =============================================================================

build:
	@echo "Building distribution packages..."
	rm -rf dist/
	uv build
	@echo "✓ Built:"
	@ls -la dist/

publish:
	@echo "Publishing to PyPI..."
	@if [ -f .env ]; then \
		export $$(cat .env | xargs) && uv publish; \
	else \
		echo "Warning: No .env file found, trying without token..."; \
		uv publish; \
	fi

release: build publish
	@echo "✓ Release complete"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf $(VENV_DIR)
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf site/public
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ty_cache" -exec rm -rf {} + 2>/dev/null || true

shell:
	@echo "Activating environment with GIL disabled..."
	@bash -c 'source $(VENV_DIR)/bin/activate && export PYTHON_GIL=0 && echo "✓ venv active, GIL disabled" && exec bash'
