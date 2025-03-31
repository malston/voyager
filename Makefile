# Makefile for Voyager development

.PHONY: setup venv install dev test lint format clean build publish activate security check-env help

PYTHON_VERSION ?= 3.13
SRC_DIR = src/voyager
TEST_DIR = tests

# Detect Python executable (prefer python3 if available)
PYTHON := $(shell which python3 2>/dev/null || which python 2>/dev/null)
# Check if the Python version is 3.x
PYTHON_IS_3 := $(shell $(PYTHON) -c "import sys; print(sys.version_info[0]==3)" 2>/dev/null)

ifeq ($(PYTHON_IS_3),)
$(error Python 3 not found. Please install Python 3 and try again.)
endif

ifeq ($(PYTHON_IS_3),False)
$(error Python 3 required but Python 2 detected. Please use Python 3.)
endif

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
	@if command -v mise >/dev/null 2>&1; then \
		echo "mise is already set up, skipping mise installation"; \
	else \
		echo "mise not found, installing..."; \
		echo "You can install mise with:"; \
		echo "  curl https://mise.run | sh"; \
		echo ""; \
		echo "Setup will continue, but you should install uv separately for best results."; \
	fi
	@echo "Installing mise Python $(PYTHON_VERSION)..."
	@mise install python
	@echo "Checking for uv installation..."
	@if command -v uv >/dev/null 2>&1; then \
		echo "uv is already installed, using existing installation"; \
	else \
		echo "uv not found, installing..."; \
		echo "You can install uv with:"; \
		echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
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
		echo "uv not found. Trying to create venv with python3..."; \
		if command -v python3 >/dev/null 2>&1; then \
			python3 -m venv .venv; \
		else \
			$(PYTHON) -m venv .venv; \
		fi; \
	fi
	@echo "Virtual environment created in .venv directory"

# Install dependencies and the package in development mode
install:
	@echo "Installing development dependencies and package..."
	@if [ -d ".venv" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			uv pip install -e ".[dev]"; \
		else \
			. .venv/bin/activate && $(PYTHON) -m pip install -e ".[dev]"; \
		fi; \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi
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
	@if [ -d ".venv" ]; then \
		. .venv/bin/activate && ruff check $(SRC_DIR) $(TEST_DIR); \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi

# Format code
format:
	@echo "Formatting code..."
	@if [ -d ".venv" ]; then \
		. .venv/bin/activate && ruff format $(SRC_DIR) $(TEST_DIR); \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi

# Run tests
test:
	@echo "Running tests..."
	@if [ -d ".venv" ]; then \
		. .venv/bin/activate && python -m pytest $(TEST_DIR) -v; \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
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
		. .venv/bin/activate && python -m build; \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi
	@echo "Build complete. Distribution files in dist/"

# Publish to PyPI
publish: build
	@echo "Publishing to PyPI..."
	@if [ -d ".venv" ]; then \
		. .venv/bin/activate && python -m twine upload dist/*; \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi
	@echo "Package published to PyPI"

# Check dev environment status
check-env:
	@echo "Checking development environment..."
	@echo "Python version: $$($(PYTHON) --version 2>&1)"
	@if [ -d ".venv" ]; then \
		echo "✓ Virtual environment found"; \
	else \
		echo "✗ Virtual environment not found. Run 'make venv'"; \
		exit 1; \
	fi
	@if command -v mise >/dev/null 2>&1; then \
		echo "✓ mise installed"; \
	else \
		echo "✗ mise not found. Install with: curl https://mise.run | sh"; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		echo "✓ uv installed"; \
	else \
		echo "✗ uv not found. Using standard venv/pip"; \
	fi
	@if [ -f "pyproject.toml" ]; then \
		echo "✓ pyproject.toml found"; \
	else \
		echo "✗ pyproject.toml missing"; \
		exit 1; \
	fi
	@echo "Environment check complete. Development setup looks good!"

# Check all dependencies for security vulnerabilities
security:
	@echo "Checking dependencies for security vulnerabilities..."
	@if [ -d ".venv" ]; then \
		. .venv/bin/activate && python -m pip_audit; \
	else \
		echo "Virtual environment not found. Please run 'make venv' first."; \
		exit 1; \
	fi