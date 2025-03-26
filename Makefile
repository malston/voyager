# Makefile for Voyager development

.PHONY: setup venv install dev test lint format clean build publish help

PYTHON_VERSION ?= 3.13
SRC_DIR = voyager
TEST_DIR = tests

# Default target when just running 'make'
help:
	@echo "Available commands:"
	@echo "  make setup     - Set up development environment with mise and uv"
	@echo "  make venv      - Create a virtual environment using uv"
	@echo "  make install   - Install dependencies and package in development mode"
	@echo "  make dev       - Complete development setup (venv + install)"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linting checks (ruff)"
	@echo "  make format    - Format code (ruff format)"
	@echo "  make clean     - Remove build artifacts and cache directories"
	@echo "  make build     - Build package distribution files"
	@echo "  make publish   - Publish package to PyPI (requires credentials)"

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
		echo "  curl -sSf https://astral.sh/uv/install.sh | sh"; \
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
	@echo "Run 'source .venv/bin/activate' to activate the virtual environment"

# Run tests
test:
	@echo "Running tests..."
	@if [ -d ".venv" ]; then \
		.venv/bin/python -m pytest $(TEST_DIR) -v; \
	else \
		mise exec -- python -m pytest $(TEST_DIR) -v; \
	fi

# Run linting
lint:
	@echo "Running linting checks..."
	@if [ -d ".venv" ]; then \
		.venv/bin/ruff check $(SRC_DIR) $(TEST_DIR); \
	else \
		mise exec -- ruff check $(SRC_DIR) $(TEST_DIR); \
	fi

# Format code
format:
	@echo "Formatting code..."
	@if [ -d ".venv" ]; then \
		.venv/bin/ruff format $(SRC_DIR) $(TEST_DIR); \
	else \
		mise exec -- ruff format $(SRC_DIR) $(TEST_DIR); \
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
	@if [ -d ".venv" ]; then \
		.venv/bin/python -m build; \
	else \
		mise exec -- python -m build; \
	fi
	@echo "Build complete. Distribution files in dist/"

# Publish to PyPI
publish: build
	@echo "Publishing to PyPI..."
	@if [ -d ".venv" ]; then \
		.venv/bin/python -m twine upload dist/*; \
	else \
		mise exec -- python -m twine upload dist/*; \
	fi
	@echo "Package published to PyPI"

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
		.venv/bin/python -m pip-audit; \
	else \
		mise exec -- python -m pip-audit; \
	fi