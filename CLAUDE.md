# Voyager Development Guidelines

## Commands
- **Setup & Install**: `make dev` (creates venv and installs dependencies)
- **Run Tests**: `make test` (all tests)
- **Run Single Test**: `python -m pytest tests/test_file.py::test_function -v`
- **Lint Code**: `make lint` (ruff check)
- **Format Code**: `make format` (ruff format)
- **Clean**: `make clean` (removes build artifacts)
- **Build**: `make build` (creates package distributions)

## Code Style Guidelines
- **Line Length**: 100 characters maximum
- **Quotation Style**: Single quotes preferred (`'`)
- **Import Order**: Standard library → third-party → local
- **Indentation**: 4 spaces, no tabs
- **Type Hints**: Use for function parameters and return values
- **Error Handling**: Use specific exception types, include meaningful error messages
- **Docstrings**: Required for classes and public functions
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Version Detection**: Use flexible version detection patterns for different file formats

## Linting
Voyager uses ruff for linting with these rules enabled: E (pycodestyle), F (Pyflakes), B (flake8-bugbear), I (isort), W (warnings)