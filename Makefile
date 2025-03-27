# Makefile for Voyager development

.PHONY: setup venv install dev test lint format clean build publish activate security check-env help

PYTHON_VERSION ?= 3.13
SRC_DIR = voyager
TEST_DIR = tests

# Default target when just running 'make'
help:
	@echo "Available commands:"
	@echo "  make setup     - Set up development environment with mise"
	@echo "  make venv      - Create a virtual environment using uv"
	@echo "  make install   - Install dependencies and package in development mode"
	@echo "  make dev       - Complete development setup (venv + install)"
	@echo "  make activate  - Show instructions to activate virtual environment"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linting checks (ruff)"
	@echo "  make format    - Format code (ruff format)"
	@echo "  make clean     - Remove build artifacts and cache directories"
	@echo "  make build     - Build package distribution files"
	@echo "  make publish   - Publish package to PyPI (requires credentials)"
	@echo "  make check-env - Check if development environment is properly set up"

# Set up the development environment with mise and uv
setup:
	@echo "Creating .mise.toml file..."
	@echo '[tools]\npython = "$(PYTHON_VERSION)"\n\n[env]\n_.python.venv = ".venv"' > .mise.toml
	@echo "Installing mise Python $(PYTHON_VERSION)..."
	@mise install python
	@echo "Checking for uv installation..."
	@if command -v uv >/dev/null 2>&1; then \
		echo "uv is already installed, using existing installation"; \
	else \
		echo "uv not found, installing..."; \
		echo "You can install uv with:"; \
		echo "  curl -sSf https://astral.sh/uv/install.sh | sh"; \
		echo ""; \
		echo "Setup will continue, but you should install uv separately for best results."; \
	fi
	@echo "Setup complete. Next step: run 'make dev'"

# Create a virtual environment using uv
venv:
	@echo "Creating virtual environment with uv..."
	@if command -v uv >/dev/null 2>&1; then \
		uv venv; \
	else \
		echo "uv not found. Please install uv first:"; \
		echo "  curl -LsSf https://astral.sh/uv/install.sh | sh; \
		exit 1; \
	fi
	@echo "Virtual environment created in .venv directory"

# Install dependencies and the package in development mode
install:
	@echo "Installing development dependencies and package..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "uv not found. Please install uv first:"; \
		echo "  curl -sSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@uv pip install -e ".[dev]"
	@echo "Installation complete"

# Complete development setup
dev: venv install
	@echo "Development environment setup complete"
	@make activate

# Add a special target for activating the virtual environment
activate:
	@echo "To activate the virtual environment, run:"
	@echo "source .venv/bin/activate"
	@echo ""
	@echo "To deactivate, simply run:"
	@echo "deactivate"

# Run linting
lint:
	@echo "Running linting checks..."
	@if ! command -v ruff >/dev/null 2>&1; then \
		echo "ruff not found, installing dependencies first..."; \
		make install; \
	fi
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" ruff check $(SRC_DIR) $(TEST_DIR); \
	else \
		ruff check $(SRC_DIR) $(TEST_DIR); \
	fi

# Format code
format:
	@echo "Formatting code..."
	@if ! command -v ruff >/dev/null 2>&1; then \
		echo "ruff not found, installing dependencies first..."; \
		make install; \
	fi
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" ruff format $(SRC_DIR) $(TEST_DIR); \
	else \
		ruff format $(SRC_DIR) $(TEST_DIR); \
	fi

# Run tests
test:
	@echo "Running tests..."
	@if ! command -v pytest >/dev/null 2>&1; then \
		echo "pytest not found, installing dependencies first..."; \
		make install; \
	fi
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" python -m pytest $(TEST_DIR) -v; \
	else \
		python -m pytest $(TEST_DIR) -v; \
	fi

# Clean build artifacts and cache directories
clean:
	@echo "Cleaning build artifacts and cache directories..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage .ruff_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@echo "Cleaned"

# Build package distribution files
build: clean
	@echo "Building package distribution files..."
	@if ! command -v build >/dev/null 2>&1; then \
		echo "build package not found, installing dependencies first..."; \
		make install; \
	fi
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" python -m build; \
	else \
		python -m build; \
	fi
	@echo "Build complete. Distribution files in dist/"

# Publish to PyPI
publish: build
	@echo "Publishing to PyPI..."
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" python -m twine upload dist/*; \
	else \
		python -m twine upload dist/*; \
	fi
	@echo "Package published to PyPI"

# Check dev environment status
check-env:
	@echo "Checking development environment..."
	@if [ -d ".venv" ]; then \
		echo "✓ Virtual environment found"; \
	else \
		echo "✗ Virtual environment not found. Run 'make venv'"; \
		exit 1; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		echo "✓ uv installed"; \
	else \
		echo "✗ uv not found. Install with: curl -sSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@if [ -f "pyproject.toml" ]; then \
		echo "✓ pyproject.toml found"; \
	else \
		echo "✗ pyproject.toml missing"; \
		exit 1; \
	fi
	@echo "Environment check complete. Development setup looks good!"

# Initialize a basic test structure
init-tests:
	@echo "Initializing basic test structure..."
	@mkdir -p $(TEST_DIR)
	@touch $(TEST_DIR)/__init__.py
	@echo 'import pytest\nfrom voyager import cli\n\ndef test_cli_version():\n    assert hasattr(cli, "cli")' > $(TEST_DIR)/test_cli.py
	@echo "Test structure initialized. Run 'make test' to execute tests."

# Check all dependencies for security vulnerabilities
security:
	@echo "Checking dependencies for security vulnerabilities..."
	@if [ -d ".venv" ]; then \
		PATH="$(PWD)/.venv/bin:$$PATH" python -m pip_audit; \
	else \
		python -m pip_audit; \
	fi